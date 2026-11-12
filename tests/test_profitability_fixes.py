"""Regression tests for the profitability audit fixes.

Covers: honest fees, exits that let winners reach the planned target, the stop
ratchet, entry re-anchoring, sizing that respects the risk budget, a kill switch
that survives restarts, the realized-edge gate, the go-live expectancy check,
and the historical backtest (including a look-ahead check).
"""

import asyncio
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from core.config.settings import settings
from core.domain.models import MarketRegime, TradeAction
from core.schemas.trade import PositionSnapshot
from risk import profit_math
from risk.edge_gate import evaluate_realized_edge
from risk.go_live_gate import score_go_live
from strategy.entry_anchor import reanchor_levels, shift_levels_to_fill


# ----------------------------------------------------------------------- fees

def test_fees_include_gst_on_both_sides():
    assert profit_math.TAKER_FEE_PCT == pytest.approx(0.0005 * 1.18)
    # entry fee + exit fee + entry slippage + exit slippage
    assert profit_math.ROUND_TRIP_COST_PCT == pytest.approx(2 * 0.00059 + 0.001)


# ---------------------------------------------------------------- entry anchor

def test_reanchor_keeps_planned_distances_long_and_short():
    e, sl, tp = reanchor_levels(100.0, 98.5, 103.3, fresh_price=100.5, is_short=False)
    assert (e, round(sl, 6), round(tp, 6)) == (100.5, 99.0, 103.8)
    e, sl, tp = reanchor_levels(100.0, 101.5, 96.7, fresh_price=99.6, is_short=True)
    assert (e, round(sl, 6), round(tp, 6)) == (99.6, 101.1, 96.3)


@pytest.mark.parametrize("fresh", [100.8, 99.2])  # > 0.5 x 1.5 stop distance either way
def test_reanchor_skips_stale_setups(fresh):
    assert reanchor_levels(100.0, 98.5, 103.3, fresh_price=fresh, is_short=False) is None


def test_bracket_shifts_with_actual_fill():
    assert shift_levels_to_fill(100.0, 98.5, 103.3, fill_price=100.4) == pytest.approx((98.9, 103.7))
    assert shift_levels_to_fill(100.0, 98.5, 103.3, fill_price=0.0) == (98.5, 103.3)


# ------------------------------------------------------------ guardian exits

def _worker(entry=100.0, stop=98.5, target=103.3, side="BUY", symbol="XRPUSD"):
    from guardian.position_guardian import PositionGuardianWorker
    pos = PositionSnapshot(
        position_id="P1", symbol=symbol, exchange="DELTA", side=side, quantity=10,
        entry_price=entry, current_price=entry, stop_loss=stop, target_1=target,
        highest_price_seen=entry, lowest_price_seen=entry, unrealized_pnl=0.0,
        opened_at=datetime.now(UTC) - timedelta(hours=1), is_active=True,
    )
    return PositionGuardianWorker(pos, atr_14=3.0)


def _tick(w, px):
    return asyncio.run(w.evaluate_tick(current_ltp=px))


def test_crypto_winner_is_not_harvested_early_by_default(monkeypatch):
    from guardian.models import GuardianAction
    monkeypatch.setattr(settings, "GUARDIAN_DISCRETIONARY_EXITS", False)
    w = _worker()
    _tick(w, 101.0)          # +1%
    action, _ = _tick(w, 100.7)  # pulled back 0.3% from peak: old rule harvested here
    assert action != GuardianAction.TARGET_EXIT
    assert w.state.is_active


def test_ratchet_breakeven_at_1R_then_plus_1R_at_1_8R(monkeypatch):
    from guardian.models import GuardianAction
    monkeypatch.setattr(settings, "GUARDIAN_DISCRETIONARY_EXITS", False)
    w = _worker()
    # Peak ~ +1.7% (> 1R net of costs): stop moves to about breakeven, NOT to +1R.
    action, _ = _tick(w, 101.7)
    assert action == GuardianAction.ADJUST_TRAILING_STOP
    assert 100.0 < w.state.stop_loss < 100.5
    # Peak ~ +2.9% (>= 1.8R net): stop locks +1R (around +1.7%).
    _tick(w, 102.9)
    assert 101.4 < w.state.stop_loss < 102.0
    # Target still reachable.
    action, _ = _tick(w, 103.4)
    assert action == GuardianAction.TARGET_EXIT


def test_hard_stop_still_fires(monkeypatch):
    from guardian.models import GuardianAction
    monkeypatch.setattr(settings, "GUARDIAN_DISCRETIONARY_EXITS", False)
    action, _ = _tick(_worker(), 98.4)
    assert action == GuardianAction.HARD_STOP_EXIT


# ----------------------------------------------------------------- sizing

def _decision(entry, stop, symbol="XRPUSD"):
    from core.schemas.trade import TradeDecision
    return TradeDecision(
        analysis_id="A1", symbol=symbol, exchange="DELTA", decision=TradeAction.BUY,
        confidence=0.8, entry_price=entry, stop_loss=stop, target_1=entry + 2.2 * (entry - stop),
        expected_risk_reward=2.2, thesis=["t"], supporting_evidence=[], opposing_evidence=[],
        risk_factors=[], invalidation_conditions=[],
        strategy_version="1", prompt_version="1",
    )


def _approved():
    from core.schemas.trade import RiskCheckResult
    return RiskCheckResult(approved=True, rejection_reasons=[])


def test_micro_account_risk_is_capped_at_configured_budget():
    from portfolio.position_sizer import PositionSizer
    sizer = PositionSizer(total_equity=10.0, available_margin=10.0)
    # XRP mult 1.0, 1.5% stop on 1.28 = $0.0192/contract; 1% of $10 = $0.10 -> 5 contracts
    qty = sizer.calculate_quantity(_decision(1.28, 1.2608), _approved())
    assert qty == 5
    assert qty * (1.28 - 1.2608) <= 10.0 * settings.MICRO_ACCOUNT_RISK_PER_TRADE_PCT + 1e-9


def test_trade_skipped_when_one_contract_exceeds_risk_budget():
    from portfolio.position_sizer import PositionSizer
    sizer = PositionSizer(total_equity=10.0, available_margin=10.0)
    # DOGE mult 100: 1 contract with a 1.5% stop at 0.0774 risks $0.116 > $0.10 budget
    assert sizer.calculate_quantity(_decision(0.0774, 0.076239, "DOGEUSD"), _approved()) == 0


# ------------------------------------------------------------- kill switch

def test_kill_switch_survives_restart_and_does_not_auto_rebase(tmp_path, monkeypatch):
    from risk.kill_switch import EmergencyKillSwitch
    monkeypatch.setenv("KILL_SWITCH_STATE_PATH", str(tmp_path / "ks.json"))
    monkeypatch.delenv("KILL_SWITCH_AUTO_RECOVERY_HOURS", raising=False)
    ks = EmergencyKillSwitch()
    ok, _ = ks.verify_system_integrity(daily_loss=0.0, current_drawdown_pct=0.20, max_capital=10.0)
    assert ok is False and ks.is_engaged

    restarted = EmergencyKillSwitch()  # new process
    assert restarted.is_engaged
    restarted._engaged_at = datetime.now(UTC) - timedelta(days=3)  # long after the old 6h window
    ok, _ = restarted.verify_system_integrity(daily_loss=0.0, current_drawdown_pct=0.0, max_capital=10.0)
    assert ok is False and restarted.rebase_required is False

    restarted.reset("operator")
    assert not restarted.is_engaged and restarted.rebase_required is True
    assert not (tmp_path / "ks.json").exists()


def test_daily_loss_halt_clears_next_utc_day_without_rebase(tmp_path, monkeypatch):
    from risk.kill_switch import EmergencyKillSwitch
    monkeypatch.setenv("KILL_SWITCH_STATE_PATH", str(tmp_path / "ks.json"))
    ks = EmergencyKillSwitch()
    ks.verify_system_integrity(daily_loss=5.0, current_drawdown_pct=0.0, max_capital=10.0)
    assert ks.is_engaged
    ks._engaged_at = datetime.now(UTC) - timedelta(days=1)
    ok, _ = ks.verify_system_integrity(daily_loss=0.0, current_drawdown_pct=0.0, max_capital=10.0)
    assert ok is True and ks.rebase_required is False


# --------------------------------------------------------------- edge gates

def test_realized_edge_gate_blocks_live_only_when_evidence_is_negative():
    losing = {"total": 30, "expectancy": -0.01, "win_rate": 0.48}
    assert evaluate_realized_edge(losing, 20, is_live=True).allow_live_entries is False
    assert evaluate_realized_edge(losing, 20, is_live=False).allow_live_entries is True
    assert evaluate_realized_edge({"total": 5, "expectancy": -1}, 20, True).allow_live_entries is True
    assert evaluate_realized_edge({"total": 30, "expectancy": 0.02}, 20, True).allow_live_entries is True


def test_expectancy_gate_uses_real_win_rate_once_available():
    from core.schemas.trade import AnalystReport, CandidateSignal, DebateTranscript
    from risk.expectancy_gate import ExpectancyGate
    dec = _decision(1.28, 1.2608)
    sig = CandidateSignal(symbol="XRPUSD", exchange="DELTA", ltp=1.28, volume=1, avg_volume_20d=1,
                          relative_volume=1.0, momentum_score=90, atr_14=0.05,
                          regime=MarketRegime.BULLISH_TREND)
    deb = DebateTranscript.model_construct(consensus_score=0.6)
    tech = AnalystReport.model_construct(agent_name="Technical Analyst", stance="BULLISH", confidence=0.7,
                                         key_observations=[], risk_warnings=[])
    # Opinions alone pass...
    ok, _, m = ExpectancyGate.evaluate(dec, sig, deb, [tech], is_crypto=True)
    assert ok
    # ...but 40 real trades winning only 20% at 2.2R is negative EV and must be rejected.
    ok, _, m = ExpectancyGate.evaluate(dec, sig, deb, [tech], is_crypto=True,
                                       realized_win_rate=0.20, realized_trades=40)
    assert not ok and m["p_win"] < 0.35
    # 40% real win rate at 2.2R is profitable after fees even though it is < 0.52.
    ok, _, _ = ExpectancyGate.evaluate(dec, sig, deb, [tech], is_crypto=True,
                                       realized_win_rate=0.40, realized_trades=200)
    assert ok


def test_go_live_requires_positive_expectancy():
    start = datetime(2026, 11, 1, tzinfo=UTC)
    # 60% wins but losses twice the wins: PF 0.75, expectancy negative -> NO_GO
    trades = [{"net_pnl": 1.0, "timestamp": (start + timedelta(hours=i)).isoformat()} for i in range(12)]
    trades += [{"net_pnl": -2.0, "timestamp": (start + timedelta(hours=20 + i)).isoformat()} for i in range(8)]
    res = score_go_live(now=start + timedelta(hours=73), started_at=start, trades=trades, drawdown_pct=1.0)
    assert res["checks"]["expectancy"] is False and res["decision"] == "NO_GO"


# ----------------------------------------------------------------- backtest

def _synthetic_hourly(n_days=150, drift=0.0, seed=1):
    rng = np.random.default_rng(seed)
    n = n_days * 24
    rets = rng.normal(drift, 0.006, n)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[100.0], close[:-1]])
    spread = np.abs(rng.normal(0, 0.003, n)) * close
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "open": open_, "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread, "close": close,
        "volume": rng.uniform(1e5, 2e5, n),
    }, index=idx)


def test_backtest_signals_have_no_lookahead():
    from tools.backtest_delta import compute_signals
    h1 = _synthetic_hourly()
    full = compute_signals(h1)
    cut = 24 * 100
    truncated = compute_signals(h1.iloc[:cut])
    pd.testing.assert_series_equal(full["score"].iloc[:cut], truncated["score"], check_names=False)


def test_backtest_on_random_walk_shows_no_edge_after_costs():
    from tools.backtest_delta import Params, compute_signals, simulate, summarize
    trades = []
    for seed in range(6):
        h1 = _synthetic_hourly(seed=seed)
        trades += simulate(f"S{seed}", h1, compute_signals(h1), Params(min_score=80))
    s = summarize(trades)
    assert s["trades"] > 50
    # No predictability in a random walk: costs must make the average trade lose.
    assert s["avg_net_pct_per_trade"] < 0
    assert set(s["exit_reasons"]) <= {"STOP", "TRAIL_STOP", "TARGET", "END_OF_DATA"}
    # Losses are bounded near -1R (plus costs / gaps), wins near the 2.2R target.
    r = np.array([t.r_multiple for t in trades])
    assert r.min() > -2.0 and r.max() < 2.6


def test_backtest_params_side_cooldown_and_window():
    from tools.backtest_delta import Params, compute_signals, simulate
    h1 = _synthetic_hourly(seed=3)
    sig = compute_signals(h1)
    longs = simulate("S", h1, sig, Params(min_score=80, side="long"))
    assert longs and all(t.direction == "LONG" for t in longs)
    cooled = simulate("S", h1, sig, Params(min_score=80, cooldown_h=24))
    for a, b in zip(cooled, cooled[1:]):
        gap_h = (pd.Timestamp(b.entry_time) - pd.Timestamp(a.exit_time)).total_seconds() / 3600
        assert gap_h >= 24
    start = h1.index[24 * 100]
    windowed = simulate("S", h1, sig, Params(min_score=80), start=start)
    assert all(pd.Timestamp(t.entry_time) > start for t in windowed)
    # Wider stop -> costs are a smaller share of risk
    wide = simulate("S", h1, sig, Params(min_score=80, stop_atr=2.0, stop_max_pct=0.08))
    assert np.mean([t.stop_dist / t.entry for t in wide]) > np.mean([t.stop_dist / t.entry for t in longs])


# ------------------------------------------------------- daily trend backtest

def _synthetic_daily(n=900, drift=0.0, vol=0.03, seed=7):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[100.0], close[:-1]])
    wick = np.abs(rng.normal(0, vol / 2, n)) * close
    idx = pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC")
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + wick,
                         "low": np.minimum(open_, close) - wick, "close": close,
                         "volume": 1.0}, index=idx)


@pytest.mark.parametrize("family,a,b", [("donchian", 55, 20), ("ema", 20, 100)])
def test_trend_signals_have_no_lookahead(family, a, b):
    from tools.backtest_trend_daily import TrendParams, compute_trend_signals
    d = _synthetic_daily()
    p = TrendParams(family, a, b, 3.0, "both")
    full = compute_trend_signals(d, p)
    part = compute_trend_signals(d.iloc[:500], p)
    pd.testing.assert_frame_equal(full.iloc[:500], part)


def test_trend_rule_captures_a_real_trend_and_not_noise():
    from tools.backtest_trend_daily import PRE_REGISTERED, simulate_trend
    from tools.backtest_delta import summarize
    trending = simulate_trend("T", _synthetic_daily(drift=0.004, vol=0.025), PRE_REGISTERED)
    assert summarize(trending)["expectancy_R"] > 0.5
    noise = []
    for seed in range(8):
        noise += simulate_trend(f"N{seed}", _synthetic_daily(seed=seed), PRE_REGISTERED)
    s = summarize(noise)
    assert s["trades"] > 40
    lo, hi = s["expectancy_R_95ci"]
    assert lo < 0.15  # no reliable edge can be found in pure noise


def test_trend_costs_include_daily_funding():
    from tools.backtest_trend_daily import _net
    no_funding = _net(100.0, 110.0, False, 10, 0.0)
    with_funding = _net(100.0, 110.0, False, 10, 0.0003)
    assert no_funding - with_funding == pytest.approx(0.003)


def test_compounding_risks_one_percent_of_current_equity():
    from tools.backtest_delta import Trade
    from tools.backtest_trend_daily import compound
    t = lambda d0, d1, r: Trade("X", "LONG", d0, d1, 1, 1, 0.1, "T", 0.0, r)
    res = compound([t("2026-01-01", "2026-01-05", 2.0), t("2026-01-06", "2026-01-09", -1.0)], 10.0, 0.01)
    # +2% of 10 -> 10.2, then -1% of 10.2 -> 10.098
    assert res["end_equity"] == pytest.approx(10.10, abs=0.01)
    assert res["max_drawdown_pct"] == pytest.approx(1.0, abs=0.05)


def test_trend_simulator_is_unbiased_on_driftless_prices():
    # Additive random walk: no drift, no edge. Without funding, the average trade must
    # lose roughly the trading costs — not more (a bug against us) and not less (look-ahead).
    from tools.backtest_delta import summarize
    from tools.backtest_trend_daily import TrendParams, simulate_trend
    trades = []
    for seed in range(40):
        rng = np.random.default_rng(seed)
        c = np.maximum(1000 + np.cumsum(rng.normal(0, 3, 3000)), 50)
        o = np.r_[1000, c[:-1]]
        idx = pd.date_range("2015-01-01", periods=3000, freq="1D", tz="UTC")
        d = pd.DataFrame(dict(open=o, high=np.maximum(o, c), low=np.minimum(o, c), close=c, volume=1.0), index=idx)
        trades += simulate_trend("x", d, TrendParams(funding_pct_per_day=0.0))
    lo, hi = summarize(trades)["expectancy_R_95ci"]
    assert lo < -0.02 and hi > -0.2 and hi < 0.1


def test_binance_daily_parser_pages_and_drops_unfinished_day(monkeypatch):
    import tools.backtest_trend_daily as t
    assert t.binance_symbol("XRPUSD") == "XRPUSDT" and t.binance_symbol("BTCUSDT") == "BTCUSDT"
    day = 86_400_000
    today = int(pd.Timestamp.now(tz="UTC").normalize().timestamp() * 1000)
    start = today - 1500 * day
    calls = []

    def fake_get(url, params=None, timeout=15.0):
        calls.append(params["startTime"])
        rows = [[start + i * day, "1", "2", "0.5", "1.5", "10"] for i in range(1501)]  # incl. today
        return [r for r in rows if r[0] >= params["startTime"]][:1000]

    monkeypatch.setattr(t, "_get_json", fake_get)
    df = t.fetch_binance_daily("XRPUSD", 1500)
    assert len(calls) >= 2                      # paged past the 1000-row limit
    # Window starts 1500 days before *now* (mid-day), so day 0 is just outside it;
    # today's unfinished candle is dropped -> 1499 completed days.
    assert len(df) == 1499
    assert df.index[-1] < pd.Timestamp.now(tz="UTC").normalize()
    assert df.index.is_monotonic_increasing and df["close"].iloc[0] == 1.5


def test_by_year_breakdown_splits_on_exit_year():
    from tools.backtest_delta import Trade
    from tools.backtest_trend_daily import by_year
    t = lambda d0, d1, r: Trade("X", "LONG", d0, d1, 1, 1, 0.1, "T", 0.0, r)
    rows = by_year([t("2021-12-20", "2022-01-03", 2.0), t("2022-03-01", "2022-03-09", -1.0),
                    t("2023-02-01", "2023-02-10", 1.0)], None, 0.01)
    assert [r["year"] for r in rows] == [2022, 2023]
    assert rows[0]["trades"] == 2 and rows[0]["expectancy_R"] == pytest.approx(0.5)


def test_monte_carlo_drawdown_distribution():
    from tools.backtest_delta import Trade
    from tools.backtest_trend_daily import monte_carlo
    mk = lambda r: Trade("X", "LONG", "2026-01-01", "2026-01-02", 1, 1, 0.1, "T", 0.0, r)
    mc = monte_carlo([mk(2.0)] * 40 + [mk(-1.0)] * 60, risk_pct=0.01, runs=500)
    d = mc["max_drawdown_pct"]
    assert 0 < d["median"] <= d["p90"] <= d["p95"] <= d["p99"]
    assert mc["equity_multiple"]["p5"] <= mc["equity_multiple"]["median"] <= mc["equity_multiple"]["p95"]
    assert monte_carlo([mk(1.0)] * 5) == {}  # too few trades to say anything

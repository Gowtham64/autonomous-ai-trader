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

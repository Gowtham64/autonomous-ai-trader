"""Daily trend engine: live behaviour must match the backtest, and fail safe."""

import asyncio

import numpy as np
import pandas as pd
import pytest

from apps.daemon.daily_trend_engine import STRATEGY_TAG, DailyTrendEngine
from execution.paper.delta_paper import DeltaPaperBroker
from risk.kill_switch import kill_switch
from strategy.daily_trend import PRE_REGISTERED, completed_bars, size_position


@pytest.fixture(autouse=True)
def isolated_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(kill_switch, "_state_path", tmp_path / "ks.json")
    kill_switch._is_engaged = False
    kill_switch._engaged_kind = None
    kill_switch.reason = None
    kill_switch.rebase_required = False
    yield
    kill_switch._is_engaged = False
    kill_switch.reason = None


def _trending_market(n=420, seed=11):
    """Alternating up / down / sideways regimes so breakouts, trails and exits all happen."""
    rng = np.random.default_rng(seed)
    drift = np.concatenate([np.full(70, 0.0), np.full(70, 0.006), np.full(70, -0.006),
                            np.full(70, 0.0), np.full(70, 0.007), np.full(n - 350, -0.004)])
    r = rng.normal(drift, 0.02)
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[100.0, c[:-1]] * (1 + rng.normal(0, 0.003, n))
    hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.008, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.008, n)))
    idx = pd.date_range("2025-01-01", periods=n, freq="1D", tz="UTC")
    return pd.DataFrame(dict(open=o, high=hi, low=lo, close=c, volume=1.0), index=idx)


class Clock:
    def __init__(self, t):
        self.t = pd.Timestamp(t)

    def __call__(self):
        return self.t


def _make_engine(tmp_path, df, clock, journal, capital=1_000_000.0, live=False, stats=None, sym="XYZUSD"):
    broker = DeltaPaperBroker(initial_capital=capital, state_file=None, slippage_pct=0.0005)
    broker._resolve_multiplier = lambda s: 0.01

    async def candles(_s):
        return df

    async def mark(_s):
        return clock.mark

    async def jrnl(**kw):
        journal.append(kw)

    return DailyTrendEngine(
        broker=broker, candles_fn=candles, mark_fn=mark, multiplier_fn=lambda s: 0.01,
        journal_fn=jrnl, stats_fn=stats, is_live=live, params=PRE_REGISTERED,
        symbols=[sym], state_path=tmp_path / "state.json", now_fn=clock,
    )


def _drive(engine, df, clock, days):
    """Each day: 00:30 at the open, 12:00 at the low, 23:00 at the close."""
    for day in days:
        row = df.loc[day]
        for hour, px in ((0.5, row.open), (12, row.low), (23, row.close)):
            clock.t = day + pd.Timedelta(hours=hour)
            clock.mark = float(px)
            asyncio.run(engine.run_cycle())


def test_engine_trades_the_same_days_as_the_backtest(tmp_path):
    """The live engine, driven through a year of days, must open and close trades on
    exactly the days the backtest does, for the same reasons, at the same entry prices."""
    from tools.backtest_trend_daily import simulate_trend
    df = _trending_market()
    journal: list = []
    clock = Clock(df.index[0])
    eng = _make_engine(tmp_path, df, clock, journal)
    _drive(eng, df, clock, df.index[60:])

    bt = [t for t in simulate_trend("XYZUSD", df, PRE_REGISTERED) if t.exit_reason != "END_OF_DATA"]
    assert len(bt) >= 3, "scenario should produce several trades"
    live = eng.closed
    assert [(pd.Timestamp(t.entry_time).date(), pd.Timestamp(t.exit_time).date()) for t in bt] == \
           [(pd.Timestamp(c["opened_at"]).date(), pd.Timestamp(c["closed_at"]).date()) for c in live]
    assert [("TREND_EXIT" if t.exit_reason == "TREND_EXIT" else "STOP") for t in bt] == [c["reason"] for c in live]
    for t, c in zip(bt, live):
        assert c["entry"] == pytest.approx(t.entry, rel=1e-6)
    assert all(j["market_regime"] == STRATEGY_TAG for j in journal) and len(journal) == len(live)


def test_entry_sizing_stop_and_persistence_across_restart(tmp_path):
    df = _trending_market()
    journal: list = []
    clock = Clock(df.index[0])
    eng = _make_engine(tmp_path, df, clock, journal)
    # run until the first entry
    for day in df.index[60:]:
        _drive(eng, df, clock, [day])
        if eng.state.positions:
            break
    pos = eng.state.positions["XYZUSD"]
    assert pos.quantity > 0 and pos.stop < pos.entry_price
    risk = (pos.entry_price - pos.stop) * pos.quantity * pos.multiplier
    assert risk <= 1_000_000.0 * 0.01 * 1.0001

    # "Crash" and restart: a fresh engine on the same state file knows the position.
    eng2 = _make_engine(tmp_path, df, clock, journal)
    eng2.broker = eng.broker
    assert "XYZUSD" in eng2.state.positions
    assert eng2.state.positions["XYZUSD"].stop == pos.stop


def test_stop_only_moves_up_for_longs(tmp_path):
    df = _trending_market()
    clock = Clock(df.index[0])
    eng = _make_engine(tmp_path, df, clock, [])
    stops = []
    for day in df.index[60:300]:
        _drive(eng, df, clock, [day])
        if "XYZUSD" in eng.state.positions:
            stops.append(eng.state.positions["XYZUSD"].stop)
        elif stops:
            break
    assert len(stops) > 3
    assert all(b >= a for a, b in zip(stops, stops[1:]))


def test_stale_signal_is_not_chased(tmp_path):
    from tools.backtest_trend_daily import simulate_trend
    df = _trending_market()
    first = simulate_trend("XYZUSD", df, PRE_REGISTERED)[0]
    entry_day = pd.Timestamp(first.entry_time)
    clock = Clock(entry_day + pd.Timedelta(hours=10))  # 10h after the signal close
    clock.mark = float(df.loc[entry_day].close)
    eng = _make_engine(tmp_path, df, clock, [])
    eng.state.last_daily_bar = str((entry_day - pd.Timedelta(days=2)).date())
    s = asyncio.run(eng.run_cycle())
    assert not eng.state.positions
    assert any("after the close" in x for x in s["skipped"])


def test_kill_switch_blocks_entries_but_exits_still_run(tmp_path):
    df = _trending_market()
    journal: list = []
    clock = Clock(df.index[0])
    eng = _make_engine(tmp_path, df, clock, journal)
    for day in df.index[60:]:
        _drive(eng, df, clock, [day])
        if eng.state.positions:
            break
    kill_switch.trigger("TEST", "halt", kind="MANUAL_RESET")
    pos = eng.state.positions["XYZUSD"]
    clock.t += pd.Timedelta(hours=1)
    clock.mark = pos.stop * 0.99  # through the stop
    asyncio.run(eng.run_cycle())
    assert "XYZUSD" not in eng.state.positions and journal  # exit still happened
    # and no new entry while halted, even on a later breakout
    for day in df.index[df.index.get_loc(clock.t.normalize()) + 1:]:
        _drive(eng, df, clock, [day])
    assert not eng.state.positions


def test_realized_edge_gate_blocks_live_entries(tmp_path):
    df = _trending_market()
    clock = Clock(df.index[0])

    async def losing_stats():
        return {"total": 30, "expectancy": -0.5, "win_rate": 0.2}

    eng = _make_engine(tmp_path, df, clock, [], live=True, stats=losing_stats)
    _drive(eng, df, clock, df.index[60:200])
    assert not eng.state.positions


def test_exchange_closed_position_is_reconciled_and_journaled(tmp_path):
    df = _trending_market()
    journal: list = []
    clock = Clock(df.index[0])
    eng = _make_engine(tmp_path, df, clock, journal)
    for day in df.index[60:]:
        _drive(eng, df, clock, [day])
        if eng.state.positions:
            break
    stop = eng.state.positions["XYZUSD"].stop
    eng.broker.positions.clear()  # e.g. the exchange-side stop fired while we were offline
    asyncio.run(eng.run_cycle())
    assert not eng.state.positions
    assert journal[-1]["exit_price"] == stop and "EXCHANGE_STOP" in journal[-1]["exit_reason"]


def test_size_position_refuses_rather_than_oversizes():
    # $10 account, 1% risk = $0.10; DOGE-like contract (100 x $0.077) with a 12% stop risks ~$0.92
    d = size_position(10.0, 10.0, 0.077, 0.077 * 0.88, 100.0, 0.01, 5.0)
    assert d.contracts == 0 and "account too small" in d.reason
    # $500 account: $5 budget -> 5 contracts
    d = size_position(500.0, 500.0, 0.077, 0.077 * 0.88, 100.0, 0.01, 5.0)
    assert d.contracts == 5 and d.risk_usd <= 5.0


def test_completed_bars_never_includes_a_forming_candle():
    idx = pd.date_range("2026-01-01", periods=5, freq="1D", tz="UTC") + pd.Timedelta(hours=5, minutes=30)
    df = pd.DataFrame({"close": range(5)}, index=idx)
    # At 12:00 on Jan 5 the Jan 4 05:30 candle has closed (Jan 5 05:30); Jan 5's is forming.
    assert completed_bars(df, pd.Timestamp("2026-01-05 12:00", tz="UTC")).index[-1] == idx[3]
    # One minute before Jan 4's candle closes, the newest complete one is Jan 3.
    assert completed_bars(df, pd.Timestamp("2026-01-05 05:29", tz="UTC")).index[-1] == idx[2]


def test_status_file_and_dashboard_render(tmp_path, monkeypatch):
    import json
    import run_trend_dashboard as dash
    df = _trending_market()
    clock = Clock(df.index[0])
    eng = _make_engine(tmp_path, df, clock, [], capital=500.0)
    _drive(eng, df, clock, df.index[60:200])
    st = json.loads((tmp_path / "daily_trend_status.json").read_text())
    assert st["mode"] == "PAPER" and st["starting_capital"] == 500.0
    assert (tmp_path / "daily_trend_equity.csv").read_text().startswith("time,equity")
    for p in st["positions"]:
        assert p["mark"] > 0 and p["qty"] > 0
        # "If stopped out" is what the current stop locks in, relative to entry
        assert p["locked_in_usd"] == pytest.approx((p["stop"] - p["entry"]) * p["qty"] * 0.01, abs=1e-3)

    monkeypatch.setattr(dash, "DATA", tmp_path)
    monkeypatch.setattr(dash, "ROOT", tmp_path)
    html = dash.render()
    assert "Daily Trend Bot" in html and "PAPER" in html
    assert "may be stopped" in html  # replay clock is in 2025, so the status looks stale
    st["kill_switch"] = "test halt"
    (tmp_path / "daily_trend_status.json").write_text(json.dumps(st))
    assert "Kill switch engaged" in dash.render()


def test_dashboard_without_any_data(tmp_path, monkeypatch):
    import run_trend_dashboard as dash
    monkeypatch.setattr(dash, "DATA", tmp_path)
    monkeypatch.setattr(dash, "ROOT", tmp_path)
    assert "No status yet" in dash.render()

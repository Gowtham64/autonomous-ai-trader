from risk.position_budget import decide_open_trade_cap


def _liquid_quotes():
    return [
        {"symbol": "BTCUSD", "spread_pct": 0.02, "change": -0.4},
        {"symbol": "ETHUSD", "spread_pct": 0.03, "change": -0.8},
        {"symbol": "SOLUSD", "spread_pct": 0.04, "change": 0.2},
        {"symbol": "XRPUSD", "spread_pct": 0.05, "change": -1.0},
        {"symbol": "DOGEUSD", "spread_pct": 0.04, "change": 0.1},
    ]


def test_small_capital_stays_near_two_until_the_market_is_orderly():
    quiet = decide_open_trade_cap(equity=6.0, quotes=[])
    assert quiet.capital_slots == 2
    assert quiet.cap == 1

    orderly = decide_open_trade_cap(equity=6.0, quotes=_liquid_quotes())
    assert orderly.capital_slots == 2
    assert orderly.market_delta == 1
    assert orderly.cap == 3


def test_fifty_dollars_and_a_proven_record_open_more_slots():
    decision = decide_open_trade_cap(
        equity=50.0,
        closed_trades=20,
        win_rate=0.60,
        profit_factor=1.8,
        drawdown_pct=0.01,
        quotes=_liquid_quotes(),
    )
    assert decision.capital_slots == 4
    assert decision.performance_delta == 1
    assert decision.market_delta == 1
    assert decision.cap == 6


def test_a_cold_streak_and_a_fast_market_cut_the_cap():
    wild = [
        {"symbol": "BTCUSD", "spread_pct": 0.40, "change": 9.0},
        {"symbol": "ETHUSD", "spread_pct": 0.50, "change": 8.0},
        {"symbol": "SOLUSD", "spread_pct": 0.30, "change": 7.0},
    ]
    decision = decide_open_trade_cap(
        equity=50.0,
        closed_trades=12,
        win_rate=0.30,
        profit_factor=0.7,
        quotes=wild,
    )
    assert decision.cap < decision.capital_slots
    assert decision.cap >= 1


def test_cap_never_passes_the_ceiling():
    decision = decide_open_trade_cap(
        equity=500.0,
        closed_trades=40,
        win_rate=0.70,
        profit_factor=2.4,
        quotes=_liquid_quotes(),
    )
    assert decision.cap <= 8

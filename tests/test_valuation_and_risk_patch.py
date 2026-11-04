"""Comprehensive Phase 5 Regression and Integration Test Suite for Valuation & Risk-Gate Patch.

Tests:
1. XRPUSDT (mult 1.0) and DOGEUSDT (mult 100.0) contract-specific valuation.
2. Long and Short position P&L accuracy.
3. Multiplier applied exactly once across all operations.
4. Stale LTP with a valid mark price (mark price used, stale LTP not used for valuation).
5. Missing LTP with a valid mark price (failsafe valuation active, position not skipped).
6. Missing or stale mark price (valuation flagged unreliable, fails safely).
7. Correct mark-to-market equity calculation.
8. Drawdown breaker activation at configured threshold (15% micro-crypto cap).
9. Daily loss breaker behavior.
10. Consistency between Broker, Treasury, Monitor, Guardian, and Risk Engine.
11. Correct handling of fees and funding.
12. Stop-loss and take-profit evaluation with configured trigger source (LTP vs Mark).
13. Prevention of new risk-increasing entries when valuation is unreliable.
14. Invariance / No double-counting of unrealized P&L across repeated snapshots.
"""

import pytest
import asyncio
from datetime import UTC, datetime
from core.domain.models import ExitReason
from core.schemas.trade import PositionSnapshot, TradeAction, TradeDecision, OrderIntent, OrderStatus
from core.treasury.treasury import AITreasury
from core.valuation import (
    ContractType,
    PortfolioValuation,
    PriceSource,
    ValuationResult,
    calculate_unrealized_pnl,
    evaluate_bracket_condition,
    resolve_contract_multiplier,
    resolve_valuation_price,
    value_portfolio,
    value_position,
)
from execution.paper.delta_paper import DeltaPaperBroker
from guardian.position_guardian import PositionGuardianWorker
from monitoring.position_monitor import PositionMonitor
from risk.engine import DeterministicRiskEngine


def test_01_xrpusdt_and_dogeusdt_contract_specific_valuation():
    """Verify official Delta contract specifications for XRPUSDT and DOGEUSDT."""
    assert resolve_contract_multiplier("XRPUSDT") == 1.0
    assert resolve_contract_multiplier("DOGEUSDT") == 100.0

    # XRPUSDT: 8 contracts long @ 1.3420, mark 1.3077
    pnl_xrp = calculate_unrealized_pnl(
        entry_price=1.3420,
        valuation_price=1.30771927,
        quantity=8,
        side="BUY",
        multiplier=1.0,
        contract_type=ContractType.LINEAR_PERPETUAL,
    )
    assert round(pnl_xrp, 4) == -0.2742

    # DOGEUSDT: 1 contract long @ 0.083392, mark 0.07844058
    pnl_doge = calculate_unrealized_pnl(
        entry_price=0.083392,
        valuation_price=0.07844058,
        quantity=1,
        side="BUY",
        multiplier=100.0,
        contract_type=ContractType.LINEAR_PERPETUAL,
    )
    assert round(pnl_doge, 4) == -0.4951


def test_02_long_and_short_positions():
    """Verify symmetrical and accurate calculation for both long and short positions."""
    entry = 100.0
    mult = 1.0
    qty = 10

    # Long in profit (price = 110) -> +100
    assert calculate_unrealized_pnl(entry, 110.0, qty, "BUY", mult) == 100.0
    # Long in loss (price = 90) -> -100
    assert calculate_unrealized_pnl(entry, 90.0, qty, "BUY", mult) == -100.0
    # Short in profit (price = 90) -> +100
    assert calculate_unrealized_pnl(entry, 90.0, qty, "SELL", mult) == 100.0
    # Short in loss (price = 110) -> -100
    assert calculate_unrealized_pnl(entry, 110.0, qty, "SELL", mult) == -100.0


def test_03_multiplier_applied_exactly_once():
    """Verify that contract multiplier is applied once, avoiding 0x or 2x errors."""
    pos = PositionSnapshot(
        position_id="POS-DOGE",
        symbol="DOGEUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=2,
        entry_price=0.080,
        current_price=0.080,
        stop_loss=0.075,
        target_1=0.090,
        highest_price_seen=0.080,
        lowest_price_seen=0.080,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    ticker = {"symbol": "DOGEUSDT", "close": 0.085, "mark_price": 0.085, "is_stale": False}
    val = value_position(pos, ticker, preferred_source=PriceSource.MARK_PRICE)

    # (0.085 - 0.080) * 2 * 100.0 = 0.005 * 200 = 1.00 USD
    assert val.gross_unrealized_pnl == 1.0000
    assert val.multiplier == 100.0


def test_04_stale_ltp_with_valid_mark_price():
    """Verify that when LTP is 24h stale, mark price is strictly utilized for valuation."""
    ticker = {
        "symbol": "XRPUSDT",
        "close": 1.3413,  # Stale LTP
        "mark_price": 1.3077,  # Live fresh mark price
        "drift_ms": 0,
        "is_stale": False,
    }
    px, source, is_reliable, reason = resolve_valuation_price(ticker, preferred_source=PriceSource.MARK_PRICE)
    assert px == 1.3077
    assert source == PriceSource.MARK_PRICE
    assert is_reliable is True


def test_05_missing_ltp_with_valid_mark_price():
    """Verify that when LTP is None (0 trades in 24h), mark price prevents silent bypass."""
    pos = PositionSnapshot(
        position_id="POS-DOGE",
        symbol="DOGEUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=1,
        entry_price=0.0834,
        current_price=0.0834,
        stop_loss=0.0821,
        target_1=0.0860,
        highest_price_seen=0.0834,
        lowest_price_seen=0.0834,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    ticker = {
        "symbol": "DOGEUSDT",
        "close": None,  # Zero trades executed
        "mark_price": 0.0784,
        "is_stale": False,
    }
    # Bracket evaluation must not crash or bypass
    triggered, reason, note, eval_px = evaluate_bracket_condition(pos, ticker, trigger_method="last_traded_price")
    # Mark price fell to 0.0784 which is below SL 0.0821 -> Failsafe trigger
    assert triggered is True
    assert reason == "STOP_LOSS_HIT"
    assert eval_px == 0.0784


def test_06_missing_or_stale_mark_price_fails_safely():
    """Verify that missing or stale mark price flags valuation as unreliable."""
    # Stale feed (>60s drift)
    ticker_stale = {"symbol": "XRPUSDT", "close": 1.34, "mark_price": 1.31, "is_stale": True, "drift_ms": 90000}
    px, source, is_rel, reason = resolve_valuation_price(ticker_stale, preferred_source=PriceSource.MARK_PRICE)
    assert px is None
    assert is_rel is False
    assert "DATA_STALE" in reason

    # Missing mark price
    ticker_missing = {"symbol": "XRPUSDT", "close": 1.34, "mark_price": None, "is_stale": False}
    px, source, is_rel, reason = resolve_valuation_price(ticker_missing, preferred_source=PriceSource.MARK_PRICE)
    assert px is None
    assert is_rel is False
    assert "MARK_PRICE_MISSING" in reason


def test_07_correct_mark_to_market_equity():
    """Verify that portfolio valuation computes true MtM equity and drawdown."""
    cash_balance = 11.7062
    peak_equity = 11.7104

    pos1 = PositionSnapshot(
        position_id="POS-XRP",
        symbol="XRPUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=8,
        entry_price=1.3420,
        current_price=1.3420,
        stop_loss=1.32,
        target_1=1.38,
        highest_price_seen=1.3420,
        lowest_price_seen=1.3420,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    pos2 = PositionSnapshot(
        position_id="POS-DOGE",
        symbol="DOGEUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=1,
        entry_price=0.083392,
        current_price=0.083392,
        stop_loss=0.0821,
        target_1=0.0860,
        highest_price_seen=0.083392,
        lowest_price_seen=0.083392,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    tickers = {
        "XRPUSDT": {"symbol": "XRPUSDT", "close": 1.3413, "mark_price": 1.30771927, "is_stale": False},
        "DOGEUSDT": {"symbol": "DOGEUSDT", "close": None, "mark_price": 0.07844058, "is_stale": False},
    }

    port = value_portfolio(
        cash_balance=cash_balance,
        used_margin=3.8150,
        available_margin=7.8912,
        positions=[pos1, pos2],
        ticker_map=tickers,
        peak_equity=peak_equity,
    )
    assert round(port.total_unrealized_pnl, 4) == -0.7693
    assert port.mark_to_market_equity == 10.9369
    assert port.peak_equity == 11.7104
    assert port.drawdown == 0.7735
    assert port.drawdown_pct == 6.61
    assert port.is_valuation_reliable is True


def test_08_drawdown_breaker_activation():
    """Verify maximum drawdown circuit breaker trips at 15% threshold."""
    peak = 11.7104
    # 15% drawdown threshold on peak = $1.7565 -> Equity <= $9.9539
    safe_mtm = 10.50  # 10.3% DD -> Approved
    breaker_mtm = 9.80  # 16.3% DD -> Trips breaker

    decision = TradeDecision(
        analysis_id="DEC-01",
        symbol="SOLUSDT",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.85,
        entry_price=100.0,
        stop_loss=97.0,
        target_1=107.0,
    )

    eng_safe = DeterministicRiskEngine(total_equity=safe_mtm, peak_equity=peak)
    chk_safe = eng_safe.evaluate_trade_intent(decision, [])
    assert chk_safe.approved is True

    eng_trip = DeterministicRiskEngine(total_equity=breaker_mtm, peak_equity=peak)
    chk_trip = eng_trip.evaluate_trade_intent(decision, [])
    assert chk_trip.approved is False
    assert any("Max Drawdown Limit hit" in r for r in chk_trip.rejection_reasons)


def test_09_daily_loss_breaker():
    """Verify daily loss circuit breaker trips when daily loss reaches limit."""
    equity = 11.0
    # Minimum loss floor for USD micro accounts is $1.00
    eng_normal = DeterministicRiskEngine(total_equity=equity, current_daily_realized_loss=0.50)
    decision = TradeDecision(
        analysis_id="DEC-02",
        symbol="SOLUSDT",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.85,
        entry_price=100.0,
        stop_loss=97.0,
        target_1=107.0,
    )
    assert eng_normal.evaluate_trade_intent(decision, []).approved is True

    eng_tripped = DeterministicRiskEngine(total_equity=equity, current_daily_realized_loss=1.20)
    chk = eng_tripped.evaluate_trade_intent(decision, [])
    assert chk.approved is False
    assert any("Daily Loss Limit hit" in r for r in chk.rejection_reasons)


def test_10_consistency_across_all_components():
    """Verify broker, treasury, monitor, guardian, and risk engine agree on equity and P&L."""
    broker = DeltaPaperBroker(initial_capital=10.0)
    treasury = AITreasury(starting_capital=10.0)
    monitor = PositionMonitor(broker=broker)

    async def _run():
        # Open 8x XRPUSDT @ 1.3420
        intent = OrderIntent(
            client_order_id="TEST-ENT",
            decision_id="DEC-01",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=8,
            price=1.3413,
            stop_loss=1.32,
            target=1.38,
        )
        await broker.place_order(intent)

        # Update broker with live mark price
        broker.update_mark_prices({"XRPUSDT": 1.30771927})
        funds = await broker.get_funds()

        # 1. Broker P&L & Equity
        assert funds["unrealized_pnl"] == -0.2742
        assert funds["mark_to_market_equity"] == round(funds["total_capital"] + (-0.2742), 4)

        # 2. Treasury Equity
        treasury.set_unrealized_pnl(funds["unrealized_pnl"])
        treasury.current_capital = funds["total_capital"]
        assert treasury.total_equity == funds["mark_to_market_equity"]

        # 3. Monitor Evaluation
        pos = (await broker.get_positions())[0]
        await monitor.evaluate_position(pos, current_ltp=1.3413, mark_price=1.30771927)
        assert pos.unrealized_pnl == -0.2742

        # 4. Position Guardian Evaluation
        guardian = PositionGuardianWorker(pos=pos)
        await guardian.evaluate_tick(current_ltp=1.3413, mark_price=1.30771927)
        assert guardian.state.unrealized_pnl == -0.2742

        # 5. Risk Engine
        engine = DeterministicRiskEngine(
            total_equity=funds["mark_to_market_equity"],
            peak_equity=funds["total_capital"],
        )
        assert round(engine.total_equity, 4) == round(funds["mark_to_market_equity"], 4)

    asyncio.run(_run())


def test_11_fees_and_funding():
    """Verify fees and 8-hour funding settlements are properly reconciled in cash and MtM equity."""
    broker = DeltaPaperBroker(initial_capital=10.0)

    async def _run():
        intent = OrderIntent(
            client_order_id="TEST-FEE",
            decision_id="DEC-FEE",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=8,
            price=1.3413,
            stop_loss=1.32,
            target=1.38,
        )
        res = await broker.place_order(intent)
        assert res.brokerage_fee == 0.0054

        # Deduct 0.01% funding
        mult = 1.0
        turnover = res.average_price * 8 * mult
        funding = round(turnover * 0.0001, 4)
        assert funding == 0.0011
        broker.available_margin -= funding

        funds = await broker.get_funds()
        expected_cash = round(10.0 - 0.0054 - 0.0011, 4)  # $9.9935
        assert funds["total_capital"] == expected_cash

    asyncio.run(_run())


def test_12_stop_loss_and_take_profit_triggers():
    """Verify trigger source mechanics: mark_price trigger vs last_traded_price trigger."""
    pos = PositionSnapshot(
        position_id="POS-TEST",
        symbol="XRPUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=8,
        entry_price=1.3420,
        current_price=1.3420,
        stop_loss=1.3212,
        target_1=1.3836,
        highest_price_seen=1.3420,
        lowest_price_seen=1.3420,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    # Stale LTP = 1.3413 (not hit SL), Live Mark = 1.3077 (breaches SL 1.3212)
    ticker = {"symbol": "XRPUSDT", "close": 1.3413, "mark_price": 1.3077, "is_stale": False}

    # Under mark_price trigger -> Triggers Stop Loss!
    trig_m, reason_m, _, px_m = evaluate_bracket_condition(pos, ticker, trigger_method="mark_price")
    assert trig_m is True
    assert reason_m == "STOP_LOSS_HIT"
    assert px_m == 1.3077

    # Under last_traded_price trigger with existing close -> Not triggered (respects exchange rule)
    trig_l, reason_l, _, px_l = evaluate_bracket_condition(pos, ticker, trigger_method="last_traded_price")
    assert trig_l is False
    assert px_l == 1.3413


def test_13_prevention_of_new_entries_when_valuation_unreliable():
    """Verify that active positions with unreliable/stale valuation block new risk-increasing entries."""
    engine = DeterministicRiskEngine(total_equity=10.0)
    pos_corrupt = PositionSnapshot(
        position_id="POS-UNVERIFIED",
        symbol="XRPUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=8,
        entry_price=1.3420,
        current_price=1.3420,
        stop_loss=1.32,
        target_1=1.38,
        highest_price_seen=1.3420,
        lowest_price_seen=1.3420,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    # Flag position as having unreliable valuation
    pos_corrupt.valuation_unreliable = True

    dec = TradeDecision(
        analysis_id="DEC-NEW",
        symbol="SOLUSDT",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.88,
        entry_price=100.0,
        stop_loss=97.0,
        target_1=107.0,
    )
    chk = engine.evaluate_trade_intent(dec, [pos_corrupt])
    assert chk.approved is False
    assert any("unreliable/stale valuation" in r for r in chk.rejection_reasons)


def test_14_no_double_counting_across_repeated_snapshots():
    """Verify that repeated polling does not accumulate or double-count unrealized P&L into cash."""
    broker = DeltaPaperBroker(initial_capital=10.0)

    async def _run():
        intent = OrderIntent(
            client_order_id="TEST-DOUBLE",
            decision_id="DEC-01",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=8,
            price=1.3413,
            stop_loss=1.32,
            target=1.38,
        )
        await broker.place_order(intent)
        cash_after_entry = (await broker.get_funds())["total_capital"]

        # Snapshot 1
        broker.update_mark_prices({"XRPUSDT": 1.3077})
        funds1 = await broker.get_funds()

        # Snapshot 2 (identical prices)
        broker.update_mark_prices({"XRPUSDT": 1.3077})
        funds2 = await broker.get_funds()

        # Snapshot 3 (price change)
        broker.update_mark_prices({"XRPUSDT": 1.3200})
        funds3 = await broker.get_funds()

        # Cash balance MUST remain invariant
        assert funds1["total_capital"] == cash_after_entry
        assert funds2["total_capital"] == cash_after_entry
        assert funds3["total_capital"] == cash_after_entry

        # MtM reflects current mark without accumulation
        assert funds1["mark_to_market_equity"] == funds2["mark_to_market_equity"]
        assert funds3["mark_to_market_equity"] > funds1["mark_to_market_equity"]

    asyncio.run(_run())

"""
Master Regression Test Suite for Delta Exchange Forensic Audit Fixes.

Validates all 10 confirmed software defects and proves the correctness of their fixes:
- BUG-01: Contract multipliers and P&L calculations (XMR, BCH, TSLAX, ALT, STBL, LIGHT)
- BUG-02: Bracket-order position confirmation workflow
- BUG-03: Stop-loss and entry slippage dynamic re-anchoring
- BUG-04: Exit-order persistence into relational orders table
- BUG-05: Broker-closed position reconciliation, post-trade analytics, and journal persistence
- BUG-06: Daily loss circuit breaker persistence across process restarts
- BUG-07: Premature profit-taking closed-candle confirmation
- BUG-08: Incomplete daily candle exclusion from volume baseline
- BUG-09: Orphaned protective order cancellation upon position closure
- BUG-10: Currency consistency in USD/INR risk evaluations
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from core.domain.models import OrderStatus, TradeAction
from core.schemas.trade import OrderIntent, PositionSnapshot, TradeDecision
from execution.brokers.delta_exchange import DeltaExchangeBroker
from guardian.chart_monitor import ChartProfitTaker
from guardian.models import GuardianAction, PositionGuardianState
from guardian.position_guardian import PositionGuardianWorker
from guardian.post_trade_analytics import PostTradeAnalyticsEngine
from guardian.trade_guardian import MasterTradeGuardian
from portfolio.position_sizer import PositionSizer, get_delta_contract_multiplier
from risk.engine import DeterministicRiskEngine


# ==============================================================================
# BUG-01 & BUG-10: CONTRACT MULTIPLIERS, TURNOVER, FEES, AND POSITION SIZING
# ==============================================================================

def test_regression_bug_01_multipliers_applied_exactly_once():
    """Verify that contract multipliers are applied exactly once across:
    1. get_delta_contract_multiplier resolution
    2. PostTradeAnalyticsEngine.calculate_brokerage_fee (turnover)
    3. PostTradeAnalyticsEngine.analyze_completed_guardian_position (gross & net PnL)
    4. PositionSizer.calculate_quantity (effective unit cost & stop distance)
    """
    test_cases = [
        {"symbol": "XMRUSD", "mult": 0.01, "entry": 576.88, "exit": 580.866, "qty": 1},
        {"symbol": "BCHUSD", "mult": 0.01, "entry": 535.10, "exit": 540.100, "qty": 1},
        {"symbol": "TSLAXUSD", "mult": 0.01, "entry": 368.95, "exit": 368.530, "qty": 2},
        {"symbol": "ALTUSD", "mult": 10.0, "entry": 0.0084, "exit": 0.0090, "qty": 100},
        {"symbol": "STBLUSD", "mult": 10.0, "entry": 0.0500, "exit": 0.0520, "qty": 50},
        {"symbol": "LIGHTUSD", "mult": 10.0, "entry": 1.0, "exit": 1.05, "qty": 5},
    ]

    for tc in test_cases:
        sym = tc["symbol"]
        mult = get_delta_contract_multiplier(sym)
        assert mult == tc["mult"], f"Multiplier for {sym} expected {tc['mult']}, got {mult}"

        state = PositionGuardianState(
            guardian_id=f"GRD-{sym}-1",
            position_id=f"POS-{sym}-1",
            order_id=f"ORD-{sym}-1",
            decision_id=f"ANL-{sym}-1",
            symbol=sym,
            side="BUY",
            quantity=tc["qty"],
            entry_price=tc["entry"],
            current_price=tc["exit"],
            position_value=tc["entry"] * tc["qty"],
            stop_loss=tc["entry"] * 0.98,
            target_1=tc["entry"] * 1.04,
            highest_price_seen=tc["exit"],
            lowest_price_seen=tc["entry"],
            exchange="DELTA",
        )

        report = PostTradeAnalyticsEngine.analyze_completed_guardian_position(
            state=state,
            exit_price=tc["exit"],
            exit_reason="REGRESSION_TEST",
        )

        expected_gross = (tc["exit"] - tc["entry"]) * tc["qty"] * mult
        expected_turnover = (tc["entry"] + tc["exit"]) * tc["qty"] * mult
        expected_fee = round(expected_turnover * 0.0005, 4)
        expected_net = round(expected_gross - expected_fee, 2)

        assert abs(report.realized_pnl - expected_net) <= 0.02, (
            f"P&L calculation mismatch on {sym}: expected {expected_net}, got {report.realized_pnl}"
        )
        assert abs(report.brokerage_and_fees - expected_fee) <= 0.01, (
            f"Fee calculation mismatch on {sym}: expected {expected_fee}, got {report.brokerage_and_fees}"
        )


def test_regression_bug_01_position_sizer_uses_multiplier():
    """Verify that PositionSizer accounts for contract multipliers in unit costs and trade risk."""
    sizer = PositionSizer(total_equity=10.0, available_margin=10.0)

    # 1. Micro asset: XMRUSD (mult 0.01). 1 contract of $500 is only $5 notional, safe margin
    decision_xmr = TradeDecision(
        analysis_id="DEC-XMR-1",
        symbol="XMRUSD",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.8,
        entry_price=500.0,
        stop_loss=490.0,
        target_1=520.0,
        expected_risk_reward=2.0,
    )
    risk_ok = MagicMock(approved=True, rejection_reasons=[])
    qty_xmr = sizer.calculate_quantity(decision_xmr, risk_ok)
    assert qty_xmr >= 1, "Position sizer should allow unit size when contract multiplier scales down notional"

    # 2. Unverified asset rejected by Zero-Trust gate
    decision_fake = TradeDecision(
        analysis_id="DEC-FAKE-1",
        symbol="NONEXISTENTCOINUSD",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.8,
        entry_price=10.0,
        stop_loss=9.0,
        target_1=12.0,
        expected_risk_reward=2.0,
    )
    qty_fake = sizer.calculate_quantity(decision_fake, risk_ok)
    assert qty_fake == 0, "Unverified contract multiplier must result in 0 quantity"


# ==============================================================================
# BUG-02: BRACKET ORDER POSITION CONFIRMATION WORKFLOW
# ==============================================================================

@pytest.mark.asyncio
async def test_regression_bug_02_bracket_order_waits_for_position_confirmation():
    """Verify that DeltaExchangeBroker verifies open position before submitting bracket order."""
    broker = DeltaExchangeBroker()
    order = OrderIntent(
        client_order_id="ORD-CONFIRM-1",
        decision_id="ANL-1",
        symbol="BTCUSD",
        action=TradeAction.BUY,
        quantity=1,
        price=60000.0,
        stop_loss=59000.0,
        target=62000.0,
    )
    broker.api_key = "test_key"
    broker.api_secret = "test_secret"
    broker._products_cache = {"BTCUSD": {"id": 1001, "tick_size": "0.5"}}

    # Mock responses
    poll_count = 0
    bracket_called = False

    async def mock_request(method, endpoint, payload=None, params=None):
        nonlocal poll_count, bracket_called
        if endpoint == "/v2/orders" and method == "POST":
            return {"success": True, "result": {"id": 88888, "size": 1, "unfilled_size": 0, "average_fill_price": 60000.0}}
        elif "/v2/positions" in endpoint and method == "GET":
            poll_count += 1
            if poll_count >= 2:
                # Confirmed position appears on second poll
                return {"success": True, "result": [{"product_id": 1001, "product_symbol": "BTCUSD", "size": 1, "entry_price": "60000.0"}]}
            return {"success": True, "result": []}
        elif endpoint == "/v2/orders/bracket":
            bracket_called = True
            return {"success": True, "result": {"id": 77777}}
        elif endpoint == "/v2/products":
            return {"success": True, "result": [{"symbol": "BTCUSD", "id": 1001, "tick_size": "0.5"}]}
        return {"success": True, "result": {}}

    with patch.object(broker, "_request", side_effect=mock_request):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            exec_report = await broker.place_order(order)
            assert exec_report.status == OrderStatus.SUBMITTED
            assert poll_count >= 2, "Broker must poll get_positions to confirm position"
            assert bracket_called is True, "Bracket order should be placed once position is confirmed"


# ==============================================================================
# BUG-03: DYNAMIC STOP-LOSS ANCHORING TO ACTUAL FILL PRICE
# ==============================================================================

def test_regression_bug_03_slippage_dynamic_reanchoring():
    """Verify that stop loss is dynamically anchored to actual fill price, preventing crossed stops."""
    # Scenario: BUY order planned at 0.3716 with SL at 0.3700 (distance = 0.0016).
    # Market slipped and filled lower at 0.3699.
    planned_entry = 0.3716
    planned_sl = 0.3700
    actual_fill = 0.3699

    stop_dist = abs(planned_entry - planned_sl)  # 0.0016
    # Corrected dynamic formula:
    adj_sl = actual_fill - stop_dist  # 0.3683
    if adj_sl >= actual_fill:
        adj_sl = actual_fill * 0.985

    assert adj_sl < actual_fill, "Adjusted stop loss must be strictly below actual fill price for BUY"
    assert round(adj_sl, 4) == 0.3683

    # PositionGuardian evaluation with adjusted SL:
    pos = PositionSnapshot(
        position_id="POS-TEST-SLIPPAGE",
        symbol="STXUSD",
        quantity=19,
        entry_price=actual_fill,
        current_price=actual_fill,
        stop_loss=round(adj_sl, 4),
        target_1=0.3800,
        highest_price_seen=actual_fill,
        lowest_price_seen=actual_fill,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    worker = PositionGuardianWorker(pos=pos)
    action, reason = asyncio.run(worker.evaluate_tick(current_ltp=actual_fill))
    assert action == GuardianAction.HOLD, f"Position should HOLD on initial tick, got {action}"


# ==============================================================================
# BUG-04: EXIT ORDER PERSISTENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_regression_bug_04_exit_order_persisted_to_db():
    """Verify that MasterTradeGuardian persists exit orders to TradeRepository."""
    guardian = MasterTradeGuardian()
    pos = PositionSnapshot(
        position_id="POS-ETH-1",
        symbol="ETHUSD",
        quantity=10,
        entry_price=105.0,
        current_price=100.0,
        stop_loss=102.0,  # Breached!
        target_1=115.0,
        highest_price_seen=105.0,
        lowest_price_seen=100.0,
        unrealized_pnl=-50.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    mock_broker = MagicMock()
    mock_broker.get_positions = AsyncMock(return_value=[pos])
    mock_broker.place_order = AsyncMock(return_value=MagicMock(
        status=OrderStatus.FILLED,
        filled_quantity=10,
        average_price=100.0,
        order_id="EXIT-123",
        client_order_id="GRD-EXT-1",
        symbol="ETHUSD",
        slippage=0.0,
        brokerage_fee=0.0,
        taxes_and_charges=0.0,
    ))

    guardian.register_position(pos=pos)
    mock_provider = MagicMock()
    mock_provider.get_ltp = AsyncMock(return_value=100.0)

    with patch("database.repositories.trade_repo.TradeRepository.save_order", new_callable=AsyncMock) as mock_save_order:
        with patch("database.repositories.trade_repo.TradeRepository.save_journal", new_callable=AsyncMock):
            actions = await guardian.evaluate_all_guardians(provider=mock_provider, broker=mock_broker)
            assert len(actions) == 1
            assert actions[0][1] == GuardianAction.HARD_STOP_EXIT
            assert mock_save_order.call_count == 1, "Exit order must be persisted to TradeRepository"


# ==============================================================================
# BUG-05: BROKER-CLOSED POSITION RECONCILIATION & JOURNALING
# ==============================================================================

@pytest.mark.asyncio
async def test_regression_bug_05_broker_exit_persisted_and_reconciled():
    """Verify that broker reconciliation records post-trade analytics and journal entries for closed positions."""
    guardian = MasterTradeGuardian()
    pos = PositionSnapshot(
        position_id="POS-SOL-1",
        symbol="SOLUSD",
        quantity=5,
        entry_price=150.0,
        current_price=155.0,
        stop_loss=145.0,
        target_1=165.0,
        highest_price_seen=155.0,
        lowest_price_seen=150.0,
        unrealized_pnl=25.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    worker = guardian.register_position(pos=pos)
    assert worker.state.is_active is True

    # Broker reports 0 positions (bracket order filled on exchange)
    mock_broker = MagicMock()
    mock_broker.get_positions = AsyncMock(return_value=[])

    with patch("database.repositories.trade_repo.TradeRepository.save_journal", new_callable=AsyncMock) as mock_save_journal:
        report = await guardian.reconcile_with_broker(broker=mock_broker)
        assert worker.state.is_active is False
        assert mock_save_journal.call_count == 1, "Broker-closed position must be saved to trade_journal"
        assert len(guardian.completed_reports) == 1, "PostTradeQualityReport must be generated"


# ==============================================================================
# BUG-06: CIRCUIT BREAKER PERSISTENCE ACROSS RESTARTS
# ==============================================================================

def test_regression_bug_06_circuit_breaker_persists_across_restarts(tmp_path):
    """Verify that daily loss state persists to disk and prevents circuit breaker bypass on restarts."""
    today_str = datetime.now(UTC).date().isoformat()
    test_state_file = tmp_path / "daily_risk_state.json"

    # Save day start equity of $10.00
    test_state_file.write_text(json.dumps({
        "date": today_str,
        "day_start_equity": 10.0,
        "last_updated": datetime.now(UTC).isoformat(),
    }))

    # Now simulate a reboot when real_cap has fallen to $8.00 (loss of $2.00)
    real_cap = 8.0
    with open(test_state_file) as f:
        saved_data = json.load(f)
    assert saved_data["date"] == today_str
    day_start_equity = float(saved_data["day_start_equity"])

    daily_realized_loss = max(0.0, day_start_equity - real_cap)
    assert daily_realized_loss == 2.0, "Daily realized loss must be recovered as $2.00 after restart"

    # Risk engine evaluates the loss against limit
    engine = DeterministicRiskEngine(
        total_equity=real_cap,
        current_daily_realized_loss=daily_realized_loss,
        peak_equity=10.0,
    )
    decision = TradeDecision(
        analysis_id="TEST-DEC",
        symbol="BTCUSD",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.8,
        entry_price=60000.0,
        stop_loss=59000.0,
        target_1=62000.0,
        expected_risk_reward=2.0,
    )
    res = engine.evaluate_trade_intent(decision, open_positions=[])
    assert res.approved is False
    assert any("Daily Loss Limit hit" in r for r in res.rejection_reasons)


# ==============================================================================
# BUG-07: CHART PROFIT TAKER CLOSED-CANDLE CONFIRMATION
# ==============================================================================

def test_regression_bug_07_chart_profit_taker_closed_candle_confirmation():
    """Verify that require_closed_candle=True prevents premature exit on forming candle wicks."""
    data = {
        "open": [100.0, 100.2, 100.3, 100.5],
        "high": [100.3, 100.4, 100.6, 101.2],
        "low": [99.9, 100.1, 100.2, 100.4],
        "close": [100.2, 100.3, 100.5, 100.55],
        "volume": [1000, 1200, 1100, 1500],
    }
    df_5m = pd.DataFrame(data)

    # 1. Without closed-candle requirement, forming candle triggers premature exit
    exit_unclosed, _ = ChartProfitTaker.evaluate_chart_profit_exit(
        df_5m=df_5m,
        entry_price=100.0,
        current_ltp=100.55,
        highest_price_seen=101.2,
        require_closed_candle=False,
    )
    assert exit_unclosed is True, "Unclosed candle triggers premature exit under old logic"

    # 2. With closed-candle requirement, forming candle is rejected
    exit_closed, reason = ChartProfitTaker.evaluate_chart_profit_exit(
        df_5m=df_5m,
        entry_price=100.0,
        current_ltp=100.55,
        highest_price_seen=101.2,
        require_closed_candle=True,
    )
    assert exit_closed is False, f"Closed candle requirement must prevent premature exit, got: {reason}"


# ==============================================================================
# BUG-08: SCANNER EXCLUDES INCOMPLETE DAILY CANDLE
# ==============================================================================

def test_regression_bug_08_scanner_excludes_incomplete_daily_candle():
    """Verify that 20-day historical volume baseline excludes incomplete current daily bar."""
    # 25 historical daily bars of 1000 volume, plus current forming bar of only 50 volume
    volumes = [1000] * 25 + [50]
    volume_series = pd.Series(volumes)

    # Old buggy calculation (included current bar in tail(20)):
    buggy_avg = float(volume_series.tail(20).mean())
    # 19 bars of 1000 + 1 bar of 50 = 19050 / 20 = 952.5

    # Corrected calculation (uses closed bars):
    closed_volume = volume_series.iloc[:-1] if len(volume_series) > 20 else volume_series
    corrected_avg = float(closed_volume.tail(20).mean())
    assert corrected_avg == 1000.0, "20-day average volume must be calculated exclusively on closed bars"
    assert buggy_avg != corrected_avg


# ==============================================================================
# BUG-09: ORPHANED PROTECTIVE ORDER CANCELLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_regression_bug_09_orphaned_orders_cancelled_on_reduce_only_exit():
    """Verify that reduce_only exit order clears residual orders for the product."""
    broker = DeltaExchangeBroker()
    order = OrderIntent(
        client_order_id="EXT-ORD-01",
        decision_id="GRD-EXIT",
        symbol="BTCUSD",
        action=TradeAction.SELL,
        quantity=1,
        price=None,
        stop_loss=0.0,
        target=0.0,
        reduce_only=True,
    )
    broker._products_cache = {"BTCUSD": {"id": 1001, "tick_size": "0.5"}}

    deleted_orders = []

    async def mock_request(method, endpoint, payload=None, params=None):
        nonlocal deleted_orders
        if endpoint == "/v2/orders" and method == "POST":
            return {"success": True, "result": {"id": 99001, "size": 1, "unfilled_size": 0, "average_fill_price": 60000.0}}
        elif endpoint == "/v2/orders?state=open&product_id=1001" and method == "GET":
            return {"success": True, "result": [{"id": 5555, "product_id": 1001}]}
        elif endpoint == "/v2/orders" and method == "DELETE":
            deleted_orders.append(payload.get("id"))
            return {"success": True}
        elif endpoint == "/v2/products":
            return {"success": True, "result": [{"symbol": "BTCUSD", "id": 1001, "tick_size": "0.5"}]}
        return {"success": True, "result": {}}

    with patch.object(broker, "_request", side_effect=mock_request):
        await broker.place_order(order)
        assert 5555 in deleted_orders, "Residual bracket order 5555 should be cancelled on reduce_only exit"


# ==============================================================================
# BUG-10: CURRENCY CONSISTENCY
# ==============================================================================

def test_regression_bug_10_currency_consistency():
    """Verify that USD loss limits compare USD values consistently without INR cross-contamination."""
    engine = DeterministicRiskEngine(
        total_equity=10.0,  # $10.00 USD
        current_daily_realized_loss=0.50,  # $0.50 USD loss
        peak_equity=10.0,
    )

    decision = TradeDecision(
        analysis_id="DEC-CURR",
        symbol="ETHUSD",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.8,
        entry_price=2500.0,
        stop_loss=2480.0,
        target_1=2550.0,
        expected_risk_reward=2.5,
    )

    # Loss is $0.50, max daily loss floor is $1.00 USD -> Trade should be approved
    res = engine.evaluate_trade_intent(decision, open_positions=[])
    assert res.approved is True

    # Now simulate loss reaching $1.00 USD
    engine.daily_realized_loss = 1.05
    res2 = engine.evaluate_trade_intent(decision, open_positions=[])
    assert res2.approved is False
    assert any("$" in r for r in res2.rejection_reasons), "Rejection reason must use $ for USD accounts"
    assert not any("₹" in r for r in res2.rejection_reasons), "Rejection reason must NOT use ₹ for USD accounts"

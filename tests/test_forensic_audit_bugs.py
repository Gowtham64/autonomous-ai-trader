"""
Comprehensive Forensic Audit Bug Reproduction Test Suite.

Proves the existence and mechanics of software defects discovered during the
Delta Exchange forensic audit:
1. BUG-01: Post-trade analytics P&L ignores Delta contract multipliers.
2. BUG-02: Delta bracket order placement timing / race condition without open position verification.
3. BUG-03: Stop-loss slippage inversion causing instantaneous stop-outs.
4. BUG-04: Exit orders never persisted to database orders table.
5. BUG-05: Broker-reconciled position closures silently bypass trade journal persistence.
6. BUG-06: In-memory day-start equity resets on process restart, bypassing daily loss limits.
7. BUG-07: Premature chart profit-take on forming 5m candle truncating R:R expectancy.
8. BUG-08: Scanner daily candle indexing on unclosed bars skewing relative volume and ATR.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from core.domain.models import OrderStatus, TradeAction
from core.schemas.trade import OrderIntent, PositionSnapshot, TradeDecision
from guardian.chart_monitor import ChartProfitTaker
from guardian.models import PositionGuardianState
from guardian.post_trade_analytics import PostTradeAnalyticsEngine
from portfolio.position_sizer import get_delta_contract_multiplier
from risk.engine import DeterministicRiskEngine


def test_bug_01_pnl_ignores_contract_multiplier():
    """BUG-01: PostTradeAnalyticsEngine calculates P&L as (exit - entry) * qty,

    completely ignoring contract multipliers. This overstates 0.01 multiplier assets
    (XMR, BCH, TSLAX) by ~100x and understates 10.0 multiplier assets (ALT, STBL) by 10x.
    """
    mult_xmr = get_delta_contract_multiplier("XMRUSD")
    assert mult_xmr == 0.01, "XMR contract multiplier must be 0.01"

    state_xmr = PositionGuardianState(
        guardian_id="GRD-XMRUSD-1",
        position_id="POS-XMRUSD-1",
        order_id="ORD-XMR-1",
        decision_id="ANL-XMR-1",
        symbol="XMRUSD",
        side="BUY",
        quantity=1,
        entry_price=576.88,
        current_price=580.866238,
        position_value=576.88,
        stop_loss=571.39,
        target_1=589.27,
        highest_price_seen=580.866238,
        lowest_price_seen=576.88,
        exchange="DELTA",
    )
    exit_price_xmr = 580.866238

    report = PostTradeAnalyticsEngine.analyze_completed_guardian_position(
        state=state_xmr,
        exit_price=exit_price_xmr,
        exit_reason="CHART_PROFIT_TAKE",
    )

    # Actual real exchange math
    price_move = exit_price_xmr - 576.88
    true_gross_pnl = price_move * 1 * mult_xmr  # ~ $0.0399 USD
    true_turnover = (576.88 + exit_price_xmr) * 1 * mult_xmr  # ~ $11.577 USD
    true_fee = round(true_turnover * 0.0005, 4)  # ~ $0.0058 USD
    true_net_pnl = round(true_gross_pnl - true_fee, 2)  # +$0.03 USD

    # BUG RESOLUTION VERIFICATION: PostTradeAnalyticsEngine now reports real ~$0.03 P&L instead of inflated ~$3.41
    assert abs(report.realized_pnl - true_net_pnl) < 0.05, f"Expected {true_net_pnl}, got {report.realized_pnl}"
    assert report.realized_pnl < 0.10


def test_bug_01_short_asset_multiplier_distortion():
    """BUG-01: Proves distortion on TSLAXUSD (multiplier 0.01) where a tiny 40-cent

    fluctuation was recorded as a catastrophic -$1.58 loss.
    """
    mult_tslax = get_delta_contract_multiplier("TSLAXUSD")
    assert mult_tslax == 0.01

    state_tslax = PositionGuardianState(
        guardian_id="GRD-TSLAX-1",
        position_id="POS-TSLAX-1",
        order_id="ORD-TSLAX-1",
        decision_id="ANL-TSLAX-1",
        symbol="TSLAXUSD",
        side="BUY",
        quantity=2,
        entry_price=368.95,
        current_price=368.530376,
        position_value=737.9,
        stop_loss=365.0,
        target_1=375.0,
        highest_price_seen=368.95,
        lowest_price_seen=368.530376,
        exchange="DELTA",
    )
    exit_price = 368.530376

    report = PostTradeAnalyticsEngine.analyze_completed_guardian_position(
        state=state_tslax,
        exit_price=exit_price,
        exit_reason="STAGNATION_SCRATCH_EXIT",
    )

    # Real loss: (368.53 - 368.95) * 2 contracts * 0.01 = -$0.0084 USD
    true_loss = (exit_price - 368.95) * 2 * mult_tslax
    assert abs(true_loss) < 0.01  # less than 1 cent!

    # BUG RESOLUTION VERIFICATION: The bot now correctly records tiny ~$0.01 loss instead of -$1.58
    assert abs(report.realized_pnl) < 0.05, f"Loss should be under $0.05, got {report.realized_pnl}"


@pytest.mark.asyncio
async def test_bug_02_bracket_order_race_condition():
    """BUG-02: DeltaExchangeBroker.place_order sleeps 0.5s and then calls place_bracket_order.

    If the exchange has not registered an open position, place_bracket_order fails with
    400 no_open_position, leaving the position without exchange-side stop-loss protection.
    """
    from execution.brokers.delta_exchange import DeltaExchangeBroker

    broker = DeltaExchangeBroker()
    order = OrderIntent(
        client_order_id="TEST-ORD-01",
        decision_id="ANL-TEST-01",
        symbol="ALTUSD",
        action=TradeAction.BUY,
        quantity=100,
        price=0.0084,
        stop_loss=0.0080,
        target=0.0100,
    )

    broker._products_cache = {"ALTUSD": {"id": 1234, "tick_size": "0.0001"}}

    async def mock_request(method, endpoint, payload=None, params=None):
        if endpoint == "/v2/orders":
            return {"success": True, "result": {"id": 99999, "size": 100, "unfilled_size": 0, "average_fill_price": 0.0084}}
        elif endpoint == "/v2/orders/bracket":
            return {"success": False, "error": {"code": "no_open_position"}}
        elif endpoint == "/v2/products":
            return {"success": True, "result": [{"symbol": "ALTUSD", "id": 1234, "tick_size": "0.0001"}]}
        return {"success": True, "result": {}}

    with patch.object(broker, "_request", side_effect=mock_request):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            exec_report = await broker.place_order(order)
            assert exec_report.status == OrderStatus.SUBMITTED
            assert exec_report.order_id == "99999"


def test_bug_03_stop_loss_slippage_inversion():
    """BUG-03: When a market buy order experiences slippage such that the fill price

    is at or below the stop loss, Guardian triggers HARD_STOP_EXIT immediately.
    """
    from guardian.position_guardian import PositionGuardianWorker

    pos = PositionSnapshot(
        position_id="POS-STXUSD-TEST",
        symbol="STXUSD",
        quantity=19,
        entry_price=0.3699,  # Slipped fill price
        current_price=0.3699,
        stop_loss=0.3700,    # Planned SL was never adjusted for slippage!
        target_1=0.3800,
        highest_price_seen=0.3699,
        lowest_price_seen=0.3699,
        unrealized_pnl=-0.0019,
        opened_at=datetime.now(UTC),
        is_active=True,
    )

    worker = PositionGuardianWorker(pos=pos)
    action, reason = asyncio.run(worker.evaluate_tick(current_ltp=0.3699))

    # BUG PROOF: The trade is instantly killed with HARD_STOP_EXIT on tick 1!
    assert action.value == "HARD_STOP_EXIT"
    assert "Hard Stop-Loss breached" in reason


def test_bug_06_in_memory_daily_loss_reset_on_restart():
    """BUG-06: AutonomousTradingDaemon tracks daily loss via self._day_start_equity.

    On process crash/restart, _day_start_equity is reinitialized to current equity,
    resetting daily_realized_loss to 0.0 and rendering the daily loss limit ineffective.
    """
    total_capital = 10.0
    engine = DeterministicRiskEngine(
        total_equity=total_capital,
        current_daily_realized_loss=0.0,
        peak_equity=total_capital,
    )

    capital_after_loss = 8.0
    engine.daily_realized_loss = 10.0 - capital_after_loss
    assert engine.daily_realized_loss == 2.0

    dummy_decision = TradeDecision(
        analysis_id="TEST-01",
        symbol="ETHUSD",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.8,
        entry_price=2400.0,
        stop_loss=2380.0,
        target_1=2450.0,
        expected_risk_reward=2.5,
    )
    res = engine.evaluate_trade_intent(dummy_decision, open_positions=[])
    assert not res.approved
    assert any("Daily Loss Limit hit" in r for r in res.rejection_reasons)

    # SIMULATE PROCESS RESTART:
    restarted_engine = DeterministicRiskEngine(
        total_equity=capital_after_loss,
        current_daily_realized_loss=0.0,  # Reset to 0!
        peak_equity=capital_after_loss,
    )
    res_restarted = restarted_engine.evaluate_trade_intent(dummy_decision, open_positions=[])

    # BUG PROOF: After restart, the daily loss limit is completely bypassed!
    assert res_restarted.approved is True, "Circuit breaker was bypassed by process restart!"


def test_bug_07_chart_profit_taker_premature_exit():
    """BUG-07: ChartProfitTaker triggers CHART_PROFIT_TAKE on forming 5m candle

    upper-wick rejection when position is up only +0.30%, snipping winners before
    they can reach planned R:R targets.
    """
    data = {
        "open": [100.0, 100.2, 100.3, 100.5],
        "high": [100.3, 100.4, 100.6, 101.2],
        "low": [99.9, 100.1, 100.2, 100.4],
        "close": [100.2, 100.3, 100.5, 100.55],
        "volume": [1000, 1200, 1100, 1500],
    }
    df_5m = pd.DataFrame(data)

    should_exit, reason = ChartProfitTaker.evaluate_chart_profit_exit(
        df_5m=df_5m,
        entry_price=100.0,
        current_ltp=100.55,
        highest_price_seen=101.2,
    )

    # BUG PROOF: Triggers CHART_PROFIT_TAKE at 0.55% profit due to forming upper wick
    assert should_exit is True
    assert "Chart Exhaustion: Shooting Star" in reason
    assert "Taking profit (+0.55%)" in reason


@pytest.mark.asyncio
async def test_bug_04_exit_order_omitted_from_database():
    """BUG-04: MasterTradeGuardian.evaluate_all_guardians executes protective market exits

    via OrderRouter, but NEVER invokes TradeRepository.save_order, causing 100% of exit orders
    to be absent from the relational orders ledger.
    """
    from guardian.trade_guardian import MasterTradeGuardian
    from guardian.models import GuardianAction

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
    mock_broker.place_order = AsyncMock(return_value=MagicMock(status=OrderStatus.FILLED, filled_quantity=10, average_price=100.0, order_id="EXIT-123", client_order_id="GRD-EXT-1", symbol="ETHUSD", slippage=0.0, brokerage_fee=0.0, taxes_and_charges=0.0))

    worker = guardian.register_position(pos=pos)

    mock_provider = MagicMock()
    mock_provider.get_ltp = AsyncMock(return_value=100.0)

    # Patch TradeRepository.save_order to monitor if it gets called on exit
    with patch("database.repositories.trade_repo.TradeRepository.save_order") as mock_save_order:
        with patch("database.repositories.trade_repo.TradeRepository.save_journal", new_callable=AsyncMock):
            actions = await guardian.evaluate_all_guardians(provider=mock_provider, broker=mock_broker)
            
            # An exit was executed
            assert len(actions) == 1
            assert actions[0][1] == GuardianAction.HARD_STOP_EXIT

            # BUG RESOLUTION VERIFICATION: TradeRepository.save_order is now invoked for exit orders
            assert mock_save_order.call_count == 1, "Exit order must be persisted to TradeRepository!"


@pytest.mark.asyncio
async def test_bug_05_broker_exit_drops_journal():
    """BUG-05: When a position is closed directly on the exchange (e.g. by exchange bracket order),

    reconcile_with_broker merely deactivates the position, bypassing post-trade analytics and
    never persisting to trade_journal or treasury.
    """
    from guardian.trade_guardian import MasterTradeGuardian

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

    # Broker now reports 0 positions (bracket order filled on exchange)
    mock_broker = MagicMock()
    mock_broker.get_positions = AsyncMock(return_value=[])

    with patch("database.repositories.trade_repo.TradeRepository.save_journal") as mock_save_journal:
        report = await guardian.reconcile_with_broker(broker=mock_broker)

        # Worker is marked inactive
        assert worker.state.is_active is False
        assert any("closed on broker but active in AI state" in d for d in report.discrepancies)

        # BUG RESOLUTION VERIFICATION: Journal record is now created for exchange-closed trades
        assert mock_save_journal.call_count == 1, "Exchange-closed trade must be persisted to trade_journal!"



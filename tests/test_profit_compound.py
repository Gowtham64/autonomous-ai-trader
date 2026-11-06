import asyncio
from datetime import UTC, datetime

from core.schemas.trade import OrderIntent, PositionSnapshot, TradeAction
from execution.paper.delta_paper import DeltaPaperBroker
from guardian.position_guardian import PositionGuardianWorker
from risk.profit_math import expected_net_pnl


def test_small_uptick_does_not_add_cash():
    net = expected_net_pnl(entry=100.0, exit_mark=100.1, quantity=1, multiplier=1.0, is_short=False)
    assert net < 0


def test_two_percent_winner_adds_cash():
    net = expected_net_pnl(entry=100.0, exit_mark=102.0, quantity=1, multiplier=1.0, is_short=False)
    assert net > 0


def test_guardian_holds_a_target_that_does_not_clear_fees():
    pos = PositionSnapshot(
        position_id="POS-SOLUSD",
        symbol="SOLUSD",
        exchange="DELTA",
        side="BUY",
        quantity=1,
        entry_price=100.0,
        current_price=100.05,
        stop_loss=98.0,
        target_1=100.05,
        highest_price_seen=100.05,
        lowest_price_seen=100.0,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    action, _reason = asyncio.run(PositionGuardianWorker(pos=pos, atr_14=1.0).evaluate_tick(current_ltp=100.05))
    assert action.value != "TARGET_EXIT"


def test_guardian_banks_a_target_that_clears_fees():
    pos = PositionSnapshot(
        position_id="POS-SOLUSD",
        symbol="SOLUSD",
        exchange="DELTA",
        side="BUY",
        quantity=1,
        entry_price=100.0,
        current_price=103.0,
        stop_loss=98.0,
        target_1=103.0,
        highest_price_seen=103.0,
        lowest_price_seen=100.0,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )
    action, reason = asyncio.run(PositionGuardianWorker(pos=pos, atr_14=1.0).evaluate_tick(current_ltp=103.0))
    assert action.value == "TARGET_EXIT"
    assert "Profit Target" in reason


def test_winning_close_compounds_cash_and_keeps_the_original_stake():
    broker = DeltaPaperBroker(initial_capital=6.0, state_file=None)

    async def _run():
        opened = await broker.place_order(OrderIntent(
            client_order_id="open",
            symbol="BTCUSD",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=1,
            price=100.0,
            stop_loss=90.0,
            target=140.0,
            decision_id="open",
        ))
        assert opened.filled_quantity == 1
        closed = await broker.place_order(OrderIntent(
            client_order_id="close",
            symbol="BTCUSD",
            exchange="DELTA",
            action=TradeAction.SELL,
            quantity=1,
            price=140.0,
            stop_loss=0.0,
            target=0.0,
            reduce_only=True,
            decision_id="close",
        ))
        assert closed.filled_quantity == 1
        funds = await broker.get_funds()
        assert funds["starting_capital"] == 6.0
        assert funds["total_capital"] > 6.0
        assert funds["used_margin"] == 0.0

    asyncio.run(_run())

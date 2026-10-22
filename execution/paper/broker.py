import uuid
from datetime import UTC, datetime

from core.logging import logger
from core.schemas.trade import (
    OrderExecution,
    OrderIntent,
    OrderStatus,
    PositionSnapshot,
    TradeAction,
)
from execution.interface import BaseBroker


class PaperBroker(BaseBroker):
    """High-fidelity Paper Broker simulating slippage, STT, exchange fees, and GST for Indian equities."""

    def __init__(self, initial_capital: float = 500000.0, slippage_pct: float = 0.0005):
        self.initial_capital = initial_capital
        self.available_margin = initial_capital
        self.used_margin = 0.0
        self.slippage_pct = slippage_pct
        self.orders: dict[str, OrderExecution] = {}
        self.positions: dict[str, PositionSnapshot] = {}

    def _calculate_indian_charges(self, turnover: float) -> tuple[float, float]:
        """Calculates standard Indian Equity Delivery/Intraday transaction charges.
        STT: 0.1%, Brokerage: ₹20 or 0.03%, Exchange: 0.00345%, GST: 18% on brokerage+turnover, Stamp: 0.015%
        """
        brokerage = min(20.0, turnover * 0.0003)
        stt = turnover * 0.001
        exchange_turnover = turnover * 0.0000345
        gst = (brokerage + exchange_turnover) * 0.18
        stamp_duty = turnover * 0.00015
        total_taxes = stt + exchange_turnover + gst + stamp_duty
        return round(brokerage, 2), round(total_taxes, 2)

    async def get_funds(self) -> dict[str, float]:
        return {
            "total_capital": round(self.available_margin + self.used_margin, 2),
            "available_margin": round(self.available_margin, 2),
            "used_margin": round(self.used_margin, 2),
        }

    async def get_positions(self) -> list[PositionSnapshot]:
        return list(self.positions.values())

    async def place_order(self, order: OrderIntent) -> OrderExecution:
        logger.info(f"[PaperBroker] Receiving order for {order.symbol} (Qty: {order.quantity})")
        base_price = order.price if (order.price and order.price > 0) else order.stop_loss + abs(order.target - order.stop_loss) / 2

        # 1. Simulate Slippage (Slightly worse execution price)
        if order.action == TradeAction.BUY:
            executed_price = round(base_price * (1.0 + self.slippage_pct), 2)
        else:
            executed_price = round(base_price * (1.0 - self.slippage_pct), 2)

        order_value = executed_price * order.quantity
        brokerage, taxes = self._calculate_indian_charges(order_value)
        total_cost = order_value + brokerage + taxes

        if total_cost > self.available_margin and order.action == TradeAction.BUY:
            logger.warning(f"[PaperBroker] REJECTED: Insufficient funds (Needed ₹{total_cost:.2f}, Avail ₹{self.available_margin:.2f})")
            exec_report = OrderExecution(
                order_id=f"REJ-{uuid.uuid4().hex[:6].upper()}",
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                average_price=0.0,
            )
            return exec_report

        order_id = f"PAP-{uuid.uuid4().hex[:8].upper()}"
        exec_report = OrderExecution(
            order_id=order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_price=executed_price,
            slippage=round(abs(executed_price - base_price), 2),
            brokerage_fee=brokerage,
            taxes_and_charges=taxes,
            executed_at=datetime.now(UTC),
        )

        self.orders[order_id] = exec_report

        # Update Margin and Positions
        if order.action == TradeAction.BUY:
            self.available_margin -= total_cost
            self.used_margin += order_value

            pos_id = f"POS-{order.symbol}"
            self.positions[pos_id] = PositionSnapshot(
                position_id=pos_id,
                symbol=order.symbol,
                exchange=order.exchange,
                quantity=order.quantity,
                entry_price=executed_price,
                current_price=executed_price,
                stop_loss=order.stop_loss,
                target_1=order.target,
                highest_price_seen=executed_price,
                unrealized_pnl=0.0,
                opened_at=datetime.now(UTC),
                is_active=True,
            )
        elif order.action == TradeAction.SELL:
            pos_id = f"POS-{order.symbol}"
            if pos_id in self.positions:
                pos = self.positions[pos_id]
                realized = (executed_price - pos.entry_price) * order.quantity - (brokerage + taxes)
                pos.realized_pnl = round(realized, 2)
                pos.quantity -= order.quantity
                if pos.quantity <= 0:
                    pos.is_active = False
                    pos.quantity = 0
                self.available_margin += (executed_price * order.quantity) - (brokerage + taxes)
                self.used_margin = max(0.0, self.used_margin - (pos.entry_price * order.quantity))

        logger.info(f"[PaperBroker] FILLED {order.symbol} @ ₹{executed_price} (Order ID: {order_id})")
        return exec_report

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id in self.orders:
            return self.orders[order_id].status
        return OrderStatus.REJECTED

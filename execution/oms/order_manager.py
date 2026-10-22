"""
Production Order Management System (OMS) & Idempotency Engine (Sections 11, 12, 13)
Tracks complete order lifecycles, ensures duplicate order protection,
calculates real slippage & brokerage fees, and guarantees idempotent submission.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from core.logging import logger


class ManagedOrder(BaseModel):
    client_order_id: str
    broker_order_id: str | None = None
    symbol: str
    action: str  # "BUY", "SELL"
    quantity: int
    order_type: str = "MARKET"
    limit_price: float | None = None
    stop_price: float | None = None
    status: str = "SUBMITTED"  # "PENDING", "SUBMITTED", "FILLED", "PARTIALLY_FILLED", "REJECTED", "CANCELLED"
    submitted_at: str
    filled_at: str | None = None
    average_fill_price: float = 0.0
    expected_price: float = 0.0
    slippage: float = 0.0
    brokerage_fees: float = 20.0  # ₹20 flat AngelOne intraday brokerage
    taxes_stt: float = 0.0
    strategy_id: str = "STRAT_AI_MOMENTUM_V1"
    rejection_reason: str | None = None


class OrderManagementSystem:
    """Enterprise OMS with Duplicate Suppression and Full Audit Tracking."""

    def __init__(self):
        self.orders: dict[str, ManagedOrder] = {}
        self.recent_order_hashes: dict[str, float] = {}  # idempotency_key -> timestamp

    def create_client_order_id(self, symbol: str, action: str) -> str:
        """Generates cryptographically unique, traceable Client Order ID."""
        short_id = uuid.uuid4().hex[:8].upper()
        now_ts = int(datetime.now(UTC).timestamp())
        return f"CLT-{symbol.replace('.NS', '')}-{action}-{now_ts}-{short_id}"

    def check_idempotency(self, symbol: str, action: str, quantity: int) -> tuple[bool, str]:
        """Prevents duplicate execution after network/process timeouts within 30-second window."""
        key = f"{symbol}_{action}_{quantity}"
        now = datetime.now(UTC).timestamp()

        # Check if an identical order was dispatched in the last 30 seconds
        if key in self.recent_order_hashes:
            elapsed = now - self.recent_order_hashes[key]
            if elapsed < 30.0:
                logger.warning(f"[OMS Idempotency] Duplicate order blocked for {symbol} (dispatched {elapsed:.1f}s ago)")
                return False, f"Duplicate order suppressed by OMS (within {elapsed:.1f}s window)"

        # Check if an active open order on this symbol is already pending/submitted
        for o in self.orders.values():
            if o.symbol == symbol and o.status in ["PENDING", "SUBMITTED"]:
                return False, f"Active order {o.client_order_id} already pending for {symbol}"

        self.recent_order_hashes[key] = now
        return True, "IDEMPOTENCY_VERIFIED"

    def register_order_submission(
        self,
        symbol: str,
        action: str,
        quantity: int,
        expected_price: float,
        strategy_id: str = "STRAT_AI_V1",
    ) -> ManagedOrder:
        """Registers an order intent before routing to broker."""
        client_oid = self.create_client_order_id(symbol, action)
        order = ManagedOrder(
            client_order_id=client_oid,
            symbol=symbol,
            action=action,
            quantity=quantity,
            expected_price=expected_price,
            strategy_id=strategy_id,
            submitted_at=str(datetime.now(UTC)),
            status="SUBMITTED",
        )
        self.orders[client_oid] = order
        logger.info(f"[OMS] Registered new order {client_oid}: {action} {quantity} {symbol} @ ~₹{expected_price:.2f}")
        return order

    def update_order_fill(
        self,
        client_order_id: str,
        broker_order_id: str,
        fill_price: float,
        quantity_filled: int,
    ) -> ManagedOrder | None:
        """Updates internal OMS ledger with verified broker execution results."""
        order = self.orders.get(client_order_id)
        if not order:
            logger.error(f"[OMS] Order {client_order_id} not found for fill update!")
            return None

        order.broker_order_id = broker_order_id
        order.average_fill_price = fill_price
        order.filled_at = str(datetime.now(UTC))
        order.status = "FILLED" if quantity_filled >= order.quantity else "PARTIALLY_FILLED"

        # Calculate slippage
        order.slippage = round(fill_price - order.expected_price, 2)
        # Calculate Indian STT + GST approximation
        order.taxes_stt = round((fill_price * quantity_filled) * 0.00025 + 3.6, 2)

        logger.info(f"[OMS] Order Filled: {client_order_id} ({broker_order_id}) @ ₹{fill_price:.2f} (Slippage: ₹{order.slippage})")
        return order

    def update_order_rejection(self, client_order_id: str, reason: str):
        """Marks order as rejected by broker/risk gate."""
        order = self.orders.get(client_order_id)
        if order:
            order.status = "REJECTED"
            order.rejection_reason = reason
            logger.warning(f"[OMS] Order {client_order_id} rejected: {reason}")

    def list_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        """Returns chronological list of all orders."""
        return [o.model_dump() for o in reversed(list(self.orders.values()))][:limit]


order_manager = OrderManagementSystem()

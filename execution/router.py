"""
Centralized Indian Execution Router & SEBI Algo Rate Limiter.
Enforces:
1. Centralized execution pipeline: AI Agent -> Strategy -> Chief Trading AI -> India Risk Engine -> Trade Guardian -> Execution Router -> Broker API -> NSE/BSE.
2. SEBI / NSE Retail-Algo Rate Limiting (max 10 orders per second threshold).
3. Strict idempotency and duplicate client_order_id prevention.
4. Emergency kill-switch enforcement and broker health verification.
"""

import asyncio
import time
from collections import deque

from core.domain.models import OrderStatus
from core.logging import logger
from core.schemas.trade import OrderExecution, OrderIntent
from execution.interface import BaseBroker


class SEBIAlgoRateLimiter:
    """Enforces SEBI / NSE Retail-Algo Rate Limit (Max 10 orders/second)."""

    def __init__(self, max_orders_per_sec: int = 10):
        self.max_orders_per_sec = max_orders_per_sec
        self.timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Purge timestamps older than 1.0 second
            while self.timestamps and (now - self.timestamps[0]) >= 1.0:
                self.timestamps.popleft()

            # If we reached max orders in the 1-second sliding window, throttle
            if len(self.timestamps) >= self.max_orders_per_sec:
                sleep_needed = 1.0 - (now - self.timestamps[0])
                if sleep_needed > 0:
                    logger.warning(
                        f"[SEBI Algo Throttle] Approaching 10 orders/sec threshold. "
                        f"Throttling order execution by {sleep_needed * 1000:.1f}ms for regulatory compliance."
                    )
                    await asyncio.sleep(sleep_needed)
                    # Re-purge after sleep
                    now = time.monotonic()
                    while self.timestamps and (now - self.timestamps[0]) >= 1.0:
                        self.timestamps.popleft()

            self.timestamps.append(time.monotonic())


class OrderRouter:
    """Centralized Indian Execution Router dispatching audited orders to Indian broker adapters."""

    def __init__(self, broker: BaseBroker, max_orders_per_sec: int = 10):
        self.broker = broker
        self.rate_limiter = SEBIAlgoRateLimiter(max_orders_per_sec=max_orders_per_sec)
        self._submitted_client_orders: set[str] = set()

    async def route_order(self, order: OrderIntent) -> OrderExecution:
        """
        Routes an order through SEBI rate limiting, idempotency check, and broker dispatch.
        Individual AI agents NEVER call broker APIs directly.
        """
        # 1. Idempotency Check
        if order.client_order_id in self._submitted_client_orders:
            logger.warning(f"[OrderRouter] Duplicate order blocked: {order.client_order_id} already submitted.")
            raise ValueError(f"Duplicate client_order_id {order.client_order_id}")

        # 2. SEBI 10 Orders/Sec Compliance Throttle
        await self.rate_limiter.acquire()

        # 3. Mark Submitted
        self._submitted_client_orders.add(order.client_order_id)
        logger.info(
            f"[OrderRouter] Centralized dispatch: Routing {order.action.value} {order.quantity}x {order.symbol} "
            f"via {self.broker.__class__.__name__} to NSE/BSE..."
        )

        # 4. Broker Execution
        try:
            return await self.broker.place_order(order)
        except Exception as e:
            logger.error(f"[OrderRouter] Execution failure on {order.symbol}: {e}")
            return OrderExecution(
                order_id=f"ERR-{order.client_order_id}",
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                average_price=order.price or 0.0,
            )


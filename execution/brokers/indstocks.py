from core.config.settings import TradingMode, settings
from core.logging import logger
from core.schemas.trade import OrderExecution, OrderIntent, OrderStatus, PositionSnapshot
from execution.interface import BaseBroker


class INDstocksBroker(BaseBroker):
    """Production INDstocks Broker Adapter for Indian Equities."""

    def __init__(self):
        if settings.TRADING_MODE == TradingMode.LIVE and not settings.LIVE_TRADING_ENABLED:
            raise PermissionError("Live trading is disabled! Set LIVE_TRADING_ENABLED=true to allow live orders.")

    async def get_funds(self) -> dict[str, float]:
        logger.info("[INDstocks API] Fetching funds (Live unconfigured)...")
        return {
            "total_capital": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
        }

    async def get_positions(self) -> list[PositionSnapshot]:
        logger.info("[INDstocks API] Querying positions...")
        return []

    async def place_order(self, order: OrderIntent) -> OrderExecution:
        logger.warning(f"[INDstocks API] Live integration unconfigured; rejecting order for {order.symbol}")
        return OrderExecution(
            order_id=f"REJ-IND-{order.client_order_id}",
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            status=OrderStatus.REJECTED,
            filled_quantity=0,
            average_price=order.price or 0.0,
        )

    async def cancel_order(self, order_id: str) -> bool:
        logger.info(f"[INDstocks API] Cancelling order {order_id}...")
        return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        return OrderStatus.FILLED

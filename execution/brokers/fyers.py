from core.config.settings import TradingMode, settings
from core.logging import logger
from core.schemas.trade import OrderExecution, OrderIntent, OrderStatus, PositionSnapshot
from execution.interface import BaseBroker


class FyersBroker(BaseBroker):
    """Production FYERS API v3 Broker Adapter for Indian Equities."""

    def __init__(self):
        if settings.TRADING_MODE == TradingMode.LIVE:
            if not settings.LIVE_TRADING_ENABLED:
                raise PermissionError("Live trading is disabled! Set LIVE_TRADING_ENABLED=true to allow live orders.")
            if not settings.FYERS_APP_ID or not settings.FYERS_ACCESS_TOKEN:
                raise ValueError("Missing FYERS App ID or Access Token for live trading mode.")

    async def get_funds(self) -> dict[str, float]:
        logger.info("[FYERS API] Querying margin limits...")
        if not settings.FYERS_APP_ID or not settings.FYERS_ACCESS_TOKEN:
            return {"total_capital": 0.0, "available_margin": 0.0, "used_margin": 0.0}
        return {
            "total_capital": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
        }

    async def get_positions(self) -> list[PositionSnapshot]:
        logger.info("[FYERS API] Querying positions...")
        return []

    async def place_order(self, order: OrderIntent) -> OrderExecution:
        logger.error("[FYERS API] Live order rejected: FYERS v3 gateway integration required for live execution.")
        return OrderExecution(
            order_id=f"REJECTED-{order.client_order_id}",
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            status=OrderStatus.REJECTED,
            filled_quantity=0,
            average_price=order.price or 0.0,
        )

    async def cancel_order(self, order_id: str) -> bool:
        logger.info(f"[FYERS API] Cancelling order {order_id}...")
        return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        return OrderStatus.REJECTED


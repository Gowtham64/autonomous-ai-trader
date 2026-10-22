from core.config.settings import TradingMode, settings
from core.logging import logger
from core.schemas.trade import OrderExecution, OrderIntent, OrderStatus, PositionSnapshot
from execution.interface import BaseBroker


class ZerodhaBroker(BaseBroker):
    """Production Zerodha Kite Connect Adapter for Indian Equities.
    Protected by multiple production safety gates.
    """

    def __init__(self):
        self._verify_live_trading_gates()
        self.api_key = settings.ZERODHA_API_KEY
        self.access_token = settings.ZERODHA_ACCESS_TOKEN

    def _verify_live_trading_gates(self):
        if settings.TRADING_MODE == TradingMode.LIVE:
            if not settings.LIVE_TRADING_ENABLED:
                raise PermissionError("Live trading is disabled! Set LIVE_TRADING_ENABLED=true to allow live orders.")
            if not settings.ZERODHA_API_KEY or not settings.ZERODHA_ACCESS_TOKEN:
                raise ValueError("Missing Zerodha API Key or Access Token for live trading mode.")

    async def get_funds(self) -> dict[str, float]:
        self._verify_live_trading_gates()
        logger.info("[Zerodha Kite] Querying margins and available funds...")
        if not self.api_key or not self.access_token:
            return {"total_capital": 0.0, "available_margin": 0.0, "used_margin": 0.0}
        # Fail closed until live KiteConnect session is established
        return {
            "total_capital": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
        }

    async def get_positions(self) -> list[PositionSnapshot]:
        self._verify_live_trading_gates()
        logger.info("[Zerodha Kite] Querying active net positions...")
        return []

    async def place_order(self, order: OrderIntent) -> OrderExecution:
        self._verify_live_trading_gates()
        logger.error("[Zerodha Kite] Live order rejected: Kite Connect API gateway integration required for live execution.")
        return OrderExecution(
            order_id=f"REJECTED-{order.client_order_id}",
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            status=OrderStatus.REJECTED,
            filled_quantity=0,
            average_price=order.price or 0.0,
        )

    async def cancel_order(self, order_id: str) -> bool:
        self._verify_live_trading_gates()
        logger.info(f"[Zerodha Kite] Cancelling order {order_id}...")
        return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        self._verify_live_trading_gates()
        return OrderStatus.REJECTED


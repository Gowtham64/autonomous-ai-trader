from datetime import UTC, datetime

from core.config.settings import TradingMode, settings
from core.domain.models import TradeAction
from core.logging import logger
from core.schemas.trade import OrderIntent
from market.calendar import IndianMarketCalendar


class SafetyChecker:
    """Immutable final gate before order execution. Performs zero-trust sanity checks."""

    @staticmethod
    def verify_order(
        order: OrderIntent,
        current_ltp: float,
        bid_price: float | None = None,
        ask_price: float | None = None,
        bid_volume: float | None = None,
        ask_volume: float | None = None,
        data_timestamp: datetime | None = None,
    ) -> tuple[bool, str]:
        logger.info(f"SafetyChecker validating order {order.client_order_id} for {order.symbol}")

        # 1. Check positive quantity
        if order.quantity <= 0:
            return False, "Order quantity must be strictly greater than 0."

        # 2. Check stale market data (> 60 seconds old during live session)
        if data_timestamp is not None:
            if data_timestamp.tzinfo is None:
                data_timestamp = data_timestamp.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - data_timestamp).total_seconds()
            if age > 60.0 and settings.TRADING_MODE == TradingMode.LIVE:
                return False, f"Market data is stale ({age:.1f}s old > 60s limit)."

        # 3. Check abnormal price slippage / deviation from current LTP
        if order.price is not None and order.price > 0:
            dev = abs(order.price - current_ltp) / current_ltp
            if dev > settings.MAX_SLIPPAGE_PCT:
                return False, f"Order price ₹{order.price} deviates {dev*100:.2f}% from LTP ₹{current_ltp} (> {settings.MAX_SLIPPAGE_PCT*100}% allowable)."

        # 4. Check Bid-Ask spread if depth available
        if bid_price is not None and ask_price is not None and ask_price > 0:
            spread = (ask_price - bid_price) / ask_price
            if spread > settings.MAX_SPREAD_PCT:
                return False, f"Bid-Ask spread {spread*100:.2f}% exceeds maximum allowable {settings.MAX_SPREAD_PCT*100}%."

        # 4.5. AstraQuant Order Book Imbalance (OBI) & Supply Wall Defense
        if bid_volume is not None and ask_volume is not None and (bid_volume + ask_volume) > 0:
            obi = (bid_volume - ask_volume) / (bid_volume + ask_volume)
            if order.action == TradeAction.BUY and obi < -0.40:
                return False, (
                    f"AstraQuant OBI Gate: Severe overhead supply wall detected "
                    f"(OBI: {obi:.2f}, Ask Depth: {ask_volume:,.0f} vs Bid Depth: {bid_volume:,.0f}). "
                    f"Bull trap vetoed."
                )
            elif order.action == TradeAction.SELL and obi > 0.40:
                return False, (
                    f"AstraQuant OBI Gate: Severe demand absorption cushion detected "
                    f"(OBI: {obi:.2f}, Bid Depth: {bid_volume:,.0f} vs Ask Depth: {ask_volume:,.0f}). "
                    f"Bear trap vetoed."
                )

        # 5. Check Market Status for LIVE trading (Exempt 24/7 Crypto exchanges like DELTA)
        is_crypto_order = (
            (order.exchange and order.exchange.upper() in ["DELTA", "CRYPTO", "BINANCE", "BYBIT"])
            or ("USD" in order.symbol.upper())
            or (settings.BROKER_NAME and settings.BROKER_NAME.lower() in ["delta", "delta_exchange"])
        )
        if not is_crypto_order and settings.TRADING_MODE == TradingMode.LIVE and not IndianMarketCalendar.is_market_open():
            return False, "NSE/BSE Market is currently closed."

        return True, "Safety validation passed."

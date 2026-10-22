from core.config.settings import TradingMode, settings
from core.logging import logger
from execution.brokers.angelone import AngelOneBroker
from execution.brokers.delta_exchange import DeltaExchangeBroker
from execution.brokers.fyers import FyersBroker
from execution.brokers.zerodha import ZerodhaBroker
from execution.interface import BaseBroker
from execution.paper.broker import PaperBroker

_cached_brokers: dict[str, BaseBroker] = {}


def get_active_broker(broker_name: str | None = None) -> BaseBroker:
    """Instantiates or returns the cached singleton production or paper broker adapter."""
    if settings.TRADING_MODE == TradingMode.PAPER:
        if "paper" not in _cached_brokers:
            logger.info(f"[Broker Factory] Using PaperBroker with ₹{settings.INITIAL_CAPITAL:.2f} bootstrap capital.")
            _cached_brokers["paper"] = PaperBroker(initial_capital=settings.INITIAL_CAPITAL)
        return _cached_brokers["paper"]

    resolved_name = (broker_name or settings.BROKER_NAME or "angelone").lower()
    if resolved_name in _cached_brokers:
        return _cached_brokers[resolved_name]

    logger.info(f"[Broker Factory] Initializing Live Broker Adapter: '{resolved_name.upper()}' (Live Trading Mode)")
    if resolved_name == "angelone":
        broker = AngelOneBroker()
    elif resolved_name == "zerodha":
        broker = ZerodhaBroker()
    elif resolved_name == "fyers":
        broker = FyersBroker()
    elif resolved_name in ["delta", "delta_exchange"]:
        broker = DeltaExchangeBroker()
    else:
        logger.warning(f"[Broker Factory] Unknown broker '{resolved_name}'. Falling back to AngelOne.")
        broker = AngelOneBroker()

    _cached_brokers[resolved_name] = broker
    return broker

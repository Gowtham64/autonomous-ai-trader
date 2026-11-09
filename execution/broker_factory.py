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
    is_delta = (
        (settings.EXCHANGE or "").lower() in ["delta", "crypto"]
        or (settings.BROKER_NAME or "").lower() in ["delta", "delta_exchange"]
    )
    default_name = "delta" if is_delta else (settings.BROKER_NAME or "angelone")
    resolved_name = (broker_name or default_name).lower()
    if is_delta and resolved_name in ["nse", "angelone", "bootstrap"]:
        resolved_name = "delta"

    if not settings.LIVE_TRADING_ENABLED or settings.TRADING_MODE == TradingMode.PAPER:
        cache_key = f"paper_{resolved_name}"
        if cache_key not in _cached_brokers:
            if resolved_name in ["delta", "delta_exchange"]:
                from execution.paper.delta_paper import DeltaPaperBroker
                paper_cap = float(settings.INITIAL_CAPITAL) if settings.INITIAL_CAPITAL < 100.0 else 10.0
                logger.info(f"[Broker Factory] Using DeltaPaperBroker for isolated crypto paper trading (${paper_cap:.2f} USD).")
                _cached_brokers[cache_key] = DeltaPaperBroker(initial_capital=paper_cap)
            else:
                logger.info(f"[Broker Factory] Using PaperBroker with ₹{settings.INITIAL_CAPITAL:.2f} bootstrap capital.")
                _cached_brokers[cache_key] = PaperBroker(initial_capital=settings.INITIAL_CAPITAL)
        return _cached_brokers[cache_key]
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

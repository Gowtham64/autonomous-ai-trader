import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.logging import logger


class SystemEventType(str, Enum):
    PRICE_MOVEMENT = "PRICE_MOVEMENT"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    NEWS_EVENT = "NEWS_EVENT"
    EARNINGS_EVENT = "EARNINGS_EVENT"
    RISK_LIMIT_REACHED = "RISK_LIMIT_REACHED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    POSITION_CHANGED = "POSITION_CHANGED"
    MARKET_REGIME_CHANGED = "MARKET_REGIME_CHANGED"
    STRATEGY_FAILURE = "STRATEGY_FAILURE"
    AGENT_FAILURE = "AGENT_FAILURE"
    NEW_AGENT_CREATED = "NEW_AGENT_CREATED"
    MEMORY_UPDATED = "MEMORY_UPDATED"
    TREASURY_WARNING = "TREASURY_WARNING"
    PREMARKET_REPORT_READY = "PREMARKET_REPORT_READY"
    AGENTS_ARMED = "AGENTS_ARMED"



class SystemEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    event_type: SystemEventType
    source: str
    symbol: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RealtimeEventBus:
    """Centralized Real-Time Event Bus for Connected AI Organization (Sections 51–52).
    
    Routes events to relevant agents only, avoiding unnecessary LLM token consumption.
    """

    def __init__(self):
        self.subscribers: dict[SystemEventType, list[Callable[[SystemEvent], None]]] = {
            t: [] for t in SystemEventType
        }
        self.event_log: list[SystemEvent] = []

    def subscribe(self, event_type: SystemEventType, handler: Callable[[SystemEvent], None]) -> None:
        """Subscribes an agent handler to a specific event type."""
        self.subscribers[event_type].append(handler)

    def publish_event(
        self,
        event_type: SystemEventType,
        source: str,
        payload: dict[str, Any],
        symbol: str | None = None,
    ) -> SystemEvent:
        """Publishes an event and triggers registered handlers."""
        event = SystemEvent(
            event_type=event_type,
            source=source,
            symbol=symbol,
            payload=payload,
        )
        self.event_log.append(event)
        logger.info(f"[Event Bus] [{event.event_type.value}] from '{source}' (Symbol: {symbol})")

        # Notify registered subscribers
        handlers = self.subscribers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"[Event Bus] Handler error on {event_type}: {e}")

        return event

    def get_recent_events(self, limit: int = 20) -> list[dict]:
        return [e.model_dump() for e in self.event_log[-limit:]]


# Global Event Bus singleton
realtime_event_bus = RealtimeEventBus()

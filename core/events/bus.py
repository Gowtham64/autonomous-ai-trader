import asyncio
from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    """Decoupled in-memory asynchronous Event Bus for system-wide event broadcasting."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable[[Any], asyncio.Future]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, data: Any) -> None:
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(asyncio.create_task(handler(data)))
            else:
                handler(data)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Global event bus singleton
bus = EventBus()

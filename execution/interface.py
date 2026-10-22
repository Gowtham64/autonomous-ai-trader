from abc import ABC, abstractmethod

from core.schemas.trade import OrderExecution, OrderIntent, OrderStatus, PositionSnapshot


class BaseBroker(ABC):
    """Abstract base broker interface for Paper and Live Indian market brokers."""

    @abstractmethod
    async def get_funds(self) -> dict[str, float]:
        """Returns available margin, used margin, and total account balance."""

    @abstractmethod
    async def get_positions(self) -> list[PositionSnapshot]:
        """Returns all open and active positions."""

    @abstractmethod
    async def place_order(self, order: OrderIntent) -> OrderExecution:
        """Submits an order and returns an execution report."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancels an existing pending or open order."""

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Checks the current status of an order."""

    async def get_order_book(self) -> list[dict]:
        """Returns the list of placed/pending/filled orders from broker."""
        return []

    async def get_trade_book(self) -> list[dict]:
        """Returns the list of executed trades from broker."""
        return []


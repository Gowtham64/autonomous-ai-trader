from datetime import UTC, datetime

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    entry_id: str
    symbol: str
    regime: str
    action_taken: str
    outcome_pnl: float
    key_lesson: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TradeMemoryStore:
    """Episodic trade memory and reflection storage for contextual analysis."""

    def __init__(self):
        self._memories: list[MemoryEntry] = []

    def record_experience(
        self,
        symbol: str,
        regime: str,
        action: str,
        pnl: float,
        lesson: str,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            entry_id=f"MEM-{len(self._memories)+1}",
            symbol=symbol,
            regime=regime,
            action_taken=action,
            outcome_pnl=pnl,
            key_lesson=lesson,
        )
        self._memories.append(entry)
        return entry

    def retrieve_similar_contexts(self, symbol: str, regime: str) -> list[MemoryEntry]:
        """Retrieves past lessons for the same symbol or market regime."""
        return [
            m for m in self._memories
            if m.symbol == symbol or m.regime == regime
        ]

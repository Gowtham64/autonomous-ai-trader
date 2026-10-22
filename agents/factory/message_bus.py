from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.logging import logger


class MessagePriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL_VETO = "CRITICAL_VETO"


class AgentMessage(BaseModel):
    message_id: str
    sender_agent: str
    recipient_agent: str  # specific agent name or "BROADCAST" or "CHIEF_TRADING_AGENT"
    priority: MessagePriority = MessagePriority.NORMAL
    subject: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentVote(BaseModel):
    agent_name: str
    stance: str  # "BUY", "SELL", "HOLD", "VETO_REJECT"
    confidence: float
    rationale: str


class AgentMessageBus:
    """Inter-Agent Hierarchical Message Bus & Voting System.
    
    Routes intelligence messages through the organization's chain of command
    and tallies multi-agent votes on candidate trading setups.
    """

    def __init__(self):
        self.message_history: list[AgentMessage] = []
        self.active_voting_sessions: dict[str, list[AgentVote]] = {}

    def publish_message(
        self,
        sender_agent: str,
        recipient_agent: str,
        subject: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        """Publishes an inter-agent message to the organizational bus."""
        msg = AgentMessage(
            message_id=f"MSG-{len(self.message_history) + 1:04d}",
            sender_agent=sender_agent,
            recipient_agent=recipient_agent,
            priority=priority,
            subject=subject,
            payload=payload,
        )
        self.message_history.append(msg)
        logger.info(f"[Message Bus] [{msg.priority.value}] {sender_agent} ➔ {recipient_agent}: {subject}")
        return msg

    def register_vote(
        self,
        symbol: str,
        agent_name: str,
        stance: str,
        confidence: float,
        rationale: str,
    ) -> None:
        """Registers an agent vote for a candidate symbol opportunity."""
        if symbol not in self.active_voting_sessions:
            self.active_voting_sessions[symbol] = []

        vote = AgentVote(
            agent_name=agent_name,
            stance=stance.upper(),
            confidence=confidence,
            rationale=rationale,
        )
        self.active_voting_sessions[symbol].append(vote)
        logger.info(f"[Voting Hub] {agent_name} voted '{vote.stance}' ({confidence:.2f}) on {symbol}: {rationale}")

    def get_voting_consensus(self, symbol: str) -> dict:
        """Computes consensus score, tallies votes, and checks for Risk Agent vetoes."""
        votes = self.active_voting_sessions.get(symbol, [])
        if not votes:
            return {"symbol": symbol, "consensus_score": 0.0, "total_votes": 0, "veto_triggered": False}

        veto = any(v.stance == "VETO_REJECT" for v in votes)
        buy_votes = sum(1 for v in votes if v.stance == "BUY")
        sell_votes = sum(1 for v in votes if v.stance == "SELL")
        total = len(votes)

        consensus = (buy_votes - sell_votes) / max(1, total) if not veto else -1.0

        return {
            "symbol": symbol,
            "total_votes": total,
            "buy_votes": buy_votes,
            "sell_votes": sell_votes,
            "consensus_score": round(consensus, 2),
            "veto_triggered": veto,
            "votes_detail": [v.model_dump() for v in votes],
        }

    def get_recent_messages(self, limit: int = 15) -> list[dict]:
        return [m.model_dump() for m in self.message_history[-limit:]]


# Global Message Bus
agent_message_bus = AgentMessageBus()

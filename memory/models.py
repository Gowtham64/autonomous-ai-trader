import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class MemoryLevel(str, Enum):
    PRIVATE = "PRIVATE"                  # Level 1: Private Agent Memory
    ORGANIZATIONAL = "ORGANIZATIONAL"    # Level 2: Shared Organizational Memory
    LONG_TERM = "LONG_TERM"              # Level 3: Permanent Knowledge Memory


class MemoryType(str, Enum):
    EPISODIC = "EPISODIC"                # Specific event occurrence
    SEMANTIC = "SEMANTIC"                # Learned facts & concepts
    PROCEDURAL = "PROCEDURAL"            # How-to execution rules
    STRATEGIC = "STRATEGIC"              # High-level strategic wisdom
    AGENT = "AGENT"                      # Individual agent experience
    PORTFOLIO = "PORTFOLIO"              # Portfolio-level history
    ORGANIZATIONAL = "ORGANIZATIONAL"    # Cross-firm collective intelligence


class QualityCategory(str, Enum):
    FACT = "FACT"
    OBSERVATION = "OBSERVATION"
    PREDICTION = "PREDICTION"
    OPINION = "OPINION"
    HYPOTHESIS = "HYPOTHESIS"
    LESSON = "LESSON"


class MemoryImportance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    SUPERSEDED = "SUPERSEDED"


class MemoryRecord(BaseModel):
    """Unified memory record for individual agents, shared organization, and permanent knowledge."""
    memory_id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:8]}")
    created_by: str                       # e.g. "technical_agent", "risk_agent"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    level: MemoryLevel = MemoryLevel.ORGANIZATIONAL
    memory_type: MemoryType = MemoryType.EPISODIC
    category: QualityCategory = QualityCategory.OBSERVATION
    symbol: str | None = None
    sector: str | None = None
    strategy: str | None = None
    content: str
    confidence: float = 0.80
    source: str = "market_data"           # "market_data", "debate", "trade_outcome", "user_rule"
    importance: MemoryImportance = MemoryImportance.MEDIUM
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    evidence: list[str] = Field(default_factory=list)
    version: str = "v1.0"
    version_history: list[dict] = Field(default_factory=list)
    expires_at: datetime | None = None  # None for permanent/long-term memory
    decay_score: float = 1.0              # Starts at 1.0, decays over time
    access_roles: list[str] = Field(default_factory=lambda: ["ALL"])

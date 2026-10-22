"""
AI Agent Skills Framework — Data Models & Schemas
Implements structured Skill Definitions, Permissions, Risk Levels, Metrics, and Agent Compositions.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    MARKET = "market"
    SCANNER = "scanner"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    REGIME = "regime"
    STRATEGY = "strategy"
    BACKTESTING = "backtesting"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    TRADING = "trading"
    EXECUTION_QUALITY = "execution_quality"
    MEMORY = "memory"
    COMMUNICATION = "communication"
    RESEARCH = "research"
    DIAGNOSTICS = "diagnostics"
    FINANCE = "finance"
    AI_OPTIMIZATION = "ai_optimization"
    SYSTEM_UPGRADE = "system_upgrade"
    CUSTOM = "custom"


class SkillRiskLevel(int, Enum):
    LEVEL_0_INFO = 0           # Information retrieval (Quotes, OHLC, Breadth)
    LEVEL_1_ANALYSIS = 1       # Indicator computation & analytics (RSI, SMA, PE)
    LEVEL_2_RECOMMENDATION = 2 # Signal & candidate generation (Breakout, Scanner)
    LEVEL_3_SIMULATION = 3     # Backtesting, Monte Carlo, Paper execution
    LEVEL_4_FINANCIAL = 4      # Live Order Routing & Capital allocation
    LEVEL_5_CRITICAL = 5       # Emergency Kill Switch, Broker Auth, System Upgrade


class SkillPermission(str, Enum):
    READ = "market_data.read"
    ANALYZE = "analysis.compute"
    GENERATE = "signal.generate"
    COMMUNICATE = "agent.communicate"
    MODIFY = "portfolio.modify"
    EXECUTE = "broker.trade"
    FINANCIAL = "treasury.allocate"
    ADMIN = "system.admin"


class SkillSharingScope(str, Enum):
    PRIVATE = "PRIVATE"
    TEAM = "TEAM"
    ORGANIZATION = "ORGANIZATION"
    SYSTEM = "SYSTEM"


class SkillStatus(str, Enum):
    ACTIVE = "active"
    TESTING = "testing"
    DEPRECATED = "deprecated"
    SANDBOXED = "sandboxed"
    DISABLED = "disabled"


class SkillMetric(BaseModel):
    """Real-time performance and reliability metrics for a specific skill."""
    executions: int = 0
    successful: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    total_cost_inr: float = 0.0
    last_executed: datetime | None = None
    last_error: str | None = None
    success_rate_pct: float = 100.0


class SkillDefinition(BaseModel):
    """Canonical Skill Definition Schema."""
    skill_id: str = Field(..., description="Unique skill identifier, e.g., skill.market.stock_scanner.v1")
    name: str = Field(..., description="Human-readable skill name")
    version: str = Field(default="1.0.0", description="Semantic version string")
    category: SkillCategory = Field(..., description="Functional skill category")
    description: str = Field(..., description="Detailed description of skill purpose")

    inputs: list[str] = Field(default_factory=list, description="Expected input parameters")
    outputs: list[str] = Field(default_factory=list, description="Structured outputs produced")

    required_tools: list[str] = Field(default_factory=list, description="External APIs or data engines needed")
    required_permissions: list[SkillPermission] = Field(default_factory=list, description="Permission gates needed")

    risk_level: SkillRiskLevel = Field(default=SkillRiskLevel.LEVEL_1_ANALYSIS, description="Risk level (0 to 5)")
    can_trade: bool = Field(default=False, description="Whether this skill can directly route orders")

    memory_access: list[str] = Field(default_factory=list, description="Memory partitions accessed")
    dependencies: list[str] = Field(default_factory=list, description="Other skill IDs this skill relies upon")

    sharing_scope: SkillSharingScope = Field(default=SkillSharingScope.SYSTEM, description="Sharing visibility")
    status: SkillStatus = Field(default=SkillStatus.ACTIVE, description="Lifecycle status")

    metrics: SkillMetric = Field(default_factory=SkillMetric, description="Runtime execution telemetry")
    author: str = Field(default="System", description="Creator (User, System, or AI Agent)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillExecutionRequest(BaseModel):
    skill_id: str
    agent_id: str | None = "user_manual"
    parameters: dict[str, Any] = Field(default_factory=dict)
    enforce_permissions: bool = True


class SkillExecutionResult(BaseModel):
    skill_id: str
    agent_id: str
    status: str  # "SUCCESS" or "FAILED"
    data: Any
    latency_ms: float
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillProposalRequest(BaseModel):
    prompt: str = Field(..., description="Natural language description of the requested skill")
    suggested_category: SkillCategory | None = None
    author: str = "User"


class AgentSkillComposition(BaseModel):
    """The complete modular composition of an AI Agent: Identity + Role + Goal + Memory + Skills + Tools + Permissions + Risk."""
    agent_id: str
    name: str
    role: str
    goal: str
    personality_rules: list[str] = Field(default_factory=list)

    skill_ids: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    permissions: list[SkillPermission] = Field(default_factory=list)

    risk_level_limit: SkillRiskLevel = SkillRiskLevel.LEVEL_3_SIMULATION
    can_live_trade: bool = False

    private_memory_enabled: bool = True
    shared_memory_enabled: bool = True

    status: str = "ACTIVE"
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Department(str, Enum):
    RESEARCH = "Research"
    RISK = "Risk Office"
    TRADING = "Trading Office"
    PORTFOLIO = "Portfolio Management"
    EXECUTION = "Execution Desk"
    OPERATIONS = "Operations & Data"


class LifecycleStage(str, Enum):
    CREATED = "CREATED"
    CONFIGURED = "CONFIGURED"
    TESTING = "TESTING"
    SANDBOX = "SANDBOX"
    PAPER_TRADING = "PAPER_TRADING"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    MONITORED = "MONITORED"
    PAUSED = "PAUSED"
    RETIRED = "RETIRED"


class AgentPermissions(BaseModel):
    # Intelligence Permissions (Default Allowed)
    read_market_data: bool = True
    read_historical_data: bool = True
    run_technical_analysis: bool = True
    run_fundamental_analysis: bool = True
    search_news: bool = True
    run_backtest: bool = True
    generate_signals: bool = True

    # Action & Financial Permissions (DENY BY DEFAULT)
    paper_trade: bool = True
    place_live_orders: bool = False
    modify_orders: bool = False
    cancel_orders: bool = False
    modify_risk_limits: bool = False
    withdraw_money: bool = False
    create_sub_agents: bool = False
    delete_agents: bool = False


class AgentRiskLimits(BaseModel):
    max_trade_risk_pct: float = 0.5       # Max 0.5% risk per signal
    max_daily_loss_pct: float = 1.0       # Max 1.0% daily loss contribution
    max_position_size_inr: float = 500.0  # Max allocation per trade


class AgentResourceBudget(BaseModel):
    max_api_calls_per_day: int = 500
    daily_budget_inr: float = 5.0
    max_concurrent_tasks: int = 3
    max_tool_calls_per_hour: int = 50


class AgentCostCenter(BaseModel):
    total_api_calls: int = 0
    total_cost_inr: float = 0.0
    value_generated_inr: float = 0.0
    losses_prevented_inr: float = 0.0


class AgentPerformanceMetrics(BaseModel):
    tasks_completed: int = 0
    signals_generated: int = 0
    accurate_signals: int = 0
    false_signals: int = 0
    decisions_overturned: int = 0
    uptime_pct: float = 100.0


class CustomAgentProfile(BaseModel):
    agent_id: str
    name: str
    department: Department = Department.RESEARCH
    role: str = "Specialist"
    objective: str = "Market Analysis"
    responsibilities: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=lambda: ["NSE_OHLCV", "YFINANCE_REALTIME"])
    functions: list[str] = Field(default_factory=list)
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    risk_limits: AgentRiskLimits = Field(default_factory=AgentRiskLimits)
    budget: AgentResourceBudget = Field(default_factory=AgentResourceBudget)
    cost_center: AgentCostCenter = Field(default_factory=AgentCostCenter)
    performance: AgentPerformanceMetrics = Field(default_factory=AgentPerformanceMetrics)
    status: LifecycleStage = LifecycleStage.SANDBOX
    version: str = "v1.0"
    is_core: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_active: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version_history: list[dict] = Field(default_factory=list)

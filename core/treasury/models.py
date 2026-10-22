import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class SustainabilityState(str, Enum):
    BOOTSTRAP = "BOOTSTRAP"              # State 1: ₹2,000 initial capital, extreme capital preservation
    LEARNING = "LEARNING"                # State 2: Strategy/Agent validation, restricted exposure
    VALIDATED = "VALIDATED"              # State 3: Demonstrating stable risk/reward under tests
    SELF_SUSTAINING = "SELF_SUSTAINING"  # State 4: Trading income covers all operating costs
    GROWTH = "GROWTH"                    # State 5: Surpluses fund expanded compute & trading capital


class LedgerCategory(str, Enum):
    TRADE_PNL = "TRADE_PNL"
    BROKER_FEE = "BROKER_FEE"
    DATA_FEED = "DATA_FEED"
    LLM_API_COST = "LLM_API_COST"
    CLOUD_COMPUTE = "CLOUD_COMPUTE"
    STORAGE_DB = "STORAGE_DB"
    AI_UPGRADE_EXPENSE = "AI_UPGRADE_EXPENSE"
    RESERVE_ALLOCATION = "RESERVE_ALLOCATION"
    CAPITAL_INJECTION = "CAPITAL_INJECTION"


class ModelCostTier(str, Enum):
    LOW_COST = "LOW_COST"          # Fast / lightweight models for simple parsing
    STANDARD = "STANDARD"          # Standard models for normal market analysis
    ADVANCED = "ADVANCED"          # Advanced reasoning models for deep research & debate
    MULTI_MODEL = "MULTI_MODEL"    # Critical decisions requiring multi-model consensus


class ProfitAllocationPolicy(BaseModel):
    operating_reserve_pct: float = 0.25   # 25% of net profit to operating reserve
    emergency_reserve_pct: float = 0.25   # 25% to emergency capital protection
    ai_upgrade_fund_pct: float = 0.20     # 20% to AI Upgrade Fund
    infrastructure_fund_pct: float = 0.10 # 10% to compute & data
    trading_reinvestment_pct: float = 0.20 # 20% reinvested into trading balance


class TreasuryBuckets(BaseModel):
    trading_capital: float = 2000.0       # Active bootstrap capital for trading
    operating_reserve: float = 0.0        # Buffer for daily LLM & compute burn
    infrastructure_reserve: float = 0.0   # Buffer for cloud & data feeds
    ai_upgrade_fund: float = 0.0          # Fund for testing/improving models & tools
    emergency_reserve: float = 0.0        # Hard reserve never touched for trading
    reinvestment_capital: float = 0.0     # Surplus trading profits ready for deployment


class LedgerEntry(BaseModel):
    transaction_id: str = Field(default_factory=lambda: f"tx_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    category: LedgerCategory
    amount: float
    source: str
    destination: str
    trading_pnl: float = 0.0
    operating_cost: float = 0.0
    balance_after: float
    description: str

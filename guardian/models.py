"""
AI Trade Guardian - Domain Models & Data Structures
Defines states, risk levels, guardian actions, broker reconciliation reports,
and post-trade analysis metrics for continuous position and capital protection.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class GuardianRiskLevel(str, Enum):
    LOW = "LOW"            # 🟢 Normal operating condition
    MEDIUM = "MEDIUM"      # 🟡 Warning / elevated volatility / near trailing SL
    HIGH = "HIGH"          # 🔴 Critical risk / thesis under stress / nearing max loss
    CRITICAL = "CRITICAL"  # 🚨 Emergency condition / hard stop breach / circuit freeze


class GuardianAction(str, Enum):
    HOLD = "HOLD"
    ADJUST_TRAILING_STOP = "ADJUST_TRAILING_STOP"
    REDUCE_EXPOSURE = "REDUCE_EXPOSURE"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"
    HARD_STOP_EXIT = "HARD_STOP_EXIT"
    TARGET_EXIT = "TARGET_EXIT"
    THESIS_INVALIDATION_EXIT = "THESIS_INVALIDATION_EXIT"
    STAGNATION_SCRATCH_EXIT = "STAGNATION_SCRATCH_EXIT"
    MIDDAY_PEAK_HARVEST = "MIDDAY_PEAK_HARVEST"
    CHART_PROFIT_TAKE = "CHART_PROFIT_TAKE"
    GLIDE_PATH_PROFIT_LOCK = "GLIDE_PATH_PROFIT_LOCK"
    EOD_SQUAREOFF = "EOD_SQUAREOFF"
    CIRCUIT_FREEZE = "CIRCUIT_FREEZE"


class EmergencyConditionType(str, Enum):
    PRICE_COLLAPSE = "PRICE_COLLAPSE"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    LIQUIDITY_DISAPPEARANCE = "LIQUIDITY_DISAPPEARANCE"
    ABNORMAL_SPREAD = "ABNORMAL_SPREAD"
    BROKER_OUTAGE = "BROKER_OUTAGE"
    MARKET_WIDE_CIRCUIT = "MARKET_WIDE_CIRCUIT"
    UNAUTHORIZED_EXPOSURE = "UNAUTHORIZED_EXPOSURE"


class PositionGuardianState(BaseModel):
    """Real-time live operational state of a single Position Guardian."""
    guardian_id: str
    symbol: str
    exchange: str = "NSE"
    side: str = "BUY"
    order_id: str
    decision_id: str
    entry_price: float
    current_price: float
    quantity: int
    position_value: float
    stop_loss: float
    original_stop_loss: float = 0.0
    target_1: float
    target_2: float | None = None

    @property
    def current_stop_loss(self) -> float:
        return self.stop_loss

    @property
    def current_action(self) -> str:
        return "HOLD"

    # High-Water Marks & Risk Calculations
    highest_price_seen: float
    lowest_price_seen: float
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    distance_to_stop_pct: float = 0.0
    distance_to_target_pct: float = 0.0

    # Multi-Factor Risk
    risk_level: GuardianRiskLevel = GuardianRiskLevel.LOW
    max_permitted_loss_inr: float = 20.0
    atr_14: float = 0.0
    relative_volume: float = 1.0
    spread_pct: float = 0.0
    slippage_estimated_pct: float = 0.001

    # Thesis & Invalidation Conditions
    strategy_name: str = "Momentum Breakout"
    trade_thesis: list[str] = Field(default_factory=list)
    invalidating_scenarios: list[str] = Field(default_factory=list)
    thesis_intact: bool = True
    invalidation_reason: str | None = None

    # Broker Sync
    broker_verified: bool = True
    broker_shares_matched: bool = True
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_sync_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True
    last_evaluation_time: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrokerReconciliationReport(BaseModel):
    """Detailed audit report comparing AI internal state against Broker Actual State."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    broker_connected: bool = True
    ai_open_positions_count: int = 0
    broker_open_positions_count: int = 0
    is_synchronized: bool = True
    discrepancies: list[str] = Field(default_factory=list)
    duplicate_orders_detected: list[str] = Field(default_factory=list)
    unmanaged_broker_positions: list[str] = Field(default_factory=list)
    remedial_action_taken: str = "NONE"

    @property
    def status(self) -> str:
        return "MATCHED" if self.is_synchronized else "MISMATCH"


class PostTradeQualityReport(BaseModel):
    """Comprehensive institutional post-trade execution and decision quality metrics."""
    trade_id: str
    symbol: str
    entry_price: float
    exit_price: float
    quantity: int
    realized_pnl: float
    realized_pnl_pct: float
    exit_reason: str

    # Excursion & Slippage Analysis
    max_favorable_excursion_pct: float = 0.0   # MFE: Maximum potential profit while open
    max_adverse_excursion_pct: float = 0.0     # MAE: Maximum drawdown experienced while open
    entry_slippage_pct: float = 0.0
    exit_slippage_pct: float = 0.0
    brokerage_and_fees: float = 0.0

    @property
    def slippage_cost(self) -> float:
        return round((self.entry_slippage_pct + self.exit_slippage_pct) * self.entry_price * self.quantity, 2)

    # Decision Evaluation
    planned_risk_reward: float = 1.5
    actual_risk_reward: float = 0.0
    thesis_accuracy_score: float = 1.0         # 0.0 to 1.0
    guardian_interventions_count: int = 0
    decision_vs_outcome_quadrant: str = "GOOD_DECISION_GOOD_OUTCOME"
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

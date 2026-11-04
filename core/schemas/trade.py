from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.domain.models import MarketRegime, OrderStatus, OrderType, TradeAction


class CandidateSignal(BaseModel):
    symbol: str
    exchange: str = "NSE"
    ltp: float
    volume: float
    avg_volume_20d: float
    relative_volume: float
    momentum_score: float
    atr_14: float
    regime: MarketRegime
    sector: str = "General"
    setup_direction: str = "LONG"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnalystReport(BaseModel):
    agent_name: str
    symbol: str
    stance: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_observations: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    suggested_entry: float | None = None
    suggested_stop: float | None = None
    suggested_target: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DebateTranscript(BaseModel):
    symbol: str
    bull_thesis: str
    bear_thesis: str
    bull_rebuttal: str
    bear_rebuttal: str
    facilitator_summary: str
    key_conflict_points: list[str] = Field(default_factory=list)
    invalidating_scenarios: list[str] = Field(default_factory=list)
    consensus_score: float = Field(ge=-1.0, le=1.0)  # -1 = Strong Bearish, +1 = Strong Bullish


class TradeDecision(BaseModel):
    analysis_id: str
    symbol: str
    exchange: str = "NSE"
    decision: TradeAction
    confidence: float = Field(ge=0.0, le=1.0)
    entry_price: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    expected_risk_reward: float | None = None
    thesis: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    opposing_evidence: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    strategy_version: str = "1.0.0"
    prompt_version: str = "1.0.0"
    model_version: str = "default"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RiskCheckResult(BaseModel):
    approved: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    max_allowable_quantity: int = 0
    calculated_risk_amount: float = 0.0
    capital_allocation: float = 0.0
    portfolio_exposure_after_trade: float = 0.0
    sector_exposure_after_trade: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderIntent(BaseModel):
    client_order_id: str
    symbol: str
    exchange: str = "NSE"
    action: TradeAction
    order_type: OrderType = OrderType.MARKET
    quantity: int = Field(gt=0)
    price: float | None = None
    trigger_price: float | None = None
    stop_loss: float
    target: float
    trailing_sl_step: float | None = None
    decision_id: str
    product_type: str = "INTRADAY"  # "INTRADAY" (MIS) or "DELIVERY" (CNC) for multi-day swing
    reduce_only: bool = False  # Exit-only order: must never open or increase a position
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderExecution(BaseModel):
    order_id: str
    client_order_id: str
    symbol: str
    status: OrderStatus
    filled_quantity: int
    average_price: float
    slippage: float = 0.0
    brokerage_fee: float = 0.0
    taxes_and_charges: float = 0.0
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PositionSnapshot(BaseModel):
    position_id: str
    symbol: str
    exchange: str = "NSE"
    side: str = "BUY"
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float | None = None
    highest_price_seen: float
    lowest_price_seen: float = 0.0
    unrealized_pnl: float
    realized_pnl: float = 0.0
    opened_at: datetime
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    thesis_invalidation_rules: list[str] = Field(default_factory=list)
    mark_price: float | None = None
    valuation_unreliable: bool = False
    is_active: bool = True

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from database.session import Base


class TradeDecisionEntity(Base):
    __tablename__ = "trade_decisions"

    analysis_id = Column(String, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    exchange = Column(String, default="NSE")
    decision = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_1 = Column(Float, nullable=True)
    expected_risk_reward = Column(Float, nullable=True)
    thesis_json = Column(Text, default="[]")
    supporting_evidence_json = Column(Text, default="[]")
    opposing_evidence_json = Column(Text, default="[]")
    invalidation_conditions_json = Column(Text, default="[]")
    strategy_version = Column(String, default="1.0.0")
    prompt_version = Column(String, default="1.0.0")
    model_version = Column(String, default="default")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class OrderEntity(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True, index=True)
    client_order_id = Column(String, unique=True, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False)
    status = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    average_price = Column(Float, nullable=False)
    slippage = Column(Float, default=0.0)
    brokerage_fee = Column(Float, default=0.0)
    taxes_and_charges = Column(Float, default=0.0)
    decision_id = Column(String, index=True, nullable=True)
    executed_at = Column(DateTime, default=lambda: datetime.now(UTC))


class PositionEntity(Base):
    __tablename__ = "positions"

    position_id = Column(String, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    exchange = Column(String, default="NSE")
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target_1 = Column(Float, nullable=False)
    highest_price_seen = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True, index=True)
    opened_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))


class TradeJournalEntity(Base):
    __tablename__ = "trade_journal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    exit_reason = Column(String, nullable=False)
    holding_period_seconds = Column(Float, default=0.0)
    market_regime = Column(String, default="UNKNOWN")
    reflection_notes = Column(Text, default="")
    logged_at = Column(DateTime, default=lambda: datetime.now(UTC))

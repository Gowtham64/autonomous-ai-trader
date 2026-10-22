from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from database.session import Base


class MarketDataEntity(Base):
    __tablename__ = "market_data_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True, nullable=False)
    exchange = Column(String, default="NSE", index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    adjusted_close = Column(Float, nullable=True)
    volume = Column(Float, nullable=False)
    relative_volume = Column(Float, default=1.0)
    vwap = Column(Float, nullable=True)
    twap = Column(Float, nullable=True)
    bid_price = Column(Float, nullable=True)
    ask_price = Column(Float, nullable=True)
    bid_ask_spread = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    free_float = Column(Float, nullable=True)
    shares_outstanding = Column(Float, nullable=True)
    turnover = Column(Float, nullable=True)
    circuit_limit_upper = Column(Float, nullable=True)
    circuit_limit_lower = Column(Float, nullable=True)
    is_trading_halted = Column(Boolean, default=False)
    corporate_action_flag = Column(String, nullable=True)


class TechnicalIndicatorEntity(Base):
    __tablename__ = "technical_indicator_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    # Trend
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    sma_200 = Column(Float, nullable=True)
    ema_20 = Column(Float, nullable=True)
    ema_50 = Column(Float, nullable=True)
    vwma_20 = Column(Float, nullable=True)
    macd_line = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    macd_hist = Column(Float, nullable=True)
    adx_14 = Column(Float, nullable=True)
    supertrend_direction = Column(Integer, default=1)
    supertrend_val = Column(Float, nullable=True)
    psar = Column(Float, nullable=True)
    # Momentum
    rsi_14 = Column(Float, nullable=True)
    stoch_k = Column(Float, nullable=True)
    stoch_d = Column(Float, nullable=True)
    cci_20 = Column(Float, nullable=True)
    roc_12 = Column(Float, nullable=True)
    williams_r = Column(Float, nullable=True)
    # Volatility
    atr_14 = Column(Float, nullable=True)
    historical_volatility = Column(Float, nullable=True)
    bb_upper = Column(Float, nullable=True)
    bb_middle = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    bb_bandwidth = Column(Float, nullable=True)
    keltner_upper = Column(Float, nullable=True)
    keltner_lower = Column(Float, nullable=True)
    # Volume
    obv = Column(Float, nullable=True)
    mfi_14 = Column(Float, nullable=True)
    cmf_20 = Column(Float, nullable=True)
    # Price Structure
    support_level = Column(Float, nullable=True)
    resistance_level = Column(Float, nullable=True)
    pivot_point = Column(Float, nullable=True)
    gap_detected = Column(String, nullable=True)


class FundamentalDataEntity(Base):
    __tablename__ = "fundamental_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True, nullable=False)
    as_of_date = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    revenue = Column(Float, nullable=True)
    ebitda = Column(Float, nullable=True)
    ebit = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)
    eps = Column(Float, nullable=True)
    gross_margin_pct = Column(Float, nullable=True)
    operating_margin_pct = Column(Float, nullable=True)
    net_margin_pct = Column(Float, nullable=True)
    free_cash_flow = Column(Float, nullable=True)
    operating_cash_flow = Column(Float, nullable=True)
    capex = Column(Float, nullable=True)
    total_assets = Column(Float, nullable=True)
    total_liabilities = Column(Float, nullable=True)
    total_equity = Column(Float, nullable=True)
    cash_and_equivalents = Column(Float, nullable=True)
    total_debt = Column(Float, nullable=True)
    current_ratio = Column(Float, nullable=True)
    quick_ratio = Column(Float, nullable=True)
    roe_pct = Column(Float, nullable=True)
    roa_pct = Column(Float, nullable=True)
    roic_pct = Column(Float, nullable=True)
    debt_to_equity = Column(Float, nullable=True)
    interest_coverage = Column(Float, nullable=True)
    pe_ratio = Column(Float, nullable=True)
    forward_pe = Column(Float, nullable=True)
    peg_ratio = Column(Float, nullable=True)
    pb_ratio = Column(Float, nullable=True)
    ps_ratio = Column(Float, nullable=True)
    ev_ebitda = Column(Float, nullable=True)
    dividend_yield_pct = Column(Float, nullable=True)
    revenue_growth_yoy = Column(Float, nullable=True)
    earnings_growth_yoy = Column(Float, nullable=True)


class DerivativesDataEntity(Base):
    __tablename__ = "derivatives_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    instrument_type = Column(String, default="OPTION")  # "OPTION" or "FUTURES"
    strike_price = Column(Float, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    option_type = Column(String, nullable=True)        # "CE" or "PE"
    underlying_price = Column(Float, nullable=False)
    option_premium = Column(Float, nullable=True)
    open_interest = Column(Float, nullable=True)
    change_in_oi = Column(Float, nullable=True)
    implied_volatility = Column(Float, nullable=True)
    iv_rank = Column(Float, nullable=True)
    iv_percentile = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    gamma = Column(Float, nullable=True)
    theta = Column(Float, nullable=True)
    vega = Column(Float, nullable=True)
    rho = Column(Float, nullable=True)
    put_call_ratio = Column(Float, nullable=True)
    max_pain_strike = Column(Float, nullable=True)
    dealer_gamma_exposure = Column(Float, nullable=True)
    futures_basis = Column(Float, nullable=True)
    futures_contango_backwardation = Column(String, nullable=True)


class OrderFlowDataEntity(Base):
    __tablename__ = "order_flow_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    buy_volume = Column(Float, default=0.0)
    sell_volume = Column(Float, default=0.0)
    aggressive_buy_volume = Column(Float, default=0.0)
    aggressive_sell_volume = Column(Float, default=0.0)
    volume_delta = Column(Float, default=0.0)
    cumulative_volume_delta = Column(Float, default=0.0)
    order_book_imbalance = Column(Float, default=0.0)
    bid_depth_total = Column(Float, default=0.0)
    ask_depth_total = Column(Float, default=0.0)
    block_deals_count = Column(Integer, default=0)
    sweep_orders_count = Column(Integer, default=0)
    market_impact_bps = Column(Float, default=0.0)


class MarketRegimeEntity(Base):
    __tablename__ = "market_regime_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    regime_name = Column(String, nullable=False)         # "BULL_TREND", "BEAR_TREND", "HIGH_VOLATILITY_SIDEWAYS", etc.
    trend_state = Column(String, default="BULLISH")
    volatility_state = Column(String, default="NORMAL")
    risk_state = Column(String, default="RISK_ON")
    india_vix = Column(Float, default=14.0)
    advance_decline_ratio = Column(Float, default=1.0)
    nifty50_breadth_pct = Column(Float, default=50.0)
    sector_rotation_lead = Column(String, default="IT")
    market_correlation_avg = Column(Float, default=0.45)


class SentimentDataEntity(Base):
    __tablename__ = "sentiment_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    source = Column(String, default="news")              # "news", "announcement", "social", "earnings"
    headline = Column(Text, nullable=False)
    sentiment_polarity = Column(Float, default=0.0)      # -1.0 to +1.0
    sentiment_class = Column(String, default="NEUTRAL")  # "BULLISH", "BEARISH", "NEUTRAL"
    classification_tag = Column(String, default="OBSERVATION") # "FACT", "PREDICTION", "OPINION", "RUMOR"
    confidence = Column(Float, default=0.80)
    event_detected = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)


class MacroDataEntity(Base):
    __tablename__ = "macro_economic_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    rbi_repo_rate = Column(Float, default=6.50)
    fed_funds_rate = Column(Float, default=5.25)
    cpi_inflation_yoy = Column(Float, default=5.1)
    gdp_growth_pct = Column(Float, default=7.2)
    manufacturing_pmi = Column(Float, default=58.5)
    india_10y_bond_yield = Column(Float, default=7.15)
    us_10y_bond_yield = Column(Float, default=4.20)
    usd_inr_exchange_rate = Column(Float, default=83.50)
    crude_oil_brent_usd = Column(Float, default=82.0)
    gold_usd_oz = Column(Float, default=2350.0)
    copper_usd_lb = Column(Float, default=4.40)


class IndianMarketEntity(Base):
    __tablename__ = "indian_market_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    nifty50_close = Column(Float, nullable=False)
    bank_nifty_close = Column(Float, nullable=False)
    nifty_it_close = Column(Float, nullable=True)
    india_vix_close = Column(Float, default=14.0)
    fii_net_flow_cr = Column(Float, default=0.0)
    dii_net_flow_cr = Column(Float, default=0.0)
    nifty_delivery_pct = Column(Float, default=48.5)
    fno_total_turnover_cr = Column(Float, default=0.0)
    advances_count = Column(Integer, default=25)
    declines_count = Column(Integer, default=25)


class PortfolioMetricEntity(Base):
    __tablename__ = "portfolio_metrics_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    total_capital = Column(Float, default=2000.0)
    available_cash = Column(Float, default=2000.0)
    invested_capital = Column(Float, default=0.0)
    gross_exposure = Column(Float, default=0.0)
    net_exposure = Column(Float, default=0.0)
    long_exposure_pct = Column(Float, default=0.0)
    short_exposure_pct = Column(Float, default=0.0)
    top_position_concentration_pct = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    daily_pnl = Column(Float, default=0.0)
    drawdown_pct = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    var_95_inr = Column(Float, default=0.0)
    expected_shortfall_inr = Column(Float, default=0.0)


class TradeMetricEntity(Base):
    __tablename__ = "trade_metrics_records"

    trade_id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, index=True, nullable=False)
    strategy_id = Column(String, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    gross_pnl = Column(Float, nullable=False)
    net_pnl = Column(Float, nullable=False)
    brokerage_commission = Column(Float, default=0.0)
    stt_and_taxes = Column(Float, default=0.0)
    slippage_bps = Column(Float, default=0.0)
    holding_seconds = Column(Float, default=0.0)
    max_favorable_excursion = Column(Float, default=0.0)
    max_adverse_excursion = Column(Float, default=0.0)
    planned_rr = Column(Float, default=2.0)
    actual_rr = Column(Float, default=2.0)
    market_regime = Column(String, default="UNKNOWN")
    entry_confidence = Column(Float, default=0.80)
    outcome_quadrant = Column(String, default="GOOD_DECISION_GOOD_OUTCOME")
    closed_at = Column(DateTime, default=lambda: datetime.now(UTC))


class RiskMetricEntity(Base):
    __tablename__ = "risk_metric_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    total_portfolio_risk_pct = Column(Float, default=0.5)
    max_single_trade_risk_pct = Column(Float, default=0.5)
    kelly_fraction = Column(Float, default=0.15)
    current_leverage = Column(Float, default=1.0)
    margin_utilization_pct = Column(Float, default=0.0)
    liquidity_risk_score = Column(Float, default=1.0)
    gap_risk_score = Column(Float, default=1.0)
    overnight_risk_score = Column(Float, default=1.0)
    counterparty_risk_score = Column(Float, default=1.0)


class ExecutionMetricEntity(Base):
    __tablename__ = "execution_metric_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    submission_latency_ms = Column(Float, default=12.0)
    broker_latency_ms = Column(Float, default=45.0)
    exchange_fill_latency_ms = Column(Float, default=15.0)
    fill_ratio_pct = Column(Float, default=100.0)
    slippage_inr = Column(Float, default=0.0)
    implementation_shortfall_bps = Column(Float, default=2.5)
    vwap_deviation_bps = Column(Float, default=1.2)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))


class AgentPerformanceEntity(Base):
    __tablename__ = "agent_performance_records"

    agent_id = Column(String, primary_key=True, index=True)
    agent_name = Column(String, nullable=False)
    department = Column(String, default="Research")
    total_signals = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate_pct = Column(Float, default=0.0)
    average_win_inr = Column(Float, default=0.0)
    average_loss_inr = Column(Float, default=0.0)
    profit_factor = Column(Float, default=1.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    prediction_accuracy_pct = Column(Float, default=0.0)
    calibration_score = Column(Float, default=0.85)
    losses_prevented_inr = Column(Float, default=0.0)
    total_operating_cost_inr = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))


class PredictionMetricEntity(Base):
    __tablename__ = "prediction_metric_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, index=True, nullable=False)
    task_type = Column(String, default="CLASSIFICATION") # "CLASSIFICATION" or "REGRESSION"
    accuracy = Column(Float, default=0.0)
    precision_score = Column(Float, default=0.0)
    recall_score = Column(Float, default=0.0)
    f1_score = Column(Float, default=0.0)
    roc_auc = Column(Float, default=0.0)
    mae = Column(Float, default=0.0)
    rmse = Column(Float, default=0.0)
    directional_accuracy_pct = Column(Float, default=0.0)
    hit_rate_pct = Column(Float, default=0.0)
    expected_value = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))


class BacktestMetricEntity(Base):
    __tablename__ = "backtest_metrics_records"

    backtest_id = Column(String, primary_key=True, index=True)
    strategy_name = Column(String, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    cagr_pct = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    annualized_return_pct = Column(Float, default=0.0)
    win_rate_pct = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    expectancy_per_trade = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    calmar_ratio = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    total_trades_count = Column(Integer, default=0)
    alpha = Column(Float, default=0.0)
    beta = Column(Float, default=1.0)
    walk_forward_stability_score = Column(Float, default=0.80)
    executed_at = Column(DateTime, default=lambda: datetime.now(UTC))


class DataQualityEntity(Base):
    __tablename__ = "data_quality_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_feed = Column(String, index=True, nullable=False) # "NSE_OHLCV", "YFINANCE", "ORDER_BOOK", "NEWS_FEED"
    freshness_latency_ms = Column(Float, default=0.0)
    missing_values_count = Column(Integer, default=0)
    duplicate_records_count = Column(Integer, default=0)
    timestamp_jitter_ms = Column(Float, default=0.0)
    price_anomalies_detected = Column(Integer, default=0)
    volume_anomalies_detected = Column(Integer, default=0)
    feed_failures_count = Column(Integer, default=0)
    quality_score = Column(Float, default=100.0)           # 0 to 100
    is_feed_healthy = Column(Boolean, default=True)
    checked_at = Column(DateTime, default=lambda: datetime.now(UTC))


class EconomicEventEntity(Base):
    __tablename__ = "economic_event_records"

    event_id = Column(String, primary_key=True, index=True)
    event_type = Column(String, index=True, nullable=False) # "EARNINGS", "RBI_RATE", "UNION_BUDGET", "DIVIDEND", "STOCK_SPLIT"
    symbol = Column(String, index=True, nullable=True)
    headline = Column(Text, nullable=False)
    impact_level = Column(String, default="HIGH")           # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    scheduled_at = Column(DateTime, nullable=False)
    actual_value = Column(String, nullable=True)
    forecast_value = Column(String, nullable=True)
    trading_restriction_enforced = Column(Boolean, default=False)

from enum import Enum


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL_M"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class MarketRegime(str, Enum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    SIDEWAYS_RANGING = "SIDEWAYS_RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    RISK_OFF_EXTREME = "RISK_OFF_EXTREME"


class TradingSessionState(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    PRE_FLIGHT = "PRE_FLIGHT"
    MARKET_OPEN = "MARKET_OPEN"
    SCANNING = "SCANNING"
    ANALYZING = "ANALYZING"
    DEBATING = "DEBATING"
    DECIDING = "DECIDING"
    RISK_GATING = "RISK_GATING"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"
    CLOSING = "CLOSING"
    REPORTING = "REPORTING"
    SESSION_END = "SESSION_END"


class IndianMarketSegment(str, Enum):
    NSE_CASH_EQUITY = "NSE_CASH_EQUITY"
    BSE_CASH_EQUITY = "BSE_CASH_EQUITY"
    NSE_EQUITY_FUTURES = "NSE_EQUITY_FUTURES"
    NSE_EQUITY_OPTIONS = "NSE_EQUITY_OPTIONS"
    NSE_INDEX_FUTURES = "NSE_INDEX_FUTURES"
    NSE_INDEX_OPTIONS = "NSE_INDEX_OPTIONS"
    NSE_CURRENCY_DERIVATIVES = "NSE_CURRENCY_DERIVATIVES"
    NSE_COMMODITY_DERIVATIVES = "NSE_COMMODITY_DERIVATIVES"
    BSE_EQUIVALENTS = "BSE_EQUIVALENTS"


class AgentDepartment(str, Enum):
    EXECUTIVE = "Executive"
    MARKET_INTELLIGENCE = "Market Intelligence"
    STRATEGY = "Strategy"
    EXECUTION = "Execution"
    RISK = "Risk"
    RESEARCH = "Research"
    INFRASTRUCTURE = "Infrastructure"


class AgentRole(str, Enum):
    # Executive
    AI_CEO = "ai_ceo"
    CIO = "cio"
    CTO = "cto"
    CFO_TREASURY = "cfo_treasury"
    CHIEF_RISK = "chief_risk"

    # Market Intelligence
    NSE_SCANNER = "nse_scanner"
    BSE_SCANNER = "bse_scanner"
    INDEX_SCANNER = "index_scanner"
    SECTOR_SCANNER = "sector_scanner"
    STOCK_SCANNER = "stock_scanner"
    TECHNICAL_ANALYSIS = "technical_analyst"
    FUNDAMENTAL_ANALYSIS = "fundamental_analyst"
    NEWS_AI = "news_analyst"
    SENTIMENT_AI = "sentiment_analyst"
    MACRO_AI = "macro_analyst"
    CORPORATE_ACTIONS_AI = "corporate_actions_ai"
    MARKET_REGIME_AI = "market_regime"
    VOLATILITY_AI = "volatility_ai"
    LIQUIDITY_AI = "liquidity_ai"

    # Strategy
    INTRADAY_STRATEGY = "intraday_strategy"
    SWING_STRATEGY = "swing_strategy"
    MOMENTUM_AI = "momentum_analyst"
    MEAN_REVERSION_AI = "mean_reversion_ai"
    BREAKOUT_AI = "breakout_ai"
    TREND_FOLLOWING_AI = "trend_following_ai"
    STATISTICAL_STRATEGY = "quant_research"
    OPTIONS_STRATEGY = "options_analyst"
    FUTURES_STRATEGY = "futures_strategy"
    BNF_MASTER = "bnf_master"
    JHUNJHUNWALA_MASTER = "jhunjhunwala_master"
    LIVERMORE_MASTER = "livermore_master"
    BULL_RESEARCHER = "bull_researcher"
    BEAR_RESEARCHER = "bear_researcher"
    DEBATE_FACILITATOR = "debate_facilitator"
    FUND_MANAGER = "fund_manager"

    # Execution
    ORDER_MANAGEMENT_AI = "order_management_ai"
    EXECUTION_AI = "execution_agent"
    SLIPPAGE_AI = "slippage_ai"
    BROKER_HEALTH_AI = "broker_agent"
    RECONCILIATION_AI = "reconciliation_ai"
    TRADE_GUARDIAN = "position_monitor"

    # Risk
    POSITION_RISK_AI = "position_risk_ai"
    PORTFOLIO_RISK_AI = "portfolio_manager"
    EXPOSURE_AI = "exposure_ai"
    DRAWDOWN_AI = "drawdown_ai"
    MARGIN_AI = "capital_manager"
    CONCENTRATION_AI = "concentration_ai"
    STOP_LOSS_GUARDIAN = "stop_loss_guardian"
    KILL_SWITCH_AI = "compliance_agent"
    RISK_MANAGER = "risk_manager"

    # Research
    BACKTESTING_AI = "backtest_agent"
    STRATEGY_RESEARCH_AI = "strategy_research_ai"
    DATA_QUALITY_AI = "data_quality_ai"
    EXPERIMENT_AI = "experiment_ai"
    MODEL_EVALUATION_AI = "model_evaluation_ai"

    # Infrastructure
    SYSTEM_ARCHITECT_AI = "system_architect_ai"
    DEVOPS_AI = "devops_ai"
    DATABASE_AI = "database_ai"
    MONITORING_AI = "system_monitoring"
    COST_OPTIMIZATION_AI = "cost_optimization_ai"
    SECURITY_AI = "security_ai"


class ExitReason(str, Enum):
    HARD_STOP_LOSS = "HARD_STOP_LOSS"
    TRAILING_STOP_LOSS = "TRAILING_STOP_LOSS"
    TARGET_1 = "TARGET_1"
    TARGET_2 = "TARGET_2"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    EOD_SAFETY = "EOD_SAFETY"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"

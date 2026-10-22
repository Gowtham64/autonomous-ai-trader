"""
16 Specialized Production AI Agents Roster (Section 7)
Defines clear roles, operational boundaries, and authority splits.
No individual AI agent has unrestricted authority to execute trades.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class AgentRole(str, Enum):
    MARKET_DATA = "MARKET_DATA_AGENT"
    MARKET_REGIME = "MARKET_REGIME_AGENT"
    TECHNICAL_ANALYSIS = "TECHNICAL_ANALYSIS_AGENT"
    FUNDAMENTAL_ANALYSIS = "FUNDAMENTAL_ANALYSIS_AGENT"
    NEWS_SENTIMENT = "NEWS_SENTIMENT_AGENT"
    QUANT_SIGNAL = "QUANT_SIGNAL_AGENT"
    STOCK_SCREENING = "STOCK_SCREENING_AGENT"
    PORTFOLIO = "PORTFOLIO_AGENT"
    RISK = "RISK_AGENT"
    ORDER = "ORDER_AGENT"
    EXECUTION = "EXECUTION_AGENT"
    CAPITAL_MANAGEMENT = "CAPITAL_MANAGEMENT_AGENT"
    COMPLIANCE = "COMPLIANCE_AGENT"
    MONITORING = "MONITORING_AGENT"
    INCIDENT_RECOVERY = "INCIDENT_RECOVERY_AGENT"
    PERFORMANCE_ANALYSIS = "PERFORMANCE_ANALYSIS_AGENT"


class SpecializedAgentSpec(BaseModel):
    agent_id: str
    name: str
    role: AgentRole
    department: str
    responsibilities: list[str]
    allowed_tools: list[str]
    can_execute_trades: bool = False
    has_veto_power: bool = False
    status: str = "ACTIVE"


SIXTEEN_PRODUCTION_AGENTS: list[SpecializedAgentSpec] = [
    SpecializedAgentSpec(
        agent_id="agt_market_data",
        name="Market Data Agent",
        role=AgentRole.MARKET_DATA,
        department="Market Intelligence",
        responsibilities=["Ingest live ticks & OHLCV", "Validate timestamp freshness", "Detect stale feeds & data gaps"],
        allowed_tools=["read_websocket_feed", "audit_data_freshness", "calculate_vwap"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_market_regime",
        name="Market Regime Agent",
        role=AgentRole.MARKET_REGIME,
        department="Macro & Economics",
        responsibilities=["Classify market state (Bull, Bear, Choppy, High Vol)", "Monitor India VIX & RBI Rates"],
        allowed_tools=["read_india_vix", "classify_regime", "check_macro_calendar"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_technical",
        name="Technical Analysis Agent",
        role=AgentRole.TECHNICAL_ANALYSIS,
        department="Quantitative Research",
        responsibilities=["Compute RSI, MACD, Supertrend, EMA 20/50/200", "Identify support/resistance & breakouts"],
        allowed_tools=["compute_technical_indicators", "detect_chart_patterns", "calculate_atr"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_fundamental",
        name="Fundamental Analysis Agent",
        role=AgentRole.FUNDAMENTAL_ANALYSIS,
        department="Fundamental Research",
        responsibilities=["Analyze P/E, P/B, Debt/Equity, ROCE, EPS growth", "Assess corporate governance & earnings"],
        allowed_tools=["fetch_quarterly_results", "calculate_fair_value", "check_fii_dii_holdings"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_news_sentiment",
        name="News & Sentiment Agent",
        role=AgentRole.NEWS_SENTIMENT,
        department="Market Intelligence",
        responsibilities=["Parse live NSE/BSE corporate filings & news", "Calculate sentiment polarity score"],
        allowed_tools=["fetch_rss_news", "extract_news_sentiment", "filter_fake_rumors"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_quant_signal",
        name="Quant Signal Agent",
        role=AgentRole.QUANT_SIGNAL,
        department="Quantitative Research",
        responsibilities=["Combine multi-factor momentum, mean reversion, and order flow into composite signal"],
        allowed_tools=["generate_composite_score", "run_quant_scoring", "detect_volume_climax"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_screener",
        name="Stock Screening Agent",
        role=AgentRole.STOCK_SCREENING,
        department="Market Intelligence",
        responsibilities=["Filter 2,000+ NSE stocks down to top candidates", "Enforce liquidity and volume filters"],
        allowed_tools=["scan_universe", "apply_liquidity_gate", "rank_candidates"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_portfolio",
        name="Portfolio Agent",
        role=AgentRole.PORTFOLIO,
        department="Portfolio Management",
        responsibilities=["Maintain target sector allocations", "Prevent over-concentration in single stock/sector"],
        allowed_tools=["check_sector_exposure", "calculate_portfolio_beta", "evaluate_correlation"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_risk",
        name="Risk Agent (Veto Authority)",
        role=AgentRole.RISK,
        department="Risk Office",
        responsibilities=["Enforce 14-Point Pre-Trade Audit Gate", "Verify 2% Daily Loss Circuit Breaker", "Has absolute VETO power"],
        allowed_tools=["audit_14_point_gate", "check_daily_drawdown", "enforce_hard_veto"],
        can_execute_trades=False,
        has_veto_power=True,
    ),
    SpecializedAgentSpec(
        agent_id="agt_order",
        name="Order Agent",
        role=AgentRole.ORDER,
        department="Trading Desk",
        responsibilities=["Structure compliant order requests", "Enforce ClientOrderID idempotency & duplicate checks"],
        allowed_tools=["generate_client_order_id", "validate_order_schema", "check_idempotency"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_execution",
        name="Execution Agent",
        role=AgentRole.EXECUTION,
        department="Trading Desk",
        responsibilities=["Route orders to AngelOne SmartAPI", "Verify broker fill confirmations", "Track slippage"],
        allowed_tools=["submit_broker_order", "poll_order_status", "calculate_slippage"],
        can_execute_trades=True,  # Gated execution only after Risk & Compliance pass
    ),
    SpecializedAgentSpec(
        agent_id="agt_capital",
        name="Capital Management Agent",
        role=AgentRole.CAPITAL_MANAGEMENT,
        department="Treasury & Finance",
        responsibilities=["Track settled cash, buying power, and deployed funds", "Enforce ₹2,000 bootstrap runway rules"],
        allowed_tools=["get_capital_breakdown", "reserve_trade_funds", "reconcile_rms"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_compliance",
        name="Compliance Agent",
        role=AgentRole.COMPLIANCE,
        department="Legal & Compliance",
        responsibilities=["Enforce SEBI & exchange trading rules", "Block restricted securities & verify KYC state"],
        allowed_tools=["check_sebi_compliance", "verify_trading_hours", "block_asm_gsm_stocks"],
        can_execute_trades=False,
        has_veto_power=True,
    ),
    SpecializedAgentSpec(
        agent_id="agt_monitoring",
        name="Monitoring Agent",
        role=AgentRole.MONITORING,
        department="Operations & DevOps",
        responsibilities=["Monitor API latencies, WebSocket health, memory usage", "Track open positions trailing stops"],
        allowed_tools=["check_system_health", "monitor_trailing_stops", "audit_feed_latency"],
        can_execute_trades=False,
    ),
    SpecializedAgentSpec(
        agent_id="agt_incident_recovery",
        name="Incident & Recovery Agent",
        role=AgentRole.INCIDENT_RECOVERY,
        department="Operations & DevOps",
        responsibilities=["Trigger Emergency Kill Switch on failure", "Perform state reconciliation on restart"],
        allowed_tools=["engage_kill_switch", "reconcile_state_after_crash", "dispatch_critical_alert"],
        can_execute_trades=False,
        has_veto_power=True,
    ),
    SpecializedAgentSpec(
        agent_id="agt_performance",
        name="Performance Analysis Agent",
        role=AgentRole.PERFORMANCE_ANALYSIS,
        department="Portfolio Management",
        responsibilities=["Calculate Sharpe, Sortino, Win Rate, Profit Factor", "Run 4-Quadrant post-trade learning loops"],
        allowed_tools=["calculate_performance_metrics", "update_4_quadrant_stats", "extract_trade_lessons"],
        can_execute_trades=False,
    ),
]


class SixteenAgentsRosterManager:
    """Manages the 16 specialized agents in the AI Trading Organization."""

    @staticmethod
    def list_agents() -> list[dict[str, Any]]:
        return [a.model_dump() for a in SIXTEEN_PRODUCTION_AGENTS]

    @staticmethod
    def get_agent_by_role(role: AgentRole) -> SpecializedAgentSpec | None:
        for a in SIXTEEN_PRODUCTION_AGENTS:
            if a.role == role:
                return a
        return None


sixteen_agents_roster = SixteenAgentsRosterManager()

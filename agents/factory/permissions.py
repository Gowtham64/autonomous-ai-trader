from agents.factory.models import CustomAgentProfile
from core.logging import logger


class PermissionDeniedError(Exception):
    """Raised when an agent attempts an unauthorized tool or financial action."""


class PermissionEnforcer:
    """Strict 'Deny-by-Default' Security & Authorization Gateway.
    
    Ensures absolute separation between Intelligence permissions (read, analyze, generate signal)
    and Action/Financial permissions (orders, risk modification, withdrawals).
    """

    @staticmethod
    def verify_permission(
        agent: CustomAgentProfile,
        action: str,
        is_live_trading_requested: bool = False,
    ) -> tuple[bool, str]:
        """Validates requested action against the agent's explicit permissions."""
        perms = agent.permissions

        # Non-negotiable immutable security rules:
        if action == "withdraw_money":
            return False, "Security Violation: AI agents are strictly forbidden from withdrawing funds."

        if action == "modify_risk_limits":
            return False, "Security Violation: AI agents cannot alter deterministic risk constraints."

        if action == "place_live_orders" or is_live_trading_requested:
            if not perms.place_live_orders:
                return False, f"Permission Denied: Agent '{agent.name}' does NOT have 'place_live_orders' permission."

        # Map actions to permission attributes
        action_map = {
            "get_live_price": perms.read_market_data,
            "get_ohlc_data": perms.read_historical_data,
            "scan_stocks": perms.read_market_data,
            "compare_stocks": perms.read_market_data,
            "technical_analysis": perms.run_technical_analysis,
            "fundamental_analysis": perms.run_fundamental_analysis,
            "news_analysis": perms.search_news,
            "market_regime_detection": perms.run_technical_analysis,
            "backtest_strategy": perms.run_backtest,
            "generate_reports": perms.generate_signals,
            "read_portfolio": perms.read_market_data,
            "calculate_position_size": perms.read_market_data,
            "calculate_turtle_metrics": perms.run_technical_analysis,
            "evaluate_trend_and_discipline": perms.run_technical_analysis,
            "calculate_black_scholes_greeks": perms.run_technical_analysis,
            "evaluate_spread_strategy": perms.run_technical_analysis,
            "send_dashboard_alert": perms.generate_signals,
            "paper_trade_order": perms.paper_trade,
            "place_live_orders": perms.place_live_orders,
        }

        allowed = action_map.get(action, False)
        if not allowed:
            msg = f"Access Denied: Agent '{agent.name}' lacks permission for function '{action}' (Deny by Default)."
            logger.warning(f"[Permission Enforcer] {msg}")
            return False, msg

        return True, "Authorized"

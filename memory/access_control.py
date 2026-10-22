import re
from typing import ClassVar

from memory.models import MemoryLevel, MemoryRecord


class MemorySecurityError(Exception):
    pass


class MemoryAccessControl:
    """Strict Memory Access Control & Security Governance (Section 46).
    
    Ensures private agent memories remain isolated, sensitive API keys/credentials
    are NEVER stored in AI memory, and roles only read authorized knowledge domains.
    """

    FORBIDDEN_KEYWORDS: ClassVar[list[str]] = [
        "api_key", "secret", "password", "totp", "pin", "auth_token",
        "broker_secret", "jwt_secret", "private_key"
    ]

    # Role Access Matrix
    ROLE_PERMISSIONS: ClassVar[dict[str, list[str]]] = {
        "technical_agent": ["TECHNICAL_RESEARCH", "MARKET_OBSERVATIONS", "TRADING_HISTORY", "ORGANIZATIONAL", "LONG_TERM"],
        "fundamental_agent": ["FUNDAMENTAL_RESEARCH", "EARNINGS", "TRADING_HISTORY", "ORGANIZATIONAL", "LONG_TERM"],
        "news_agent": ["NEWS_INTEL", "ANNOUNCEMENTS", "TRADING_HISTORY", "ORGANIZATIONAL", "LONG_TERM"],
        "risk_agent": ["RISK_DECISIONS", "PORTFOLIO_EXPOSURE", "DRAWDOWN_EVENTS", "TRADING_HISTORY", "ORGANIZATIONAL", "LONG_TERM"],
        "portfolio_agent": ["PORTFOLIO_EXPOSURE", "POSITION_SIZING", "TRADING_HISTORY", "ORGANIZATIONAL", "LONG_TERM"],
        "chief_trading_agent": ["ALL"],
        "cfo_agent": ["COST_ACCOUNTING", "RESOURCE_USAGE", "TRADING_HISTORY", "ORGANIZATIONAL", "LONG_TERM"],
        "cto_agent": ["SYSTEM_ARCHITECTURE", "BOTTLENECKS", "UPGRADE_PROPOSALS", "ORGANIZATIONAL", "LONG_TERM"],
        "memory_manager": ["ALL"],
    }

    @classmethod
    def validate_write_security(cls, memory: MemoryRecord) -> None:
        """Enforces that no sensitive secrets or credentials are ever written to AI memory."""
        content_lower = memory.content.lower()
        for kw in cls.FORBIDDEN_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", content_lower):
                raise MemorySecurityError(
                    f"Security Violation: Sensitive keyword '{kw}' detected in memory content. "
                    f"Credentials and secrets MUST be stored in the dedicated secure secrets manager, NEVER in AI memory."
                )


    @classmethod
    def can_read_memory(cls, agent_role: str, agent_id: str, memory: MemoryRecord) -> bool:
        """Determines if the requesting agent is authorized to read the specified memory entry."""
        # 1. Private Memory Isolation: Only the author can read their private memory
        if memory.level == MemoryLevel.PRIVATE:
            return memory.created_by == agent_id or agent_role in ["chief_trading_agent", "memory_manager"]

        # 2. Universal organizational access
        if "ALL" in memory.access_roles:
            return True

        # 3. Check role permissions
        allowed_domains = cls.ROLE_PERMISSIONS.get(agent_role, ["ORGANIZATIONAL", "LONG_TERM"])
        if "ALL" in allowed_domains:
            return True

        return any(role in allowed_domains for role in memory.access_roles)

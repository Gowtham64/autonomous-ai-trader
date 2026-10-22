from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from core.config.settings import settings
from core.logging import logger


class AgentType(str, Enum):
    CORE = "CORE"
    DYNAMIC = "DYNAMIC"


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STANDBY = "STANDBY"
    THROTTLED = "THROTTLED"
    SHUTDOWN = "SHUTDOWN"


class AgentMetadata(BaseModel):
    agent_id: str
    name: str
    role: str
    agent_type: AgentType
    status: AgentStatus = AgentStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    invocations_count: int = 0
    total_cost_inr: float = 0.0
    accuracy_score: float = 0.85
    shutdown_reason: str | None = None


class AgentLifecycleManager:
    """Manages the AI Trading Office roster and the lifecycle of dynamic specialized agents.
    
    Enforces strict permissions, computational limits, resource costs, and automatic
    decommissioning under Survival Mode or poor performance.
    """

    def __init__(self, max_dynamic_agents: int = settings.MAX_ACTIVE_DYNAMIC_AGENTS):
        self.max_dynamic_agents = max_dynamic_agents
        self.registry: dict[str, AgentMetadata] = {}
        self._init_core_office()

    def _init_core_office(self) -> None:
        """Initializes the permanent core specialized AI agents of the trading office."""
        core_agents = [
            ("chief_trading_agent", "Chief Trading Officer", "Central decision-maker, synthesis & execution approval"),
            ("market_scanner_agent", "Quant Market Scanner", "Universe pre-filtering, liquidity & momentum screening"),
            ("technical_analyst_agent", "Technical Analyst", "Multi-timeframe price action, indicators & trend structure"),
            ("fundamental_analyst_agent", "Fundamental Analyst", "Valuation, financials, earnings quality & growth"),
            ("news_event_agent", "News & Event Analyst", "Corporate filings, regulatory events & news verification"),
            ("sentiment_analyst_agent", "Sentiment Analyst", "Market sentiment, social volume & institutional flows"),
            ("macro_analyst_agent", "Macro Analyst", "RBI policy, yield curves, crude, USD/INR & market breadth"),
            ("bull_researcher_agent", "Bull Researcher", "Constructs bullish thesis and upside reward catalysts"),
            ("bear_researcher_agent", "Bear Researcher", "Constructs adversarial bear counter-theses and failure modes"),
            ("facilitator_agent", "Debate Facilitator", "Mediates adversarial debate, synthesizes consensus & invalidations"),
            ("risk_manager_agent", "Risk Manager", "Veto authority, position sizing, drawdown & circuit breaker enforcement"),
            ("strategy_agent", "Strategy Evaluator", "Multi-strategy evaluation and market regime validation"),
            ("portfolio_manager_agent", "Portfolio Manager", "Concentration, sector allocation & rebalancing"),
            ("execution_agent", "Execution Router", "Order routing, safety gate verification & execution reports"),
        ]

        for aid, name, role in core_agents:
            self.registry[aid] = AgentMetadata(
                agent_id=aid,
                name=name,
                role=role,
                agent_type=AgentType.CORE,
                status=AgentStatus.ACTIVE,
            )

    def spawn_dynamic_agent(
        self,
        name: str,
        role: str,
        reason: str,
        is_survival_mode: bool = False,
    ) -> AgentMetadata | None:
        """Dynamically instantiates a specialized agent within strict safety bounds."""
        if is_survival_mode:
            logger.warning(f"[Agent Manager] Rejected spawning '{name}': Survival Mode is active to preserve capital.")
            return None

        active_dynamics = [
            a for a in self.registry.values()
            if a.agent_type == AgentType.DYNAMIC and a.status == AgentStatus.ACTIVE
        ]

        if len(active_dynamics) >= self.max_dynamic_agents:
            logger.warning(
                f"[Agent Manager] Dynamic agent limit ({self.max_dynamic_agents}) reached. "
                f"Cannot spawn '{name}' without decommissioning inactive agents."
            )
            return None

        agent_id = f"dyn_{name.lower().replace(' ', '_')}_{int(datetime.now(UTC).timestamp())}"
        metadata = AgentMetadata(
            agent_id=agent_id,
            name=name,
            role=role,
            agent_type=AgentType.DYNAMIC,
            status=AgentStatus.ACTIVE,
        )
        self.registry[agent_id] = metadata
        logger.info(f"[Agent Manager] Spawned dynamic specialized agent '{name}' [{agent_id}] for: {reason}")
        return metadata

    def record_agent_usage(self, agent_id: str, cost_inr: float = 0.05, accurate: bool = True) -> None:
        """Records agent activity, resource expenditure, and rolling accuracy."""
        if agent_id in self.registry:
            agent = self.registry[agent_id]
            agent.invocations_count += 1
            agent.total_cost_inr += cost_inr
            # Update rolling accuracy
            weight = 0.1
            agent.accuracy_score = round(
                (agent.accuracy_score * (1.0 - weight)) + ((1.0 if accurate else 0.0) * weight),
                3,
            )

    def decommission_agent(self, agent_id: str, reason: str = "Inactivity or Survival Mode") -> bool:
        """Decommissions a dynamic agent."""
        if agent_id in self.registry:
            agent = self.registry[agent_id]
            if agent.agent_type == AgentType.CORE:
                logger.warning(f"[Agent Manager] Cannot shutdown permanent CORE agent '{agent.name}'")
                return False
            agent.status = AgentStatus.SHUTDOWN
            agent.shutdown_reason = reason
            logger.info(f"[Agent Manager] Decommissioned dynamic agent '{agent.name}' [{agent_id}]. Reason: {reason}")
            return True
        return False

    def enforce_survival_mode_constraints(self) -> list[str]:
        """Automatically throttles / shuts down non-essential dynamic agents during Survival Mode."""
        decommissioned = []
        for agent_id, agent in list(self.registry.items()):
            if agent.agent_type == AgentType.DYNAMIC and agent.status == AgentStatus.ACTIVE:
                self.decommission_agent(agent_id, reason="Survival Mode activated: Preserving bootstrap capital")
                decommissioned.append(agent.name)
        return decommissioned

    def get_office_roster(self) -> list[dict]:
        """Returns the full roster of the AI Trading Office."""
        return [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "role": a.role,
                "type": a.agent_type.value,
                "status": a.status.value,
                "invocations": a.invocations_count,
                "cost_inr": round(a.total_cost_inr, 2),
                "accuracy": f"{a.accuracy_score*100:.1f}%",
                "shutdown_reason": a.shutdown_reason,
            }
            for a in self.registry.values()
        ]


# Global Office Manager instance
agent_manager = AgentLifecycleManager()

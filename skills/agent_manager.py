"""
Agent Skill Manager — Manages Modular Agent Compositions & Dynamic Skill Bindings
"""


from core.logging import logger
from skills.models import (
    AgentSkillComposition,
    SkillPermission,
    SkillRiskLevel,
)
from skills.registry import skill_registry


class AgentSkillManager:
    """Manages the full modular composition of AI Agents (Identity + Role + Memory + Skills + Tools + Permissions)."""

    def __init__(self):
        self._agents: dict[str, AgentSkillComposition] = {}
        self._initialize_default_workforce()

    def _initialize_default_workforce(self):
        """Initializes the institutional trading workforce with pre-assigned modular skills."""
        default_roster = [
            AgentSkillComposition(
                agent_id="ceo",
                name="Chief Executive Officer",
                role="Strategic Governance & Capital Stewardship",
                goal="Oversee autonomous company sustainability and long-term capital preservation.",
                skill_ids=[
                    "skill.finance.treasury_runway.v1",
                    "skill.regime.market_classifier.v1",
                    "skill.diagnostics.system_health.v1",
                ],
                tools=["treasury_engine", "system_diagnostics"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.FINANCIAL, SkillPermission.ADMIN],
                risk_level_limit=SkillRiskLevel.LEVEL_5_CRITICAL,
            ),
            AgentSkillComposition(
                agent_id="technical_analyst",
                name="Chief Technical Analyst",
                role="Price Action & Indicator Lead",
                goal="Extract high-probability candlestick, RSI, and moving average trend alignments.",
                skill_ids=[
                    "skill.market.live_price.v1",
                    "skill.analysis.rsi.v1",
                    "skill.analysis.moving_averages.v1",
                    "skill.analysis.atr_volatility.v1",
                ],
                tools=["market_data_api"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
            ),
            AgentSkillComposition(
                agent_id="stock_screener",
                name="Stock Screener Agent",
                role="Universe Funnel Lead",
                goal="Filter liquid NSE 500 stocks to identify top volume spike and momentum candidates.",
                skill_ids=[
                    "skill.market.live_price.v1",
                    "skill.scanner.universe_momentum.v1",
                    "skill.scanner.volume_spike.v1",
                ],
                tools=["market_data_api", "quant_scanner"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
            ),
            AgentSkillComposition(
                agent_id="risk_manager",
                name="Risk Manager Agent",
                role="Risk Gatekeeper & Circuit Breaker",
                goal="Enforce immutable 2% daily loss limit, position sizing, and trade veto barriers.",
                skill_ids=[
                    "skill.risk.position_sizing.v1",
                    "skill.risk.trade_veto.v1",
                ],
                tools=["risk_engine", "treasury_engine", "kill_switch"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.MODIFY],
                risk_level_limit=SkillRiskLevel.LEVEL_4_FINANCIAL,
            ),
            AgentSkillComposition(
                agent_id="order_router",
                name="Execution Router Agent",
                role="Order Routing & Broker Dispatch",
                goal="Validate orders and route approved trades to AngelOne SmartAPI gateway.",
                skill_ids=[
                    "skill.execution_quality.order_validator.v1",
                    "skill.trading.check_broker_funds.v1",
                ],
                tools=["broker_api", "market_data_api"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.EXECUTE],
                risk_level_limit=SkillRiskLevel.LEVEL_4_FINANCIAL,
                can_live_trade=True,
            ),
        ]

        for agent in default_roster:
            self._agents[agent.agent_id] = agent

        logger.info(f"[AgentSkillManager] Initialized workforce with {len(self._agents)} modular agents.")

    def get_agent(self, agent_id: str) -> AgentSkillComposition | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentSkillComposition]:
        return list(self._agents.values())

    def create_or_update_agent(self, agent: AgentSkillComposition) -> AgentSkillComposition:
        self._agents[agent.agent_id] = agent
        logger.info(f"[AgentSkillManager] Saved modular agent '{agent.name}' ({agent.agent_id}) with {len(agent.skill_ids)} skills.")
        return agent

    def assign_skill_to_agent(self, agent_id: str, skill_id: str) -> bool:
        agent = self.get_agent(agent_id)
        skill = skill_registry.get_skill(skill_id)
        if not agent or not skill:
            return False

        if skill_id not in agent.skill_ids:
            agent.skill_ids.append(skill_id)
            logger.info(f"[AgentSkillManager] Assigned skill '{skill_id}' to agent '{agent_id}'.")
        return True

    def remove_skill_from_agent(self, agent_id: str, skill_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent or skill_id not in agent.skill_ids:
            return False
        agent.skill_ids.remove(skill_id)
        logger.info(f"[AgentSkillManager] Removed skill '{skill_id}' from agent '{agent_id}'.")
        return True


# Global Singleton Agent Skill Manager
agent_skill_manager = AgentSkillManager()

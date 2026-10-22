"""
Autonomous Agent Procreation & Workforce Expansion Engine
Enables AI Agents to dynamically analyze their workload, detect capability gaps, and autonomously spawn specialized support agents funded by the AI Treasury's AI Upgrade Fund.
"""

from core.logging import logger
from core.treasury.treasury import treasury
from orchestration.event_bus import SystemEventType, realtime_event_bus
from skills.agent_manager import agent_skill_manager
from skills.models import AgentSkillComposition, SkillPermission, SkillRiskLevel


class AutonomousAgentProcreationEngine:
    """Evaluates organizational workload and autonomously spawns support agents when needed."""

    def __init__(self, spawn_cost_inr: float = 15.0):
        self.spawn_cost_inr = spawn_cost_inr
        self.spawned_count = 0

    async def evaluate_and_auto_spawn(self, scanned_candidates: list, market_regime: str = "Trending") -> list[AgentSkillComposition]:
        """Checks if the organization requires new specialized support agents and has treasury budget."""
        spawned_agents = []

        # 1. Check if AI Treasury has sufficient capital
        current_capital = treasury.current_capital

        # If in severe survival mode, preserve funds
        if treasury.is_survival_mode and current_capital <= 0:
            logger.debug("[AutoProcreation] Survival mode active with zero funds: Delaying agent spawning.")
            return []

        # 2. Identify Domain Gaps based on Market Candidates
        symbols = [getattr(c, "symbol", "") for c in scanned_candidates]
        has_bank = any("BANK" in s or "HDFC" in s or "ICICI" in s or "SBIN" in s for s in symbols)
        has_tech = any("TCS" in s or "INFY" in s or "WIPRO" in s or "TECHM" in s for s in symbols)

        existing_agents = [a.agent_id for a in agent_skill_manager.list_agents()]

        # Gap 1: Market News & Sentiment Harvester Specialist
        if "agent_news_sentiment_harvester" not in existing_agents:
            new_agent = AgentSkillComposition(
                agent_id="agent_news_sentiment_harvester",
                name="Market News & Macro Sentiment Harvester",
                role="Real-Time News & Corporate Announcements Specialist",
                goal="Continuously crawl corporate disclosures, earnings reports, regulatory updates, and global macro news across N stocks.",
                skill_ids=[
                    "skill.market.live_price.v1",
                    "skill.scanner.volume_spike.v1",
                ],
                tools=["market_data_api", "news_crawler", "sentiment_analyzer"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
            )
            agent_skill_manager.create_or_update_agent(new_agent)
            treasury.record_operating_cost(self.spawn_cost_inr, "AI Procreation: Spawned News Sentiment Harvester")
            spawned_agents.append(new_agent)
            logger.info(f"✨ [Autonomous Procreation] AI Agents spawned support worker: '{new_agent.name}' for real-time news & sentiment!")
            realtime_event_bus.publish_event(
                SystemEventType.AGENT_STATUS_CHANGED,
                source="Autonomous Procreation Desk",
                payload={"agent_id": new_agent.agent_id, "action": "AUTONOMOUS_SPAWN", "name": new_agent.name},
            )

        # Gap 2: High-Speed Quant Screener Sub-Agent
        if len(scanned_candidates) >= 5 and "agent_quant_screener_worker" not in existing_agents:
            new_agent = AgentSkillComposition(
                agent_id="agent_quant_screener_worker",
                name="High-Speed Quant Screener Worker",
                role="Parallel Technical & Momentum Pattern Screener",
                goal="Execute high-throughput parallel algorithmic screening on 200+ NSE stocks to detect instant breakout opportunities.",
                skill_ids=[
                    "skill.analysis.rsi.v1",
                    "skill.scanner.volume_spike.v1",
                    "skill.analysis.atr_volatility.v1",
                ],
                tools=["quant_scanner", "market_data_api"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
            )
            agent_skill_manager.create_or_update_agent(new_agent)
            treasury.record_operating_cost(self.spawn_cost_inr, "AI Procreation: Spawned High-Speed Quant Screener")
            spawned_agents.append(new_agent)
            logger.info(f"✨ [Autonomous Procreation] AI Agents spawned support worker: '{new_agent.name}' for multi-stock parallel scanning!")
            realtime_event_bus.publish_event(
                SystemEventType.AGENT_STATUS_CHANGED,
                source="Autonomous Procreation Desk",
                payload={"agent_id": new_agent.agent_id, "action": "AUTONOMOUS_SPAWN", "name": new_agent.name},
            )

        # Gap 3: PSU, Energy & Defense Specialist
        has_psu = any(s in ["COALINDIA.NS", "GAIL.NS", "SAIL.NS", "BHEL.NS", "IREDA.NS", "NTPC.NS", "ONGC.NS", "BEL.NS", "HAL.NS"] for s in symbols)
        if has_psu and "agent_psu_energy_specialist" not in existing_agents:
            new_agent = AgentSkillComposition(
                agent_id="agent_psu_energy_specialist",
                name="PSU, Energy & Defense Specialist",
                role="Sovereign Enterprise & Infrastructure Analyst",
                goal="Analyze government capex cycles, order book execution, dividend yields, and commodity trends for PSU stocks.",
                skill_ids=[
                    "skill.market.live_price.v1",
                    "skill.analysis.rsi.v1",
                ],
                tools=["market_data_api", "quant_scanner"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
            )
            agent_skill_manager.create_or_update_agent(new_agent)
            treasury.record_operating_cost(self.spawn_cost_inr, "AI Procreation: Spawned PSU & Defense Specialist")
            spawned_agents.append(new_agent)
            logger.info(f"✨ [Autonomous Procreation] AI Agents spawned support worker: '{new_agent.name}'!")
            realtime_event_bus.publish_event(
                SystemEventType.AGENT_STATUS_CHANGED,
                source="Autonomous Procreation Desk",
                payload={"agent_id": new_agent.agent_id, "action": "AUTONOMOUS_SPAWN", "name": new_agent.name},
            )

        # Gap 4: Banking & Financial Sector Specialist
        if has_bank and "agent_banking_specialist" not in existing_agents:
            new_agent = AgentSkillComposition(
                agent_id="agent_banking_specialist",
                name="BankNifty & Financials Specialist",
                role="Banking & Credit Market Analyst",
                goal="Monitor RBI monetary policy, net interest margins, and BankNifty breakout momentum.",
                skill_ids=[
                    "skill.market.live_price.v1",
                    "skill.analysis.rsi.v1",
                    "skill.scanner.volume_spike.v1",
                ],
                tools=["market_data_api", "quant_scanner"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
            )
            agent_skill_manager.create_or_update_agent(new_agent)
            treasury.record_operating_cost(self.spawn_cost_inr, "AI Procreation: Spawned BankNifty Specialist")
            spawned_agents.append(new_agent)
            logger.info(f"✨ [Autonomous Procreation] AI Agents spawned support worker: '{new_agent.name}' (Funded by AI Treasury)!")

            realtime_event_bus.publish_event(
                SystemEventType.AGENT_STATUS_CHANGED,
                source="Autonomous Procreation Desk",
                payload={"agent_id": new_agent.agent_id, "action": "AUTONOMOUS_SPAWN", "name": new_agent.name},
            )

        # Gap 5: Technology & IT Services Specialist
        if has_tech and "agent_tech_specialist" not in existing_agents:
            new_agent = AgentSkillComposition(
                agent_id="agent_tech_specialist",
                name="IT & Tech Export Specialist",
                role="Technology & SaaS Analyst",
                goal="Analyze USD/INR currency tailwinds, US client tech spending, and IT breakout momentum.",
                skill_ids=[
                    "skill.market.live_price.v1",
                    "skill.analysis.rsi.v1",
                    "skill.scanner.volume_spike.v1",
                ],
                tools=["market_data_api", "quant_scanner"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
            )
            agent_skill_manager.create_or_update_agent(new_agent)
            treasury.record_operating_cost(self.spawn_cost_inr, "AI Procreation: Spawned Tech Specialist")
            spawned_agents.append(new_agent)
            logger.info(f"✨ [Autonomous Procreation] AI Agents spawned support worker: '{new_agent.name}' (Funded by AI Treasury)!")

            realtime_event_bus.publish_event(
                SystemEventType.AGENT_STATUS_CHANGED,
                source="Autonomous Procreation Desk",
                payload={"agent_id": new_agent.agent_id, "action": "AUTONOMOUS_SPAWN", "name": new_agent.name},
            )

        # Gap 6: High-Volatility Scalper Support
        if market_regime == "High Volatility Sideways" and "agent_volatility_scalper" not in existing_agents:
            new_agent = AgentSkillComposition(
                agent_id="agent_volatility_scalper",
                name="Volatility Scalper Agent",
                role="Intraday Mean Reversion Specialist",
                goal="Capture quick intraday reversions during high India VIX spikes with strict ATR stops.",
                skill_ids=[
                    "skill.analysis.atr_volatility.v1",
                    "skill.risk.position_sizing.v1",
                    "skill.analysis.rsi.v1",
                ],
                tools=["market_data_api", "risk_engine"],
                permissions=[SkillPermission.READ, SkillPermission.ANALYZE, SkillPermission.GENERATE],
                risk_level_limit=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
                )
            agent_skill_manager.create_or_update_agent(new_agent)
            treasury.record_operating_cost(self.spawn_cost_inr, "AI Procreation: Spawned Volatility Scalper")
            spawned_agents.append(new_agent)
            logger.info(f"✨ [Autonomous Procreation] AI Agents spawned support worker: '{new_agent.name}' (Funded by AI Treasury)!")

            realtime_event_bus.publish_event(
                SystemEventType.AGENT_STATUS_CHANGED,
                source="Autonomous Procreation Desk",
                payload={"agent_id": new_agent.agent_id, "action": "AUTONOMOUS_SPAWN", "name": new_agent.name},
            )

        return spawned_agents


# Global Singleton Auto-Procreation Engine
auto_procreation_engine = AutonomousAgentProcreationEngine()

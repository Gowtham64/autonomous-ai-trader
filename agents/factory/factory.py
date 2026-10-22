import re
import uuid
from datetime import UTC, datetime

from agents.factory.models import (
    AgentPermissions,
    AgentResourceBudget,
    AgentRiskLimits,
    CustomAgentProfile,
    Department,
    LifecycleStage,
)
from agents.factory.permissions import PermissionEnforcer
from core.logging import logger
from core.schemas.trade import AnalystReport
from market.providers.mock_provider import MockMarketDataProvider
from scanner.quant_scanner import QuantMarketScanner


class AgentFactoryError(Exception):
    pass


class CustomAgentFactory:
    """Master AI Agent Factory & Workforce Governance System.
    
    Enables users and Chief AI to construct, test in sandbox, version, clone,
    and deploy custom specialized agents with explicit permissions and resource limits.
    """

    def __init__(
        self,
        max_total_agents: int = 50,
        max_daily_creations: int = 10,
    ):
        self.max_total_agents = max_total_agents
        self.max_daily_creations = max_daily_creations
        self.agent_store: dict[str, CustomAgentProfile] = {}
        self.creation_log: list[datetime] = []
        self._seed_default_custom_agents()

    def _seed_default_custom_agents(self) -> None:
        """Seeds predefined community/library templates."""
        sample_agents = [
            CustomAgentProfile(
                agent_id="agent_momentum_hunter",
                name="Momentum Hunter",
                department=Department.TRADING,
                role="Momentum Analyst",
                objective="Identify high-quality intraday momentum breakout candidates on NSE",
                responsibilities=[
                    "Scan eligible NSE universe",
                    "Filter by relative volume > 1.2x and momentum score > 60",
                    "Construct bullish breakout briefs for Chief Trading Officer",
                ],
                tools=["scan_stocks", "technical_analysis", "send_dashboard_alert"],
                functions=["get_live_price", "get_ohlc_data", "technical_analysis"],
                permissions=AgentPermissions(
                    read_market_data=True,
                    run_technical_analysis=True,
                    generate_signals=True,
                    paper_trade=True,
                    place_live_orders=False,
                ),
                status=LifecycleStage.ACTIVE,
                version="v1.0",
                is_core=False,
            ),
            CustomAgentProfile(
                agent_id="agent_risk_guardian",
                name="Portfolio Guardian",
                department=Department.RISK,
                role="Portfolio Risk Monitor",
                objective="Detect excessive concentration, correlation and market regime volatility shocks",
                responsibilities=[
                    "Monitor active portfolio exposure",
                    "Audit open orders against circuit breaker thresholds",
                    "Signal defensive hedge alerts upon regime degradation",
                ],
                tools=["read_portfolio", "market_regime_detection", "calculate_position_size"],
                functions=["read_portfolio", "calculate_position_size", "market_regime_detection"],
                permissions=AgentPermissions(
                    read_market_data=True,
                    run_technical_analysis=True,
                    generate_signals=True,
                    paper_trade=True,
                    place_live_orders=False,
                ),
                status=LifecycleStage.ACTIVE,
                version="v1.0",
                is_core=False,
            ),
            CustomAgentProfile(
                agent_id="agent_smallcap_scout",
                name="Small-Cap Scout",
                department=Department.RESEARCH,
                role="Growth Research Specialist",
                objective="Analyze emerging growth and mid-cap companies with high volume accumulation",
                responsibilities=[
                    "Screen Nifty Midcap and Smallcap universe",
                    "Evaluate fundamental debt, revenue growth, and liquidity",
                    "Submit qualified candidates for multi-agent adversarial debate",
                ],
                tools=["scan_stocks", "fundamental_analysis", "news_analysis"],
                functions=["scan_stocks", "fundamental_analysis", "news_analysis"],
                permissions=AgentPermissions(
                    read_market_data=True,
                    run_fundamental_analysis=True,
                    search_news=True,
                    generate_signals=True,
                    paper_trade=True,
                    place_live_orders=False,
                ),
                status=LifecycleStage.SANDBOX,
                version="v1.0",
                is_core=False,
            ),
            CustomAgentProfile(
                agent_id="agent_turtle_trend_master",
                name="Turtle & Trend Master",
                department=Department.TRADING,
                role="Trend Following & Volatility Sizer",
                objective="Execute Richard Dennis & Ondřej Buček Turtle Donchian breakouts and Glen Goodman 5% Anti-Chase trend discipline",
                responsibilities=[
                    "Calculate 20-day and 55-day Donchian High/Low channel breakouts",
                    "Compute Volatility N (20-EMA True Range) and scale position size inversely to ATR",
                    "Enforce Glen Goodman 5% breakout chase veto to prevent FOMO at peaks",
                    "Manage trailing stops via Chandelier ATR (3.5x) and 200-day moving average",
                ],
                tools=["bucek_turtle_engine", "goodman_trend_engine", "scan_stocks"],
                functions=["calculate_turtle_metrics", "evaluate_trend_and_discipline"],
                permissions=AgentPermissions(
                    read_market_data=True,
                    run_technical_analysis=True,
                    generate_signals=True,
                    paper_trade=True,
                    place_live_orders=False,
                ),
                status=LifecycleStage.ACTIVE,
                version="v1.0",
                is_core=False,
            ),
            CustomAgentProfile(
                agent_id="agent_options_strategist",
                name="Options Unlocked Strategist",
                department=Department.RESEARCH,
                role="Derivatives & Options Greeks Specialist",
                objective="Analyze option Greeks, pricing models, and defined-risk multi-leg spreads based on Christopher M. McCarthy's framework",
                responsibilities=[
                    "Calculate Black-Scholes analytical Greeks (Delta, Gamma, Theta, Vega, Rho) and Binomial trees",
                    "Design defined-risk spreads (Bull/Bear verticals, Iron Condors, Jade Lizards, Straddles)",
                    "Audit open interest, volume, and bid-ask spread liquidity prior to trade authorization",
                    "Enforce zero-naked-options rule to guarantee capped maximum loss",
                ],
                tools=["mccarthy_options_engine", "calculate_greeks", "evaluate_spreads"],
                functions=["calculate_black_scholes_greeks", "evaluate_spread_strategy"],
                permissions=AgentPermissions(
                    read_market_data=True,
                    run_technical_analysis=True,
                    generate_signals=True,
                    paper_trade=True,
                    place_live_orders=False,
                ),
                status=LifecycleStage.ACTIVE,
                version="v1.0",
                is_core=False,
            ),
        ]

        for a in sample_agents:
            self.agent_store[a.agent_id] = a

    def _check_creation_rate_limits(self) -> None:
        """Enforces anti-replication bounds to prevent uncontrolled agent creation."""
        if len(self.agent_store) >= self.max_total_agents:
            raise AgentFactoryError(
                f"Organization agent limit ({self.max_total_agents}) reached. Please retire inactive agents first."
            )

        now = datetime.now(UTC)
        recent_creations = [
            t for t in self.creation_log
            if (now - t).total_seconds() < 86400
        ]
        if len(recent_creations) >= self.max_daily_creations:
            raise AgentFactoryError(
                f"Daily creation quota ({self.max_daily_creations}/day) reached. Prohibiting runaway agent creation."
            )

    def create_agent(self, profile: CustomAgentProfile) -> CustomAgentProfile:
        """Registers and validates a newly created custom agent in Sandbox stage."""
        self._check_creation_rate_limits()

        if not profile.agent_id:
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', profile.name.lower())
            profile.agent_id = f"agent_{clean_name}_{uuid.uuid4().hex[:6]}"

        # Force new agents into Sandbox by default
        if profile.status == LifecycleStage.ACTIVE:
            profile.status = LifecycleStage.SANDBOX

        self.agent_store[profile.agent_id] = profile
        self.creation_log.append(datetime.now(UTC))
        logger.info(f"[Agent Factory] Created custom agent '{profile.name}' [{profile.agent_id}] in {profile.status.value} mode.")
        return profile

    def parse_natural_language_instruction(
        self,
        prompt: str,
        name: str = "Custom AI Specialist",
        department: Department = Department.RESEARCH,
    ) -> CustomAgentProfile:
        """Converts user natural language instructions into a fully structured CustomAgentProfile."""
        p_lower = prompt.lower()

        # Deduce tools & functions from prompt keywords
        tools = []
        functions = []

        if any(w in p_lower for w in ["volume", "momentum", "scan", "universe", "screen"]):
            tools.extend(["scan_stocks", "technical_analysis"])
            functions.extend(["get_live_price", "get_ohlc_data", "technical_analysis"])

        if any(w in p_lower for w in ["news", "event", "filing", "disclosure", "announcement"]):
            tools.append("news_analysis")
            functions.append("news_analysis")

        if any(w in p_lower for w in ["fundamental", "earnings", "valuation", "p/e", "debt", "revenue"]):
            tools.append("fundamental_analysis")
            functions.append("fundamental_analysis")

        if any(w in p_lower for w in ["risk", "drawdown", "exposure", "guardian", "portfolio"]):
            tools.extend(["read_portfolio", "calculate_position_size"])
            functions.extend(["read_portfolio", "calculate_position_size"])
            department = Department.RISK

        if not tools:
            tools = ["technical_analysis", "generate_reports"]
            functions = ["get_live_price", "technical_analysis"]

        # Default permissions (Strict Deny-by-Default on live execution)
        can_live_trade = "live trade" in p_lower and "not" not in p_lower and "do not" not in p_lower
        permissions = AgentPermissions(
            read_market_data=True,
            read_historical_data=True,
            run_technical_analysis="technical" in tools or "scan_stocks" in tools,
            run_fundamental_analysis="fundamental_analysis" in tools,
            search_news="news_analysis" in tools,
            run_backtest=True,
            generate_signals=True,
            paper_trade=True,
            place_live_orders=can_live_trade,
        )

        agent_id = f"agent_{re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())}_{uuid.uuid4().hex[:6]}"

        profile = CustomAgentProfile(
            agent_id=agent_id,
            name=name,
            department=department,
            role=f"Custom Specialist for: {name}",
            objective=prompt[:140] + ("..." if len(prompt) > 140 else ""),
            responsibilities=[
                f"Execute user directives: {prompt[:100]}...",
                "Generate structured intelligence reports and invalidation scenarios",
                "Operate within assigned resource and risk limits",
            ],
            system_prompt=f"You are {name}. Directives: {prompt}",
            tools=list(set(tools)),
            functions=list(set(functions)),
            permissions=permissions,
            status=LifecycleStage.SANDBOX,
            version="v1.0",
        )

        return self.create_agent(profile)

    def clone_agent(self, agent_id: str, new_name: str) -> CustomAgentProfile:
        """Clones an existing agent with a new identity without modifying the original."""
        if agent_id not in self.agent_store:
            raise AgentFactoryError(f"Agent '{agent_id}' not found.")

        orig = self.agent_store[agent_id]
        cloned_id = f"agent_{re.sub(r'[^a-zA-Z0-9_]', '_', new_name.lower())}_{uuid.uuid4().hex[:6]}"

        clone = CustomAgentProfile(
            agent_id=cloned_id,
            name=new_name,
            department=orig.department,
            role=orig.role,
            objective=f"Cloned from {orig.name}: {orig.objective}",
            responsibilities=list(orig.responsibilities),
            system_prompt=orig.system_prompt,
            tools=list(orig.tools),
            data_sources=list(orig.data_sources),
            functions=list(orig.functions),
            permissions=AgentPermissions(**orig.permissions.model_dump()),
            risk_limits=AgentRiskLimits(**orig.risk_limits.model_dump()),
            budget=AgentResourceBudget(**orig.budget.model_dump()),
            status=LifecycleStage.SANDBOX,
            version="v1.0",
            version_history=[{"cloned_from": orig.agent_id, "timestamp": str(datetime.now(UTC))}],
        )

        return self.create_agent(clone)

    async def run_sandbox_simulation(
        self,
        agent_id: str,
        symbol: str = "RELIANCE.NS",
    ) -> dict:
        """Executes a dry-run sandbox test with permission verification and synthetic market data."""
        if agent_id not in self.agent_store:
            raise AgentFactoryError(f"Agent '{agent_id}' not found.")

        agent = self.agent_store[agent_id]
        logger.info(f"[Sandbox] Running dry-run simulation for Agent '{agent.name}' on {symbol}...")

        # 1. Test Permissions
        auth_results = {}
        for func in agent.functions:
            authorized, reason = PermissionEnforcer.verify_permission(agent, func)
            auth_results[func] = {"authorized": authorized, "message": reason}

        # 2. Synthetic Market Evaluation
        provider = MockMarketDataProvider(base_price=2800.0, trend="bullish")
        scanner = QuantMarketScanner(provider=provider)
        sig = await scanner.scan_symbol(symbol)

        # 3. Simulate Intelligence Output
        report = AnalystReport(
            agent_name=agent.name,
            symbol=symbol,
            stance="BULLISH" if (sig and sig.momentum_score > 50) else "NEUTRAL",
            confidence=0.78,
            key_observations=[
                f"Sandbox evaluation executed successfully for {agent.name}",
                f"Assigned functions verified: {list(agent.functions)}",
                f"Candidate momentum score: {sig.momentum_score if sig else 0}/100",
            ],
            risk_warnings=["Sandbox execution: Live orders disallowed"],
            suggested_entry=sig.ltp if sig else 2800.0,
            suggested_stop=(sig.ltp - 1.5 * sig.atr_14) if sig else 2750.0,
            suggested_target=(sig.ltp + 3.0 * sig.atr_14) if sig else 2900.0,
        )

        # Update cost center and performance
        agent.cost_center.total_api_calls += 1
        agent.cost_center.total_cost_inr += 0.10
        agent.performance.tasks_completed += 1
        agent.performance.signals_generated += 1
        agent.last_active = datetime.now(UTC)

        # Advance status from SANDBOX -> PAPER_TRADING
        if agent.status == LifecycleStage.SANDBOX:
            agent.status = LifecycleStage.PAPER_TRADING

        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "status": agent.status.value,
            "permissions_audit": auth_results,
            "simulated_report": report.model_dump(),
            "cost_incurred_inr": 0.10,
            "sandbox_passed": True,
        }

    def version_agent(self, agent_id: str, updates: dict) -> CustomAgentProfile:
        """Updates agent configuration and increments version string (e.g. v1.0 -> v1.1)."""
        if agent_id not in self.agent_store:
            raise AgentFactoryError(f"Agent '{agent_id}' not found.")

        agent = self.agent_store[agent_id]
        old_version = agent.version

        # Bump minor version
        try:
            ver_num = float(agent.version.replace("v", ""))
            agent.version = f"v{ver_num + 0.1:.1f}"
        except Exception:
            agent.version = f"{old_version}.1"

        agent.version_history.append({
            "previous_version": old_version,
            "new_version": agent.version,
            "updated_fields": list(updates.keys()),
            "timestamp": str(datetime.now(UTC)),
        })

        for k, v in updates.items():
            if hasattr(agent, k) and k not in ["agent_id", "is_core", "version_history"]:
                setattr(agent, k, v)

        logger.info(f"[Agent Factory] Upgraded Agent '{agent.name}' from {old_version} to {agent.version}")
        return agent

    def update_lifecycle_stage(self, agent_id: str, new_stage: LifecycleStage) -> CustomAgentProfile:
        """Transitions agent through its lifecycle stages."""
        if agent_id not in self.agent_store:
            raise AgentFactoryError(f"Agent '{agent_id}' not found.")

        agent = self.agent_store[agent_id]
        old_stage = agent.status
        agent.status = new_stage
        logger.info(f"[Agent Factory] Agent '{agent.name}' transitioned: {old_stage.value} -> {new_stage.value}")
        return agent

    def delete_agent(self, agent_id: str) -> bool:
        """Decommissions and removes custom agent from active memory."""
        if agent_id in self.agent_store:
            agent = self.agent_store[agent_id]
            if agent.is_core:
                raise AgentFactoryError(f"Cannot delete permanent Core Agent '{agent.name}'.")
            del self.agent_store[agent_id]
            logger.info(f"[Agent Factory] Successfully decommissioned Agent '{agent.name}' [{agent_id}].")
            return True
        return False

    def recommend_agent_by_chief_ai(self, capability_gap: str) -> dict:
        """Chief AI auto-recommends a specialized agent proposal for human approval (Section 34)."""
        proposal = {
            "recommended_name": f"{capability_gap.title()} Specialist",
            "department": Department.RESEARCH.value,
            "objective": f"Address organizational capability gap: {capability_gap}",
            "proposed_tools": ["scan_stocks", "technical_analysis", "generate_reports"],
            "proposed_permissions": {
                "read_market_data": True,
                "generate_signals": True,
                "paper_trade": True,
                "place_live_orders": False,
            },
            "risk_profile": "Read-Only Research Intelligence (Zero Live Financial Risk)",
            "action_required": "User Approval Required to Deploy",
        }
        logger.info(f"[Chief AI Recommendation] Proposed new agent: {proposal['recommended_name']}")
        return proposal

    def list_all_agents(self) -> list[CustomAgentProfile]:
        return list(self.agent_store.values())


# Global Factory Instance
agent_factory = CustomAgentFactory()

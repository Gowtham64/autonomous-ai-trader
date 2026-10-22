"""
Skill Registry — Central Catalog, Dependency Resolver & Versioning Engine
"""

import inspect
import time
from collections.abc import Callable
from datetime import UTC, datetime

from core.logging import logger
from skills.library.advanced_skills import (
    ADVANCED_SKILLS,
    exec_crypto_academy_rules,
    exec_kronos_forecast,
    exec_laya_system_one_triage,
    exec_memory_similarity_search,
    exec_regime_classification,
    exec_system_health_diagnostic,
    exec_treasury_runway_calculation,
)
from skills.library.legendary_skills import (
    LEGENDARY_SKILLS,
    exec_bnf_disparity_analysis,
    exec_jhunjhunwala_conviction_analysis,
    exec_livermore_pivotal_analysis,
)
from skills.library.market import (
    MARKET_SKILLS,
    exec_live_price,
    exec_market_breadth,
    exec_universe_scanner,
    exec_volume_spike_scanner,
)
from skills.library.masters_trading_skills import (
    MASTERS_TRADING_SKILLS,
    exec_crypto_chart_patterns_analysis,
    exec_goodman_trend_analysis,
    exec_options_greeks_and_pricing,
    exec_options_spread_strategy,
    exec_price_action_candles_analysis,
    exec_turtle_breakout_analysis,
)
from skills.library.tauric_skills import (
    TAURIC_SKILLS,
    exec_five_tier_rating_audit,
    exec_polymarket_prediction_odds,
    exec_post_trade_reflection,
    exec_social_sentiment_stream,
    exec_three_way_risk_debate,
)
from skills.library.risk_portfolio_trading import (
    RISK_TRADING_SKILLS,
    exec_broker_funds_query,
    exec_order_validation,
    exec_position_sizing,
    exec_risk_veto_check,
)
from skills.library.technical import (
    TECHNICAL_SKILLS,
    exec_atr_volatility,
    exec_moving_averages,
    exec_rsi_analysis,
)
from skills.models import (
    SkillCategory,
    SkillDefinition,
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillRiskLevel,
    SkillStatus,
)


class SkillRegistry:
    """Centralized Skill Registry storing, versioning, and resolving modular agent skills."""

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}
        self._executors: dict[str, Callable] = {}
        self._version_history: dict[str, list[SkillDefinition]] = {}
        self._load_default_skills()

    def _load_default_skills(self):
        """Pre-populates the registry with institutional built-in skills and handlers."""
        # 1. Market & Scanner Skills
        self.register_skill(MARKET_SKILLS[0], exec_live_price)
        self.register_skill(MARKET_SKILLS[1], exec_market_breadth)
        self.register_skill(MARKET_SKILLS[2], exec_universe_scanner)
        self.register_skill(MARKET_SKILLS[3], exec_volume_spike_scanner)

        # 2. Technical Analysis Skills
        self.register_skill(TECHNICAL_SKILLS[0], exec_rsi_analysis)
        self.register_skill(TECHNICAL_SKILLS[1], exec_moving_averages)
        self.register_skill(TECHNICAL_SKILLS[2], exec_atr_volatility)

        # 3. Risk & Trading Skills
        self.register_skill(RISK_TRADING_SKILLS[0], exec_position_sizing)
        self.register_skill(RISK_TRADING_SKILLS[1], exec_risk_veto_check)
        self.register_skill(RISK_TRADING_SKILLS[2], exec_broker_funds_query)
        self.register_skill(RISK_TRADING_SKILLS[3], exec_order_validation)

        # 4. Advanced Memory & Diagnostics Skills
        self.register_skill(ADVANCED_SKILLS[0], exec_memory_similarity_search)
        self.register_skill(ADVANCED_SKILLS[1], exec_regime_classification)
        self.register_skill(ADVANCED_SKILLS[2], exec_treasury_runway_calculation)
        self.register_skill(ADVANCED_SKILLS[3], exec_system_health_diagnostic)
        self.register_skill(ADVANCED_SKILLS[4], exec_kronos_forecast)
        self.register_skill(ADVANCED_SKILLS[5], exec_laya_system_one_triage)
        self.register_skill(ADVANCED_SKILLS[6], exec_crypto_academy_rules)

        # 5. Legendary Master Skills (BNF, Jhunjhunwala, Livermore)
        self.register_skill(LEGENDARY_SKILLS[0], exec_bnf_disparity_analysis)
        self.register_skill(LEGENDARY_SKILLS[1], exec_jhunjhunwala_conviction_analysis)
        self.register_skill(LEGENDARY_SKILLS[2], exec_livermore_pivotal_analysis)

        # 6. Tauric Multi-Agent Skills (Polymarket, Post-Trade Reflection, 3-Way Risk, 5-Tier Rating, Social Sentiment)
        self.register_skill(TAURIC_SKILLS[0], exec_polymarket_prediction_odds)
        self.register_skill(TAURIC_SKILLS[1], exec_post_trade_reflection)
        self.register_skill(TAURIC_SKILLS[2], exec_three_way_risk_debate)
        self.register_skill(TAURIC_SKILLS[3], exec_five_tier_rating_audit)
        self.register_skill(TAURIC_SKILLS[4], exec_social_sentiment_stream)

        # 7. Advanced Masters Trading Skills (Bucek, Goodman, McCarthy)
        self.register_skill(MASTERS_TRADING_SKILLS[0], exec_turtle_breakout_analysis)
        self.register_skill(MASTERS_TRADING_SKILLS[1], exec_price_action_candles_analysis)
        self.register_skill(MASTERS_TRADING_SKILLS[2], exec_goodman_trend_analysis)
        self.register_skill(MASTERS_TRADING_SKILLS[3], exec_options_greeks_and_pricing)
        self.register_skill(MASTERS_TRADING_SKILLS[4], exec_options_spread_strategy)
        self.register_skill(MASTERS_TRADING_SKILLS[5], exec_crypto_chart_patterns_analysis)

        logger.info(f"[SkillRegistry] Successfully initialized with {len(self._skills)} institutional skills.")

    def register_skill(self, skill: SkillDefinition, executor: Callable | None = None) -> None:
        """Registers a new skill into the catalog with version tracking."""
        base_id = skill.skill_id.rsplit(".v", 1)[0]
        if base_id not in self._version_history:
            self._version_history[base_id] = []
        self._version_history[base_id].append(skill)

        self._skills[skill.skill_id] = skill
        if executor:
            self._executors[skill.skill_id] = executor

        logger.debug(f"[SkillRegistry] Registered skill: {skill.skill_id} ({skill.name})")

    def get_skill(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def list_skills(
        self,
        category: SkillCategory | None = None,
        risk_level: SkillRiskLevel | None = None,
        status: SkillStatus | None = None,
    ) -> list[SkillDefinition]:
        results = list(self._skills.values())
        if category:
            results = [s for s in results if s.category == category]
        if risk_level is not None:
            results = [s for s in results if s.risk_level <= risk_level]
        if status:
            results = [s for s in results if s.status == status]
        return results

    def verify_dependencies(self, skill_id: str) -> tuple[bool, list[str]]:
        """Verifies if all dependent skills for a given skill exist and are active in the registry."""
        skill = self.get_skill(skill_id)
        if not skill:
            return False, [f"Skill '{skill_id}' not found in registry."]

        missing = []
        for dep in skill.dependencies:
            dep_skill = self.get_skill(dep)
            if not dep_skill or dep_skill.status != SkillStatus.ACTIVE:
                missing.append(dep)

        return len(missing) == 0, missing

    async def execute_skill(self, request: SkillExecutionRequest) -> SkillExecutionResult:
        """Safe Execution Runtime enforcing schema validation, permissions, dependencies, and telemetry."""
        skill_id = request.skill_id
        skill = self.get_skill(skill_id)
        if not skill:
            return SkillExecutionResult(
                skill_id=skill_id,
                agent_id=request.agent_id or "unknown",
                status="FAILED",
                data=None,
                latency_ms=0.0,
                error=f"Skill '{skill_id}' does not exist in registry.",
            )

        if skill.status != SkillStatus.ACTIVE:
            return SkillExecutionResult(
                skill_id=skill_id,
                agent_id=request.agent_id or "unknown",
                status="FAILED",
                data=None,
                latency_ms=0.0,
                error=f"Skill '{skill_id}' is currently {skill.status.value}.",
            )

        # 1. Verify Dependencies
        deps_ok, missing_deps = self.verify_dependencies(skill_id)
        if not deps_ok:
            return SkillExecutionResult(
                skill_id=skill_id,
                agent_id=request.agent_id or "unknown",
                status="FAILED",
                data=None,
                latency_ms=0.0,
                error=f"Missing active skill dependencies: {missing_deps}",
            )

        # 2. Check Executor
        executor = self._executors.get(skill_id)
        if not executor:
            return SkillExecutionResult(
                skill_id=skill_id,
                agent_id=request.agent_id or "unknown",
                status="FAILED",
                data=None,
                latency_ms=0.0,
                error=f"No execution handler registered for '{skill_id}'.",
            )

        # 3. Execute with Timing & Metric Tracking
        start_time = time.perf_counter()
        try:
            if inspect.iscoroutinefunction(executor):
                res = await executor(request.parameters)
            else:
                res = executor(request.parameters)

            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            # Update Metrics
            skill.metrics.executions += 1
            skill.metrics.successful += 1
            skill.metrics.avg_latency_ms = round(
                ((skill.metrics.avg_latency_ms * (skill.metrics.executions - 1)) + latency_ms) / skill.metrics.executions,
                2,
            )
            skill.metrics.last_executed = datetime.now(UTC)
            skill.metrics.success_rate_pct = round(
                (skill.metrics.successful / skill.metrics.executions) * 100.0, 1
            )

            return SkillExecutionResult(
                skill_id=skill_id,
                agent_id=request.agent_id or "user",
                status="SUCCESS",
                data=res,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            skill.metrics.executions += 1
            skill.metrics.errors += 1
            skill.metrics.last_error = str(e)
            skill.metrics.last_executed = datetime.now(UTC)
            skill.metrics.success_rate_pct = round(
                (skill.metrics.successful / max(1, skill.metrics.executions)) * 100.0, 1
            )
            logger.error(f"[SkillRegistry] Execution failure in {skill_id}: {e}")
            return SkillExecutionResult(
                skill_id=skill_id,
                agent_id=request.agent_id or "user",
                status="FAILED",
                data=None,
                latency_ms=latency_ms,
                error=str(e),
            )

    def rollback_skill(self, base_id: str) -> SkillDefinition | None:
        """Rolls back a skill to its previous version if a problem is detected."""
        history = self._version_history.get(base_id, [])
        if len(history) >= 2:
            current = history.pop()
            previous = history[-1]
            # Replace active
            self._skills[previous.skill_id] = previous
            logger.warning(f"[SkillRegistry] Rolled back {base_id} from {current.version} to {previous.version}")
            return previous
        return None


# Global Singleton Skill Registry
skill_registry = SkillRegistry()

from pydantic import BaseModel

from core.treasury.models import ModelCostTier
from core.treasury.treasury import AITreasury, treasury


class AgentCostBenefit(BaseModel):
    agent_id: str
    name: str
    cost_inr: float
    value_generated_inr: float
    losses_prevented_inr: float
    roi_ratio: float
    is_safety_critical: bool
    recommendation: str


class AICFOAgent:
    """AI Chief Financial Officer & Cost Optimization Specialist (Sections 70–72).
    
    Monitors infrastructure burn, routes model tiers by task complexity,
    calculates agent economic value (including risk loss-prevention), and issues
    autonomous downsizing/cost-reduction recommendations.
    """

    def __init__(self, treasury_instance: AITreasury = treasury):
        self.treasury = treasury_instance

    def route_model_tier(self, task_type: str) -> ModelCostTier:
        """Assigns the most cost-efficient AI model tier based on task complexity (Section 71)."""
        # Low treasury forces cheaper models where appropriate
        if self.treasury.is_survival_mode:
            if task_type in ["format_json", "parse_text", "pre_filter"]:
                return ModelCostTier.LOW_COST
            return ModelCostTier.STANDARD

        tier_map = {
            "format_json": ModelCostTier.LOW_COST,
            "keyword_scan": ModelCostTier.LOW_COST,
            "sentiment_score": ModelCostTier.STANDARD,
            "technical_brief": ModelCostTier.STANDARD,
            "adversarial_debate": ModelCostTier.ADVANCED,
            "deep_fundamental_research": ModelCostTier.ADVANCED,
            "critical_trade_clearance": ModelCostTier.MULTI_MODEL,
        }
        return tier_map.get(task_type, ModelCostTier.STANDARD)

    def evaluate_agent_roi(
        self,
        agent_id: str,
        name: str,
        cost_inr: float,
        value_generated_inr: float,
        losses_prevented_inr: float,
        is_safety_critical: bool = False,
    ) -> AgentCostBenefit:
        """Calculates Agent Economic Value & ROI including risk mitigation credit (Section 72)."""
        effective_value = value_generated_inr + losses_prevented_inr
        roi = round(effective_value / max(0.01, cost_inr), 2)

        recommendation = "Maintain active operation"
        if not is_safety_critical:
            if cost_inr > 15.0 and roi < 1.0:
                recommendation = "Recommendation: Reduce execution frequency or migrate to cheaper model tier"
            elif cost_inr > 30.0 and roi < 0.5:
                recommendation = "Recommendation: Temporarily pause agent to preserve operating runway"
        else:
            recommendation = "Critical Safety Asset: Immutable active status regardless of direct P&L"

        return AgentCostBenefit(
            agent_id=agent_id,
            name=name,
            cost_inr=round(cost_inr, 2),
            value_generated_inr=round(value_generated_inr, 2),
            losses_prevented_inr=round(losses_prevented_inr, 2),
            roi_ratio=roi,
            is_safety_critical=is_safety_critical,
            recommendation=recommendation,
        )

    def get_financial_audit_report(self) -> dict:
        """Compiles organization financial health audit and runway forecast."""
        metrics = self.treasury.get_metrics()
        runway = metrics["estimated_runway_days"]

        status = "HEALTHY"
        if metrics["is_survival_mode"]:
            status = "CRITICAL_SURVIVAL"
        elif runway < 30.0:
            status = "WARNING_TIGHT_RUNWAY"

        return {
            "cfo_assessment": status,
            "treasury_metrics": metrics,
            "burn_rate_daily_inr": round(self.treasury.daily_operating_budget, 2),
            "estimated_runway_days": runway,
            "cost_saving_rules": [
                "Routing simple parsing tasks to LOW_COST tier",
                "Non-critical dynamic agents throttled in Survival Mode",
                "Operating and Upgrade reserves funded strictly from net trading surplus",
            ],
        }


# Global AI CFO instance
ai_cfo_agent = AICFOAgent()

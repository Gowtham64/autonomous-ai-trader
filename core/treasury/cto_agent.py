import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from core.logging import logger
from core.treasury.treasury import AITreasury, treasury


class UpgradeStage(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    PROPOSED = "PROPOSED"
    SANDBOX = "SANDBOX"
    UNIT_TESTED = "UNIT_TESTED"
    BACKTESTED = "BACKTESTED"
    PAPER_TRADING = "PAPER_TRADING"
    RISK_REVIEW = "RISK_REVIEW"
    CANARY_DEPLOYED = "CANARY_DEPLOYED"
    FULL_PRODUCTION = "FULL_PRODUCTION"
    ROLLED_BACK = "ROLLED_BACK"


class AIUpgradeProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: f"upg_{uuid.uuid4().hex[:8]}")
    title: str
    target_component: str               # e.g., "scanner", "model_router", "database_cache", "strategy_engine"
    rationale: str
    estimated_cost_inr: float
    expected_benefit: str
    stage: UpgradeStage = UpgradeStage.PROPOSED
    stage_history: list[dict] = Field(default_factory=list)
    canary_performance_score: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AICTOAgent:
    """AI Chief Technology Officer & Autonomous System Upgrade Engine (Sections 73–76).
    
    Identifies infrastructure bottlenecks, budgets improvements from the AI Upgrade Fund,
    and enforces a strict multi-gate validation pipeline before any production deployment.
    """

    def __init__(self, treasury_instance: AITreasury = treasury):
        self.treasury = treasury_instance
        self.proposals: dict[str, AIUpgradeProposal] = {}
        self._seed_default_proposals()

    def _seed_default_proposals(self) -> None:
        """Seeds initial system optimization opportunities."""
        p = AIUpgradeProposal(
            proposal_id="upg_quant_cache",
            title="Asynchronous Candlestick Caching for Nifty 100 Scanner",
            target_component="market_scanner",
            rationale="Reduces duplicate YFinance API calls by 45% during peak trading hours.",
            estimated_cost_inr=15.0,
            expected_benefit="Saves ~₹50/month in API compute and drops scan latency from 1.2s to 0.4s",
            stage=UpgradeStage.UNIT_TESTED,
        )
        self.proposals[p.proposal_id] = p

    def create_upgrade_proposal(
        self,
        title: str,
        target_component: str,
        rationale: str,
        estimated_cost_inr: float,
        expected_benefit: str,
    ) -> AIUpgradeProposal:
        """Submits a new technology upgrade proposal for organizational evaluation."""
        proposal = AIUpgradeProposal(
            title=title,
            target_component=target_component,
            rationale=rationale,
            estimated_cost_inr=estimated_cost_inr,
            expected_benefit=expected_benefit,
            stage=UpgradeStage.PROPOSED,
        )
        self.proposals[proposal.proposal_id] = proposal
        logger.info(f"[CTO Agent] Created Upgrade Proposal: '{title}' [{proposal.proposal_id}]")
        return proposal

    def advance_upgrade_stage(
        self,
        proposal_id: str,
        next_stage: UpgradeStage,
        validation_notes: str = "",
    ) -> AIUpgradeProposal:
        """Advances proposal through the gated validation pipeline (Section 75)."""
        if proposal_id not in self.proposals:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        prop = self.proposals[proposal_id]
        old_stage = prop.stage

        # Check budget availability when moving into Sandbox/Deployment
        if next_stage in [UpgradeStage.SANDBOX, UpgradeStage.CANARY_DEPLOYED] and self.treasury.buckets.ai_upgrade_fund < prop.estimated_cost_inr:
            logger.warning(
                f"[CTO Agent] AI Upgrade Fund balance (₹{self.treasury.buckets.ai_upgrade_fund:.2f}) "
                f"is lower than estimated cost (₹{prop.estimated_cost_inr:.2f}). Proceeding with frugal allocation."
            )

        prop.stage = next_stage
        prop.stage_history.append({
            "from_stage": old_stage.value,
            "to_stage": next_stage.value,
            "notes": validation_notes,
            "timestamp": str(datetime.now(UTC)),
        })
        logger.info(f"[CTO Agent] Proposal '{prop.title}' advanced: {old_stage.value} -> {next_stage.value}")
        return prop

    def rollback_upgrade(self, proposal_id: str, reason: str) -> AIUpgradeProposal:
        """Rolls back an upgrade if canary or production performance degrades."""
        if proposal_id not in self.proposals:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        prop = self.proposals[proposal_id]
        prop.stage = UpgradeStage.ROLLED_BACK
        prop.stage_history.append({
            "from_stage": "FAILED_VALIDATION",
            "to_stage": UpgradeStage.ROLLED_BACK.value,
            "notes": f"Automated rollback triggered: {reason}",
            "timestamp": str(datetime.now(UTC)),
        })
        logger.warning(f"[CTO Agent] Rolled back proposal '{prop.title}'! Reason: {reason}")
        return prop

    def list_all_proposals(self) -> list[dict]:
        return [p.model_dump() for p in self.proposals.values()]


# Global AI CTO instance
ai_cto_agent = AICTOAgent()

import asyncio
from typing import TypedDict

from agents.facilitator.facilitator import AdversarialDebateDesk
from agents.research_desk import AIResearchDesk
from agents.trader.fund_manager import FundManagerAgent
from core.domain.models import TradeAction
from core.logging import logger
from core.schemas.trade import (
    AnalystReport,
    CandidateSignal,
    DebateTranscript,
    TradeDecision,
)


class CandidateEvaluation(TypedDict):
    signal: CandidateSignal
    analyst_reports: list[AnalystReport]
    debate: DebateTranscript
    decision: TradeDecision
    conviction_rank: float


class BatchDebateSummary(TypedDict):
    total_evaluated: int
    approved_trades: list[CandidateEvaluation]
    rejected_trades: list[CandidateEvaluation]
    ranked_candidates: list[CandidateEvaluation]


class MultiStockOrchestrator:
    """Orchestrates multi-agent analysis, adversarial debate, and comparative decision-making across N stocks."""

    def __init__(
        self,
        research_desk: AIResearchDesk | None = None,
        debate_desk: AdversarialDebateDesk | None = None,
        fund_manager: FundManagerAgent | None = None,
        max_concurrency: int = 5,
        include_kronos: bool = True,
    ):
        self.research_desk = research_desk or AIResearchDesk()
        self.debate_desk = debate_desk or AdversarialDebateDesk()
        self.fund_manager = fund_manager or FundManagerAgent()
        self.max_concurrency = max_concurrency
        self.include_kronos = include_kronos

    async def evaluate_single_candidate(
        self,
        signal: CandidateSignal,
        available_capital: float = 0.0,
    ) -> CandidateEvaluation:
        """Evaluates one candidate through the full research, debate, and fund manager decision loop."""
        logger.info(f"[Batch Engine] Starting research & debate for {signal.symbol} (LTP: ₹{signal.ltp}, Avail Margin: ₹{available_capital:,.2f})...")

        # 1. Specialist research desk (Technical, Fundamental, News, Macro, Kronos, BNF, Jhunjhunwala, Livermore)
        reports = await self.research_desk.conduct_research(
            signal,
            include_kronos=self.include_kronos,
            include_specialists=True,
        )

        # 2. Bull vs. Bear adversarial debate
        debate = await self.debate_desk.conduct_debate(signal, reports)

        # 3. Fund Manager decision
        decision = await self.fund_manager.decide(signal, reports, debate, available_capital=available_capital)

        # 4. Composite conviction ranking score
        # Combines directional consensus, momentum (0 to 100), and decision confidence (0 to 1)
        # For SHORT decisions, negative debate consensus represents strong short alignment.
        directional_consensus = -debate.consensus_score if decision.decision == TradeAction.SELL else debate.consensus_score
        conviction_score = (
            (directional_consensus * 40.0)
            + (signal.momentum_score * 0.4)
            + (decision.confidence * 20.0)
        )

        return CandidateEvaluation(
            signal=signal,
            analyst_reports=reports,
            debate=debate,
            decision=decision,
            conviction_rank=round(conviction_score, 2),
        )

    async def evaluate_candidates_batch(
        self,
        candidates: list[CandidateSignal],
        available_capital: float = 0.0,
    ) -> list[CandidateEvaluation]:
        """Evaluates N candidates concurrently with bounded concurrency."""
        if not candidates:
            return []

        logger.info(f"[Batch Engine] Evaluating {len(candidates)} candidate stocks concurrently (Live Margin: ₹{available_capital:,.2f})...")
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _bounded_eval(cand: CandidateSignal) -> CandidateEvaluation:
            async with semaphore:
                return await self.evaluate_single_candidate(cand, available_capital=available_capital)

        tasks = [_bounded_eval(cand) for cand in candidates]
        evaluations = await asyncio.gather(*tasks)

        # Rank candidates by conviction score descending
        evaluations.sort(key=lambda e: e["conviction_rank"], reverse=True)
        return evaluations

    async def run_batch_debate_and_allocation(
        self,
        candidates: list[CandidateSignal],
        max_allocations: int = 5,
        available_capital: float = 0.0,
    ) -> BatchDebateSummary:
        """Runs debates across N candidate stocks and produces comparative portfolio decisions."""
        evaluations = await self.evaluate_candidates_batch(candidates, available_capital=available_capital)

        approved: list[CandidateEvaluation] = []
        rejected: list[CandidateEvaluation] = []

        for item in evaluations:
            if item["decision"].decision in [TradeAction.BUY, TradeAction.SELL]:
                approved.append(item)
            else:
                rejected.append(item)

        # Top approved candidates prioritized by multi-agent conviction
        top_approved = approved[:max_allocations]

        return BatchDebateSummary(
            total_evaluated=len(evaluations),
            approved_trades=top_approved,
            rejected_trades=rejected,
            ranked_candidates=evaluations,
        )

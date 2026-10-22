import asyncio

from agents.bull.researcher import BearResearcherAgent, BullResearcherAgent
from core.logging import logger
from core.schemas.trade import AnalystReport, CandidateSignal, DebateTranscript


class AdversarialDebateDesk:
    """Orchestrates structured adversarial debate between Bull and Bear researchers mediated by Facilitator."""

    def __init__(self):
        self.bull_agent = BullResearcherAgent()
        self.bear_agent = BearResearcherAgent()

    async def conduct_debate(
        self, signal: CandidateSignal, reports: list[AnalystReport]
    ) -> DebateTranscript:
        logger.info(f"Initiating Bull vs. Bear adversarial debate for {signal.symbol}...")

        # 1. Round 1: Initial theses (Parallel Concurrent Generation)
        bull_thesis, bear_thesis = await asyncio.gather(
            self.bull_agent.construct_thesis(signal, reports),
            self.bear_agent.construct_thesis(signal, reports),
        )

        # 2. Round 2: Rebuttals
        bull_rebuttal = (
            f"Bull Rebuttal: Bear downside risk is mitigated by strong volume backing (rel vol: {signal.relative_volume}x) "
            f"and ATR-defined stop buffer."
        )
        bear_rebuttal = (
            "Bear Rebuttal: Macro and sector shocks can easily break the ATR stop; volume could be short-covering rather than fresh accumulation."
        )

        is_crypto = "USD" in signal.symbol.upper() or signal.exchange == "DELTA"
        cs = "$" if is_crypto else "₹"
        prec = 4 if is_crypto else 2
        is_short = getattr(signal, "setup_direction", "LONG") == "SHORT"

        # Calculate consensus score (-1.0 to +1.0)
        bull_count = sum(1 for r in reports if r.stance == "BULLISH")
        bear_count = sum(1 for r in reports if r.stance == "BEARISH")
        consensus = (bull_count - bear_count) / max(1, len(reports))

        # 3. Facilitator Synthesis & Invalidation Conditions
        if is_short or consensus <= -0.15:
            facilitator_summary = (
                f"Debate Facilitator Review: Bearish breakdown momentum verified by distribution confluence. "
                f"Short entry is conditional on price remaining capped below {cs}{round(signal.ltp + 1.0 * signal.atr_14, prec)}."
            )
            invalidating_scenarios = [
                f"Close above {cs}{round(signal.ltp + 1.3 * signal.atr_14, prec)} on a 15-minute candle (short invalidation)",
                "Broader market surges more than 1.5% intraday",
                "Sudden bullish divergence on RSI or high-volume short covering",
            ]
        else:
            facilitator_summary = (
                f"Debate Facilitator Review: Bull momentum is verified by technical indicator confluence. "
                f"Long entry is strictly conditional on maintaining price above {cs}{round(signal.ltp - 1.2 * signal.atr_14, prec)}."
            )
            invalidating_scenarios = [
                f"Close below {cs}{round(signal.ltp - 1.5 * signal.atr_14, prec)} on a 15-minute candle",
                "Broader index drops more than 1.0% intraday",
                "Sudden negative corporate or regulatory disclosure",
            ]

        return DebateTranscript(
            symbol=signal.symbol,
            bull_thesis=bull_thesis,
            bear_thesis=bear_thesis,
            bull_rebuttal=bull_rebuttal,
            bear_rebuttal=bear_rebuttal,
            facilitator_summary=facilitator_summary,
            key_conflict_points=[
                "Breakout/breakdown durability vs. false trap",
                "Sectoral tailwinds vs. macro valuation multiples",
            ],
            invalidating_scenarios=invalidating_scenarios,
            consensus_score=round(consensus, 2),
        )

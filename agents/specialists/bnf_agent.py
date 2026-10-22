"""
Takashi Kotegawa (BNF) - Legendary Mean Reversion & Panic Scalper Agent.
Emulates the execution style of Takashi Kotegawa (BNF):
- Captures extreme oversold capitulation wicks deviating from 25-EMA (Kairi Index).
- Exploits liquidity vacuums and panic selling for violent 1-3% intraday bounces.
- Executes with detached zen emotional discipline.
"""

import pandas as pd

from agents.llm_router import router
from core.schemas.trade import AnalystReport, CandidateSignal
from core.tools.legendary_tools import legendary_tools


class BNFAgent:
    """Takashi Kotegawa (BNF) Specialist Agent."""

    def __init__(self):
        self.name = "Takashi Kotegawa (BNF)"
        self.role = "25-EMA Disparity & Panic Dip Master"
        self.department = "EXECUTION & MEAN REVERSION"

    async def analyze(self, signal: CandidateSignal, df: pd.DataFrame | None = None) -> AnalystReport:
        """Evaluates 25-EMA Disparity, Panic Exhaustion, and Mean Reversion setup."""
        if df is None or df.empty:
            # Synthetic candle mock for single point
            df = pd.DataFrame([{
                "High": signal.ltp * 1.01,
                "Low": signal.ltp * 0.99,
                "Close": signal.ltp,
                "Volume": signal.volume,
            }] * 30)

        disparity_analysis = legendary_tools.calculate_bnf_disparity(signal.symbol, df)

        def fallback() -> AnalystReport:
            stance = "BULLISH" if disparity_analysis.is_extreme_oversold else ("NEUTRAL" if disparity_analysis.disparity_pct < 0 else "BEARISH")
            conf = min(0.95, max(0.50, disparity_analysis.panic_exhaustion_score / 100.0))
            return AnalystReport(
                agent_name=self.name,
                symbol=signal.symbol,
                stance=stance,
                confidence=round(conf, 2),
                key_observations=[
                    f"BNF 25-EMA Disparity: {disparity_analysis.disparity_pct:+.2f}% (EMA25: ₹{disparity_analysis.ema_25:.2f})",
                    f"Panic Exhaustion Score: {disparity_analysis.panic_exhaustion_score:.1f}/100",
                    disparity_analysis.thesis_summary,
                ],
                risk_warnings=["Violent capitulation risk if support fails"],
                suggested_entry=signal.ltp,
                suggested_stop=disparity_analysis.stop_capitulation_price,
                suggested_target=disparity_analysis.target_bounce_price,
            )

        system_prompt = (
            "You are Takashi Kotegawa (BNF), the legendary Japanese day trader who turned $13,000 into $150+ Million.\n"
            "Your philosophy: Buy stocks that have violently collapsed and deviated significantly below their 25-day moving average (Kairi),\n"
            "enter on panic exhaustion, and take rapid mean-reversion profits back to the moving average without greed."
        )

        user_prompt = (
            f"Analyze {signal.symbol}:\n"
            f"LTP: ₹{signal.ltp}\n"
            f"25-EMA Disparity: {disparity_analysis.disparity_pct:+.2f}%\n"
            f"Panic Exhaustion Score: {disparity_analysis.panic_exhaustion_score}/100\n"
            f"Relative Volume: {signal.relative_volume}x\n"
            f"Target Bounce: ₹{disparity_analysis.target_bounce_price}, Stop: ₹{disparity_analysis.stop_capitulation_price}\n"
            f"Provide your structured trading assessment."
        )

        return await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback_factory=fallback,
        )


bnf_agent = BNFAgent()

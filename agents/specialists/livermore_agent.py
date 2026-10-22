"""
Jesse Livermore - Legendary Speculator & Pivotal Point Tape Reading Agent.
Emulates the speculative mastery of Jesse Livermore:
- Trades only along the Line of Least Resistance.
- Enters exclusively at Pivotal Points with explosive volume confirmation.
- Uses Pilot Probe Order sizing (30% initial stake) and ruthlessly cuts losses at invalidation.
"""

import pandas as pd

from agents.llm_router import router
from core.schemas.trade import AnalystReport, CandidateSignal
from core.tools.legendary_tools import legendary_tools


class LivermoreAgent:
    """Jesse Livermore Specialist Agent."""

    def __init__(self):
        self.name = "Jesse Livermore"
        self.role = "Pivotal Point Speculation & Tape Reading Master"
        self.department = "TAPE READING & SPECULATION"

    async def analyze(self, signal: CandidateSignal, df: pd.DataFrame | None = None) -> AnalystReport:
        """Evaluates Pivotal Points, Line of Least Resistance, and Pilot Order parameters."""
        if df is None or df.empty:
            df = pd.DataFrame([{
                "High": signal.ltp * 1.015,
                "Low": signal.ltp * 0.985,
                "Close": signal.ltp,
                "Volume": signal.volume,
            }] * 30)

        pivotal_analysis = legendary_tools.calculate_livermore_pivotal_points(signal.symbol, df)

        def fallback() -> AnalystReport:
            stance = "BULLISH" if (pivotal_analysis.line_of_least_resistance == "UPWARD" or pivotal_analysis.is_pivotal_breakout) else "NEUTRAL"
            conf = 0.88 if pivotal_analysis.is_pivotal_breakout else (0.72 if pivotal_analysis.line_of_least_resistance == "UPWARD" else 0.50)
            return AnalystReport(
                agent_name=self.name,
                symbol=signal.symbol,
                stance=stance,
                confidence=round(conf, 2),
                key_observations=[
                    f"Line of Least Resistance: {pivotal_analysis.line_of_least_resistance}",
                    f"Pivotal Resistance: ₹{pivotal_analysis.pivotal_resistance:.2f} | Support: ₹{pivotal_analysis.pivotal_support:.2f}",
                    f"Tape Volume Multiplier: {pivotal_analysis.volume_surge_multiplier:.2f}x",
                    f"Pivotal Breakout: {'CONFIRMED (Deploy 30% Pilot)' if pivotal_analysis.is_pivotal_breakout else 'Awaiting Breakout'}",
                    f"Confirmation Add Level: ₹{pivotal_analysis.confirmation_add_level:.2f}",
                    pivotal_analysis.thesis_summary,
                ],
                risk_warnings=["False pivotal breakout trap; exit immediately if price drops below support"],
                suggested_entry=signal.ltp,
                suggested_stop=pivotal_analysis.stop_invalidation_level,
                suggested_target=round(pivotal_analysis.pivotal_resistance * 1.08, 2),
            )

        system_prompt = (
            "You are Jesse Livermore, the greatest tape reader and speculator in financial market history.\n"
            "Your philosophy: The market is never wrong; opinions often are.\n"
            "Never anticipate a breakout — wait for the stock to cross its Pivotal Point with heavy tape volume.\n"
            "Take an initial 30% pilot probe position, add on confirmation, and ruthlessly cut losses at once if the tape fails."
        )

        user_prompt = (
            f"Analyze the tape for {signal.symbol}:\n"
            f"LTP: ₹{signal.ltp}\n"
            f"Pivotal Resistance: ₹{pivotal_analysis.pivotal_resistance}\n"
            f"Pivotal Support: ₹{pivotal_analysis.pivotal_support}\n"
            f"Line of Least Resistance: {pivotal_analysis.line_of_least_resistance}\n"
            f"Volume Tape: {pivotal_analysis.volume_surge_multiplier}x\n"
            f"Breakout State: {pivotal_analysis.is_pivotal_breakout}\n"
            f"Provide your structured speculative trading verdict."
        )

        return await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback_factory=fallback,
        )


livermore_agent = LivermoreAgent()

"""
Rakesh Jhunjhunwala - Big Bull Indian Macro, Moat & Conviction Pyramiding Agent.
Emulates the investment philosophy of the Big Bull of Dalal Street:
- Structural bullishness on the India growth story (CAPEX, Infrastructure, Banking, PSU, Manufacturing).
- High conviction sizing with aggressive pyramiding on winning trades.
- Holding winners to maximize compound gains rather than booking micro-profits prematurely.
"""

import pandas as pd

from agents.llm_router import router
from core.schemas.trade import AnalystReport, CandidateSignal
from core.tools.legendary_tools import legendary_tools


class JhunjhunwalaAgent:
    """Rakesh Jhunjhunwala Specialist Agent."""

    def __init__(self):
        self.name = "Rakesh Jhunjhunwala"
        self.role = "India Supercycle & Conviction Pyramiding Master"
        self.department = "MACRO STRATEGY & FUNDAMENTALS"

    async def analyze(self, signal: CandidateSignal, df: pd.DataFrame | None = None) -> AnalystReport:
        """Evaluates Indian Macro Supercycle, Trend Longevity, and Pyramiding Viability."""
        if df is None or df.empty:
            df = pd.DataFrame([{
                "High": signal.ltp * 1.02,
                "Low": signal.ltp * 0.98,
                "Close": signal.ltp,
                "Volume": signal.volume,
            }] * 50)

        jhunjhunwala_analysis = legendary_tools.calculate_jhunjhunwala_conviction(signal.symbol, df, sector=signal.sector)

        def fallback() -> AnalystReport:
            stance = "BULLISH" if jhunjhunwala_analysis.conviction_tier in ["ULTRA_HIGH_CONVICTION", "HIGH"] else "NEUTRAL"
            conf = min(0.98, max(0.60, (jhunjhunwala_analysis.sector_tailwinds_score + jhunjhunwala_analysis.trend_longevity_score) / 200.0))
            return AnalystReport(
                agent_name=self.name,
                symbol=signal.symbol,
                stance=stance,
                confidence=round(conf, 2),
                key_observations=[
                    f"Big Bull Conviction Tier: {jhunjhunwala_analysis.conviction_tier}",
                    f"Sector Tailwinds: {jhunjhunwala_analysis.sector_tailwinds_score:.0f}/100 in {signal.sector}",
                    f"Trend Longevity: {jhunjhunwala_analysis.trend_longevity_score:.0f}/100",
                    f"Pyramiding Permitted: {'YES (Trigger ₹' + str(jhunjhunwala_analysis.pyramid_trigger_price) + ')' if jhunjhunwala_analysis.pyramid_permitted else 'NO'}",
                    jhunjhunwala_analysis.thesis_summary,
                ],
                risk_warnings=["Macro geopolitical shock or sudden rate cycle pivot"],
                suggested_entry=signal.ltp,
                suggested_stop=round(signal.ltp * 0.96, 2),
                suggested_target=round(signal.ltp * 1.15, 2),
            )

        system_prompt = (
            "You are Rakesh Jhunjhunwala, the legendary Big Bull of Indian stock markets.\n"
            "Your philosophy: Uncompromising structural bullishness on India's demographic and economic expansion.\n"
            "You seek market leaders with deep moats in core sectors (Banking, PSU, Infra, Manufacturing),\n"
            "build massive high-conviction stakes, and pyramid aggressively into winning compounders."
        )

        user_prompt = (
            f"Analyze {signal.symbol} ({signal.sector}):\n"
            f"LTP: ₹{signal.ltp}\n"
            f"Sector Tailwinds: {jhunjhunwala_analysis.sector_tailwinds_score}/100\n"
            f"Trend Longevity: {jhunjhunwala_analysis.trend_longevity_score}/100\n"
            f"Conviction Tier: {jhunjhunwala_analysis.conviction_tier}\n"
            f"Pyramid Level: ₹{jhunjhunwala_analysis.pyramid_trigger_price}\n"
            f"Provide your structured investment & trading verdict."
        )

        return await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback_factory=fallback,
        )


jhunjhunwala_agent = JhunjhunwalaAgent()

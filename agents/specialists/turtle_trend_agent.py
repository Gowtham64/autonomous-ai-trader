"""
Turtle & Trend Specialist Agent (Buček, Dennis & Goodman).
Synthesizes:
1. Ondřej Buček & Richard Dennis: Turtle Donchian Systems (20-day / 55-day), Volatility N Sizing, 2N Stops, Pyramiding.
2. Ondřej Buček: Price Action Pinbars (Hammer & Shooting Star ratios >= 0.70 at swing points).
3. Glen Goodman (The Crypto Trader):
   - 4 Golden Rules: Trade the Trend, Grow Profits, Cut Losses, Control the Voices.
   - Never Chase Breakouts (>5% rule).
   - Basing patterns & Horizontal right-angled triangles.
   - Chandelier ATR & 200-MA Trailing Stops.
   - Cognitive Biases Guard (FOMO, Sunk Cost, Falling Knife, Disposition Effect).
"""

import pandas as pd
from agents.llm_router import router
from core.schemas.trade import AnalystReport, CandidateSignal
from core.tools.advanced_masters_tools import BucekTurtleEngine, GoodmanTrendEngine


class TurtleTrendSpecialistAgent:
    """Specialist Agent embodying Turtle Rules, Price Action, and Glen Goodman's Trend Discipline."""

    def __init__(self):
        self.name = "Turtle & Trend Specialist (Goodman/Buček)"
        self.role = "Trend-Following Mastery, Volatility Sizing & Psychological Discipline"
        self.department = "TREND & VOLATILITY"

    async def analyze(
        self,
        signal: CandidateSignal,
        df: pd.DataFrame | None = None,
        deposit: float = 2000.0,
        risk_pct: float = 0.01,
    ) -> AnalystReport:
        """Evaluates Turtle breakout signals, Price Action pinbars, and Goodman trend discipline."""
        ltp = signal.ltp or 100.0

        if df is None or df.empty:
            df = pd.DataFrame({
                "Open": [ltp * (1.0 + (i * 0.002)) for i in range(40)],
                "High": [ltp * (1.015 + (i * 0.002)) for i in range(40)],
                "Low": [ltp * (0.985 + (i * 0.002)) for i in range(40)],
                "Close": [ltp * (1.005 + (i * 0.002)) for i in range(40)],
                "Volume": [max(1000, signal.volume or 10000)] * 40,
            })

        # 1. Evaluate Buček Turtle System 1 & 2
        turtle_metrics = BucekTurtleEngine.calculate_turtle_metrics(
            symbol=signal.symbol,
            df=df,
            deposit=deposit,
            risk_pct=risk_pct,
        )

        # 2. Evaluate Buček Price Action (Hammer / Shooting Star)
        pa_metrics = BucekTurtleEngine.calculate_price_action_patterns(
            symbol=signal.symbol,
            df=df,
        )

        # 3. Evaluate Glen Goodman Trend & Anti-Chase Discipline
        goodman_metrics = GoodmanTrendEngine.evaluate_trend_and_discipline(
            symbol=signal.symbol,
            df=df,
        )

        def fallback() -> AnalystReport:
            # Determine stance based on confluence
            is_bullish = (
                turtle_metrics.system1_entry_long
                or turtle_metrics.system2_entry_long
                or pa_metrics.is_hammer_bullish
                or (goodman_metrics.is_trend_intact and signal.momentum_score > 40)
            )
            is_bearish = (
                turtle_metrics.system1_entry_short
                or turtle_metrics.system2_entry_short
                or pa_metrics.is_shooting_star_bearish
                or (not goodman_metrics.is_trend_intact and signal.momentum_score < -20)
            )

            # Goodman Veto: If chasing breakout >5% or reversal rejection
            if goodman_metrics.is_chasing_breakout:
                stance = "NEUTRAL"
                conf = 0.30
            elif is_bullish:
                stance = "BULLISH"
                conf = 0.85 if (goodman_metrics.is_trend_intact and goodman_metrics.has_volume_confirmation) else 0.70
            elif is_bearish:
                stance = "BEARISH"
                conf = 0.75
            else:
                stance = "NEUTRAL"
                conf = 0.50

            # Stop loss & Target selection
            stop = goodman_metrics.recommended_stop
            if stance == "BULLISH":
                entry = ltp
                target = round(ltp + (abs(ltp - stop) * 2.0), 2)
            elif stance == "BEARISH":
                entry = ltp
                target = round(ltp - (abs(stop - ltp) * 2.0), 2)
            else:
                entry = ltp
                target = ltp

            observations = [
                f"Turtle Volatility N: ₹{turtle_metrics.volatility_n:.2f} | 1 Unit Sizing: {turtle_metrics.unit_size} shares",
                f"Turtle Breakout State: {turtle_metrics.recommendation} (Long 2N Stop: ₹{turtle_metrics.stop_loss_long:.2f})",
                f"Price Action Pinbar: {pa_metrics.signal_type} (Hammer: {pa_metrics.hammer_ratio:.2f}, Shooting Star: {pa_metrics.shooting_star_ratio:.2f})",
                f"Goodman Trend Status: {'INTACT' if goodman_metrics.is_trend_intact else 'BENT'} (200-SMA: ₹{goodman_metrics.ma_200_trailing_stop:.2f})",
                f"Goodman Chandelier Stop: ₹{goodman_metrics.chandelier_trailing_stop:.2f} (Highest - 3.5x ATR)",
                f"Breakout Chase Guard: {'VIOLATION (>5% extension)' if goodman_metrics.is_chasing_breakout else 'CLEAN (<= 5% of base)'}",
                f"Risk Parity Sizing Multiplier: {goodman_metrics.risk_parity_size_multiplier}x based on 30-day ATR",
                turtle_metrics.rationale,
                goodman_metrics.rationale,
            ]

            warnings = list(goodman_metrics.cognitive_bias_warnings)
            if turtle_metrics.system1_exit_long or turtle_metrics.system2_exit_long:
                warnings.append("Turtle Donchian exit threshold breached — close long immediately.")

            return AnalystReport(
                agent_name=self.name,
                symbol=signal.symbol,
                stance=stance,
                confidence=round(conf, 2),
                key_observations=observations,
                risk_warnings=warnings or ["Monitor Chandelier stop closely for trend bend"],
                suggested_entry=entry,
                suggested_stop=stop,
                suggested_target=target,
            )

        system_prompt = (
            "You are the Turtle & Trend Specialist Agent, combining Richard Dennis, Ondřej Buček, and Glen Goodman.\n"
            "Your Tenets:\n"
            "1. Trade the Trend until it bends: In an uptrend, let profits run and sit tight.\n"
            "2. Never Chase Breakouts: If price is >5% above the breakout level, REJECT the trade to prevent FOMO.\n"
            "3. Cut Losses Fast: Use 2N volatility stops or Chandelier Trailing Stops without hesitation.\n"
            "4. Control Cognitive Biases: Eliminate Sunk-Cost Fallacy, Anchoring, and the Disposition Effect.\n"
            "5. Volatility-Scaled Sizing: Allocate capital inversely to ATR (Risk Parity).\n"
            "Provide your structured trend evaluation."
        )

        user_prompt = (
            f"Analyze trend structure for {signal.symbol}:\n"
            f"LTP: ₹{ltp}\n"
            f"Turtle Recommendation: {turtle_metrics.recommendation} | Volatility N: ₹{turtle_metrics.volatility_n}\n"
            f"Price Action Pinbars: Hammer {pa_metrics.hammer_ratio:.2f}, Shooting Star {pa_metrics.shooting_star_ratio:.2f}\n"
            f"Goodman Breakout Chasing: {goodman_metrics.is_chasing_breakout}\n"
            f"Goodman Chandelier Stop: ₹{goodman_metrics.chandelier_trailing_stop}\n"
            f"Cognitive Warnings: {goodman_metrics.cognitive_bias_warnings}\n"
            f"Deliver your formal specialist report."
        )

        return await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback_factory=fallback,
        )


turtle_trend_agent = TurtleTrendSpecialistAgent()

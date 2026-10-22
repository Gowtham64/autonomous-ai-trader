"""
Christopher M. McCarthy Options Specialist Agent.
Implements the options analysis, pricing models, and defined-risk spread mechanics from:
"Options Unlocked: Your Key to Learning Options Fast & Trading Like a Pro" (Christopher M. McCarthy).

Core Competencies:
1. Option Greeks evaluation: Delta, Gamma, Theta, Vega, Rho
2. Multi-Model pricing: Black-Scholes, Binomial Tree (American/European), and Monte Carlo projection
3. Multi-Leg Defined-Risk Spreads:
   - Bull Call Spreads & Bear Put Spreads (Directional with capped debit)
   - Covered Calls & Protective Puts (Hedging & income generation)
   - Iron Condor & Butterfly Spreads (Neutral range income harvest)
   - Jade Lizard (Skewed theta play with zero upside risk)
   - Straddles & Strangles (Explosive volatility expansion around news/earnings)
4. Strict Risk Safeguards:
   - Zero naked calls/puts (strictly prohibited on scarce bootstrap capital)
   - Mandatory Open Interest & Bid-Ask spread liquidity verification
   - Volatility crush avoidance into major economic/earnings announcements
"""

import pandas as pd
from agents.llm_router import router
from core.schemas.trade import AnalystReport, CandidateSignal
from core.tools.advanced_masters_tools import McCarthyOptionsEngine


class OptionsSpecialistAgent:
    """Specialist Options Analyst & Derivatives Strategist."""

    def __init__(self):
        self.name = "Options Specialist (McCarthy)"
        self.role = "Derivatives Risk, Greeks & Defined-Risk Spreads Master"
        self.department = "DERIVATIVES & HEDGING"

    async def analyze(
        self,
        signal: CandidateSignal,
        df: pd.DataFrame | None = None,
        implied_volatility: float = 0.25,
        days_to_expiry: int = 30,
    ) -> AnalystReport:
        """
        Analyzes options opportunities, computes Black-Scholes Greeks,
        and constructs the optimal defined-risk spread matching the market regime.
        """
        spot = signal.ltp or 100.0
        iv = max(0.10, implied_volatility)

        # 1. Compute ATM Greeks
        greeks_call = McCarthyOptionsEngine.calculate_black_scholes_greeks(
            spot=spot,
            strike=spot,
            time_to_expiry_years=days_to_expiry / 365.0,
            volatility=iv,
            is_call=True,
        )

        # 2. Select appropriate strategy based on signal regime and momentum
        regime_val = signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime)
        if "BULL" in regime_val.upper() or signal.momentum_score >= 55:
            strat_choice = "BULL_CALL_SPREAD"
            stance = "BULLISH"
        elif "BEAR" in regime_val.upper() or signal.momentum_score <= -20:
            strat_choice = "BEAR_PUT_SPREAD"
            stance = "BEARISH"
        elif "HIGH_VOLATILITY" in regime_val.upper():
            strat_choice = "LONG_STRADDLE"
            stance = "VOLATILITY"
        else:
            strat_choice = "IRON_CONDOR"
            stance = "NEUTRAL"

        spread_eval = McCarthyOptionsEngine.evaluate_spread_strategy(
            strategy_name=strat_choice,
            spot=spot,
            implied_volatility=iv,
            days_to_expiry=days_to_expiry,
        )

        def fallback() -> AnalystReport:
            conf = min(0.92, max(0.50, spread_eval.probability_of_profit))
            observations = [
                f"Options Model: {spread_eval.strategy_name} ({spread_eval.outlook})",
                f"ATM Call Delta: {greeks_call.delta:.3f} | Theta/day: ₹{greeks_call.theta_per_day:.3f} | Vega/1%: ₹{greeks_call.vega_per_pct:.3f}",
                f"Net Premium: {'Credit' if spread_eval.net_premium > 0 else 'Debit'} ₹{abs(spread_eval.net_premium):.2f}",
                f"Max Profit: ₹{spread_eval.max_profit:.2f} | Max Loss: ₹{spread_eval.max_loss:.2f}",
                f"Breakeven: {spread_eval.breakeven}",
                f"Probability of Profit (POP): {spread_eval.probability_of_profit * 100:.1f}%",
                f"Greeks Risk Rule: Theta decay accelerates rapidly when DTE < 30. Manage winners at 50% max profit.",
                spread_eval.audit_notes,
            ]
            warnings = []
            if not spread_eval.is_liquid_and_safe:
                warnings.append("Illiquid options chain or unbalanced risk profile detected.")
            if days_to_expiry <= 7:
                warnings.append("High Gamma risk: Near-term expiry exhibits steep curvature volatility.")

            entry = spot
            stop = spread_eval.breakeven[0] if spread_eval.breakeven else spot * 0.95
            target = spot * 1.05 if stance == "BULLISH" else spot * 0.95

            return AnalystReport(
                agent_name=self.name,
                symbol=signal.symbol,
                stance=stance,
                confidence=round(conf, 2),
                key_observations=observations,
                risk_warnings=warnings or ["Monitor implied volatility crush post-event"],
                suggested_entry=entry,
                suggested_stop=stop,
                suggested_target=target,
            )

        system_prompt = (
            "You are Christopher M. McCarthy, author of 'Options Unlocked' and expert institutional options strategist.\n"
            "Your Core Principles:\n"
            "1. Risk Management First: Never trade without a defined plan, bounded max loss, and strict stop loss.\n"
            "2. Greeks Awareness: Delta is direction and probability proxy; Gamma accelerates near expiry; "
            "Theta is daily decay; Vega rules volatility expansions/crushes.\n"
            "3. Defined-Risk Spreads: Never sell naked options. Use vertical spreads, Iron Condors, or Jade Lizards.\n"
            "4. Liquidity & Spreads: Always verify adequate Open Interest and tight bid-ask spreads before entry.\n"
            "Provide your structured derivatives verdict."
        )

        user_prompt = (
            f"Analyze options structure for {signal.symbol}:\n"
            f"Spot Price: ₹{spot}\n"
            f"Market Regime: {regime_val}\n"
            f"Proposed Spread: {spread_eval.strategy_name}\n"
            f"Net Premium: ₹{spread_eval.net_premium} | Max Loss: ₹{spread_eval.max_loss}\n"
            f"ATM Delta: {greeks_call.delta} | Theta/day: ₹{greeks_call.theta_per_day}\n"
            f"Probability of Profit: {spread_eval.probability_of_profit * 100:.1f}%\n"
            f"Deliver your formal options specialist report."
        )

        return await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback_factory=fallback,
        )


options_specialist_agent = OptionsSpecialistAgent()

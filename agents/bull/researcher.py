from core.schemas.trade import AnalystReport, CandidateSignal


class BullResearcherAgent:
    """Specialist Bull Researcher formulating the strongest upside opportunity thesis (or short counter-thesis)."""

    async def construct_thesis(self, signal: CandidateSignal, reports: list[AnalystReport]) -> str:
        is_crypto = "USD" in signal.symbol.upper() or signal.exchange == "DELTA"
        cs = "$" if is_crypto else "₹"
        is_short = getattr(signal, "setup_direction", "LONG") == "SHORT"
        kronos_rep = next((r for r in reports if "Kronos" in r.agent_name), None)
        kronos_note = ""
        if kronos_rep and kronos_rep.stance == "BULLISH":
            obs = kronos_rep.key_observations[1] if len(kronos_rep.key_observations) > 1 else "positive trajectory"
            kronos_note = f" Kronos foundation model confirms bullish momentum ({obs})."

        if is_short:
            return (
                f"BULL COUNTER-THESIS for {signal.symbol}: Potential oversold bounce or bear trap risk near current support.{kronos_note} "
                f"Intraday short-covering could trigger sudden upside spikes. Price must remain capped below {cs}{round(signal.ltp + 1.2 * signal.atr_14, 4)}."
            )

        return (
            f"BULL THESIS for {signal.symbol}: Strong momentum setup with momentum score of {signal.momentum_score}/100. "
            f"Analyst consensus indicates supportive institutional flows and resilient macro conditions.{kronos_note} "
            f"Targeting {cs}{round(signal.ltp + 2.5 * signal.atr_14, 4)} with favorable risk/reward."
        )


class BearResearcherAgent:
    """Specialist Bear Researcher aggressively searching for short opportunities or long risks."""

    async def construct_thesis(self, signal: CandidateSignal, reports: list[AnalystReport]) -> str:
        is_crypto = "USD" in signal.symbol.upper() or signal.exchange == "DELTA"
        cs = "$" if is_crypto else "₹"
        is_short = getattr(signal, "setup_direction", "LONG") == "SHORT"
        kronos_rep = next((r for r in reports if "Kronos" in r.agent_name), None)
        kronos_warning = ""
        if kronos_rep and kronos_rep.stance in ["BEARISH", "NEUTRAL"]:
            kronos_warning = f" Kronos foundation model warns of {kronos_rep.stance.lower()} stagnation or breakdown trajectory."

        if is_short:
            return (
                f"BEAR SHORT THESIS for {signal.symbol}: Confirmed breakdown momentum with score {signal.momentum_score}/100.{kronos_warning} "
                f"Institutional distribution and heavy sell volume suggest line of least resistance is DOWNWARD. "
                f"Targeting downside expansion to {cs}{round(signal.ltp - 2.5 * signal.atr_14, 4)} with tight invalidation at {cs}{round(signal.ltp + 1.0 * signal.atr_14, 4)}."
            )

        return (
            f"BEAR COUNTER-THESIS for {signal.symbol}: Potential false breakout risk near current resistance.{kronos_warning} "
            f"Intraday market volatility or broader sector shakeout could trigger premature stop loss hits. "
            f"Critical downside support at {cs}{round(signal.ltp - 1.5 * signal.atr_14, 4)} must hold to prevent liquidation."
        )

"""
Final Pre-Trade Profit Expectancy Gate.

The last deterministic check before position sizing: a trade is only allowed when its
mathematical expected value is positive AFTER round-trip fees, with a safety buffer.

    EV per unit = p_win * reward_distance  -  (1 - p_win) * stop_distance  -  fees

p_win is estimated conservatively from multi-agent confluence (technical stance,
Kronos foundation-model direction, debate consensus). If the expected value is not
clearly positive, the trade is skipped and the scanner keeps evaluating other
candidates — no capital is deployed on coin-flips.
"""

from core.config.settings import settings
from core.domain.models import TradeAction
from core.logging import logger
from core.schemas.trade import AnalystReport, CandidateSignal, DebateTranscript, TradeDecision


class ExpectancyGate:
    """Deterministic positive-expectancy verification for every candidate trade."""

    # p_win is deliberately conservative: an unproven signal starts BELOW a coin-flip
    BASE_WIN_PROBABILITY = 0.45
    MIN_WIN_PROBABILITY = 0.30
    MAX_WIN_PROBABILITY = 0.72
    # A trade must show REAL confluence, not just a favorable R:R ratio: without this,
    # any 2:1 setup is "positive EV" even at a 43% estimated win rate.
    REQUIRED_WIN_PROBABILITY = 0.55

    @staticmethod
    def evaluate(
        decision: TradeDecision,
        signal: CandidateSignal,
        debate: DebateTranscript,
        reports: list[AnalystReport],
        is_crypto: bool,
        history_adjustment: float = 0.0,
        required_p_override: float | None = None,
    ) -> tuple[bool, str, dict]:
        entry = decision.entry_price or signal.ltp
        sl = decision.stop_loss or 0.0
        tgt = decision.target_1 or 0.0

        if not entry or not sl or not tgt:
            return False, "Missing entry/stop/target — profitability cannot be verified.", {}

        is_sell = decision.decision == TradeAction.SELL
        stop_dist = (sl - entry) if is_sell else (entry - sl)
        reward_dist = (entry - tgt) if is_sell else (tgt - entry)

        if stop_dist <= 0 or reward_dist <= 0:
            return False, "Invalid stop/target geometry for trade direction.", {}

        rr = reward_dist / stop_dist
        if round(rr, 2) < (settings.MIN_RISK_REWARD_RATIO - 0.05):
            return False, f"Risk:Reward {rr:.2f} below required {settings.MIN_RISK_REWARD_RATIO:.1f}.", {"rr": round(rr, 2)}

        # --- Estimate win probability from multi-agent confluence ---
        want_stance = "BEARISH" if is_sell else "BULLISH"
        against_stance = "BULLISH" if is_sell else "BEARISH"

        tech = next((r for r in reports if "Technical" in r.agent_name), None)
        kron = next((r for r in reports if "Kronos" in r.agent_name), None)
        news = next((r for r in reports if "News" in r.agent_name), None)
        sent = next((r for r in reports if "Sentiment" in r.agent_name), None)

        p = ExpectancyGate.BASE_WIN_PROBABILITY
        factors = []

        if tech is not None:
            if tech.stance == want_stance:
                p += 0.07
                factors.append("technical aligned (+0.07)")
            elif tech.stance == against_stance:
                p -= 0.08
                factors.append("technical OPPOSED (-0.08)")

        if kron is not None:
            if kron.stance == want_stance:
                p += 0.07
                factors.append("kronos aligned (+0.07)")
                if kron.confidence >= 0.80:
                    p += 0.04
                    factors.append("kronos high-confidence (+0.04)")
            elif kron.stance == against_stance:
                p -= 0.10
                factors.append("kronos OPPOSED (-0.10)")

        if news is not None and news.stance == want_stance:
            p += 0.04
            factors.append("news aligned (+0.04)")
        if sent is not None and sent.stance == want_stance:
            p += 0.03
            factors.append("sentiment aligned (+0.03)")

        # Debate consensus: positive favors longs, negative favors shorts
        aligned_consensus = -debate.consensus_score if is_sell else debate.consensus_score
        consensus_adj = max(-0.08, min(0.08, aligned_consensus * 0.10))
        p += consensus_adj
        factors.append(f"consensus {aligned_consensus:+.2f} ({consensus_adj:+.3f})")

        # LEARNING FEEDBACK: completed-trade history shifts the estimate.
        # Symbols that have been winning earn a small bonus; symbols that have been
        # losing are penalized harder (losses teach more than wins).
        if history_adjustment != 0.0:
            p += history_adjustment
            factors.append(f"learned-from-history ({history_adjustment:+.3f})")

        p = max(ExpectancyGate.MIN_WIN_PROBABILITY, min(ExpectancyGate.MAX_WIN_PROBABILITY, p))

        # --- Round-trip friction per unit of the asset ---
        if is_crypto:
            # Delta taker fee 0.05% each side + slippage allowance
            fee_per_unit = (entry + tgt) * 0.0005 + entry * 0.0003
        else:
            # Indian equity intraday: brokerage + STT + exchange + GST + stamp (approx)
            fee_per_unit = entry * 0.0015

        ev_per_unit = (p * reward_dist) - ((1.0 - p) * stop_dist) - fee_per_unit
        # Require EV to clear fees with a 25% buffer — "roughly breakeven" is not a trade
        required_edge = 0.25 * fee_per_unit

        # Dynamic required confluence: when R:R is highly favorable (>= 2.5:1),
        # breakeven win rate is low (25%-28%), so required confluence is calibrated appropriately.
        base_required = required_p_override if required_p_override is not None else ExpectancyGate.REQUIRED_WIN_PROBABILITY
        if rr >= 3.0:
            required_p = max(0.50, base_required - 0.06)
        elif rr >= 2.2:
            required_p = max(0.52, base_required - 0.03)
        else:
            required_p = base_required

        has_confluence = p >= required_p
        approved = (ev_per_unit > required_edge) and has_confluence

        metrics = {
            "p_win": round(p, 3),
            "required_p": round(required_p, 3),
            "history_adjustment": round(history_adjustment, 3),
            "rr": round(rr, 2),
            "ev_per_unit": round(ev_per_unit, 6),
            "fees_per_unit": round(fee_per_unit, 6),
            "required_edge": round(required_edge, 6),
            "factors": factors,
        }

        if approved:
            reason = (
                f"POSITIVE EXPECTANCY: p_win={p:.2f}, R:R={rr:.2f}, "
                f"EV/unit={ev_per_unit:.6f} > required {required_edge:.6f} (fees covered)."
            )
            logger.info(f"✅ [Expectancy Gate] {decision.symbol}: {reason}")
        else:
            fail_why = (
                f"win probability {p:.2f} below required {required_p:.2f} (insufficient confluence)"
                if not has_confluence
                else f"EV/unit {ev_per_unit:.6f} <= required {required_edge:.6f}"
            )
            reason = (
                f"INSUFFICIENT EDGE: {fail_why}. R:R={rr:.2f}. "
                f"Factors: {'; '.join(factors)}. Skipping — scanner continues to next candidate."
            )
            logger.info(f"⛔ [Expectancy Gate] {decision.symbol}: {reason}")

        return approved, reason, metrics

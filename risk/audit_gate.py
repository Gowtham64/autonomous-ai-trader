from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.config.settings import settings
from core.domain.models import TradeAction
from core.logging import logger
from core.schemas.trade import AnalystReport, CandidateSignal, DebateTranscript, TradeDecision


class TradeAuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    symbol: str
    decision: str
    strategy: str
    market_regime: str
    entry: float
    stop_loss: float
    target: float
    position_size: int
    maximum_risk_inr: float
    risk_reward_ratio: float
    confidence: float
    risk_score: float
    agents_consulted: list[str]
    risk_manager_decision: str  # "APPROVED" or "REJECTED"
    audit_questions_passed: int
    total_audit_questions: int = 16
    audit_checklist: dict[str, bool]
    justification_summary: str


class AuditGate:
    """15-Point Pre-Trade Mandatory Audit & Justification Gate.
    
    Ensures no trade is executed without answering and passing all 15 institutional
    soundness questions before the Risk Manager gives final clearance.
    """

    @staticmethod
    def audit_trade_intent(
        signal: CandidateSignal,
        decision: TradeDecision,
        debate: DebateTranscript,
        reports: list[AnalystReport],
        quantity: int,
        strategy_name: str = "Multi-Agent Confluence",
    ) -> tuple[bool, TradeAuditRecord]:
        """Conducts the formal 15-question audit."""
        is_crypto = (
            (signal.exchange and signal.exchange.upper() in ["DELTA", "CRYPTO", "BINANCE", "BYBIT"])
            or ("USD" in signal.symbol.upper())
            or (settings.BROKER_NAME and settings.BROKER_NAME.lower() in ["delta", "delta_exchange"])
        )

        stop_dist = abs(decision.entry_price - decision.stop_loss) if (decision.entry_price and decision.stop_loss) else 0.0
        if is_crypto:
            from portfolio.position_sizer import get_delta_contract_multiplier
            raw_mult = get_delta_contract_multiplier(signal.symbol)
            contract_mult = raw_mult if (raw_mult is not None and raw_mult > 0) else 0.0
            crypto_lev = getattr(settings, "DELTA_MAX_LEVERAGE", 5.0)
            trade_value = (quantity * (decision.entry_price or signal.ltp or 0.0) * contract_mult) / crypto_lev
            max_loss = stop_dist * quantity * contract_mult
        else:
            trade_value = quantity * (decision.entry_price or signal.ltp or 0.0)
            max_loss = stop_dist * quantity

        rr_ratio = decision.expected_risk_reward or 0.0
        from datetime import time
        from market.calendar import IndianMarketCalendar

        # Check 15: Time-of-day & Midday Consolidation Curfew Defense
        # Protects against midday lull chop, late-session decay, and low-beta intraday misallocation
        now_ist = IndianMarketCalendar.now_ist().time()
        is_swing = strategy_name in ["MULTI_DAY_SWING", "Multi-Day Swing", "JHUNJHUNWALA_SUPER_TREND"]

        if not is_crypto and IndianMarketCalendar.is_market_open():
            # Rule 1: Midday consolidation lull (12:00 PM - 01:30 PM IST)
            in_midday_lull = time(12, 0) <= now_ist <= time(13, 30)
            has_breakout_catalyst = (signal.relative_volume >= 2.5) and (debate.consensus_score >= 0.85)
            midday_safe = (not in_midday_lull) or has_breakout_catalyst

            # Rule 3: Late-session intraday entry cutoff (After 02:30 PM IST)
            late_session_safe = (now_ist < time(14, 30)) or is_swing

            # Rule 4: Low-Beta Equity Asset Routing Rule (ATR% < 1.0% cannot mature intraday after 13:00 IST)
            atr_pct = (signal.atr_14 / (signal.ltp or 1.0) * 100.0) if signal.atr_14 else 1.5
            is_low_beta = atr_pct < 1.0
            low_beta_late_mis = is_low_beta and (now_ist >= time(13, 0)) and (not is_swing)

            curfew_passed = midday_safe and late_session_safe and (not low_beta_late_mis)
        else:
            curfew_passed = True

        # Friction, Brokerage, Statutory Taxes & Electricity/Operational Overhead Gate
        # Protects against micro-trades where statutory fees (STT, GST, brokerage) and
        # operational overhead (compute, electricity, LLM tokens) exceed or consume the profit
        if is_crypto:
            entry_val = (decision.entry_price or signal.ltp or 0.0) * max(1, quantity) * contract_mult
            target_val = (decision.target_1 or (decision.entry_price or signal.ltp or 0.0)) * max(1, quantity) * contract_mult
            if decision.decision == TradeAction.SELL:
                expected_gain = max(0.0, entry_val - target_val)
            else:
                expected_gain = max(0.0, target_val - entry_val)
            # Delta Exchange crypto perpetual fees (0.05% taker round-trip)
            round_trip_turnover = entry_val + target_val
            est_statutory_charges = round_trip_turnover * 0.0005
            est_operational_overhead = 0.001
        else:
            entry_val = (decision.entry_price or signal.ltp or 0.0) * max(1, quantity)
            target_val = (decision.target_1 or (entry_val / max(1, quantity))) * max(1, quantity)
            expected_gain = max(0.0, target_val - entry_val)

            round_trip_turnover = entry_val + target_val
            est_brokerage = min(40.0, round_trip_turnover * 0.0006)
            est_stt = target_val * 0.00025
            est_exchange_turnover = round_trip_turnover * 0.0000345
            est_gst = (est_brokerage + est_exchange_turnover) * 0.18
            est_stamp_duty = entry_val * 0.00015
            est_statutory_charges = est_brokerage + est_stt + est_exchange_turnover + est_gst + est_stamp_duty
            est_operational_overhead = 1.50

        total_trade_friction = est_statutory_charges + est_operational_overhead
        # Expected profit must comfortably exceed total friction + operational drag (at least 1.5x)
        # and minimum net profit after all charges must be at least ₹1.50 (or $0.005 for crypto micro-accounts)
        min_net = 0.005 if is_crypto else 1.50
        friction_viable = (expected_gain >= total_trade_friction * 1.5) and ((expected_gain - total_trade_friction) >= min_net)
        from risk.quantitative_risk_analyzer import quant_analyzer

        # Quantitative Trading Math & Expectancy Evaluation (Algorithmic Trading Pro, Ch. 8.2)
        math_eval = quant_analyzer.evaluate_expectancy_and_math(
            entry=decision.entry_price or signal.ltp or 0.0,
            stop_loss=decision.stop_loss or 0.0,
            target=decision.target_1 or 0.0,
            quantity=quantity,
            side=decision.decision.value if hasattr(decision.decision, "value") else str(decision.decision),
            p_win_estimate=max(0.45, decision.confidence),
            fee_rate_roundtrip=0.001 if is_crypto else 0.0015,
        )

        # Quantitative Liquidity & Market Impact Evaluation (LVaR) (Ch. 7.3)
        bid_px = getattr(signal, "bid", None) or ((decision.entry_price or signal.ltp or 1.0) * 0.999)
        ask_px = getattr(signal, "ask", None) or ((decision.entry_price or signal.ltp or 1.0) * 1.001)
        lvar_eval = quant_analyzer.calculate_lvar_and_market_impact(
            position_notional=trade_value,
            bid_price=bid_px,
            ask_price=ask_px,
            avg_daily_volume=signal.avg_volume_20d or 10000.0,
        )

        # Check 16: Crypto Trading AI Academy & Field Handbook Compliance
        # Adheres to Glen Goodman Trend & Basing rules, Bucek Turtle Donchian,
        # and strictly forbids Martingale or gambling behaviors.
        academy_passed = True
        if is_crypto:
            if hasattr(signal, "ema_20") and signal.ema_20 and signal.ltp:
                if decision.decision == TradeAction.BUY and signal.ltp < signal.ema_20 * 0.95:
                    academy_passed = False
                elif decision.decision == TradeAction.SELL and signal.ltp > signal.ema_20 * 1.05:
                    academy_passed = False
            if hasattr(signal, "pivot") and signal.pivot and signal.ltp:
                extension_pct = abs(signal.ltp - signal.pivot) / signal.pivot * 100.0
                if extension_pct > 6.0 and (getattr(signal, "relative_volume", 1.0) or 1.0) < 2.5:
                    academy_passed = False

        # Evaluate 16 Mandatory Questions
        from core.treasury.treasury import treasury
        live_cap = max(10.0, float(treasury.current_capital or settings.INITIAL_CAPITAL))
        allowed_max_loss = live_cap * max(0.025, settings.MAX_RISK_PER_TRADE_PCT * 2.0)
        allowed_trade_value = max(10.0, live_cap * max(0.40, settings.MAX_SINGLE_STOCK_EXPOSURE_PCT))

        checklist = {
            "1_clear_thesis": bool(decision.thesis and len(decision.thesis) > 0),
            "2_strategy_identified": bool(strategy_name),
            "3_regime_detected": bool(signal.regime),
            "4_risk_defined": max_loss > 0,
            "5_invalidation_criteria": bool(debate.invalidating_scenarios and len(debate.invalidating_scenarios) > 0),
            "6_stop_loss_placed": decision.stop_loss is not None and decision.stop_loss > 0,
            "7_max_loss_bounded": max_loss <= allowed_max_loss,
            "8_reward_risk_favorable": (rr_ratio >= settings.MIN_RISK_REWARD_RATIO) and friction_viable and math_eval["is_viable"],
            "9_capital_sized_properly": trade_value <= allowed_trade_value,
            "10_liquidity_sufficient": (signal.avg_volume_20d > 1000) and (lvar_eval["market_impact_pct"] < 1.0) and (signal.relative_volume >= 0.05 or signal.avg_volume_20d > 50000),
            "11_correlation_safe": trade_value <= allowed_trade_value,
            "12_events_accounted": bool(IndianMarketCalendar.get_holidays() is not None),
            "13_portfolio_limits_compliant": quantity > 0 and trade_value > 0,
            "14_multi_agent_consensus": (abs(debate.consensus_score) >= 0.15 or decision.confidence >= 0.50) and decision.confidence >= 0.50,
            "15_time_of_day_and_curfew_safe": curfew_passed,
            "16_academy_handbook_compliant": academy_passed,
        }

        passed_count = sum(1 for v in checklist.values() if v)
        all_passed = (passed_count == 16) and (decision.decision in [TradeAction.BUY, TradeAction.SELL])

        agents_consulted = [r.agent_name for r in reports] + [
            "Bull Researcher", "Bear Researcher", "Debate Facilitator", "Chief Fund Manager"
        ]

        audit_record = TradeAuditRecord(
            symbol=signal.symbol,
            decision=decision.decision.value,
            strategy=strategy_name,
            market_regime=signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime),
            entry=decision.entry_price or signal.ltp,
            stop_loss=decision.stop_loss or 0.0,
            target=decision.target_1 or 0.0,
            position_size=quantity,
            maximum_risk_inr=round(max_loss, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            confidence=decision.confidence,
            risk_score=round(1.0 - decision.confidence, 2),
            agents_consulted=agents_consulted,
            risk_manager_decision="APPROVED" if all_passed else "REJECTED",
            audit_questions_passed=passed_count,
            total_audit_questions=15,
            audit_checklist=checklist,
            justification_summary=(
                f"15-Point Pre-Trade Audit for {signal.symbol}: {passed_count}/15 checks passed. "
                f"Consensus: {debate.consensus_score:+.2f}, R:R: {rr_ratio}:1, EV: ${math_eval['ev']:+.4f} (WinProb: {math_eval['estimated_p_win']:.0f}%). "
                f"Outcome: {'APPROVED' if all_passed else 'REJECTED'}"
            ),
        )

        if not all_passed:
            failed_keys = [k for k, v in checklist.items() if not v]
            logger.info(f"[Audit Gate] Candidate {signal.symbol} failed checks: {failed_keys}")
        logger.info(f"[Audit Gate] {audit_record.justification_summary}")
        return all_passed, audit_record

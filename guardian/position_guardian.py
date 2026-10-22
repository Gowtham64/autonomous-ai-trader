"""
AI Trade Guardian - Dedicated Per-Position Guardian Worker
Maintains continuous 24/7 oversight of an individual live position.
Tracks thesis validity, trails dynamic stops, measures distance to limits,
checks liquidity/slippage, and triggers protective actions when risk boundaries are tested.
"""

from datetime import UTC, datetime, time

from core.logging import logger
from core.schemas.trade import PositionSnapshot
from guardian.models import (
    GuardianAction,
    GuardianRiskLevel,
    PositionGuardianState,
)
from market.calendar import IndianMarketCalendar
from orchestration.event_bus import SystemEventType, realtime_event_bus


class PositionGuardianWorker:
    """Dedicated guardian assigned to exactly one open position."""

    def __init__(
        self,
        pos: PositionSnapshot,
        decision_id: str = "",
        trade_thesis: list[str] | None = None,
        invalidating_scenarios: list[str] | None = None,
        atr_14: float = 10.0,
        trailing_atr_multiplier: float = 0.8,
        max_permitted_loss_inr: float = 10.0,
    ):
        self.guardian_id = f"GRD-{pos.symbol}-{int(datetime.now(UTC).timestamp())}"
        side = getattr(pos, "side", "BUY") or "BUY"
        self.state = PositionGuardianState(
            side=side,
            guardian_id=self.guardian_id,
            symbol=pos.symbol,
            exchange=pos.exchange,
            order_id=getattr(pos, 'order_id', None) or f"ORD-{pos.symbol}",
            decision_id=decision_id or f"DEC-{pos.symbol}",
            entry_price=pos.entry_price,
            current_price=pos.current_price or pos.entry_price,
            quantity=pos.quantity,
            position_value=round(pos.entry_price * pos.quantity, 2),
            stop_loss=pos.stop_loss,
            original_stop_loss=pos.stop_loss,
            target_1=pos.target_1,
            target_2=pos.target_2,
            highest_price_seen=pos.entry_price,
            lowest_price_seen=pos.entry_price,
            max_permitted_loss_inr=max_permitted_loss_inr,
            atr_14=atr_14,
            trade_thesis=trade_thesis or ["Momentum breakout supported by volume & technical alignment"],
            invalidating_scenarios=invalidating_scenarios or [
                f"Close below ₹{round(pos.stop_loss, 2)}",
                "Severe market-wide pullback",
            ],
            opened_at=pos.opened_at or datetime.now(UTC),
            is_active=True,
        )
        self.trailing_atr_multiplier = trailing_atr_multiplier
        self.interventions_count = 0
        is_crypto_sym = getattr(pos, "exchange", "").upper() == "DELTA" or "USD" in pos.symbol
        c_sym = "$" if is_crypto_sym else "₹"
        px_fmt = f"{pos.entry_price:.4f}" if is_crypto_sym else f"{pos.entry_price:.2f}"
        sl_fmt = f"{pos.stop_loss:.4f}" if is_crypto_sym else f"{pos.stop_loss:.2f}"
        tgt_fmt = f"{pos.target_1:.4f}" if is_crypto_sym else f"{pos.target_1:.2f}"
        logger.info(f"🛡️ [Trade Guardian Assigned] {self.guardian_id} activated for {pos.symbol} (Qty: {pos.quantity} @ {c_sym}{px_fmt}, SL: {c_sym}{sl_fmt}, TGT: {c_sym}{tgt_fmt})")

    async def evaluate_tick(
        self,
        current_ltp: float,
        bid_price: float = 0.0,
        ask_price: float = 0.0,
        current_atr: float | None = None,
        relative_volume: float = 1.0,
        market_regime: str = "Trending",
        ohlcv_5m: object = None,
        provider: object = None,
    ) -> tuple[GuardianAction, str]:
        """Evaluates live market tick and chart structure to calculate risk, trailing stops, and profit-taking exits."""
        if not self.state.is_active:
            return GuardianAction.HOLD, "Guardian is inactive"

        atr = current_atr or self.state.atr_14 or (current_ltp * 0.015)
        self.state.current_price = current_ltp
        self.state.atr_14 = round(atr, 2)
        self.state.relative_volume = round(relative_volume, 2)
        self.state.last_evaluation_time = datetime.now(UTC)

        # Update high- and low-water marks
        self.state.highest_price_seen = max(self.state.highest_price_seen, current_ltp)
        self.state.lowest_price_seen = min(self.state.lowest_price_seen, current_ltp)

        # Calculate P&L & Direction
        is_short = getattr(self.state, "side", "BUY").upper() == "SELL"
        is_crypto = getattr(self.state, "exchange", "").upper() == "DELTA" or "USD" in self.state.symbol
        curr_sym = "$" if is_crypto else "₹"

        if is_crypto:
            from portfolio.position_sizer import get_delta_contract_multiplier
            mult = get_delta_contract_multiplier(self.state.symbol) or 1.0
        else:
            mult = 1.0

        if is_short:
            pnl = (self.state.entry_price - current_ltp) * self.state.quantity * mult
            pnl_pct = ((self.state.entry_price - current_ltp) / self.state.entry_price) * 100.0 if self.state.entry_price > 0 else 0.0
            peak_gain_pct = ((self.state.entry_price - self.state.lowest_price_seen) / self.state.entry_price) * 100.0 if self.state.entry_price > 0 else 0.0
            pullback_from_peak_pct = ((current_ltp - self.state.lowest_price_seen) / self.state.lowest_price_seen) * 100.0 if self.state.lowest_price_seen > 0 else 0.0
            distance_to_sl = self.state.stop_loss - current_ltp
            distance_to_tgt = current_ltp - self.state.target_1
        else:
            pnl = (current_ltp - self.state.entry_price) * self.state.quantity * mult
            pnl_pct = ((current_ltp - self.state.entry_price) / self.state.entry_price) * 100.0 if self.state.entry_price > 0 else 0.0
            peak_gain_pct = ((self.state.highest_price_seen - self.state.entry_price) / self.state.entry_price) * 100.0 if self.state.entry_price > 0 else 0.0
            pullback_from_peak_pct = ((self.state.highest_price_seen - current_ltp) / self.state.highest_price_seen) * 100.0 if self.state.highest_price_seen > 0 else 0.0
            distance_to_sl = current_ltp - self.state.stop_loss
            distance_to_tgt = self.state.target_1 - current_ltp

        self.state.unrealized_pnl = round(pnl, 4 if is_crypto else 2)
        self.state.unrealized_pnl_pct = round(pnl_pct, 2)
        self.state.distance_to_stop_pct = round((distance_to_sl / current_ltp) * 100.0, 2) if current_ltp > 0 else 0.0
        self.state.distance_to_target_pct = round((distance_to_tgt / current_ltp) * 100.0, 2) if current_ltp > 0 else 0.0

        # Spread & Liquidity assessment
        if bid_price > 0 and ask_price > 0:
            spread = ask_price - bid_price
            self.state.spread_pct = round((spread / current_ltp) * 100.0, 3)
            # Flag abnormal illiquidity
            if self.state.spread_pct > 0.8:
                self.state.risk_level = GuardianRiskLevel.HIGH
                logger.warning(f"⚠️ [Guardian {self.state.symbol}] Abnormal bid-ask spread detected ({self.state.spread_pct}%). Slippage risk elevated.")

        # Determine Risk Level
        max_allowed_loss = (self.state.max_permitted_loss_inr / 85.0) if is_crypto else self.state.max_permitted_loss_inr
        loss_ratio = abs(pnl) / max(0.50 if is_crypto else 1.0, max_allowed_loss)
        if pnl < 0 and (loss_ratio >= 0.80 or distance_to_sl <= (atr * 0.3)):
            self.state.risk_level = GuardianRiskLevel.HIGH
        elif pnl < 0 and loss_ratio >= 0.50:
            self.state.risk_level = GuardianRiskLevel.MEDIUM
        else:
            self.state.risk_level = GuardianRiskLevel.LOW

        # 1. HARD STOP LOSS PROTECTION
        sl_breached = (current_ltp >= self.state.stop_loss) if is_short else (current_ltp <= self.state.stop_loss)
        if sl_breached:
            self.state.risk_level = GuardianRiskLevel.CRITICAL
            self.interventions_count += 1
            reason = f"Hard Stop-Loss breached at {curr_sym}{current_ltp:.4f} (SL: {curr_sym}{self.state.stop_loss:.4f})"
            logger.critical(f"🚨 [Guardian Action] {self.state.symbol}: {reason}")
            self._publish_guardian_alert(GuardianAction.HARD_STOP_EXIT, reason)
            return GuardianAction.HARD_STOP_EXIT, reason

        # 2. TARGET 1 PROFIT PROTECTION
        tgt_achieved = (current_ltp <= self.state.target_1) if is_short else (current_ltp >= self.state.target_1)
        if tgt_achieved:
            self.interventions_count += 1
            reason = f"Profit Target 1 achieved at {curr_sym}{current_ltp:.4f} (Target: {curr_sym}{self.state.target_1:.4f})"
            logger.info(f"🎯 [Guardian Action] {self.state.symbol}: {reason}")
            self._publish_guardian_alert(GuardianAction.TARGET_EXIT, reason)
            return GuardianAction.TARGET_EXIT, reason

        # 2.5. LIVE CHART & PRICE ACTION MOMENTUM PROFIT-TAKING (REAL-TIME REVERSAL EXIT)
        # Instead of waiting for arbitrary clock times or static targets, continuously monitor
        # the 5-minute chart: shooting stars, upper wick rejection, 9-EMA / VWAP breaks, previous candle low breaks.
        # ChartProfitTaker logic is long-only (upper-wick/EMA-break analysis); never apply it to shorts.
        if not is_short and ohlcv_5m is not None and hasattr(ohlcv_5m, "empty") and not ohlcv_5m.empty and (pnl > 0 or self.state.highest_price_seen > self.state.entry_price):
            from guardian.chart_monitor import ChartProfitTaker
            should_exit, chart_reason = ChartProfitTaker.evaluate_chart_profit_exit(
                df_5m=ohlcv_5m,
                entry_price=self.state.entry_price,
                current_ltp=current_ltp,
                highest_price_seen=self.state.highest_price_seen,
                require_closed_candle=True,
            )
            if should_exit:
                self.interventions_count += 1
                logger.info(f"🎯 [Guardian Chart Profit-Take] {self.state.symbol}: {chart_reason}")
                self._publish_guardian_alert(GuardianAction.CHART_PROFIT_TAKE, chart_reason)
                return GuardianAction.CHART_PROFIT_TAKE, chart_reason

        # 2.6. MULTI-TIMEFRAME AI THESIS & MOMENTUM AUDIT (1m, 5m, 1h, 1d, 1y + Kronos Foundation Model)
        # Instead of waiting for arbitrary clock time or fixed stop losses, continuously evaluate
        # multi-timeframe price action and AI foundation model intelligence. If market structure
        # has broken down or momentum is exhausted, scratch early to preserve capital!
        if provider is not None and (pnl < 0 or abs(pnl_pct) < 0.30):
            try:
                from guardian.multitimeframe_auditor import multi_timeframe_auditor
                should_ai_exit, audit_reason = await multi_timeframe_auditor.audit_position(
                    symbol=self.state.symbol,
                    side=getattr(self.state, "side", "BUY"),
                    entry_price=self.state.entry_price,
                    current_ltp=current_ltp,
                    unrealized_pnl=pnl,
                    provider=provider,
                    opened_at=self.state.opened_at,
                )
                if should_ai_exit:
                    self.interventions_count += 1
                    logger.warning(f"🚨 [Guardian Action] {self.state.symbol}: {audit_reason}")
                    self._publish_guardian_alert(GuardianAction.THESIS_INVALIDATION_EXIT, audit_reason)
                    return GuardianAction.THESIS_INVALIDATION_EXIT, audit_reason
            except Exception as mtf_err:
                logger.debug(f"[Guardian Multi-TF Audit Notice] {self.state.symbol}: {mtf_err}")

        # NOTE: peak_gain_pct / pullback_from_peak_pct were already computed side-aware above.
        # (A long-only recomputation here previously broke every short position's harvest logic.)
        is_indian_equity = (
            self.state.exchange in ["NSE", "BSE"]
            or self.state.symbol.endswith(".NS")
            or self.state.symbol.endswith(".BO")
        )
        now_ist = IndianMarketCalendar.now_ist()

        # 3. CONTINUOUS REAL-TIME PERFORMANCE PROFIT HARVEST (ALL-DAY DYNAMIC PEAK HARVEST)
        # Driven 100% by STOCK PERFORMANCE, NOT arbitrary clock schedules.
        # Whenever a stock demonstrates upward traction and then peaks and decelerates,
        # harvest the profit immediately to lock in gains and prevent round-tripping.
        if pnl > 0:
            # Rule 3A: Midday Consolidation Window (12:00 - 13:30 IST) for Indian Equities
            if is_indian_equity and time(12, 0) <= now_ist.time() <= time(13, 30):
                if peak_gain_pct >= 0.80 and pullback_from_peak_pct >= 0.35:
                    self.interventions_count += 1
                    reason = (
                        f"Midday Peak Profit Harvest: Trade peaked at ₹{self.state.highest_price_seen:.2f} (+{peak_gain_pct:.2f}%) "
                        f"and pulled back by {pullback_from_peak_pct:.2f}% during 12:00-13:30 IST lull. Securing gains (+{pnl_pct:.2f}%)."
                    )
                    logger.info(f"💰 [Midday Peak Harvest] {self.state.symbol}: {reason}")
                    self._publish_guardian_alert(GuardianAction.MIDDAY_PEAK_HARVEST, reason)
                    return GuardianAction.MIDDAY_PEAK_HARVEST, reason

            # Rule 3B: Late-Session Pullback from Peak (14:00 - 14:43 IST) for Indian Equities
            if is_indian_equity and time(14, 0) <= now_ist.time() < time(14, 43):
                if peak_gain_pct >= 0.40 and pullback_from_peak_pct >= 0.20:
                    self.interventions_count += 1
                    reason = (
                        f"Market Performance Exit: Pullback from session high ₹{self.state.highest_price_seen:.2f} "
                        f"(-{pullback_from_peak_pct:.2f}%) at {now_ist.strftime('%H:%M')} IST. "
                        f"Locking gains (+{pnl_pct:+.2f}%) on momentum deceleration."
                    )
                    logger.info(f"🎯 [Performance Harvest] {self.state.symbol}: {reason}")
                    self._publish_guardian_alert(GuardianAction.TARGET_EXIT, reason)
                    return GuardianAction.TARGET_EXIT, reason

            # Rule 3C: All-Day Dynamic Performance Harvest (Active 24/7 across all market sessions and crypto)
            # If position made a substantial peak gain (>= +0.60%) and has pulled back by >= 0.25%, lock gains!
            if peak_gain_pct >= 0.60 and pullback_from_peak_pct >= 0.25:
                self.interventions_count += 1
                reason = (
                    f"Performance Exit: Position peaked at {curr_sym}{self.state.highest_price_seen:.4f if is_crypto else self.state.highest_price_seen:.2f} (+{peak_gain_pct:.2f}%) "
                    f"and pulled back by -{pullback_from_peak_pct:.2f}%. Securing profit (+{pnl_pct:+.2f}%) on price action deceleration."
                )
                logger.info(f"🎯 [Performance Harvest] {self.state.symbol}: {reason}")
                self._publish_guardian_alert(GuardianAction.TARGET_EXIT, reason)
                return GuardianAction.TARGET_EXIT, reason

        # 4. INDIAN EQUITY INTRADAY EOD DEFENSE (NSE / BSE MIS ONLY)
        # Prevents broker RMS penalty (Angel One ₹59 fee at 14:45).
        # Crypto and multi-day delivery positions are EXEMPT from EOD auto-squareoff.
        if is_indian_equity:
            # Check 4A: Late-session stagnation without directional progress (14:15 - 14:40 IST)
            duration_minutes = (datetime.now(UTC) - self.state.opened_at).total_seconds() / 60.0
            if time(14, 15) <= now_ist.time() < time(14, 40) and abs(pnl_pct) < 0.25 and duration_minutes >= 30.0:
                self.interventions_count += 1
                reason = (
                    f"Market Performance Exit: Stagnant price action ({pnl_pct:+.2f}%) in late session "
                    f"({now_ist.strftime('%H:%M')} IST). Flat momentum scratch."
                )
                logger.info(f"⏱️ [Performance Scratch] {self.state.symbol}: {reason}")
                self._publish_guardian_alert(GuardianAction.STAGNATION_SCRATCH_EXIT, reason)
                return GuardianAction.STAGNATION_SCRATCH_EXIT, reason

            # Check 4B: Pre-emptive Intraday EOD safety square-off at 14:40 - 14:43 IST
            if time(14, 40) <= now_ist.time() < time(14, 43) and (pnl <= 0 or current_ltp < self.state.highest_price_seen * 0.998):
                reason = (
                    f"Pre-emptive Intraday EOD safety square-off at 02:40 PM IST "
                    f"(Market performance deteriorating into EOD: {pnl_pct:+.2f}%). Avoiding broker RMS fee."
                )
                logger.warning(f"⏰ [Guardian Action] {self.state.symbol}: {reason}")
                self._publish_guardian_alert(GuardianAction.EOD_SQUAREOFF, reason)
                return GuardianAction.EOD_SQUAREOFF, reason

            # Check 4C: Terminal Broker RMS Penalty Defense (14:43 - 15:30 IST)
            if time(14, 43) <= now_ist.time() <= time(15, 30):
                self.interventions_count += 1
                if pnl > 0:
                    reason = (
                        f"Glide-Path Late-Session Profit Harvest: Position profitable ({pnl_pct:+.2f}%) at {now_ist.strftime('%H:%M')} IST. "
                        f"Securing profit ahead of broker RMS auto-squareoff."
                    )
                    logger.info(f"💰 [Guardian Glide-Path Harvest] {self.state.symbol}: {reason}")
                    self._publish_guardian_alert(GuardianAction.TARGET_EXIT, reason)
                    return GuardianAction.TARGET_EXIT, reason
                else:
                    reason = (
                        f"Terminal Broker RMS Penalty Defense at {now_ist.strftime('%H:%M')} IST "
                        f"(Exiting ahead of Angel One 14:45 RMS auto-squareoff to eliminate ₹59 penalty fee)."
                    )
                    logger.warning(f"🚨 [Terminal RMS Defense] {self.state.symbol}: {reason}")
                    self._publish_guardian_alert(GuardianAction.EOD_SQUAREOFF, reason)
                    return GuardianAction.EOD_SQUAREOFF, reason

            # Check 4D: 45-Minute Inactivity Defense (Intraday Equity Only)
            duration_minutes = (datetime.now(UTC) - self.state.opened_at).total_seconds() / 60.0
            if duration_minutes >= 45.0 and abs(pnl_pct) < 0.30:
                self.interventions_count += 1
                reason = f"Stagnation Time-Stop: Position stagnant ({pnl_pct:+.2f}%) for {int(duration_minutes)} mins. Scratching at market/cost to avoid EOD decay."
                logger.warning(f"⏱️ [Guardian Stagnation Scratch] {self.state.symbol}: {reason}")
                self._publish_guardian_alert(GuardianAction.STAGNATION_SCRATCH_EXIT, reason)
                return GuardianAction.STAGNATION_SCRATCH_EXIT, reason

        # 5. 24/7 CRYPTO STAGNATION DEFENSE
        # When a crypto perpetual trade has been open for > 90 minutes without reaching targets,
        # and remains negative/stagnant (pnl < 0), scratch it to free up margin for active momentum movers.
        if is_crypto:
            duration_minutes = (datetime.now(UTC) - self.state.opened_at).total_seconds() / 60.0
            if duration_minutes >= 90.0 and pnl < 0:
                self.interventions_count += 1
                reason = (
                    f"Crypto Stagnation Scratch: Position held for {int(duration_minutes)}m in negative territory "
                    f"({pnl_pct:+.2f}%). Scratching trade to recycle margin into active momentum breakouts."
                )
                logger.info(f"⏱️ [Guardian Crypto Stagnation] {self.state.symbol}: {reason}")
                self._publish_guardian_alert(GuardianAction.STAGNATION_SCRATCH_EXIT, reason)
                return GuardianAction.STAGNATION_SCRATCH_EXIT, reason

        # 7. MULTI-TIERED HIGH-WATER MARK PROFIT RATCHET & TIGHT TRAILING STOP
        # Ensures winning trades NEVER turn into losses:
        # Tier 1 (+0.50% Peak): Lock Break-Even + 0.15% (costs covered)
        # Tier 2 (+1.00% Peak): Lock at least +0.60% profit (or keep >=60% of peak gain)
        # Tier 3 (+1.50% Peak): Lock at least +1.00% profit
        # Tier 4 (+2.00% Peak): Lock at least +1.50% profit
        target_sl = self.state.stop_loss
        effective_atr = min(atr, current_ltp * 0.015)
        px_decimals = 4 if is_crypto else 2

        if is_short:
            # SHORT: stop sits ABOVE price and ratchets DOWN as the short gains.
            profit_points = self.state.entry_price - current_ltp
            peak_drop = self.state.entry_price - self.state.lowest_price_seen

            if peak_gain_pct >= 2.0:
                tier_sl = round(self.state.entry_price * 0.985, px_decimals)
                giveback_sl = round(self.state.entry_price - (peak_drop * 0.60), px_decimals)
                target_sl = min(target_sl, tier_sl, giveback_sl)
            elif peak_gain_pct >= 1.5:
                tier_sl = round(self.state.entry_price * 0.990, px_decimals)
                giveback_sl = round(self.state.entry_price - (peak_drop * 0.60), px_decimals)
                target_sl = min(target_sl, tier_sl, giveback_sl)
            elif peak_gain_pct >= 1.0:
                tier_sl = round(self.state.entry_price * 0.994, px_decimals)
                giveback_sl = round(self.state.entry_price - (peak_drop * 0.60), px_decimals)
                target_sl = min(target_sl, tier_sl, giveback_sl)
            elif peak_gain_pct >= 0.50:
                tier_sl = round(self.state.entry_price * 0.9985, px_decimals)
                target_sl = min(target_sl, tier_sl)

            if profit_points >= (effective_atr * 0.8):
                tight_trailing_stop = round(self.state.lowest_price_seen + (self.trailing_atr_multiplier * effective_atr), px_decimals)
                target_sl = min(target_sl, tight_trailing_stop)

            sl_improved = target_sl < self.state.stop_loss and target_sl > current_ltp
        else:
            profit_points = current_ltp - self.state.entry_price

            if peak_gain_pct >= 2.0:
                tier_sl = round(self.state.entry_price * 1.015, px_decimals)
                giveback_sl = round(self.state.entry_price + ((self.state.highest_price_seen - self.state.entry_price) * 0.60), px_decimals)
                target_sl = max(target_sl, tier_sl, giveback_sl)
            elif peak_gain_pct >= 1.5:
                tier_sl = round(self.state.entry_price * 1.010, px_decimals)
                giveback_sl = round(self.state.entry_price + ((self.state.highest_price_seen - self.state.entry_price) * 0.60), px_decimals)
                target_sl = max(target_sl, tier_sl, giveback_sl)
            elif peak_gain_pct >= 1.0:
                tier_sl = round(self.state.entry_price * 1.006, px_decimals)
                giveback_sl = round(self.state.entry_price + ((self.state.highest_price_seen - self.state.entry_price) * 0.60), px_decimals)
                target_sl = max(target_sl, tier_sl, giveback_sl)
            elif peak_gain_pct >= 0.50:
                tier_sl = round(self.state.entry_price * 1.0015, px_decimals)
                target_sl = max(target_sl, tier_sl)

            # Dynamic Trailing Stop using calibrated ATR
            if profit_points >= (effective_atr * 0.8):
                tight_trailing_stop = round(self.state.highest_price_seen - (self.trailing_atr_multiplier * effective_atr), px_decimals)
                target_sl = max(target_sl, tight_trailing_stop)

            sl_improved = target_sl > self.state.stop_loss and target_sl < current_ltp

        if sl_improved:
            old_sl = self.state.stop_loss
            self.state.stop_loss = target_sl
            self.interventions_count += 1
            logger.info(f"🛡️ [Guardian Profit Ratchet] Moved SL for {self.state.symbol}: {curr_sym}{old_sl:.4f} -> {curr_sym}{target_sl:.4f} (Peak gain: +{peak_gain_pct:.2f}%)")
            self._publish_guardian_alert(
                GuardianAction.ADJUST_TRAILING_STOP,
                f"Profit Ratchet: SL locked at {curr_sym}{target_sl:.4f}",
            )
            return GuardianAction.ADJUST_TRAILING_STOP, f"Stop Loss moved to {curr_sym}{target_sl:.4f}"

        # 8. TRADE THESIS INVALIDATION CHECK
        if self.state.relative_volume < 0.3 and profit_points <= 0 and market_regime == "Bearish Distribution":
            self.state.thesis_intact = False
            self.state.invalidation_reason = "Breakout volume completely vanished during market regime shift"
            self.state.risk_level = GuardianRiskLevel.HIGH
            logger.warning(f"⚠️ [Guardian Thesis Invalidation] {self.state.symbol}: {self.state.invalidation_reason}")

        return GuardianAction.HOLD, "Position within approved safety boundaries"

    def _publish_guardian_alert(self, action: GuardianAction, reason: str):
        realtime_event_bus.publish_event(
            SystemEventType.POSITION_CHANGED,
            source="AI Trade Guardian",
            symbol=self.state.symbol,
            payload={
                "guardian_id": self.guardian_id,
                "action": action.value,
                "risk_level": self.state.risk_level.value,
                "current_price": self.state.current_price,
                "unrealized_pnl": self.state.unrealized_pnl,
                "stop_loss": self.state.stop_loss,
                "reason": reason,
            },
        )

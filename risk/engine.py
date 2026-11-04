from core.config.settings import settings
from core.domain.models import TradeAction
from core.logging import logger
from core.schemas.trade import PositionSnapshot, RiskCheckResult, TradeDecision


class DeterministicRiskEngine:
    """Non-LLM, immutable deterministic risk verification engine."""

    def __init__(
        self,
        total_equity: float = settings.MAX_CAPITAL,
        current_daily_realized_loss: float = 0.0,
        peak_equity: float | None = None,
    ):
        self.total_equity = total_equity
        self.daily_realized_loss = current_daily_realized_loss
        self.peak_equity = peak_equity if peak_equity is not None else total_equity

    def evaluate_trade_intent(
        self,
        decision: TradeDecision,
        open_positions: list[PositionSnapshot],
        sector: str = "General",
    ) -> RiskCheckResult:
        logger.info(f"Deterministic Risk Engine assessing trade intent for {decision.symbol}")
        rejection_reasons = []

        # 1. Non-actionable decisions
        if decision.decision == TradeAction.NO_TRADE or decision.decision == TradeAction.HOLD:
            return RiskCheckResult(
                approved=False,
                rejection_reasons=["Decision is NO_TRADE or HOLD."],
            )

        # 2. Daily Loss Limit Circuit Breaker
        is_usd = self.total_equity < 100.0 or getattr(settings, "BROKER_NAME", "").lower() == "delta"
        curr_sym = "$" if is_usd else "₹"
        min_loss_floor = 1.00 if is_usd else 100.0
        max_daily_loss = max(min_loss_floor, self.total_equity * settings.MAX_DAILY_LOSS_PCT)
        if self.daily_realized_loss >= max_daily_loss:
            rejection_reasons.append(
                f"Daily Loss Limit hit: {curr_sym}{self.daily_realized_loss:.2f} >= max allowed {curr_sym}{max_daily_loss:.2f}"
            )

        # 3. Max Portfolio Drawdown Circuit Breaker
        drawdown_pct = (self.peak_equity - self.total_equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        effective_max_dd = 0.15 if (is_usd and self.total_equity < 30.0) else settings.MAX_PORTFOLIO_DRAWDOWN_PCT
        if drawdown_pct >= effective_max_dd:
            rejection_reasons.append(
                f"Max Drawdown Limit hit: {drawdown_pct*100:.2f}% >= {effective_max_dd*100:.1f}%"
            )

        # 4. Open Positions Count Cap
        active_positions = [p for p in open_positions if p.is_active]
        if len(active_positions) >= settings.MAX_OPEN_POSITIONS:
            rejection_reasons.append(
                f"Max open positions count reached: {len(active_positions)}/{settings.MAX_OPEN_POSITIONS}"
            )

        # 5. Duplicate Position Prevention & Valuation Integrity
        for pos in active_positions:
            if pos.symbol == decision.symbol:
                rejection_reasons.append(f"Position already open for symbol {decision.symbol}")
            if getattr(pos, "valuation_unreliable", False):
                rejection_reasons.append(
                    f"Position {pos.symbol} has unreliable/stale valuation. New risk-increasing entries blocked."
                )

        # 6. Stop Loss and Risk-to-Reward Validation
        if decision.entry_price is None or decision.stop_loss is None or decision.target_1 is None:
            rejection_reasons.append("Missing entry price, stop loss, or target 1 in trade decision.")
        else:
            if decision.decision == TradeAction.BUY:
                if decision.stop_loss >= decision.entry_price:
                    rejection_reasons.append("Stop loss cannot be greater than or equal to entry price for BUY order.")
                if decision.target_1 <= decision.entry_price:
                    rejection_reasons.append("Target cannot be lower than or equal to entry price for BUY order.")

                stop_dist = decision.entry_price - decision.stop_loss
                target_dist = decision.target_1 - decision.entry_price
                rr_ratio = target_dist / stop_dist if stop_dist > 0 else 0.0
                if rr_ratio < settings.MIN_RISK_REWARD_RATIO:
                    rejection_reasons.append(
                        f"Risk-to-Reward ratio {rr_ratio:.2f} is below minimum required {settings.MIN_RISK_REWARD_RATIO:.1f}"
                    )
            elif decision.decision == TradeAction.SELL:
                if decision.stop_loss <= decision.entry_price:
                    rejection_reasons.append("Stop loss cannot be lower than or equal to entry price for SELL order.")
                if decision.target_1 >= decision.entry_price:
                    rejection_reasons.append("Target cannot be greater than or equal to entry price for SELL order.")

                stop_dist = decision.stop_loss - decision.entry_price
                target_dist = decision.entry_price - decision.target_1
                rr_ratio = target_dist / stop_dist if stop_dist > 0 else 0.0
                if rr_ratio < settings.MIN_RISK_REWARD_RATIO:
                    rejection_reasons.append(
                        f"Risk-to-Reward ratio {rr_ratio:.2f} is below minimum required {settings.MIN_RISK_REWARD_RATIO:.1f}"
                    )

        if rejection_reasons:
            logger.warning(f"Trade REJECTED by Risk Engine: {'; '.join(rejection_reasons)}")
            return RiskCheckResult(
                approved=False,
                rejection_reasons=rejection_reasons,
            )

        return RiskCheckResult(
            approved=True,
            rejection_reasons=[],
            calculated_risk_amount=self.total_equity * settings.MAX_RISK_PER_TRADE_PCT,
        )

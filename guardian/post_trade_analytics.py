"""
AI Trade Guardian - Post-Trade Quality & Excursion Analytics
Calculates MFE, MAE, slippage, thesis accuracy, and records detailed post-mortem metrics into memory.
"""

from datetime import UTC, datetime

from core.logging import logger
from guardian.models import PositionGuardianState, PostTradeQualityReport
from memory.learning_loop import learning_loop


class PostTradeAnalyticsEngine:
    """Computes mathematical execution quality metrics for completed trades."""

    @staticmethod
    def calculate_brokerage_fee(
        state: PositionGuardianState,
        exit_price: float,
    ) -> float:
        """Calculates realistic exchange-specific brokerage fees (proportional for crypto, broker rates for equity)."""
        entry = state.entry_price
        qty = state.quantity
        symbol = state.symbol
        exchange = getattr(state, "exchange", "NSE")

        is_crypto = (
            exchange in ["DELTA", "BINANCE"]
            or symbol.endswith("USD")
            or symbol.endswith("USDT")
            or symbol.endswith("BTC")
            or symbol.endswith("ETH")
        )
        if is_crypto:
            # Delta exchange taker fee is 0.05% of notional turnover
            from portfolio.position_sizer import require_delta_contract_multiplier
            mult = require_delta_contract_multiplier(symbol)
            turnover = ((entry * qty) + (exit_price * qty)) * mult
            return round(turnover * 0.0005, 4)
        else:
            # Indian Equity: Angel One charges min(20, 0.03%) per order
            turnover = (entry * qty) + (exit_price * qty)
            return round(min(40.0, max(1.0, turnover * 0.0003)), 2)

    @staticmethod
    def analyze_completed_guardian_position(
        state: PositionGuardianState,
        exit_price: float,
        exit_reason: str,
        brokerage_fee: float | None = None,
        interventions_count: int = 0,
    ) -> PostTradeQualityReport:
        entry = state.entry_price
        qty = state.quantity
        if brokerage_fee is None:
            brokerage_fee = PostTradeAnalyticsEngine.calculate_brokerage_fee(state, exit_price)

        is_crypto = (
            getattr(state, "exchange", "NSE") in ["DELTA", "BINANCE"]
            or state.symbol.endswith("USD")
            or state.symbol.endswith("USDT")
            or state.symbol.endswith("BTC")
            or state.symbol.endswith("ETH")
        )
        if is_crypto:
            from portfolio.position_sizer import require_delta_contract_multiplier
            mult = require_delta_contract_multiplier(state.symbol)
        else:
            mult = 1.0

        # Direction-aware P&L: a short profits when price FALLS.
        is_short = getattr(state, "side", "BUY").upper() == "SELL"
        price_move = (entry - exit_price) if is_short else (exit_price - entry)
        gross_pnl = price_move * qty * mult
        realized_pnl = round(gross_pnl - brokerage_fee, 4 if is_crypto else 2)
        realized_pnl_pct = round((price_move / entry) * 100.0, 2) if entry > 0 else 0.0

        # Maximum Favorable Excursion (MFE) %: best price seen in the trade's direction
        mfe_price = state.lowest_price_seen if is_short else state.highest_price_seen
        mfe_pct = round((abs(entry - mfe_price) / entry) * 100.0, 2) if entry > 0 else 0.0

        # Maximum Adverse Excursion (MAE) %: worst price seen against the trade
        mae_price = state.highest_price_seen if is_short else state.lowest_price_seen
        mae_pct = round((abs(entry - mae_price) / entry) * 100.0, 2) if entry > 0 else 0.0

        # Planned vs Actual R:R
        risk_dist = abs(entry - state.stop_loss)
        reward_dist = abs(state.target_1 - entry)
        planned_rr = round(reward_dist / max(0.01, risk_dist), 2)
        actual_rr = round(price_move / max(0.01, risk_dist), 2)

        # Thesis Accuracy Score (1.0 if closed in profit or at target, 0.0 if hit hard stop)
        thesis_score = 1.0 if realized_pnl > 0 else (0.5 if "EOD" in exit_reason else 0.0)

        report = PostTradeQualityReport(
            trade_id=state.order_id,
            symbol=state.symbol,
            entry_price=entry,
            exit_price=exit_price,
            quantity=qty,
            realized_pnl=realized_pnl,
            realized_pnl_pct=realized_pnl_pct,
            exit_reason=exit_reason,
            max_favorable_excursion_pct=mfe_pct,
            max_adverse_excursion_pct=mae_pct,
            entry_slippage_pct=state.slippage_estimated_pct,
            exit_slippage_pct=0.0005,
            brokerage_and_fees=brokerage_fee,
            planned_risk_reward=planned_rr,
            actual_risk_reward=actual_rr,
            thesis_accuracy_score=thesis_score,
            guardian_interventions_count=interventions_count,
            completed_at=datetime.now(UTC),
        )

        # Feed into the Institutional Post-Trade Learning Loop
        try:
            record = learning_loop.analyze_completed_trade(
                trade_id=state.order_id,
                symbol=state.symbol,
                pnl=realized_pnl,
                entry_price=entry,
                exit_price=exit_price,
                decision=None,
                exit_reason=exit_reason,
            )
            if record and hasattr(record, "quadrant"):
                report.decision_vs_outcome_quadrant = record.quadrant.value
        except Exception as e:
            logger.debug(f"[PostTradeAnalytics] Learning loop ingestion note: {e}")

        logger.info(
            f"📊 [Post-Trade Guardian Audit] {state.symbol}: PnL ₹{realized_pnl} ({realized_pnl_pct}%), "
            f"MFE: +{mfe_pct}%, MAE: -{mae_pct}%, Planned R:R: 1:{planned_rr}, Actual: 1:{actual_rr}"
        )
        return report

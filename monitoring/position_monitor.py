from datetime import UTC, datetime, time

from core.domain.models import ExitReason
from core.logging import logger
from core.schemas.trade import OrderIntent, PositionSnapshot, TradeAction
from execution.interface import BaseBroker
from market.calendar import IndianMarketCalendar


class PositionMonitor:
    """Monitors open positions for stop-loss hits, target achievements, trailing ratchets, and EOD squareoff."""

    def __init__(self, broker: BaseBroker, trailing_atr_multiplier: float = 1.0):
        self.broker = broker
        self.trailing_atr_multiplier = trailing_atr_multiplier

    async def evaluate_position(
        self,
        pos: PositionSnapshot,
        current_ltp: float,
        current_atr: float = 20.0,
        check_eod: bool = True,
        mark_price: float | None = None,
    ) -> tuple[bool, ExitReason | None, str]:
        is_crypto = (pos.exchange and pos.exchange.upper() in ["DELTA", "CRYPTO"]) or ("USD" in pos.symbol.upper())
        currency_sym = "$" if is_crypto else "₹"
        prec = 6 if pos.entry_price < 0.10 else (4 if pos.entry_price < 10.0 else 2)

        def _round_p(val: float) -> float:
            return round(val, prec)

        if is_crypto:
            from portfolio.position_sizer import require_delta_contract_multiplier
            mult = require_delta_contract_multiplier(pos.symbol)
        else:
            mult = 1.0

        is_short = str(pos.side).upper() in ["SELL", "SHORT"]
        val_px = mark_price if (mark_price is not None and mark_price > 0) else current_ltp
        pnl = ((pos.entry_price - val_px) if is_short else (val_px - pos.entry_price)) * pos.quantity * mult
        pos.unrealized_pnl = round(pnl, 4 if is_crypto else 2)
        pnl_pct = (((pos.entry_price - val_px) if is_short else (val_px - pos.entry_price)) / pos.entry_price) * 100.0 if pos.entry_price > 0 else 0.0

        # Update high-water mark
        if current_ltp > pos.highest_price_seen:
            pos.highest_price_seen = current_ltp

        peak_gain_pct = ((pos.highest_price_seen - pos.entry_price) / pos.entry_price) * 100.0 if pos.entry_price > 0 else 0.0
        profit_points = current_ltp - pos.entry_price

        # Multi-Tiered High-Water Mark Profit Ratchet (Vojtko & Mesíček MTF Trailing Mechanism)
        target_sl = pos.stop_loss
        if peak_gain_pct >= 2.0:
            tier_sl = _round_p(pos.entry_price * 1.015)
            giveback_sl = _round_p(pos.entry_price + ((pos.highest_price_seen - pos.entry_price) * 0.60))
            target_sl = max(target_sl, tier_sl, giveback_sl)
        elif peak_gain_pct >= 1.5:
            tier_sl = _round_p(pos.entry_price * 1.010)
            giveback_sl = _round_p(pos.entry_price + ((pos.highest_price_seen - pos.entry_price) * 0.60))
            target_sl = max(target_sl, tier_sl, giveback_sl)
        elif peak_gain_pct >= 1.0:
            tier_sl = _round_p(pos.entry_price * 1.005)
            giveback_sl = _round_p(pos.entry_price + ((pos.highest_price_seen - pos.entry_price) * 0.50))
            target_sl = max(target_sl, tier_sl, giveback_sl)
        elif peak_gain_pct >= 0.50:
            tier_sl = _round_p(pos.entry_price * 1.001)
            target_sl = max(target_sl, tier_sl)

        # Dynamic Trailing Stop using calibrated ATR (Trailing Chandelier)
        effective_atr = min(current_atr, current_ltp * 0.02)
        if profit_points >= (effective_atr * 0.8):
            tight_trailing_sl = _round_p(pos.highest_price_seen - (self.trailing_atr_multiplier * effective_atr))
            target_sl = max(target_sl, tight_trailing_sl)

        # Safety check: trailing target SL should never be set above current LTP (prevent instant self-stopout)
        target_sl = min(target_sl, _round_p(current_ltp * 0.999))

        if target_sl > pos.stop_loss:
            logger.info(f"🛡️ [Profit Ratchet] Moved SL for {pos.symbol}: {currency_sym}{pos.stop_loss:.{prec}f} -> {currency_sym}{target_sl:.{prec}f} (Peak: {currency_sym}{pos.highest_price_seen:.{prec}f} / +{peak_gain_pct:.2f}%)")
            pos.stop_loss = target_sl

        # 1. Hard / Trailing Stop Loss Hit
        if current_ltp <= pos.stop_loss:
            return True, ExitReason.HARD_STOP_LOSS, f"Stop Loss hit at {currency_sym}{current_ltp} (SL was {currency_sym}{pos.stop_loss})"

        # 2. Target 1 Hit
        if current_ltp >= pos.target_1:
            return True, ExitReason.TARGET_1, f"Target 1 achieved at {currency_sym}{current_ltp} (Target was {currency_sym}{pos.target_1})"

        # 3. EOD Safety Square-off (Only for Indian equities MIS, never for 24/7 Crypto Perpetuals)
        is_crypto = (pos.exchange and pos.exchange.upper() in ["DELTA", "CRYPTO"]) or ("USD" in pos.symbol.upper())
        if not is_crypto and check_eod and IndianMarketCalendar.is_market_open():
            now_ist = IndianMarketCalendar.now_ist()
            if time(14, 40) <= now_ist.time() <= time(15, 30):
                return True, ExitReason.EOD_SAFETY, "Pre-emptive EOD intraday safety square-off at 02:40 PM IST (Avoiding Broker RMS liquidation)"

        return False, None, "Position healthy"

    async def execute_exit(self, pos: PositionSnapshot, reason: ExitReason, notes: str) -> None:
        logger.warning(f"EXECUTING EXIT for {pos.symbol} [Reason: {reason.value}]: {notes}")
        from execution.router import OrderRouter
        router = OrderRouter(self.broker)
        exit_side = TradeAction.BUY if str(pos.side).upper() in ["SELL", "SHORT"] else TradeAction.SELL
        exit_order = OrderIntent(
            client_order_id=f"EXT-{pos.symbol}-{int(datetime.now(UTC).timestamp())}",
            symbol=pos.symbol,
            exchange=pos.exchange,
            action=exit_side,
            quantity=pos.quantity,
            price=pos.current_price,
            stop_loss=0.0,
            target=0.0,
            decision_id=f"EXIT-{reason.value}",
            reduce_only=True,
        )
        await router.route_order(exit_order)


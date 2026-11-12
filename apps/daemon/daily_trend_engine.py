"""Daily trend-following engine — runs the backtested rule in strategy/daily_trend.py.

Every cycle (default every 15 minutes):
  1. Risk: update peak / day-start equity; trip the persisted kill switch on a
     drawdown or daily-loss breach. A halted engine still manages exits.
  2. Reconcile: a position the broker no longer holds was closed by the exchange stop.
  3. Once per newly completed daily candle (00:00 UTC = 05:30 IST):
       - for each open position: exit on the 20-day-low signal, else trail the stop
         (and move the exchange stop in live mode);
       - for each symbol without a position: enter on a 55-day breakout, sized so the
         stop risks DAILY_TREND_RISK_PCT of equity — or skip if that's impossible.
     Entries are blocked while the kill switch is engaged or the realized-edge gate
     says the strategy's own closed trades are losing money (live mode).
  4. Stops: if price is through a position's stop, exit at market (primary protection
     in paper mode, backup to the exchange-side stop in live mode).

All state lives in data/daily_trend_state.json, so restarts never forget a position.
Completed trades are journaled with market_regime="DAILY_TREND" so the strategy is
judged on its own record, separately from the old hourly bot.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from core.config.settings import settings
from core.domain.models import OrderStatus, TradeAction
from core.logging import logger
from core.schemas.trade import OrderIntent, OrderType
from risk.edge_gate import evaluate_realized_edge
from risk.kill_switch import kill_switch
from risk.profit_math import TAKER_FEE_PCT
from strategy.daily_trend import (
    PRE_REGISTERED,
    TrendParams,
    completed_bars,
    initial_stop,
    latest_view,
    size_position,
    trail_stop,
)

STRATEGY_TAG = "DAILY_TREND"
ENTRY_WINDOW_HOURS = 6

CandlesFn = Callable[[str], Awaitable[pd.DataFrame]]
MarkFn = Callable[[str], Awaitable[float]]
JournalFn = Callable[..., Awaitable[None]]
StatsFn = Callable[[], Awaitable[dict]]
MultFn = Callable[[str], "float | None"]


@dataclass
class TrendPosition:
    symbol: str
    side: str                 # BUY (long) | SELL (short)
    quantity: int
    entry_price: float
    stop: float
    best_close: float
    entry_signal_date: str    # completed bar that triggered the entry (YYYY-MM-DD)
    opened_at: str
    multiplier: float
    last_trailed_date: str = ""


@dataclass
class EngineState:
    positions: dict[str, TrendPosition] = field(default_factory=dict)
    last_daily_bar: str = ""                       # last completed daily bar processed
    last_exit_date: dict[str, str] = field(default_factory=dict)
    peak_equity: float = 0.0
    day: str = ""
    day_start_equity: float = 0.0

    @classmethod
    def load(cls, path: Path) -> "EngineState":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text())
        st = cls(**{k: v for k, v in raw.items() if k != "positions"})
        st.positions = {s: TrendPosition(**p) for s, p in raw.get("positions", {}).items()}
        return st

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)  # atomic: a crash mid-write can't corrupt the state


def _d(ts: pd.Timestamp | datetime) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


class DailyTrendEngine:
    def __init__(
        self,
        broker,
        candles_fn: CandlesFn,
        mark_fn: MarkFn,
        multiplier_fn: MultFn,
        journal_fn: JournalFn | None = None,
        stats_fn: StatsFn | None = None,
        is_live: bool = False,
        params: TrendParams = PRE_REGISTERED,
        symbols: list[str] | None = None,
        state_path: str | Path = "data/daily_trend_state.json",
        now_fn: Callable[[], pd.Timestamp] | None = None,
    ):
        self.broker = broker
        self.candles_fn = candles_fn
        self.mark_fn = mark_fn
        self.multiplier_fn = multiplier_fn
        self.journal_fn = journal_fn
        self.stats_fn = stats_fn
        self.is_live = is_live
        self.p = params
        self.symbols = symbols or list(settings.DAILY_TREND_SYMBOLS)
        self.state_path = Path(state_path)
        self.now_fn = now_fn or (lambda: pd.Timestamp.now(tz="UTC"))
        self.state = EngineState.load(self.state_path)
        self._seq = 0
        # Trades closed by this process (newest last) — for summaries and tests.
        self.closed: list[dict] = []

    # ------------------------------------------------------------------ cycle

    async def run_cycle(self) -> dict:
        now = self.now_fn()
        summary: dict = {"time": now.isoformat(), "mode": "LIVE" if self.is_live else "PAPER",
                         "entries": [], "exits": [], "stops_moved": [], "skipped": []}

        equity, available = await self._funds()
        summary["equity"] = round(equity, 4)
        self._update_risk(equity, now, summary)

        await self._reconcile(summary)

        # Same order as the backtest: at a new daily close, trend exits and stop trailing
        # happen first; then the (possibly raised) stop is checked against the live price.
        latest_bar = await self._latest_completed_bar()
        if latest_bar is not None and _d(latest_bar) > self.state.last_daily_bar:
            await self._daily_routine(latest_bar, summary)

        await self._check_stops(summary)

        self.state.save(self.state_path)
        summary["open_positions"] = {s: {"qty": p.quantity, "entry": p.entry_price, "stop": p.stop}
                                     for s, p in self.state.positions.items()}
        summary["kill_switch"] = kill_switch.reason if kill_switch.is_engaged else None
        return summary

    # ------------------------------------------------------------------- risk

    async def _funds(self) -> tuple[float, float]:
        f = await self.broker.get_funds()
        equity = float(f.get("total_capital") or 0.0)
        available = float(f.get("available_margin") or 0.0)
        return equity, available

    def _update_risk(self, equity: float, now: pd.Timestamp, summary: dict) -> None:
        st = self.state
        if kill_switch.rebase_required:
            # An operator deliberately reset a halt: restart the drawdown measure from here.
            kill_switch.rebase_required = False
            st.peak_equity = equity
            st.day, st.day_start_equity = _d(now), equity
            logger.warning(f"🔄 [Daily Trend] Operator reset: peak/day-start equity rebased to {equity:.2f}")
        kill_switch.clear_expired_halts()
        if equity <= 0:
            return
        st.peak_equity = max(st.peak_equity, equity)
        if st.day != _d(now):
            st.day, st.day_start_equity = _d(now), equity
        dd = (st.peak_equity - equity) / st.peak_equity if st.peak_equity > 0 else 0.0
        day_loss = (st.day_start_equity - equity) / st.day_start_equity if st.day_start_equity > 0 else 0.0
        summary["drawdown_pct"] = round(dd * 100, 2)
        if kill_switch.is_engaged:
            return
        if dd >= settings.DAILY_TREND_MAX_DRAWDOWN_PCT:
            kill_switch.trigger(
                "DAILY_TREND",
                f"Drawdown {dd * 100:.1f}% >= {settings.DAILY_TREND_MAX_DRAWDOWN_PCT * 100:.0f}% "
                f"(worse than the 8-year backtest). New entries halted until an operator resets.",
                kind="MANUAL_RESET",
            )
        elif day_loss >= settings.DAILY_TREND_MAX_DAILY_LOSS_PCT:
            kill_switch.trigger(
                "DAILY_TREND",
                f"Daily loss {day_loss * 100:.1f}% >= {settings.DAILY_TREND_MAX_DAILY_LOSS_PCT * 100:.0f}%.",
                kind="DAILY_LOSS",
            )

    async def _entries_allowed(self, summary: dict) -> bool:
        if kill_switch.is_engaged:
            summary["skipped"].append(f"all entries: kill switch engaged ({kill_switch.reason})")
            return False
        if self.stats_fn is not None:
            try:
                stats = await self.stats_fn()
                v = evaluate_realized_edge(stats, settings.EDGE_GATE_MIN_TRADES, is_live=self.is_live)
                summary["realized_edge"] = v.reason
                if not v.allow_live_entries:
                    logger.critical(f"⛔ [Daily Trend] {v.reason}")
                    summary["skipped"].append("all entries: realized-edge gate")
                    return False
            except Exception as e:
                logger.warning(f"[Daily Trend] Edge stats unavailable ({e}); entries continue.")
        return True

    # -------------------------------------------------------------- positions

    async def _broker_positions(self) -> dict[str, object]:
        out = {}
        for p in await self.broker.get_positions():
            if int(getattr(p, "quantity", 0) or 0) > 0 and getattr(p, "is_active", True):
                out[p.symbol] = p
        return out

    async def _reconcile(self, summary: dict) -> None:
        held = await self._broker_positions()
        for sym, pos in list(self.state.positions.items()):
            if sym in held:
                continue
            # The broker no longer has it: the exchange-side stop (or a person) closed it.
            logger.warning(f"[Daily Trend] {sym} is no longer open at the broker; recording exit at the stop {pos.stop}.")
            await self._record_exit(pos, pos.stop, "EXCHANGE_STOP (estimated fill at stop)", summary)
            del self.state.positions[sym]
            self.state.last_exit_date[sym] = _d(self.now_fn())
        for sym in held:
            if sym in self.symbols and sym not in self.state.positions:
                summary["skipped"].append(f"{sym}: broker shows a position this engine did not open; leaving it alone")

    async def _check_stops(self, summary: dict) -> None:
        for sym, pos in list(self.state.positions.items()):
            try:
                mark = float(await self.mark_fn(sym))
            except Exception as e:
                logger.warning(f"[Daily Trend] No price for {sym} ({e}); stop check skipped this cycle.")
                continue
            if mark <= 0:
                continue
            hit = mark >= pos.stop if pos.side == "SELL" else mark <= pos.stop
            if hit:
                if await self._exit(pos, mark, "STOP", summary):
                    self.state.last_exit_date[sym] = _d(self.now_fn())

    # ----------------------------------------------------------- daily routine

    async def _latest_completed_bar(self) -> pd.Timestamp | None:
        """Start time of the newest fully closed daily candle, read from the exchange's own
        candles (the first symbol that answers), so alignment never has to be assumed."""
        for sym in [*self.state.positions, *self.symbols][:5]:
            try:
                df = completed_bars(await self.candles_fn(sym), self.now_fn())
            except Exception:
                continue
            if df is not None and not df.empty:
                return df.index[-1]
        return None

    async def _daily_routine(self, bar_date: pd.Timestamp, summary: dict) -> None:
        bar = _d(bar_date)
        logger.info(f"📅 [Daily Trend] Processing completed daily candle {bar}")
        views = {}
        for sym in self.symbols:
            try:
                df = completed_bars(await self.candles_fn(sym), self.now_fn())
            except Exception as e:
                summary["skipped"].append(f"{sym}: candle error ({e})")
                continue
            if df is None or df.empty or df.index[-1] != bar_date:
                summary["skipped"].append(f"{sym}: daily candle {bar} not available yet")
                continue
            v = latest_view(df, self.p)
            if v is not None:
                views[sym] = v

        # Not every symbol's candle may be published yet; retry next cycle unless we have
        # enough to act. Positions are always handled when their own candle is present.
        missing_held = [s for s in self.state.positions if s not in views]

        # 1) Manage open positions: trend exit, else trail.
        for sym, pos in list(self.state.positions.items()):
            v = views.get(sym)
            if v is None or _d(v.bar_date) <= pos.entry_signal_date or pos.last_trailed_date == bar:
                continue
            is_short = pos.side == "SELL"
            if (v.short_exit if is_short else v.long_exit):
                ref = await self._safe_mark(sym) or v.close
                if await self._exit(pos, ref, "TREND_EXIT", summary):
                    self.state.last_exit_date[sym] = _d(self.now_fn())
                continue
            pos.best_close = min(pos.best_close, v.close) if is_short else max(pos.best_close, v.close)
            new_stop = trail_stop(pos.stop, pos.best_close, v.atr, self.p, is_short)
            pos.last_trailed_date = bar
            if new_stop != pos.stop:
                old = pos.stop
                pos.stop = round(new_stop, 8)
                summary["stops_moved"].append(f"{sym}: {old:.6g} -> {pos.stop:.6g}")
                await self._set_exchange_stop(pos)

        # 2) New entries — only while the signal is fresh. The rule enters at the open after
        # the signal close; if the bot was down for hours, chasing yesterday's breakout at a
        # very different price is not the tested trade.
        fresh_until = bar_date + pd.Timedelta(days=1) + pd.Timedelta(hours=ENTRY_WINDOW_HOURS)
        if self.now_fn() > fresh_until:
            summary["skipped"].append(f"all entries for {bar}: more than {ENTRY_WINDOW_HOURS}h after the close")
        elif await self._entries_allowed(summary):
            equity, available = await self._funds()
            for sym, v in views.items():
                if sym in self.state.positions:
                    continue
                if len(self.state.positions) >= settings.DAILY_TREND_MAX_POSITIONS:
                    summary["skipped"].append(f"{sym}: max positions reached")
                    break
                wants_long, wants_short = v.long_entry, v.short_entry
                if not (wants_long or wants_short):
                    continue
                if _d(v.bar_date) <= self.state.last_exit_date.get(sym, ""):
                    summary["skipped"].append(f"{sym}: signal on the day of its last exit (matches backtest)")
                    continue
                opened = await self._enter(sym, v, "SELL" if (wants_short and not wants_long) else "BUY",
                                           equity, available, summary)
                if opened:
                    equity, available = await self._funds()

        if not missing_held:
            self.state.last_daily_bar = bar
        else:
            logger.info(f"[Daily Trend] Waiting for {missing_held} daily candle {bar}; will retry next cycle.")

    # ------------------------------------------------------------ order flow

    def _cid(self, prefix: str, sym: str) -> str:
        self._seq += 1
        return f"{prefix}-{sym}-{int(datetime.now(UTC).timestamp())}-{self._seq}"

    async def _safe_mark(self, sym: str) -> float | None:
        try:
            m = float(await self.mark_fn(sym))
            return m if m > 0 else None
        except Exception:
            return None

    async def _enter(self, sym: str, v, side: str, equity: float, available: float, summary: dict) -> bool:
        is_short = side == "SELL"
        mult = self.multiplier_fn(sym)
        if not mult or mult <= 0:
            summary["skipped"].append(f"{sym}: contract multiplier unknown")
            return False
        ref = await self._safe_mark(sym)
        if ref is None:
            summary["skipped"].append(f"{sym}: no live price")
            return False
        stop = initial_stop(ref, v.atr, self.p, is_short)
        size = size_position(equity, available, ref, stop, mult, settings.DAILY_TREND_RISK_PCT,
                             settings.DELTA_MAX_LEVERAGE, settings.DAILY_TREND_MAX_POSITION_NOTIONAL_PCT)
        if size.contracts < 1:
            summary["skipped"].append(f"{sym}: signal, but {size.reason}")
            logger.info(f"[Daily Trend] {sym} breakout signal skipped: {size.reason}")
            return False

        order = OrderIntent(
            client_order_id=self._cid("DT-ENTRY", sym), symbol=sym, exchange="DELTA",
            action=TradeAction.SELL if is_short else TradeAction.BUY, order_type=OrderType.MARKET,
            quantity=size.contracts, price=ref, stop_loss=stop, target=0.0,
            decision_id=f"DT-ENTRY-{_d(v.bar_date)}", product_type="DELIVERY",
        )
        rep = await self.broker.place_order(order)
        if rep.status == OrderStatus.REJECTED:
            summary["skipped"].append(f"{sym}: entry rejected ({rep.order_id})")
            return False
        qty, fill = await self._confirm_fill(sym, rep, size.contracts, ref)
        if qty <= 0:
            summary["skipped"].append(f"{sym}: entry not filled ({rep.order_id})")
            return False
        # Stop is measured from the actual fill, as in the backtest.
        stop = round(initial_stop(fill, v.atr, self.p, is_short), 8)
        pos = TrendPosition(sym, side, qty, fill, stop, fill, _d(v.bar_date),
                            self.now_fn().isoformat(), float(mult))
        self.state.positions[sym] = pos
        self.state.save(self.state_path)  # persist before anything else can fail
        await self._set_exchange_stop(pos)
        msg = f"{sym} {side} {qty} @ {fill:.6g} stop {stop:.6g} (risk ${abs(fill - stop) * qty * mult:.2f})"
        summary["entries"].append(msg)
        logger.info(f"🚀 [Daily Trend] Entered {msg}")
        return True

    async def _confirm_fill(self, sym: str, rep, wanted: int, ref: float) -> tuple[int, float]:
        qty = int(rep.filled_quantity or 0)
        price = float(rep.average_price or 0.0) or ref
        if qty > 0:
            return qty, price
        for _ in range(10):  # live market orders can report SUBMITTED before the fill lands
            await asyncio.sleep(0.5)
            held = await self._broker_positions()
            if sym in held:
                p = held[sym]
                return int(p.quantity), float(p.entry_price or price)
        return 0, price

    async def _exit(self, pos: TrendPosition, ref_price: float, reason: str, summary: dict) -> bool:
        order = OrderIntent(
            client_order_id=self._cid("DT-EXIT", pos.symbol), symbol=pos.symbol, exchange="DELTA",
            action=TradeAction.BUY if pos.side == "SELL" else TradeAction.SELL, order_type=OrderType.MARKET,
            quantity=pos.quantity, price=ref_price, stop_loss=0.0, target=0.0,
            decision_id=f"DT-{reason}", reduce_only=True, product_type="DELIVERY",
        )
        rep = await self.broker.place_order(order)
        if rep.status == OrderStatus.REJECTED and (rep.filled_quantity or 0) <= 0:
            logger.error(f"🚨 [Daily Trend] Exit {reason} for {pos.symbol} REJECTED ({rep.order_id}); will retry next cycle.")
            summary["skipped"].append(f"{pos.symbol}: exit rejected, retrying")
            return False
        fill = float(rep.average_price or 0.0) or ref_price
        await self._record_exit(pos, fill, reason, summary)
        self.state.positions.pop(pos.symbol, None)
        self.state.save(self.state_path)
        return True

    async def _record_exit(self, pos: TrendPosition, exit_price: float, reason: str, summary: dict) -> None:
        is_short = pos.side == "SELL"
        unit = pos.quantity * pos.multiplier
        gross = ((pos.entry_price - exit_price) if is_short else (exit_price - pos.entry_price)) * unit
        fees = TAKER_FEE_PCT * (pos.entry_price + exit_price) * unit
        net = round(gross - fees, 6)
        closed_at = self.now_fn()
        held_s = max(0.0, (closed_at - pd.Timestamp(pos.opened_at)).total_seconds())
        self.closed.append({"symbol": pos.symbol, "side": pos.side, "opened_at": pos.opened_at,
                            "closed_at": closed_at.isoformat(), "entry": pos.entry_price,
                            "exit": exit_price, "reason": reason, "net_usd": net})
        msg = f"{pos.symbol} {reason} @ {exit_price:.6g} net ${net:+.4f}"
        summary["exits"].append(msg)
        logger.info(f"🏁 [Daily Trend] Closed {msg}")
        if self.journal_fn is not None:
            try:
                await self.journal_fn(
                    symbol=pos.symbol, entry_price=pos.entry_price, exit_price=exit_price, pnl=net,
                    exit_reason=reason, holding_period_seconds=held_s, market_regime=STRATEGY_TAG,
                    reflection_notes=f"side={pos.side} qty={pos.quantity} mult={pos.multiplier} rule={self.p.label()}",
                )
            except Exception as e:
                logger.error(f"[Daily Trend] Journal write failed for {pos.symbol}: {e}")

    async def _set_exchange_stop(self, pos: TrendPosition) -> None:
        """Live only: keep a stop resting on the exchange so a crash or outage can't
        leave a position unprotected. Paper positions are protected by _check_stops."""
        if not self.is_live:
            return
        place = getattr(self.broker, "place_bracket_order", None)
        get_products = getattr(self.broker, "get_products", None)
        if place is None or get_products is None:
            logger.error(f"🚨 [Daily Trend] Broker can't hold an exchange stop for {pos.symbol}; relying on polling.")
            return
        try:
            products = await get_products()
            pid = (products.get(pos.symbol) or {}).get("id")
            if not pid:
                raise RuntimeError("product id not found")
            cancel = getattr(self.broker, "cancel_product_orders", None)
            if cancel is not None:
                await cancel(pid)
            res = await place(product_id=pid, product_symbol=pos.symbol, stop_loss=pos.stop, take_profit=None)
            if not res.get("success", False):
                raise RuntimeError(res.get("error", "rejected"))
        except Exception as e:
            logger.error(f"🚨 [Daily Trend] Could not set exchange stop for {pos.symbol} at {pos.stop}: {e}. "
                         f"The engine still checks the stop every cycle.")

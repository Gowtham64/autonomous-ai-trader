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
from apps.terminal.store import TradeStore
from risk.daily_trend_config import RiskConfig, validate_changes
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
    initial_stop: float = 0.0  # stop at entry: defines 1R for comparing with the backtest
    take_profit: float = 0.0   # 0 = none (the rule exits on trend reversal / trailing stop)
    stop_source: str = "RULE"  # RULE | MANUAL (moved from the terminal)


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
        store: TradeStore | None = None,
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
        self.store = store or TradeStore(self.state_path.parent / "daily_trend.db")
        self.risk_path = self.state_path.parent / "daily_trend_risk.json"
        self.cfg = RiskConfig.load(self.risk_path)
        self._seq = 0
        # Trades closed by this process (newest last) — for summaries and tests.
        self.closed: list[dict] = []

    # ------------------------------------------------------------------ cycle

    async def run_cycle(self) -> dict:
        now = self.now_fn()
        summary: dict = {"time": now.isoformat(), "mode": "LIVE" if self.is_live else "PAPER",
                         "entries": [], "exits": [], "stops_moved": [], "skipped": []}

        self.cfg = RiskConfig.load(self.risk_path)
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
        try:
            await self._write_status(summary, now)
        except Exception as e:  # the dashboard is a convenience; never let it break trading
            logger.debug(f"[Daily Trend] Status write note: {e}")
        return summary

    # ------------------------------------------------------------- dashboard

    async def _write_status(self, summary: dict | None, now: pd.Timestamp, record_equity: bool = True) -> None:
        """Snapshot for the terminal: data/daily_trend_status.json (atomic) and, once per
        hour or on any entry/exit, an equity point in the trading store."""
        f = await self.broker.get_funds()
        cash = float(f.get("total_capital") or 0.0)
        start = float(f.get("starting_capital") or 0.0) or (settings.DAILY_TREND_PAPER_CAPITAL if not self.is_live else 0.0)
        positions, unreal_total = [], 0.0
        for sym, pos in self.state.positions.items():
            mark = await self._safe_mark(sym)
            is_short = pos.side == "SELL"
            unit = pos.quantity * pos.multiplier
            unreal = (((pos.entry_price - mark) if is_short else (mark - pos.entry_price)) * unit) if mark else 0.0
            unreal_total += unreal
            positions.append({
                "symbol": sym, "side": pos.side, "qty": pos.quantity, "multiplier": pos.multiplier,
                "entry": pos.entry_price, "mark": mark, "stop": pos.stop, "initial_stop": pos.initial_stop or pos.stop,
                "take_profit": pos.take_profit or None, "stop_source": pos.stop_source,
                "notional_usd": round((mark or pos.entry_price) * unit, 4),
                "unrealized_usd": round(unreal, 4),
                "locked_in_usd": round(((pos.entry_price - pos.stop) if is_short else (pos.stop - pos.entry_price)) * unit, 4),
                "initial_risk_usd": round(abs(pos.entry_price - (pos.initial_stop or pos.stop)) * unit, 4),
                "opened_at": pos.opened_at, "entry_signal_date": pos.entry_signal_date,
            })
        # Delta's live balance (net_equity) already includes open P&L; the paper broker's does not.
        equity = cash if self.is_live else cash + unreal_total
        last_cycle = {k: (summary or {}).get(k) for k in ("entries", "exits", "stops_moved", "skipped")}
        prev = {}
        out = self.state_path.parent / "daily_trend_status.json"
        if summary is None and out.exists():  # command-only refresh keeps the last cycle notes
            try:
                prev = json.loads(out.read_text())
            except Exception:
                prev = {}
        status = {
            "updated_at": now.isoformat(),
            "cycle_at": (summary or {}).get("time") or prev.get("cycle_at") or now.isoformat(),
            "mode": "LIVE" if self.is_live else "PAPER",
            "poll_minutes": settings.DAILY_TREND_POLL_MINUTES,
            "rule": self.p.label(),
            "strategy": STRATEGY_TAG,
            "symbols": self.symbols,
            "risk_pct": self.cfg.risk_pct,
            "risk_config": self.cfg.to_dict(),
            "starting_capital": start,
            "cash_equity": round(cash, 4),
            "available_margin": round(float(f.get("available_margin") or 0.0), 4),
            "used_margin": round(float(f.get("used_margin") or 0.0), 4),
            "leverage_setting": settings.DELTA_MAX_LEVERAGE,
            "equity": round(equity, 4),
            "unrealized_usd": round(unreal_total, 4),
            "peak_equity": round(self.state.peak_equity, 4),
            "day_start_equity": round(self.state.day_start_equity, 4),
            "drawdown_pct": round(max(0.0, self.state.peak_equity - equity) / self.state.peak_equity * 100, 2)
            if self.state.peak_equity > 0 else 0.0,
            "kill_switch": kill_switch.reason if kill_switch.is_engaged else None,
            "realized_edge": (summary or {}).get("realized_edge") or prev.get("realized_edge"),
            "last_daily_bar": self.state.last_daily_bar,
            "positions": positions,
            "last_cycle": last_cycle if summary is not None else prev.get("last_cycle", last_cycle),
        }
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(status, indent=2, default=str))
        os.replace(tmp, out)

        if record_equity:
            moved = bool(summary and (summary.get("entries") or summary.get("exits")))
            ts = now.isoformat() if moved else now.floor("h").isoformat()
            self.store.record_equity(ts, round(equity, 6), round(cash, 6), len(positions))

    def write_heartbeat(self) -> None:
        """Cheap liveness signal for the terminal (written every few seconds by the runner)."""
        hb = self.state_path.parent / "daily_trend_heartbeat.json"
        tmp = hb.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ts": self.now_fn().isoformat(), "pid": os.getpid(),
                                   "mode": "LIVE" if self.is_live else "PAPER"}))
        os.replace(tmp, hb)

    # ------------------------------------------------------------------- risk

    async def _funds(self) -> tuple[float, float]:
        """(mark-to-market equity, available margin).

        Risk limits and sizing must see open losses. Delta's live balance (net_equity)
        already includes them; the paper broker reports cash only, so open P&L is added
        at current marks. (Using cash alone let a large open loss hide from the drawdown
        kill switch until the trade closed.)"""
        f = await self.broker.get_funds()
        equity = float(f.get("total_capital") or 0.0)
        available = float(f.get("available_margin") or 0.0)
        if not self.is_live:
            for sym, pos in self.state.positions.items():
                mark = await self._safe_mark(sym)
                if mark:
                    unit = pos.quantity * pos.multiplier
                    equity += ((pos.entry_price - mark) if pos.side == "SELL" else (mark - pos.entry_price)) * unit
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
        if dd >= self.cfg.max_drawdown_pct:
            msg = (f"Drawdown {dd * 100:.1f}% >= {self.cfg.max_drawdown_pct * 100:.0f}% "
                   f"(worse than the 8-year backtest). New entries halted until an operator resets.")
            kill_switch.trigger("DAILY_TREND", msg, kind="MANUAL_RESET")
            self.store.event("RISK_HALT", msg, level="ERROR", data={"drawdown_pct": dd, "equity": equity})
        elif day_loss >= self.cfg.max_daily_loss_pct:
            msg = f"Daily loss {day_loss * 100:.1f}% >= {self.cfg.max_daily_loss_pct * 100:.0f}%."
            kill_switch.trigger("DAILY_TREND", msg, kind="DAILY_LOSS")
            self.store.event("RISK_HALT", msg, level="ERROR", data={"day_loss_pct": day_loss, "equity": equity})

    async def _entries_allowed(self, summary: dict) -> bool:
        if self.cfg.entries_paused:
            summary["skipped"].append("all entries: paused from the terminal")
            return False
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
            # Prefer the exchange's ACTUAL fills over assuming a fill exactly at the stop.
            exit_px, how = await self._actual_exit_price(pos)
            if exit_px is None:
                exit_px, how = pos.stop, "estimated at the stop (fills unavailable)"
            logger.warning(f"[Daily Trend] {sym} is no longer open at the broker; exit {exit_px} ({how}).")
            self.store.event("RECONCILED", f"{sym} no longer open at the broker; recorded as closed at {exit_px:.6g} "
                             f"({how})", level="WARN", symbol=sym)
            reason = "EXCHANGE_STOP" if "fills" in how and "unavailable" not in how else "EXCHANGE_STOP (estimated fill at stop)"
            await self._record_exit(pos, exit_px, reason, summary)
            del self.state.positions[sym]
            self.state.last_exit_date[sym] = _d(self.now_fn())
        for sym in held:
            if sym in self.symbols and sym not in self.state.positions:
                summary["skipped"].append(f"{sym}: broker shows a position this engine did not open; leaving it alone")

    async def _actual_exit_price(self, pos: TrendPosition) -> tuple[float | None, str]:
        """Size-weighted average price of the closing-side fills since the position opened."""
        get = getattr(self.broker, "get_recent_fills", None)
        if get is None:
            return None, "broker has no fills endpoint"
        try:
            fills = await get(pos.symbol, since=pd.Timestamp(pos.opened_at).to_pydatetime())
        except Exception as e:
            return None, f"fills unavailable: {e}"
        closing = "BUY" if pos.side == "SELL" else "SELL"
        picked, need = [], pos.quantity
        for f in sorted(fills, key=lambda f: str(f.get("created_at") or ""), reverse=True):
            if f["side"] == closing and need > 0:
                take = min(need, f["size"])
                picked.append((take, f["price"]))
                need -= take
        if not picked or need > 1e-9:
            return None, "no matching closing fills found"
        qty = sum(q for q, _ in picked)
        return sum(q * p for q, p in picked) / qty, f"from {len(picked)} exchange fills"

    async def _check_stops(self, summary: dict) -> None:
        for sym, pos in list(self.state.positions.items()):
            try:
                mark = float(await self.mark_fn(sym))
            except Exception as e:
                logger.warning(f"[Daily Trend] No price for {sym} ({e}); stop check skipped this cycle.")
                continue
            if mark <= 0:
                continue
            is_short = pos.side == "SELL"
            hit = mark >= pos.stop if is_short else mark <= pos.stop
            tp_hit = bool(pos.take_profit) and (mark <= pos.take_profit if is_short else mark >= pos.take_profit)
            if hit or tp_hit:
                reason = "STOP" if hit else "TAKE_PROFIT"
                if await self._exit(pos, mark, reason, summary):
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
        acts: dict[str, tuple[str, str]] = {}  # symbol -> (action, note) for the signals table
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
                    acts[sym] = ("EXITED", f"close {v.close:.6g} broke the {self.p.exit_n}-day low")
                else:
                    acts[sym] = ("EXIT_FAILED", "exit order rejected; retrying")
                continue
            pos.best_close = min(pos.best_close, v.close) if is_short else max(pos.best_close, v.close)
            new_stop = trail_stop(pos.stop, pos.best_close, v.atr, self.p, is_short)
            pos.last_trailed_date = bar
            if new_stop != pos.stop:
                old = pos.stop
                pos.stop = round(new_stop, 8)
                pos.stop_source = "RULE"
                summary["stops_moved"].append(f"{sym}: {old:.6g} -> {pos.stop:.6g}")
                self.store.event("STOP_MOVED", f"{sym} trailing stop {old:.6g} -> {pos.stop:.6g}", symbol=sym,
                                 data={"old": old, "new": pos.stop, "best_close": pos.best_close, "atr": v.atr})
                await self._set_exchange_stop(pos)
                acts[sym] = ("TRAILED", f"stop raised to {pos.stop:.6g}")
            else:
                acts[sym] = ("HOLDING", f"stop unchanged at {pos.stop:.6g}")

        # 2) New entries — only while the signal is fresh. The rule enters at the open after
        # the signal close; if the bot was down for hours, chasing yesterday's breakout at a
        # very different price is not the tested trade.
        fresh_until = bar_date + pd.Timedelta(days=1) + pd.Timedelta(hours=ENTRY_WINDOW_HOURS)
        if self.now_fn() > fresh_until:
            summary["skipped"].append(f"all entries for {bar}: more than {ENTRY_WINDOW_HOURS}h after the close")
            for sym, v in views.items():
                if (v.long_entry or v.short_entry) and sym not in self.state.positions:
                    acts[sym] = ("SKIPPED", f"signal, but more than {ENTRY_WINDOW_HOURS}h after the close")
        elif not await self._entries_allowed(summary):
            for sym, v in views.items():
                if (v.long_entry or v.short_entry) and sym not in self.state.positions:
                    acts[sym] = ("SKIPPED", f"signal, but {summary['skipped'][-1]}")
        else:
            equity, available = await self._funds()
            for sym, v in views.items():
                if sym in self.state.positions:
                    continue
                wants_long, wants_short = v.long_entry, v.short_entry
                if not (wants_long or wants_short):
                    continue
                if sym in self.cfg.disabled_symbols:
                    acts[sym] = ("SKIPPED", "signal, but this coin is disabled in the terminal")
                    continue
                if len(self.state.positions) >= self.cfg.max_positions:
                    summary["skipped"].append(f"{sym}: max positions reached")
                    acts[sym] = ("SKIPPED", f"signal, but max positions ({self.cfg.max_positions}) reached")
                    continue
                if _d(v.bar_date) <= self.state.last_exit_date.get(sym, ""):
                    summary["skipped"].append(f"{sym}: signal on the day of its last exit (matches backtest)")
                    acts[sym] = ("SKIPPED", "signal on the day of its last exit (matches backtest)")
                    continue
                n_skipped = len(summary["skipped"])
                opened = await self._enter(sym, v, "SELL" if (wants_short and not wants_long) else "BUY",
                                           equity, available, summary)
                if opened:
                    acts[sym] = ("ENTERED", summary["entries"][-1])
                    equity, available = await self._funds()
                else:
                    note = summary["skipped"][-1] if len(summary["skipped"]) > n_skipped else "entry not taken"
                    acts[sym] = ("SKIPPED", note)

        for sym, v in views.items():
            action, note = acts.get(sym, ("NONE", ""))
            self.store.record_signal(
                bar_date=bar, symbol=sym, close=v.close, entry_level=v.entry_level, exit_level=v.exit_level,
                atr=v.atr, long_entry=int(v.long_entry), long_exit=int(v.long_exit), action=action, note=note,
                ts=self.now_fn().isoformat(),
            )

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
        size = size_position(equity, available, ref, stop, mult, self.cfg.risk_pct,
                             settings.DELTA_MAX_LEVERAGE, self.cfg.max_position_notional_pct)
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
        self._log_order(order, rep, "ENTRY", f"{self.p.entry_n}-day breakout on {_d(v.bar_date)}", mult)
        if rep.status == OrderStatus.REJECTED:
            summary["skipped"].append(f"{sym}: entry rejected ({rep.order_id})")
            self.store.event("ORDER_REJECTED", f"{sym} entry rejected by broker ({rep.order_id})", "ERROR", sym)
            return False
        qty, fill = await self._confirm_fill(sym, rep, size.contracts, ref)
        if qty <= 0:
            summary["skipped"].append(f"{sym}: entry not filled ({rep.order_id})")
            return False
        # Stop is measured from the actual fill, as in the backtest.
        stop = round(initial_stop(fill, v.atr, self.p, is_short), 8)
        pos = TrendPosition(sym, side, qty, fill, stop, fill, _d(v.bar_date),
                            self.now_fn().isoformat(), float(mult), initial_stop=stop)
        self.state.positions[sym] = pos
        self.state.save(self.state_path)  # persist before anything else can fail
        await self._set_exchange_stop(pos)
        msg = f"{sym} {side} {qty} @ {fill:.6g} stop {stop:.6g} (risk ${abs(fill - stop) * qty * mult:.2f})"
        summary["entries"].append(msg)
        self.store.event("ENTRY", msg, symbol=sym, data={"qty": qty, "fill": fill, "stop": stop, "atr": v.atr,
                                                          "entry_level": v.entry_level, "bar": _d(v.bar_date)})
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

    async def _exit(self, pos: TrendPosition, ref_price: float, reason: str, summary: dict,
                    quantity: int | None = None) -> bool:
        """Close `quantity` contracts (default: all). Recorded as closed only after the
        broker confirms; a rejected exit leaves the position open and is retried."""
        qty = pos.quantity if quantity is None else int(quantity)
        partial = qty < pos.quantity
        order = OrderIntent(
            client_order_id=self._cid("DT-EXIT", pos.symbol), symbol=pos.symbol, exchange="DELTA",
            action=TradeAction.BUY if pos.side == "SELL" else TradeAction.SELL, order_type=OrderType.MARKET,
            quantity=qty, price=ref_price, stop_loss=0.0, target=0.0,
            decision_id=f"DT-{reason}", reduce_only=True, product_type="DELIVERY",
        )
        rep = await self.broker.place_order(order)
        self._log_order(order, rep, "PARTIAL_EXIT" if partial else "EXIT", reason, pos.multiplier)
        filled = int(rep.filled_quantity or 0)
        if rep.status == OrderStatus.REJECTED and filled <= 0:
            logger.error(f"🚨 [Daily Trend] Exit {reason} for {pos.symbol} REJECTED ({rep.order_id}); will retry next cycle.")
            summary["skipped"].append(f"{pos.symbol}: exit rejected, retrying")
            self.store.event("ORDER_REJECTED", f"{pos.symbol} exit ({reason}) rejected ({rep.order_id}); retrying",
                             "ERROR", pos.symbol)
            return False
        if filled <= 0:
            filled = qty  # broker reported SUBMITTED without a size; market exits fill
        filled = min(filled, pos.quantity)
        fill = float(rep.average_price or 0.0) or ref_price
        await self._record_exit(pos, fill, reason, summary, quantity=filled)
        if filled < pos.quantity:
            pos.quantity -= filled
            self.store.event("PARTIAL_EXIT", f"{pos.symbol} closed {filled}, {pos.quantity} still open",
                             symbol=pos.symbol)
        else:
            self.state.positions.pop(pos.symbol, None)
        self.state.save(self.state_path)
        return True

    def _log_order(self, order: OrderIntent, rep, purpose: str, reason: str, multiplier: float) -> None:
        try:
            px = float(rep.average_price or 0.0) or float(order.price or 0.0)
            filled = int(rep.filled_quantity or 0)
            self.store.record_order(
                client_order_id=order.client_order_id, ts=self.now_fn().isoformat(),
                mode="LIVE" if self.is_live else "PAPER", symbol=order.symbol, side=order.action.value,
                purpose=purpose, order_type=order.order_type.value, quantity=order.quantity,
                reference_price=order.price, status=str(getattr(rep.status, "value", rep.status)),
                filled_quantity=filled, average_price=float(rep.average_price or 0.0) or None,
                fee_estimate=round(TAKER_FEE_PCT * px * (filled or order.quantity) * multiplier, 6),
                reason=reason, broker_order_id=str(rep.order_id),
                response_json=json.dumps(rep.model_dump(mode="json") if hasattr(rep, "model_dump") else str(rep),
                                         default=str),
            )
        except Exception as e:
            logger.error(f"[Daily Trend] Could not record order {order.client_order_id}: {e}")

    async def _record_exit(self, pos: TrendPosition, exit_price: float, reason: str, summary: dict,
                           quantity: int | None = None) -> None:
        is_short = pos.side == "SELL"
        qty = pos.quantity if quantity is None else quantity
        unit = qty * pos.multiplier
        gross = ((pos.entry_price - exit_price) if is_short else (exit_price - pos.entry_price)) * unit
        fees = TAKER_FEE_PCT * (pos.entry_price + exit_price) * unit
        net = round(gross - fees, 6)
        init_risk = abs(pos.entry_price - (pos.initial_stop or pos.stop)) * unit
        r_mult = round(net / init_risk, 3) if init_risk > 0 else 0.0
        closed_at = self.now_fn()
        held_s = max(0.0, (closed_at - pd.Timestamp(pos.opened_at)).total_seconds())
        self.closed.append({"symbol": pos.symbol, "side": pos.side, "opened_at": pos.opened_at,
                            "closed_at": closed_at.isoformat(), "entry": pos.entry_price,
                            "exit": exit_price, "reason": reason, "net_usd": net, "r": r_mult, "qty": qty})
        try:
            self.store.record_trade(
                trade_uid=f"{pos.symbol}-{pos.opened_at}-{closed_at.isoformat()}-{qty}",
                mode="LIVE" if self.is_live else "PAPER", symbol=pos.symbol, side=pos.side, quantity=qty,
                multiplier=pos.multiplier, entry_time=pos.opened_at, entry_price=pos.entry_price,
                initial_stop=pos.initial_stop or pos.stop, exit_time=closed_at.isoformat(), exit_price=exit_price,
                exit_reason=reason, gross_pnl=round(gross, 6), fees=round(fees, 6), net_pnl=net, r_multiple=r_mult,
                strategy=STRATEGY_TAG,
            )
            self.store.event("EXIT", f"{pos.symbol} {reason} {qty} @ {exit_price:.6g} net ${net:+.4f} ({r_mult:+.2f}R)",
                             symbol=pos.symbol, data={"qty": qty, "exit": exit_price, "net": net, "r": r_mult})
        except Exception as e:
            logger.error(f"[Daily Trend] Could not record trade for {pos.symbol}: {e}")
        msg = f"{pos.symbol} {reason} @ {exit_price:.6g} net ${net:+.4f}"
        summary["exits"].append(msg)
        logger.info(f"🏁 [Daily Trend] Closed {msg}")
        if self.journal_fn is not None:
            try:
                await self.journal_fn(
                    symbol=pos.symbol, entry_price=pos.entry_price, exit_price=exit_price, pnl=net,
                    exit_reason=reason, holding_period_seconds=held_s, market_regime=STRATEGY_TAG,
                    reflection_notes=(f"side={pos.side} qty={qty} mult={pos.multiplier} r={r_mult} "
                                      f"opened={pos.opened_at} rule={self.p.label()}"),
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
            res = await place(product_id=pid, product_symbol=pos.symbol, stop_loss=pos.stop,
                              take_profit=pos.take_profit or None)
            if not res.get("success", False):
                raise RuntimeError(res.get("error", "rejected"))
            self.store.event("EXCHANGE_STOP_SET", f"{pos.symbol} exchange stop at {pos.stop}"
                             + (f", take-profit {pos.take_profit}" if pos.take_profit else ""), symbol=pos.symbol)
        except Exception as e:
            logger.error(f"🚨 [Daily Trend] Could not set exchange stop for {pos.symbol} at {pos.stop}: {e}. "
                         f"The engine still checks the stop every cycle.")
            self.store.event("EXCHANGE_STOP_FAILED", f"{pos.symbol}: could not set exchange stop at {pos.stop}: {e}",
                             "ERROR", pos.symbol)

    # ------------------------------------------------------------- commands

    async def process_commands(self) -> list[dict]:
        """Execute queued terminal commands. The engine is the only component that trades;
        each command is validated here (again) and answered with what the broker confirmed."""
        results = []
        for cmd in self.store.claim_commands():
            kind, p = cmd["kind"], cmd["payload"]
            try:
                ok, result = await self._run_command(kind, p)
            except Exception as e:  # never leave a command hanging
                ok, result = False, {"error": f"{type(e).__name__}: {e}"}
            self.store.finish_command(cmd["id"], ok, result)
            self.store.event("COMMAND", f"{kind} {'done' if ok else 'failed'}: {result.get('message') or result.get('error')}",
                             "INFO" if ok else "WARN", p.get("symbol"), data={"command_id": cmd["id"], "payload": p,
                                                                               "result": result})
            results.append({"id": cmd["id"], "ok": ok, **result})
        if results:
            self.state.save(self.state_path)
            try:
                await self._write_status(None, self.now_fn(), record_equity=False)
            except Exception as e:
                logger.debug(f"[Daily Trend] Status refresh note: {e}")
        return results

    async def _run_command(self, kind: str, p: dict) -> tuple[bool, dict]:
        summary = {"entries": [], "exits": [], "stops_moved": [], "skipped": []}
        if kind == "PAUSE_ENTRIES":
            paused = p.get("paused")
            if not isinstance(paused, bool):
                return False, {"error": "paused must be true or false"}
            self.cfg = RiskConfig.load(self.risk_path)
            self.cfg.entries_paused = paused
            self.cfg.save(self.risk_path)
            return True, {"message": "new entries paused" if paused else "new entries resumed"}

        if kind == "UPDATE_RISK_CONFIG":
            changes, errors = validate_changes(p.get("changes") or {}, self.symbols)
            if errors:
                return False, {"error": "; ".join(errors)}
            self.cfg = RiskConfig.load(self.risk_path)
            for k, v in changes.items():
                setattr(self.cfg, k, v)
            self.cfg.save(self.risk_path)
            return True, {"message": f"risk settings updated: {changes}", "risk_config": self.cfg.to_dict()}

        if kind == "ENGAGE_KILL_SWITCH":
            reason = str(p.get("reason") or "engaged from the terminal")[:200]
            kill_switch.trigger("TERMINAL", reason, kind="MANUAL_RESET")
            return True, {"message": f"kill switch engaged: {reason}"}

        if kind == "RESET_KILL_SWITCH":
            if not kill_switch.is_engaged:
                return False, {"error": "kill switch is not engaged"}
            kill_switch.reset("TERMINAL")
            return True, {"message": "kill switch reset; drawdown baseline restarts from current equity"}

        sym = p.get("symbol")
        pos = self.state.positions.get(sym)
        if pos is None:
            return False, {"error": f"no open position in {sym}"}
        mark = await self._safe_mark(sym)
        if mark is None:
            return False, {"error": f"no live price for {sym}; try again"}
        is_short = pos.side == "SELL"

        if kind == "CLOSE_POSITION":
            qty = p.get("quantity")
            qty = pos.quantity if qty in (None, "", 0) else qty
            try:
                qty = int(qty)
            except (TypeError, ValueError):
                return False, {"error": "quantity must be a whole number"}
            if not (1 <= qty <= pos.quantity):
                return False, {"error": f"quantity must be between 1 and {pos.quantity}"}
            reason = "MANUAL_CLOSE" if qty == pos.quantity else "MANUAL_PARTIAL_CLOSE"
            n_before = len(self.closed)
            if not await self._exit(pos, mark, reason, summary, quantity=qty):
                return False, {"error": "broker rejected the close order; position unchanged", "details": summary["skipped"]}
            if qty == pos.quantity or sym not in self.state.positions:
                self.state.last_exit_date[sym] = _d(self.now_fn())
            elif self.is_live:
                await self._set_exchange_stop(self.state.positions[sym])
            t = self.closed[-1] if len(self.closed) > n_before else {}
            return True, {"message": f"closed {qty} {sym} @ {t.get('exit', mark):.6g}, net ${t.get('net_usd', 0):+.4f}",
                          "fill": t.get("exit"), "net_usd": t.get("net_usd"), "r": t.get("r"),
                          "remaining": self.state.positions[sym].quantity if sym in self.state.positions else 0}

        if kind == "MOVE_STOP":
            try:
                new = float(p.get("stop"))
            except (TypeError, ValueError):
                return False, {"error": "stop must be a price"}
            init = pos.initial_stop or pos.stop
            if new <= 0:
                return False, {"error": "stop must be positive"}
            if (not is_short and new >= mark) or (is_short and new <= mark):
                return False, {"error": f"stop {new} is on the wrong side of the current price {mark}; it would fill immediately"}
            if (not is_short and new < init) or (is_short and new > init):
                return False, {"error": f"stop can't be wider than the initial stop {init} (that risks more than planned)"}
            old = pos.stop
            pos.stop, pos.stop_source = round(new, 8), "MANUAL"
            await self._set_exchange_stop(pos)
            self.store.event("STOP_MOVED", f"{sym} stop moved manually {old:.6g} -> {pos.stop:.6g}", symbol=sym,
                             data={"old": old, "new": pos.stop, "source": "MANUAL"})
            return True, {"message": f"{sym} stop {old:.6g} -> {pos.stop:.6g} (the trailing rule still only raises it)",
                          "stop": pos.stop}

        if kind == "SET_TAKE_PROFIT":
            tp = p.get("take_profit")
            if tp in (None, "", 0):
                pos.take_profit = 0.0
                await self._set_exchange_stop(pos)
                return True, {"message": f"{sym} take-profit removed (exits on the rule again)"}
            try:
                tp = float(tp)
            except (TypeError, ValueError):
                return False, {"error": "take_profit must be a price"}
            if (not is_short and tp <= mark) or (is_short and tp >= mark):
                return False, {"error": f"take-profit {tp} is on the wrong side of the current price {mark}"}
            pos.take_profit = round(tp, 8)
            await self._set_exchange_stop(pos)
            self.store.event("TAKE_PROFIT_SET", f"{sym} manual take-profit at {pos.take_profit:.6g}", symbol=sym)
            return True, {"message": f"{sym} take-profit set at {pos.take_profit:.6g}. Note: the tested rule has no "
                                     f"take-profit; capping winners lowers the backtested edge.", "take_profit": pos.take_profit}

        return False, {"error": f"unknown command {kind}"}

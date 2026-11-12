"""Trading terminal server (standard library only).

    GET  /                       terminal UI
    GET  /api/state              account, live positions (revalued at exchange marks), health
    GET  /api/stream             Server-Sent Events: pushes /api/state when it changes (+ heartbeats)
    GET  /api/markets            watched coins: live ticker, daily trend/indicators, strategy levels
    GET  /api/candles            ?symbol=&tf=1d|4h|1h|15m|5m|1m&bars= candles, indicators, trade markers
    GET  /api/orders             ?symbol=&status=&limit=   every order the engine sent + broker response
    GET  /api/trades             ?symbol=&limit=           closed trades
    GET  /api/analytics          summary, daily/weekly/monthly/coin/side, equity + drawdown curves
    GET  /api/signals            latest daily signal check per coin (what the engine saw and did)
    GET  /api/events             ?kind=&limit=             audit log
    GET  /api/risk               exposure, capital at risk, limits, violations
    GET  /api/strategy           rule, coins, risk settings + limits, performance
    GET  /api/system             component health (engine, cycle, scan, market feed, stops, queue)
    GET  /api/commands/<id>      command status / broker result
    POST /api/commands           {kind, payload}  -> queued for the ENGINE to execute
    POST /api/chat               {message, history} -> grounded Gemini answer (read-only)

The server never sends orders itself. Every action becomes a command the engine executes
and answers. Security: binds to 127.0.0.1; Host header must be localhost (DNS-rebinding
guard); POSTs need the per-session token and a same-origin Origin (CSRF guard).
"""

from __future__ import annotations

import hashlib
import json
import math
import mimetypes
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from apps.terminal import analytics, chat
from apps.terminal.market import MarketData, indicator_frame, summarize_coin
from apps.terminal.store import COMMAND_KINDS, TradeStore
from risk.daily_trend_config import LIMITS, RiskConfig, validate_changes
from strategy.daily_trend import PRE_REGISTERED, completed_bars

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
CHART_JS = ROOT / "apps" / "dashboard" / "lightweight-charts.standalone.production.js"
ENGINE_ALIVE_SECONDS = 30
POSITION_COMMANDS = {"CLOSE_POSITION", "MOVE_STOP", "SET_TAKE_PROFIT"}

# 8-year backtest of the same rule (tools/backtest_trend_daily.py --source binance, 2018-2026)
BACKTEST = {"period": "2018-11 to 2026-11 (Binance daily, proxy for Delta)", "trades": 376, "win_rate_pct": 41.2,
            "avg_r": 0.54, "avg_r_95ci": [0.26, 0.82], "avg_win_r": 2.32, "avg_loss_r": -0.71,
            "profit_factor": 2.29, "max_drawdown_pct_at_1pct_risk": 18.3,
            "note": "Weaker since 2024 (2024 +21%, 2025 -9%, 2026 +2%). Coin list is today's survivors."}


def clean(o):
    """JSON-safe: NaN/inf -> None."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


def _age(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return max(0.0, (datetime.now(UTC) - t).total_seconds())
    except ValueError:
        return None


class Terminal:
    def __init__(self, data_dir: str | Path = ROOT / "data", market: MarketData | None = None,
                 symbols: list[str] | None = None, chat_post=None, chat_key: str | None = None):
        from core.config.settings import settings
        self.data = Path(data_dir)
        self.store = TradeStore(self.data / "daily_trend.db")
        self.market = market or MarketData()
        self.symbols = symbols or list(settings.DAILY_TREND_SYMBOLS)
        self.token = secrets.token_urlsafe(24)
        self.chat_post = chat_post
        self.chat_key = chat_key
        self.poll_minutes = settings.DAILY_TREND_POLL_MINUTES
        self._pool = ThreadPoolExecutor(max_workers=8)

    # ----------------------------------------------------------------- files

    def _json(self, name: str) -> dict:
        try:
            return json.loads((self.data / name).read_text())
        except Exception:
            return {}

    def status(self) -> dict:
        return self._json("daily_trend_status.json")

    def heartbeat(self) -> dict:
        return self._json("daily_trend_heartbeat.json")

    def engine_alive(self) -> bool:
        age = _age(self.heartbeat().get("ts"))
        return age is not None and age < ENGINE_ALIVE_SECONDS

    # ------------------------------------------------------------------ state

    def state(self) -> dict:
        st = self.status()
        hb = self.heartbeat()
        held = [p["symbol"] for p in st.get("positions") or []]
        tick = self.market.tickers(sorted(set(self.symbols) | set(held)))
        items = tick.get("items", {})
        now = datetime.now(UTC)
        positions, live_unreal = [], 0.0
        for p in st.get("positions") or []:
            t = items.get(p["symbol"], {})
            mark = t.get("mark") or p.get("mark")
            short = p["side"] == "SELL"
            unit = p["qty"] * p["multiplier"]
            unreal = (((p["entry"] - mark) if short else (mark - p["entry"])) * unit) if mark else 0.0
            live_unreal += unreal
            init_risk = p.get("initial_risk_usd") or 0.0
            tp = p.get("take_profit")
            init_stop = p.get("initial_stop") or p["stop"]
            opened = datetime.fromisoformat(p["opened_at"]) if p.get("opened_at") else None
            positions.append({
                **p, "mark": mark, "bid": t.get("bid"), "ask": t.get("ask"),
                "unrealized_usd": round(unreal, 6),
                "pnl_pct": round(unreal / (p["entry"] * unit) * 100, 3) if p["entry"] and unit else None,
                "r_now": round(unreal / init_risk, 3) if init_risk else None,
                "distance_to_stop_pct": round(((mark - p["stop"]) if not short else (p["stop"] - mark)) / mark * 100, 3) if mark else None,
                "risk_reward": round(abs(tp - p["entry"]) / abs(p["entry"] - init_stop), 2) if tp and p["entry"] != init_stop else None,
                "duration_hours": round((now - opened).total_seconds() / 3600, 1) if opened else None,
                "status": "OPEN",
            })
        base_equity = float(st.get("equity") or 0.0) - float(st.get("unrealized_usd") or 0.0)
        equity_live = base_equity + live_unreal if st else None
        trades = self.store.query("SELECT * FROM trades ORDER BY exit_time")
        summ = analytics.summary(trades)
        start = float(st.get("starting_capital") or 0.0)
        hb_age, st_age, cyc_age = _age(hb.get("ts")), _age(st.get("updated_at")), _age(st.get("cycle_at"))
        cmds = self.store.query("SELECT id, kind, payload_json, status, result_json, created_at, updated_at "
                                "FROM commands ORDER BY created_at DESC LIMIT 12")
        for c in cmds:
            c["payload"] = json.loads(c.pop("payload_json"))
            c["result"] = json.loads(c.pop("result_json")) if c.get("result_json") else None
        return clean({
            "server_time": now.isoformat(),
            "has_engine_data": bool(st),
            "mode": st.get("mode") or hb.get("mode") or "UNKNOWN",
            "strategy": st.get("strategy", "DAILY_TREND"), "rule": st.get("rule") or PRE_REGISTERED.label(),
            "account": {
                "starting_capital": start, "equity": equity_live, "cash_equity": st.get("cash_equity"),
                "available_margin": st.get("available_margin"), "used_margin": st.get("used_margin"),
                "unrealized_usd": round(live_unreal, 6),
                "total_pnl": round(equity_live - start, 6) if (equity_live is not None and start) else None,
                "total_pnl_pct": round((equity_live - start) / start * 100, 3) if (equity_live is not None and start) else None,
                "today_realized": summ["today_realized"], "today_unrealized": round(live_unreal, 6),
                "peak_equity": st.get("peak_equity"), "drawdown_pct": st.get("drawdown_pct"),
            },
            "performance": summ,
            "positions": positions,
            "risk": analytics.risk_view({**st, "equity": equity_live or 0.0},
                                        {s: items.get(s, {}).get("mark") for s in held}),
            "risk_config": st.get("risk_config") or RiskConfig.load(self.data / "daily_trend_risk.json").to_dict(),
            "kill_switch": st.get("kill_switch"),
            "last_cycle": st.get("last_cycle") or {},
            "last_daily_bar": st.get("last_daily_bar"),
            "health": {
                "engine_alive": hb_age is not None and hb_age < ENGINE_ALIVE_SECONDS,
                "engine_heartbeat_age_s": hb_age, "status_age_s": st_age, "cycle_age_s": cyc_age,
                "poll_minutes": self.poll_minutes,
                "market_data_age_s": round(time.time() - tick["ts"], 1) if tick.get("ts") else None,
                "market_data_error": tick.get("error"),
            },
            "commands": cmds,
        })

    # ---------------------------------------------------------------- markets

    def _daily(self, sym: str) -> pd.DataFrame | None:
        try:
            return completed_bars(self.market.candles(sym, "1d", 120))
        except Exception:
            return None

    def markets(self) -> dict:
        from portfolio.position_sizer import get_delta_contract_multiplier
        tick = self.market.tickers(self.symbols)
        dailies = dict(zip(self.symbols, self._pool.map(self._daily, self.symbols)))
        latest = {r["symbol"]: r for r in self.store.query(
            "SELECT * FROM signals WHERE bar_date = (SELECT MAX(bar_date) FROM signals)")}
        st = self.status()
        held = {p["symbol"] for p in st.get("positions") or []}
        disabled = set((st.get("risk_config") or {}).get("disabled_symbols") or [])
        rows = []
        for sym in self.symbols:
            t = tick.get("items", {}).get(sym, {})
            d = summarize_coin(dailies.get(sym))
            sig = latest.get(sym) or {}
            price = t.get("mark") or t.get("last")
            entry_level = sig.get("entry_level") or d.get("high_55d")
            exit_level = sig.get("exit_level") or d.get("low_20d")
            ours = get_delta_contract_multiplier(sym)
            exch = t.get("contract_value")
            rows.append({
                **t, **{k: v for k, v in d.items() if k not in ("high_55d", "low_20d")},
                "symbol": sym, "price": price,
                "breakout_level": entry_level, "exit_level": exit_level,
                "to_breakout_pct": round((entry_level - price) / price * 100, 2) if (entry_level and price) else None,
                "signal_bar": sig.get("bar_date"), "signal_action": sig.get("action"), "signal_note": sig.get("note"),
                "long_entry_signal": bool(sig.get("long_entry")) if sig else None,
                "in_position": sym in held, "enabled": sym not in disabled,
                "contract_value_bot": ours, "contract_value_exchange": exch,
                "contract_mismatch": bool(ours and exch and abs(ours - exch) / exch > 1e-9),
            })
        return clean({"ts": tick.get("ts"), "error": tick.get("error"), "items": rows})

    def candles(self, sym: str, tf: str, bars: int) -> dict:
        if sym not in self.symbols:
            raise ValueError(f"unknown symbol {sym}")
        df = self.market.candles(sym, tf, bars)
        if df.empty:
            return {"symbol": sym, "tf": tf, "candles": [], "error": "no candles returned by Delta"}
        ind = indicator_frame(df, tf)
        secs = [int(ts.timestamp()) for ts in df.index]
        series = lambda col: [{"time": s, "value": v} for s, v in zip(secs, ind[col].tolist()) if pd.notna(v)]  # noqa: E731
        trades = self.store.query("SELECT * FROM trades WHERE symbol=? ORDER BY entry_time", (sym,))
        first = df.index[0]
        markers = []
        bar_sec = int((df.index[-1] - df.index[-2]).total_seconds()) if len(df) > 1 else 3600

        def snap(ts: str) -> int:
            t = pd.Timestamp(ts)
            t = t.tz_localize("UTC") if t.tzinfo is None else t
            return int(t.timestamp()) // bar_sec * bar_sec

        for t in trades:
            if pd.Timestamp(t["exit_time"]) >= first:
                markers.append({"time": snap(t["entry_time"]), "position": "belowBar", "shape": "arrowUp",
                                "color": "#3b82f6", "text": f"Buy {t['entry_price']:.6g}"})
                win = t["net_pnl"] > 0
                markers.append({"time": snap(t["exit_time"]), "position": "aboveBar", "shape": "arrowDown",
                                "color": "#22c55e" if win else "#ef4444",
                                "text": f"{t['exit_reason'].split(' ')[0]} {t['net_pnl']:+.2f}"})
        pos = next((p for p in self.status().get("positions") or [] if p["symbol"] == sym), None)
        lines = []
        if pos:
            markers.append({"time": snap(pos["opened_at"]), "position": "belowBar", "shape": "arrowUp",
                            "color": "#3b82f6", "text": f"Open {pos['entry']:.6g}"})
            lines.append({"price": pos["entry"], "title": "Entry", "color": "#3b82f6"})
            lines.append({"price": pos["stop"], "title": "Stop (trailing)" if pos.get("stop_source") != "MANUAL" else "Stop (manual)",
                          "color": "#ef4444"})
            if pos.get("initial_stop") and pos["initial_stop"] != pos["stop"]:
                lines.append({"price": pos["initial_stop"], "title": "Initial stop", "color": "#7f1d1d"})
            if pos.get("take_profit"):
                lines.append({"price": pos["take_profit"], "title": "Take profit", "color": "#22c55e"})
        sig = self.store.query("SELECT * FROM signals WHERE symbol=? ORDER BY bar_date DESC LIMIT 1", (sym,))
        levels = {}
        if sig:
            levels = {"breakout": sig[0]["entry_level"], "exit": sig[0]["exit_level"], "bar_date": sig[0]["bar_date"]}
        markers.sort(key=lambda m: m["time"])
        return clean({
            "symbol": sym, "tf": tf,
            "candles": [{"time": s, "open": o, "high": h, "low": lo, "close": c}
                        for s, o, h, lo, c in zip(secs, df["open"], df["high"], df["low"], df["close"])],
            "volume": [{"time": s, "value": v, "color": "rgba(34,197,94,.35)" if c >= o else "rgba(239,68,68,.35)"}
                       for s, v, o, c in zip(secs, df["volume"], df["open"], df["close"])],
            "overlays": {k: series(k) for k in ("ema20", "ema50", "sma20", "bb_upper", "bb_lower", "vwap")},
            "rsi": series("rsi"),
            "macd": {"macd": series("macd"), "signal": series("macd_signal"),
                     "hist": [{"time": s, "value": v, "color": "rgba(34,197,94,.6)" if v >= 0 else "rgba(239,68,68,.6)"}
                              for s, v in zip(secs, ind["macd_hist"].tolist()) if pd.notna(v)]},
            "markers": markers, "lines": lines, "strategy_levels": levels,
            "last": {"close": float(df["close"].iloc[-1]), "time": secs[-1]},
        })

    # ------------------------------------------------------------- records

    def orders(self, q: dict) -> list[dict]:
        sql, args = "SELECT * FROM orders WHERE 1=1", []
        if q.get("symbol"):
            sql += " AND symbol=?"
            args.append(q["symbol"])
        if q.get("status"):
            sql += " AND status=?"
            args.append(q["status"].upper())
        sql += " ORDER BY ts DESC LIMIT ?"
        args.append(min(int(q.get("limit") or 200), 1000))
        rows = self.store.query(sql, tuple(args))
        for r in rows:
            try:
                r["response"] = json.loads(r.pop("response_json") or "null")
            except json.JSONDecodeError:
                r["response"] = r.pop("response_json", None)
        return rows

    def trades(self, q: dict) -> list[dict]:
        sql, args = "SELECT * FROM trades WHERE 1=1", []
        if q.get("symbol"):
            sql += " AND symbol=?"
            args.append(q["symbol"])
        sql += " ORDER BY exit_time DESC LIMIT ?"
        args.append(min(int(q.get("limit") or 500), 5000))
        return self.store.query(sql, tuple(args))

    def analytics_view(self) -> dict:
        trades = self.store.query("SELECT * FROM trades ORDER BY exit_time")
        eq = self.store.query("SELECT ts, equity FROM equity ORDER BY ts")
        return clean({"summary": analytics.summary(trades), "groups": analytics.grouped(trades),
                      "win_rate_trend": analytics.win_rate_trend(trades), "curve": analytics.equity_curve(eq),
                      "backtest": BACKTEST})

    def signals(self) -> dict:
        rows = self.store.query("SELECT * FROM signals WHERE bar_date = (SELECT MAX(bar_date) FROM signals) ORDER BY symbol")
        return {"bar_date": rows[0]["bar_date"] if rows else None, "items": rows}

    def events(self, q: dict) -> list[dict]:
        sql, args = "SELECT * FROM events WHERE 1=1", []
        if q.get("kind"):
            sql += " AND kind=?"
            args.append(q["kind"])
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(min(int(q.get("limit") or 200), 2000))
        rows = self.store.query(sql, tuple(args))
        for r in rows:
            r["data"] = json.loads(r.pop("data_json")) if r.get("data_json") else None
        return rows

    def risk(self) -> dict:
        s = self.state()
        viol = self.events({"limit": 500})
        viol = [e for e in viol if e["kind"] in ("RISK_HALT", "ORDER_REJECTED", "EXCHANGE_STOP_FAILED", "RECONCILED")][:50]
        return clean({**s["risk"], "limits": {k: {"min": v[0], "max": v[1], "description": v[2]} for k, v in LIMITS.items()},
                      "violations": viol, "mode": s["mode"], "risk_config": s["risk_config"]})

    def strategy(self) -> dict:
        st = self.status()
        cfg = st.get("risk_config") or RiskConfig.load(self.data / "daily_trend_risk.json").to_dict()
        trades = self.store.query("SELECT * FROM trades ORDER BY exit_time")
        p = PRE_REGISTERED
        return clean({
            "name": "Daily Trend (Donchian breakout)", "id": "DAILY_TREND", "type": "Trend following",
            "status": "PAUSED" if cfg.get("entries_paused") else ("HALTED" if st.get("kill_switch") else "ACTIVE"),
            "mode": st.get("mode", "PAPER"), "timeframe": "1 day (decides after each daily close, 05:30 IST)",
            "market_conditions": "Profits in sustained trends; loses small amounts in sideways markets.",
            "entry": f"Completed daily close above the highest high of the previous {p.entry_n} days (long only).",
            "exit": f"Completed daily close below the lowest low of the previous {p.exit_n} days, or the stop.",
            "stop": f"Initial stop {p.atr_k:g} x ATR(20) below the fill; trails up from the best close; never moves down.",
            "indicators": {"donchian_entry_days": p.entry_n, "donchian_exit_days": p.exit_n, "atr_period": 20,
                           "atr_stop_multiple": p.atr_k, "side": p.side},
            "rule_editable": False,
            "rule_note": "The rule is fixed: it is what was backtested. Changing it would trade something untested.",
            "symbols": [{"symbol": s, "enabled": s not in (cfg.get("disabled_symbols") or [])} for s in self.symbols],
            "risk_config": cfg,
            "limits": {k: {"min": v[0], "max": v[1], "description": v[2]} for k, v in LIMITS.items()},
            "performance": analytics.summary(trades), "backtest": BACKTEST,
        })

    def system(self) -> dict:
        st, hb = self.status(), self.heartbeat()
        tick = self.market.tickers(self.symbols)
        hb_age, cyc_age = _age(hb.get("ts")), _age(st.get("cycle_at"))
        pending = self.store.query("SELECT COUNT(*) n, MIN(created_at) oldest FROM commands WHERE status IN ('PENDING','EXECUTING')")[0]
        counts = {t: self.store.query(f"SELECT COUNT(*) n FROM {t}")[0]["n"] for t in ("orders", "trades", "signals", "events", "equity")}
        stop_fail = self.store.query("SELECT ts, message FROM events WHERE kind='EXCHANGE_STOP_FAILED' ORDER BY id DESC LIMIT 1")
        today = datetime.now(UTC).date()
        expected_bar = (pd.Timestamp(today) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        poll_s = self.poll_minutes * 60

        def comp(name, role, ok, detail, last=None, warn=False):
            return {"name": name, "role": role, "status": "OK" if ok else ("WARN" if warn else "DOWN"),
                    "detail": detail, "last_activity": last}

        comps = [
            comp("Engine process", "Runs the strategy and is the only component that places orders",
                 hb_age is not None and hb_age < ENGINE_ALIVE_SECONDS,
                 f"heartbeat {hb_age:.0f}s ago (pid {hb.get('pid')})" if hb_age is not None else "no heartbeat — engine not running",
                 hb.get("ts")),
            comp("Trading cycle", f"Risk checks, reconciliation, stops; every {self.poll_minutes} min",
                 cyc_age is not None and cyc_age < 2.5 * poll_s,
                 f"last cycle {cyc_age / 60:.1f} min ago" if cyc_age is not None else "no cycle yet", st.get("cycle_at")),
            comp("Daily signal scan", "Checks every coin after each daily close",
                 (st.get("last_daily_bar") or "") >= expected_bar,
                 f"last processed candle {st.get('last_daily_bar') or '—'} (expected {expected_bar} after 05:30 IST)",
                 st.get("last_daily_bar"), warn=True),
            comp("Market data feed", "Live Delta tickers for prices, P&L and stops",
                 not tick.get("error") and bool(tick.get("items")),
                 tick.get("error") or f"{len(tick.get('items', {}))} coins, updated {time.time() - tick['ts']:.0f}s ago",
                 datetime.fromtimestamp(tick["ts"], UTC).isoformat() if tick.get("ts") else None),
            comp("Exchange-side stops", "Resting stop orders on Delta (live only)",
                 st.get("mode") != "LIVE" or not stop_fail,
                 "paper mode: stops are enforced by the engine every cycle" if st.get("mode") != "LIVE"
                 else (f"last failure: {stop_fail[0]['message']}" if stop_fail else "no failures recorded"),
                 stop_fail[0]["ts"] if stop_fail else None, warn=True),
            comp("Risk gates", "Kill switch, daily loss, drawdown, realized-edge gate",
                 not st.get("kill_switch") and not (st.get("risk_config") or {}).get("entries_paused"),
                 st.get("kill_switch") or ("entries paused from the terminal" if (st.get("risk_config") or {}).get("entries_paused")
                                           else (st.get("realized_edge") or "all clear")), warn=True),
            comp("Command queue", "Terminal actions waiting for the engine",
                 pending["n"] == 0 or (_age(pending["oldest"]) or 0) < 30,
                 f"{pending['n']} pending" + (f", oldest {_age(pending['oldest']):.0f}s" if pending["n"] else ""), warn=True),
            comp("Trade store", "Orders, trades, signals, events, equity (SQLite)", True,
                 ", ".join(f"{k}: {v}" for k, v in counts.items()), str(self.data / "daily_trend.db")),
        ]
        return clean({"components": comps, "events": self.events({"limit": 100}),
                      "note": "This strategy has no AI agents. The old hourly bot's agents are not running "
                              "(that strategy lost money in every backtest), so none are shown."})

    # ------------------------------------------------------------- commands

    def submit(self, kind: str, payload: dict) -> tuple[int, dict]:
        if kind not in COMMAND_KINDS:
            return 400, {"error": f"unknown command {kind}"}
        if not isinstance(payload, dict):
            return 400, {"error": "payload must be an object"}
        if not self.engine_alive():
            return 503, {"error": "The engine is not running, so nothing would execute. Start it with ./start_auto.sh."}
        st = self.status()
        if kind in POSITION_COMMANDS:
            pos = next((p for p in st.get("positions") or [] if p["symbol"] == payload.get("symbol")), None)
            if pos is None:
                return 400, {"error": f"no open position in {payload.get('symbol')}"}
            if kind == "CLOSE_POSITION" and payload.get("quantity") not in (None, ""):
                try:
                    q = int(payload["quantity"])
                except (TypeError, ValueError):
                    return 400, {"error": "quantity must be a whole number"}
                if not (1 <= q <= pos["qty"]):
                    return 400, {"error": f"quantity must be between 1 and {pos['qty']}"}
            if kind == "MOVE_STOP":
                try:
                    if float(payload.get("stop")) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    return 400, {"error": "stop must be a positive price"}
            if kind == "SET_TAKE_PROFIT" and payload.get("take_profit") not in (None, "", 0):
                try:
                    if float(payload["take_profit"]) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    return 400, {"error": "take_profit must be a positive price"}
        if kind == "UPDATE_RISK_CONFIG":
            _, errors = validate_changes(payload.get("changes") or {}, self.symbols)
            if errors or not payload.get("changes"):
                return 400, {"error": "; ".join(errors) or "no changes given"}
        if kind == "PAUSE_ENTRIES" and not isinstance(payload.get("paused"), bool):
            return 400, {"error": "paused must be true or false"}
        cid = self.store.submit_command(kind, payload)
        return 202, {"id": cid, "status": "PENDING", "message": "queued for the engine (usually executes within 2–5 seconds)"}

    def ask(self, message: str, history: list[dict]) -> dict:
        s = self.state()
        ctx = {
            "now_utc": s["server_time"], "mode": s["mode"], "account": s["account"], "positions": s["positions"],
            "risk": s["risk"], "risk_config": s["risk_config"], "kill_switch": s["kill_switch"],
            "last_cycle": s["last_cycle"], "health": s["health"],
            "performance": s["performance"], "strategy": self.strategy(),
            "recent_trades": self.trades({"limit": 30}),
            "recent_orders": [{k: v for k, v in o.items() if k != "response"} for o in self.orders({"limit": 30})],
            "latest_signals": self.signals(),
            "recent_events": self.events({"limit": 40}),
        }
        kw = {"post": self.chat_post} if self.chat_post else {}
        return chat.ask(message, clean(ctx), history, key=self.chat_key, **kw)


# ------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    terminal: Terminal
    port: int
    protocol_version = "HTTP/1.1"
    _sse = threading.BoundedSemaphore(20)

    def log_message(self, *a):
        pass

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(clean(obj), default=str).encode())

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._json(403, {"error": "forbidden host"})
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        t = self.terminal
        try:
            if u.path in ("/", "/index.html"):
                html = (STATIC / "index.html").read_text().replace("__TERMINAL_TOKEN__", t.token)
                return self._send(200, html.encode(), "text/html; charset=utf-8",
                                  {"Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                              "img-src 'self' data:; connect-src 'self'"})
            if u.path == "/static/lightweight-charts.js":
                return self._send(200, CHART_JS.read_bytes(), "application/javascript")
            if u.path.startswith("/static/"):
                f = (STATIC / u.path[len("/static/"):]).resolve()
                if STATIC.resolve() not in f.parents or not f.is_file():
                    return self._json(404, {"error": "not found"})
                return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            if u.path == "/api/stream":
                return self._stream()
            routes = {
                "/api/state": t.state, "/api/markets": t.markets, "/api/analytics": t.analytics_view,
                "/api/signals": t.signals, "/api/risk": t.risk, "/api/strategy": t.strategy, "/api/system": t.system,
                "/api/orders": lambda: t.orders(q), "/api/trades": lambda: t.trades(q), "/api/events": lambda: t.events(q),
                "/api/candles": lambda: t.candles(q.get("symbol", ""), q.get("tf", "1d"), int(q.get("bars") or 300)),
            }
            if u.path in routes:
                return self._json(200, routes[u.path]())
            if u.path.startswith("/api/commands/"):
                c = t.store.command(u.path.rsplit("/", 1)[-1])
                return self._json(200 if c else 404, c or {"error": "unknown command"})
            return self._json(404, {"error": "not found"})
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):  # noqa: N802
        if not self._host_ok():
            return self._json(403, {"error": "forbidden host"})
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        if origin not in allowed or not secrets.compare_digest(self.headers.get("X-Terminal-Token", ""), self.terminal.token):
            return self._json(403, {"error": "forbidden: missing or wrong terminal token / origin"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 100_000:
                return self._json(413, {"error": "request too large"})
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "invalid JSON"})
        u = urlparse(self.path)
        try:
            if u.path == "/api/commands":
                code, res = self.terminal.submit(str(body.get("kind", "")), body.get("payload") or {})
                return self._json(code, res)
            if u.path == "/api/chat":
                msg = str(body.get("message", "")).strip()
                if not msg:
                    return self._json(400, {"error": "empty message"})
                return self._json(200, self.terminal.ask(msg, body.get("history") or []))
            return self._json(404, {"error": "not found"})
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def _stream(self):
        if not self._sse.acquire(blocking=False):
            return self._json(429, {"error": "too many live connections"})
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(b"retry: 3000\n\n")
            last_hash, last_ping, seq = None, 0.0, 0
            while True:
                try:
                    data = json.dumps(self.terminal.state(), default=str)
                except Exception as e:
                    data = json.dumps({"error": f"{type(e).__name__}: {e}"})
                h = hashlib.sha1(data.encode()).hexdigest()
                now = time.monotonic()
                if h != last_hash:
                    seq += 1
                    self.wfile.write(f"id: {seq}\nevent: state\ndata: {data}\n\n".encode())
                    last_hash = h
                    last_ping = now
                elif now - last_ping > 15:
                    self.wfile.write(f": ping {int(time.time())}\n\n".encode())
                    last_ping = now
                self.wfile.flush()
                time.sleep(2)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self._sse.release()
            self.close_connection = True


def make_server(terminal: Terminal, port: int = 8787) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"terminal": terminal, "port": port})
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    handler.port = srv.server_address[1]  # actual port (matters when port=0)
    return srv

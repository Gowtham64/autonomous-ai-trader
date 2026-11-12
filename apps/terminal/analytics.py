"""Performance and risk analytics computed from persisted records (no estimates).

Inputs are rows from the trading store (`trades`, `equity`) and the engine's status
snapshot (open positions with live marks). Every figure on the terminal comes from here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import pandas as pd


def _ts(s: str) -> pd.Timestamp:
    t = pd.Timestamp(s)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def summary(trades: list[dict], now: datetime | None = None) -> dict:
    now = pd.Timestamp(now or datetime.now(UTC))
    n = len(trades)
    if not n:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate_pct": None, "net_pnl": 0.0, "gross_pnl": 0.0,
                "fees": 0.0, "avg_win": None, "avg_loss": None, "profit_factor": None, "expectancy": None,
                "avg_r": None, "avg_hold_hours": None, "best": None, "worst": None, "today_realized": 0.0,
                "max_consecutive_losses": 0}
    nets = [t["net_pnl"] for t in trades]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    rs = [t["r_multiple"] for t in trades if t.get("r_multiple") is not None]
    holds = [(_ts(t["exit_time"]) - _ts(t["entry_time"])).total_seconds() / 3600 for t in trades]
    today = now.tz_convert("UTC").normalize() if now.tzinfo else now.normalize()
    streak = best_streak = 0
    for t in sorted(trades, key=lambda t: t["exit_time"]):
        streak = streak + 1 if t["net_pnl"] <= 0 else 0
        best_streak = max(best_streak, streak)
    gl = -sum(losses)
    return {
        "trades": n, "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / n, 1),
        "net_pnl": round(sum(nets), 6),
        "gross_pnl": round(sum(t["gross_pnl"] for t in trades), 6),
        "fees": round(sum(t["fees"] for t in trades), 6),
        "avg_win": round(sum(wins) / len(wins), 6) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 6) if losses else None,
        "profit_factor": round(sum(wins) / gl, 3) if gl > 0 else None,
        "expectancy": round(sum(nets) / n, 6),
        "avg_r": round(sum(rs) / len(rs), 3) if rs else None,
        "avg_hold_hours": round(sum(holds) / n, 1),
        "best": round(max(nets), 6), "worst": round(min(nets), 6),
        "today_realized": round(sum(t["net_pnl"] for t in trades if _ts(t["exit_time"]) >= today), 6),
        "max_consecutive_losses": best_streak,
    }


def grouped(trades: list[dict]) -> dict:
    """Performance by day / ISO week / month / coin / direction, oldest first."""
    def agg(key_fn):
        g: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            g[key_fn(t)].append(t)
        rows = []
        for k in sorted(g):
            ts = g[k]
            w = sum(1 for t in ts if t["net_pnl"] > 0)
            rows.append({"key": k, "trades": len(ts), "wins": w, "win_rate_pct": round(100 * w / len(ts), 1),
                         "net_pnl": round(sum(t["net_pnl"] for t in ts), 6),
                         "avg_r": round(sum(t["r_multiple"] or 0 for t in ts) / len(ts), 3)})
        return rows
    return {
        "daily": agg(lambda t: _ts(t["exit_time"]).strftime("%Y-%m-%d")),
        "weekly": agg(lambda t: "%d-W%02d" % _ts(t["exit_time"]).isocalendar()[:2]),
        "monthly": agg(lambda t: _ts(t["exit_time"]).strftime("%Y-%m")),
        "by_symbol": agg(lambda t: t["symbol"]),
        "by_side": agg(lambda t: "Long" if t["side"] == "BUY" else "Short"),
        "by_exit_reason": agg(lambda t: t["exit_reason"].split(" ")[0]),
    }


def win_rate_trend(trades: list[dict], window: int = 10) -> list[dict]:
    out, ordered = [], sorted(trades, key=lambda t: t["exit_time"])
    for i in range(len(ordered)):
        w = ordered[max(0, i - window + 1): i + 1]
        out.append({"time": ordered[i]["exit_time"], "win_rate_pct": round(100 * sum(t["net_pnl"] > 0 for t in w) / len(w), 1),
                    "trades_in_window": len(w)})
    return out


def equity_curve(points: list[dict]) -> dict:
    """Equity series plus drawdown series (from running peak)."""
    pts = sorted(points, key=lambda p: p["ts"])
    peak, eq, dd, max_dd = 0.0, [], [], 0.0
    for p in pts:
        e = float(p["equity"])
        peak = max(peak, e)
        d = (peak - e) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, d)
        eq.append({"time": p["ts"], "value": round(e, 6)})
        dd.append({"time": p["ts"], "value": round(-d, 4)})
    return {"equity": eq, "drawdown": dd, "max_drawdown_pct": round(max_dd, 3)}


def risk_view(status: dict, marks: dict[str, float | None]) -> dict:
    """Live risk from the engine's positions, revalued at the latest exchange marks."""
    equity = float(status.get("equity") or 0.0)
    cfg = status.get("risk_config") or {}
    positions = []
    tot_notional = tot_risk = tot_unreal = 0.0
    for p in status.get("positions") or []:
        mark = marks.get(p["symbol"]) or p.get("mark") or p["entry"]
        short = p["side"] == "SELL"
        unit = p["qty"] * p["multiplier"]
        notional = mark * unit
        risk_now = max(0.0, ((p["stop"] - mark) if short else (mark - p["stop"])) * unit)  # $ lost if stop fills now
        unreal = ((p["entry"] - mark) if short else (mark - p["entry"])) * unit
        tot_notional += notional
        tot_risk += risk_now
        tot_unreal += unreal
        positions.append({"symbol": p["symbol"], "notional_usd": round(notional, 4), "risk_to_stop_usd": round(risk_now, 4),
                          "share_of_equity_pct": round(notional / equity * 100, 2) if equity else None})
    risk_pct = float(cfg.get("risk_pct") or status.get("risk_pct") or 0.01)
    max_pos = int(cfg.get("max_positions") or 15)
    open_n = len(positions)
    day_start = float(status.get("day_start_equity") or 0.0)
    day_loss_pct = max(0.0, (day_start - equity) / day_start * 100) if day_start else 0.0
    return {
        "equity": equity,
        "exposure_usd": round(tot_notional, 4),
        "exposure_pct": round(tot_notional / equity * 100, 2) if equity else None,
        "effective_leverage": round(tot_notional / equity, 3) if equity else None,
        "capital_at_risk_usd": round(tot_risk, 4),
        "capital_at_risk_pct": round(tot_risk / equity * 100, 3) if equity else None,
        "unrealized_usd": round(tot_unreal, 4),
        "largest_position_pct": max((p["share_of_equity_pct"] or 0 for p in positions), default=0.0),
        "open_positions": open_n, "max_positions": max_pos,
        "risk_per_trade_pct": round(risk_pct * 100, 3),
        "remaining_new_trade_risk_usd": round(max(0, max_pos - open_n) * risk_pct * equity, 4),
        "drawdown_pct": float(status.get("drawdown_pct") or 0.0),
        "drawdown_limit_pct": round(float(cfg.get("max_drawdown_pct") or 0.25) * 100, 1),
        "daily_loss_pct": round(day_loss_pct, 3),
        "daily_loss_limit_pct": round(float(cfg.get("max_daily_loss_pct") or 0.06) * 100, 1),
        "kill_switch": status.get("kill_switch"),
        "entries_paused": bool(cfg.get("entries_paused")),
        "positions": positions,
    }

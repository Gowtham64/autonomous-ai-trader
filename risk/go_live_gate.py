"""Scores a 3-day paper run. It never turns live trading on."""

from datetime import UTC, datetime

WINDOW_HOURS = 72.0
MIN_CLOSED_TRADES = 20
MIN_WIN_RATE = 55.0
MIN_PROFIT_FACTOR = 1.6
MAX_DRAWDOWN_PCT = 4.5


def _parse_time(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text or text == "—":
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S UTC")
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def score_go_live(
    *,
    now: datetime,
    started_at: datetime | None,
    trades: list[dict],
    drawdown_pct: float,
    interruptions: int = 0,
    live_trading_enabled: bool = False,
) -> dict:
    """Return the paper-window status. A passing score is a review, not an order switch."""
    start = _parse_time(started_at) if not isinstance(started_at, datetime) else started_at
    if start is None:
        elapsed = 0.0
        window_done = False
        in_window = []
    else:
        elapsed = max(0.0, (now - start).total_seconds())
        window_done = elapsed >= WINDOW_HOURS * 3600.0
        in_window = []
        for trade in trades:
            stamp = _parse_time(trade.get("timestamp"))
            if stamp is not None and stamp >= start:
                in_window.append(trade)

    closed = len(in_window)
    wins = sum(1 for trade in in_window if float(trade.get("net_pnl") or 0.0) > 0)
    gross_win = sum(float(trade.get("net_pnl") or 0.0) for trade in in_window if float(trade.get("net_pnl") or 0.0) > 0)
    gross_loss = abs(sum(float(trade.get("net_pnl") or 0.0) for trade in in_window if float(trade.get("net_pnl") or 0.0) < 0))
    win_rate = (wins / closed * 100.0) if closed else 0.0
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        profit_factor = gross_win
    else:
        profit_factor = 0.0

    checks = {
        "hours": window_done,
        "trades": closed >= MIN_CLOSED_TRADES,
        "win_rate": win_rate >= MIN_WIN_RATE,
        "profit_factor": profit_factor >= MIN_PROFIT_FACTOR,
        "drawdown": drawdown_pct < MAX_DRAWDOWN_PCT,
        "continuity": interruptions == 0,
        "still_paper": not live_trading_enabled,
    }
    if not window_done:
        decision = "COLLECTING"
        detail = "Paper only. The live switch stays off until this 3-day record is complete and a person reviews it."
    elif all(checks.values()):
        decision = "READY_FOR_MANUAL_REVIEW"
        detail = "The paper record passed. Live trading is still off until you set it yourself."
    else:
        decision = "NO_GO"
        detail = "The 3-day paper record did not pass. Live trading stays off."

    return {
        "decision": decision,
        "detail": detail,
        "elapsed_seconds": elapsed,
        "window_complete": window_done,
        "closed_trades": closed,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "checks": checks,
        "live_trading_enabled": False,
    }

"""Each cycle chooses how many trades may be open. Capital, results, and the market each move the number."""

from dataclasses import dataclass, field

from core.config.settings import settings


@dataclass
class OpenTradeDecision:
    cap: int
    capital_slots: int
    performance_delta: int
    market_delta: int
    reasons: list[str] = field(default_factory=list)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def capital_slots(equity: float) -> int:
    if equity < 12:
        return 2
    if equity < 30:
        return 3
    if equity < 60:
        return 4
    if equity < 120:
        return 5
    return 6


def decide_open_trade_cap(
    equity: float,
    closed_trades: int = 0,
    win_rate: float = 0.0,
    profit_factor: float = 0.0,
    drawdown_pct: float = 0.0,
    daily_loss: float = 0.0,
    quotes: list[dict] | None = None,
    survival_mode: bool = False,
) -> OpenTradeDecision:
    """Return the open-trade cap for one cycle. The ceiling stays a hard risk limit."""
    reasons: list[str] = []
    base = capital_slots(max(0.0, equity))
    reasons.append(f"Capital ${equity:.2f} starts at {base} open trades.")

    performance_delta = 0
    if closed_trades >= 8:
        if win_rate < 0.45 or (profit_factor < 1.0 and profit_factor > 0):
            performance_delta -= 1
            reasons.append(
                f"Recent results are weak ({closed_trades} trades, win rate {win_rate * 100:.0f}%, profit factor {profit_factor:.2f})."
            )
        elif win_rate >= 0.55 and profit_factor >= 1.6 and drawdown_pct < 0.045:
            performance_delta += 1
            reasons.append(
                f"Recent results earn one more slot ({closed_trades} trades, win rate {win_rate * 100:.0f}%, profit factor {profit_factor:.2f})."
            )
        else:
            reasons.append("Recent results do not change the slot count.")
    else:
        reasons.append(f"Only {closed_trades} closed trades, so performance does not change the slot count.")

    is_small_usd = equity < 100
    daily_limit = max(1.0 if is_small_usd else 0.0, equity * settings.MAX_DAILY_LOSS_PCT)
    if daily_loss >= daily_limit * 0.5 and daily_limit > 0:
        performance_delta -= 1
        reasons.append(f"Daily loss ${daily_loss:.2f} is at least half of the ${daily_limit:.2f} stop.")

    dd_limit = 0.15 if equity < 30 else settings.MAX_PORTFOLIO_DRAWDOWN_PCT
    if drawdown_pct >= dd_limit * 0.5 and dd_limit > 0:
        performance_delta -= 1
        reasons.append(f"Drawdown {drawdown_pct * 100:.1f}% is at least half of the {dd_limit * 100:.0f}% stop.")

    market_delta = 0
    usable = []
    seen = set()
    for quote in quotes or []:
        symbol = str(quote.get("symbol") or "")
        key = symbol.upper().replace("USDT", "USD").replace("-", "")
        if not key or key in seen:
            continue
        seen.add(key)
        usable.append(quote)

    spreads = [float(q["spread_pct"]) for q in usable if q.get("spread_pct") is not None]
    moves = [abs(float(q.get("change") or 0.0)) for q in usable]
    if len(spreads) < 3:
        market_delta -= 1
        reasons.append("Fewer than 3 live Delta quotes, so the market slot is withheld.")
    else:
        spread = _median(spreads)
        move = _median(moves) if moves else 0.0
        if spread > 0.20 or move > 6:
            market_delta -= 1
            reasons.append(f"Market is wide or fast (spread {spread:.3f}%, move {move:.2f}%).")
        elif spread <= 0.08 and move <= 4:
            market_delta += 1
            reasons.append(f"Market is liquid and orderly (spread {spread:.3f}%, move {move:.2f}%).")
        else:
            reasons.append(f"Market is ordinary (spread {spread:.3f}%, move {move:.2f}%).")

    if survival_mode:
        performance_delta -= 1
        reasons.append("Survival mode removes one slot.")

    raw = base + performance_delta + market_delta
    ceiling = max(1, int(getattr(settings, "OPEN_POSITION_CEILING", 8)))
    cap = max(1, min(ceiling, raw))
    reasons.append(f"This cycle may hold {cap} open trades.")
    return OpenTradeDecision(
        cap=cap,
        capital_slots=base,
        performance_delta=performance_delta,
        market_delta=market_delta,
        reasons=reasons,
    )

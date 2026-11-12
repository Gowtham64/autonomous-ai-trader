"""Daily trend-following rules — the single source of truth for live trading AND backtests.

tools/backtest_trend_daily.py imports these exact functions, so the live bot trades
precisely the rules that were tested (Binance 2018-2026: +0.54R/trade over 376 trades,
95% CI [+0.26, +0.82], survived 2022 at -8% vs BTC -64%; weaker since 2024).

Rule (PRE_REGISTERED, chosen before any testing):
  * Enter long when a COMPLETED daily close breaks the highest high of the previous
    55 days.
  * Initial stop = entry - 3 x ATR(20). Trailing stop = best close since entry - 3 x ATR,
    only ever moving up.
  * Exit when a completed daily close breaks the lowest low of the previous 20 days,
    or when the stop is hit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

DEFAULT_FUNDING_PCT_PER_DAY = 0.0003


@dataclass(frozen=True)
class TrendParams:
    family: str = "donchian"   # donchian | ema
    entry_n: int = 55          # donchian entry lookback, or EMA fast
    exit_n: int = 20           # donchian exit lookback, or EMA slow
    atr_k: float = 3.0         # initial + trailing stop distance in ATR(20)
    side: str = "long"         # long | both
    funding_pct_per_day: float = DEFAULT_FUNDING_PCT_PER_DAY

    def label(self) -> str:
        rule = f"Donchian {self.entry_n}/{self.exit_n}" if self.family == "donchian" else f"EMA {self.entry_n}/{self.exit_n}"
        return f"{rule} stop={self.atr_k:g}xATR side={self.side}"


PRE_REGISTERED = TrendParams("donchian", 55, 20, 3.0, "long")


# ------------------------------------------------------------------ indicators
# Same definitions as the `ta` library (Wilder ATR, span EMA).

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def compute_trend_signals(d: pd.DataFrame, p: TrendParams) -> pd.DataFrame:
    """Signals at each daily close using only that close and earlier bars."""
    out = pd.DataFrame(index=d.index)
    c = d["close"]
    out["atr"] = atr(d["high"], d["low"], c, 20)
    if p.family == "donchian":
        prev_hi = d["high"].rolling(p.entry_n).max().shift(1)
        prev_lo = d["low"].rolling(p.entry_n).min().shift(1)
        exit_lo = d["low"].rolling(p.exit_n).min().shift(1)
        exit_hi = d["high"].rolling(p.exit_n).max().shift(1)
        out["long_entry"] = c > prev_hi
        out["short_entry"] = c < prev_lo
        out["long_exit"] = c < exit_lo
        out["short_exit"] = c > exit_hi
        warm = max(p.entry_n, p.exit_n, 20) + 1
    else:
        fast, slow = ema(c, p.entry_n), ema(c, p.exit_n)
        above = fast > slow
        out["long_entry"] = above & ~above.shift(1, fill_value=False)
        out["short_entry"] = ~above & above.shift(1, fill_value=False)
        out["long_exit"] = ~above
        out["short_exit"] = above
        warm = p.exit_n * 2
    out.iloc[:warm, out.columns.get_indexer(["long_entry", "short_entry"])] = False
    return out


# ------------------------------------------------------------- live helpers

def completed_bars(d: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Keep only candles whose full 24 hours have elapsed (works for any candle alignment).
    Decisions use closed days only — a still-forming candle would be look-ahead."""
    if d is None or d.empty:
        return d
    now = now or pd.Timestamp.now(tz="UTC")
    return d[d.index + pd.Timedelta(days=1) <= now]


def min_history_days(p: TrendParams) -> int:
    return (max(p.entry_n, p.exit_n, 20) + 21) if p.family == "donchian" else p.exit_n * 3


@dataclass(frozen=True)
class DailyView:
    bar_date: pd.Timestamp     # the completed day the decision is based on
    close: float
    atr: float
    long_entry: bool
    short_entry: bool
    long_exit: bool
    short_exit: bool


def latest_view(d: pd.DataFrame, p: TrendParams) -> DailyView | None:
    """Signals for the last COMPLETED daily bar (caller passes completed bars only)."""
    if d is None or len(d) < min_history_days(p):
        return None
    sig = compute_trend_signals(d, p).iloc[-1]
    a = float(sig["atr"])
    if not math.isfinite(a) or a <= 0:
        return None
    return DailyView(
        bar_date=d.index[-1],
        close=float(d["close"].iloc[-1]),
        atr=a,
        long_entry=bool(sig["long_entry"]),
        short_entry=bool(sig["short_entry"]) and p.side == "both",
        long_exit=bool(sig["long_exit"]),
        short_exit=bool(sig["short_exit"]),
    )


def initial_stop(entry: float, atr_value: float, p: TrendParams, is_short: bool) -> float:
    dist = p.atr_k * atr_value
    return entry + dist if is_short else entry - dist


def trail_stop(current_stop: float, best_close: float, atr_value: float, p: TrendParams, is_short: bool) -> float:
    """Chandelier trail from the best close; the stop only ever moves in the trade's favor."""
    if atr_value <= 0:
        return current_stop
    if is_short:
        return min(current_stop, best_close + p.atr_k * atr_value)
    return max(current_stop, best_close - p.atr_k * atr_value)


@dataclass(frozen=True)
class SizeDecision:
    contracts: int
    risk_usd: float
    notional_usd: float
    reason: str


def size_position(
    equity: float,
    available_margin: float,
    entry: float,
    stop: float,
    multiplier: float,
    risk_pct: float,
    leverage: float,
    max_position_notional_pct: float = 0.5,
) -> SizeDecision:
    """Contracts so that hitting the stop loses at most `risk_pct` of equity.

    Never rounds UP: if even one contract would risk more than the budget, the trade is
    skipped (on a $10 account most majors can't be traded correctly — that is the honest
    answer, not a reason to take an oversized position).
    """
    if equity <= 0 or entry <= 0 or multiplier <= 0 or stop <= 0:
        return SizeDecision(0, 0.0, 0.0, "invalid inputs")
    per_contract_risk = abs(entry - stop) * multiplier
    per_contract_notional = entry * multiplier
    if per_contract_risk <= 0:
        return SizeDecision(0, 0.0, 0.0, "zero stop distance")
    budget = equity * risk_pct
    by_risk = math.floor(budget / per_contract_risk)
    if by_risk < 1:
        return SizeDecision(
            0, 0.0, 0.0,
            f"1 contract risks ${per_contract_risk:.2f} > budget ${budget:.2f} ({risk_pct * 100:.1f}% of ${equity:.2f}); "
            f"account too small for this symbol",
        )
    by_notional = math.floor((equity * max_position_notional_pct) / per_contract_notional)
    by_margin = math.floor((available_margin * 0.95 * leverage) / per_contract_notional) if leverage > 0 else 0
    qty = min(by_risk, by_notional, by_margin)
    if qty < 1:
        limit = "position-size cap" if by_notional < 1 else "available margin"
        return SizeDecision(0, 0.0, 0.0, f"1 contract (${per_contract_notional:.2f} notional) exceeds {limit}")
    return SizeDecision(qty, round(qty * per_contract_risk, 4), round(qty * per_contract_notional, 4), "ok")

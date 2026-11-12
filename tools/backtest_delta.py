"""Historical backtest of the bot's rule-based core on Delta Exchange candles.

Answers the one question everything else depends on: do the scanner's signals,
with the planned stop/target and the guardian's ratchet, make money AFTER fees?

What it replays (no look-ahead — every decision uses only bars already closed):
  * Signal: the same bull/bear scoring as scanner/quant_scanner.py (daily EMA20/50,
    RSI14, relative volume, daily trend; hourly EMA9/21 + RSI confirmation), evaluated
    at each hourly close. Long or short, like the live crypto engine.
  * Entry: next hourly bar's open, plus slippage.
  * Stop: min(0.8 x daily ATR14, 1.5% of entry)   (agents/trader/fund_manager.py)
  * Target: 2.2 x stop distance
  * Ratchet (guardian/position_guardian.py): once the peak has netted 1R, stop to
    breakeven-after-fees; once it has netted 1.8R, stop to +1R.
  * If a bar touches both stop and target, the STOP is assumed (conservative).
  * Costs: Delta taker fee + 18% GST on both sides, plus entry/exit slippage
    (risk/profit_math.py).

What it can't replay: the LLM debate / fund-manager judgement. Those only filter
signals; if the unfiltered core has no edge, a filter on top is unlikely to create one,
and if it does, that is what the live realized-edge gate will show.

Usage (needs internet access to api.india.delta.exchange):
    python tools/backtest_delta.py --symbols XRPUSD DOGEUSD SOLUSD --days 120
    python tools/backtest_delta.py --top 15 --days 180 --min-score 100 --csv trades.csv
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from risk.profit_math import ENTRY_SLIPPAGE_PCT, EXIT_SLIPPAGE_PCT, TAKER_FEE_PCT  # noqa: E402

DELTA_BASE_URL = os.getenv("DELTA_BASE_URL", "https://api.india.delta.exchange")

STOP_ATR_MULT = 0.8
STOP_MAX_PCT = 0.015
TARGET_R = 2.2
BREAKEVEN_AT_R = 1.0
LOCK_1R_AT_R = 1.8


# --------------------------------------------------------------------------- data

def _get_json(url: str, params: dict | None = None, timeout: float = 15.0) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "autonomous-ai-trader-backtest"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_hourly_candles(symbol: str, days: int) -> pd.DataFrame:
    """Hourly OHLCV from Delta's /v2/chart/history, paged in 30-day chunks."""
    end = int(time.time())
    start = end - days * 86400
    frames = []
    chunk = 30 * 86400
    t0 = start
    while t0 < end:
        t1 = min(end, t0 + chunk)
        data = _get_json(
            f"{DELTA_BASE_URL}/v2/chart/history",
            {"symbol": symbol, "resolution": "60", "from": t0, "to": t1},
        ).get("result", {})
        if isinstance(data, dict) and data.get("t"):
            frames.append(pd.DataFrame(
                {k: [float(x) for x in data[s]] for k, s in
                 [("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v")]},
                index=pd.to_datetime(data["t"], unit="s", utc=True),
            ))
        t0 = t1
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.dropna(subset=["close"])


def top_perpetuals(n: int) -> list[str]:
    tickers = _get_json(f"{DELTA_BASE_URL}/v2/tickers").get("result", [])
    perps = [
        t for t in tickers
        if t.get("contract_type") == "perpetual_futures" and t.get("product_trading_status") == "operational"
    ]
    perps.sort(key=lambda t: float(t.get("turnover_usd") or 0.0), reverse=True)
    return [t["symbol"] for t in perps[:n]]


# ---------------------------------------------------------------------- indicators
# Same definitions as the `ta` library used by the live scanner.

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0)


def atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


# ------------------------------------------------------------------------- signals

def compute_signals(h1: pd.DataFrame) -> pd.DataFrame:
    """Per hourly bar: (direction, score, daily ATR) using only data closed by that bar.

    Daily indicators come from COMPLETED days (yesterday and before); the hour's close
    stands in for the live price, like the scanner's last (partial) daily close.
    """
    daily = h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    d = pd.DataFrame(index=daily.index)
    d["ema20"] = ema(daily["close"], 20)
    d["ema50"] = ema(daily["close"], 50)
    d["rsi"] = rsi(daily["close"], 14)
    d["atr"] = atr(daily["high"], daily["low"], daily["close"], 14)
    d["avgvol20"] = daily["volume"].rolling(20).mean()
    # shift: the values for day D become usable from day D+1 00:00
    d = d.shift(1)

    day_key = h1.index.floor("1D")
    feats = d.reindex(day_key)
    feats.index = h1.index

    out = pd.DataFrame(index=h1.index)
    ltp = h1["close"]
    # Today's cumulative volume so far vs 20-day average (as the live scanner does)
    cumvol = h1["volume"].groupby(day_key).cumsum()
    rel_vol = cumvol / feats["avgvol20"]

    e9 = ema(ltp, 9)
    e21 = ema(ltp, 21)
    r1h = rsi(ltp, 14)

    up = (ltp > feats["ema50"]) & (feats["ema20"] > feats["ema50"])
    down = (ltp < feats["ema50"]) & (feats["ema20"] < feats["ema50"])
    r = feats["rsi"]

    bull = (
        (ltp > feats["ema20"]) * 25.0 + (feats["ema20"] > feats["ema50"]) * 25.0
        + np.select([(r >= 40) & (r <= 65), (r >= 30) & (r < 40), (r > 65) & (r <= 75)], [30.0, 20.0, 15.0], 0.0)
        + np.select([rel_vol > 1.2, rel_vol > 0.8], [20.0, 10.0], 0.0)
        + np.where(up, 15.0, np.where(down, -25.0, 0.0))
    )
    bear = (
        (ltp < feats["ema20"]) * 25.0 + (feats["ema20"] < feats["ema50"]) * 25.0
        + np.select([(r >= 35) & (r <= 55), r < 35, (r > 55) & (r <= 65)], [30.0, 25.0, 10.0], 0.0)
        + np.select([rel_vol > 1.2, rel_vol > 0.8], [20.0, 10.0], 0.0)
        + np.where(down, 15.0, np.where(up, -25.0, 0.0))
    )
    bull_mtf = (ltp > e21) & (e9 >= e21) & (r1h >= 45) & (r1h <= 75)
    bull_against = (ltp < e21) & (e9 < e21)
    bull = bull + np.where(bull_mtf, np.where(up, 35.0, 15.0), np.where(bull_against, -20.0, 0.0))
    bear_mtf = (ltp < e21) & (e9 <= e21) & (r1h >= 25) & (r1h <= 55)
    bear_against = (ltp > e21) & (e9 > e21)
    bear = bear + np.where(bear_mtf, np.where(down, 35.0, 15.0), np.where(bear_against, -20.0, 0.0))

    is_short = (bear > bull) & (bear >= 30.0)
    out["direction"] = np.where(is_short, "SHORT", "LONG")
    out["score"] = np.where(is_short, bear, bull)
    out["atr_d"] = feats["atr"]
    valid = feats[["ema20", "ema50", "rsi", "atr", "avgvol20"]].notna().all(axis=1) & r1h.notna()
    out.loc[~valid, "score"] = np.nan
    return out


# ----------------------------------------------------------------------- simulator

@dataclass
class Trade:
    symbol: str
    direction: str
    entry_time: str
    exit_time: str
    entry: float
    exit: float
    stop_dist: float
    exit_reason: str
    net_pct: float     # net return on notional, after fees+slippage, in %
    r_multiple: float  # net P&L / planned risk


def _net_return(entry: float, exit_px: float, is_short: bool) -> float:
    """Net return fraction on notional after both fees (entry slippage already in entry)."""
    fill = exit_px * (1 + EXIT_SLIPPAGE_PCT) if is_short else exit_px * (1 - EXIT_SLIPPAGE_PCT)
    gross = (entry - fill) / entry if is_short else (fill - entry) / entry
    return gross - TAKER_FEE_PCT - TAKER_FEE_PCT * (fill / entry)


def _price_for_net(entry: float, is_short: bool, net_frac: float) -> float:
    """Exit price whose market exit leaves `net_frac` of notional after costs."""
    f, s = TAKER_FEE_PCT, EXIT_SLIPPAGE_PCT
    if is_short:
        return entry * (1 - f - net_frac) / ((1 + s) * (1 + f))
    return entry * (1 + f + net_frac) / ((1 - s) * (1 - f))


def simulate(symbol: str, h1: pd.DataFrame, sig: pd.DataFrame, min_score: float) -> list[Trade]:
    trades: list[Trade] = []
    idx = h1.index
    o, hi, lo, c = (h1[k].to_numpy() for k in ("open", "high", "low", "close"))
    score = sig["score"].to_numpy()
    direction = sig["direction"].to_numpy()
    atr_d = sig["atr_d"].to_numpy()

    i = 0
    n = len(h1)
    while i < n - 1:
        if not (score[i] >= min_score) or not (atr_d[i] > 0):
            i += 1
            continue
        is_short = direction[i] == "SHORT"
        j = i + 1  # enter on next bar's open
        raw = o[j]
        entry = raw * (1 - ENTRY_SLIPPAGE_PCT) if is_short else raw * (1 + ENTRY_SLIPPAGE_PCT)
        stop_dist = min(STOP_ATR_MULT * atr_d[i], STOP_MAX_PCT * raw)
        stop = entry + stop_dist if is_short else entry - stop_dist
        initial_stop = stop
        target = entry - TARGET_R * stop_dist if is_short else entry + TARGET_R * stop_dist
        risk_frac = stop_dist / entry  # planned risk as fraction of notional (before costs)
        peak_net = -1.0
        exit_px, reason, k = None, None, j

        for k in range(j, n):
            # Stop is checked first within a bar (conservative when both are touched).
            if (is_short and hi[k] >= stop) or (not is_short and lo[k] <= stop):
                gap = (o[k] > stop) if is_short else (o[k] < stop)
                exit_px = o[k] if gap else stop  # gaps through the stop fill at the open
                reason = "STOP" if stop == initial_stop else "TRAIL_STOP"
                break
            if (is_short and lo[k] <= target) or (not is_short and hi[k] >= target):
                exit_px, reason = target, "TARGET"
                break
            # Update ratchet at bar close, effective from the next bar.
            best = lo[k] if is_short else hi[k]
            peak_net = max(peak_net, _net_return(entry, best, is_short))
            new_stop = stop
            if peak_net >= LOCK_1R_AT_R * risk_frac:
                new_stop = _price_for_net(entry, is_short, risk_frac)
            elif peak_net >= BREAKEVEN_AT_R * risk_frac:
                new_stop = _price_for_net(entry, is_short, 0.0)
            stop = min(stop, new_stop) if is_short else max(stop, new_stop)

        if exit_px is None:
            exit_px, reason, k = c[n - 1], "END_OF_DATA", n - 1

        net = _net_return(entry, exit_px, is_short)
        trades.append(Trade(
            symbol=symbol,
            direction="SHORT" if is_short else "LONG",
            entry_time=str(idx[j]),
            exit_time=str(idx[k]),
            entry=round(entry, 8),
            exit=round(float(exit_px), 8),
            stop_dist=round(stop_dist, 8),
            exit_reason=reason,
            net_pct=round(net * 100, 4),
            r_multiple=round(net / risk_frac, 3) if risk_frac > 0 else 0.0,
        ))
        i = k + 1  # one position per symbol; look for the next signal after exit
    return trades


# ------------------------------------------------------------------------- report

def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {"trades": 0}
    r = np.array([t.r_multiple for t in trades])
    pct = np.array([t.net_pct for t in trades])
    wins = r[r > 0]
    losses = r[r <= 0]
    eq = np.cumsum(r)
    max_dd_r = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq])) - np.concatenate([[0.0], eq])))
    se = float(r.std(ddof=1) / math.sqrt(len(r))) if len(r) > 1 else float("nan")
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    return {
        "trades": len(trades),
        "win_rate_pct": round(100 * len(wins) / len(r), 1),
        "avg_win_R": round(float(wins.mean()), 3) if len(wins) else 0.0,
        "avg_loss_R": round(float(losses.mean()), 3) if len(losses) else 0.0,
        "expectancy_R": round(float(r.mean()), 3),
        "expectancy_R_95ci": [round(float(r.mean() - 1.96 * se), 3), round(float(r.mean() + 1.96 * se), 3)],
        "avg_net_pct_per_trade": round(float(pct.mean()), 4),
        "profit_factor": round(float(wins.sum() / -losses.sum()), 2) if len(losses) and losses.sum() < 0 else None,
        "total_R": round(float(r.sum()), 2),
        "max_drawdown_R": round(max_dd_r, 2),
        "exit_reasons": reasons,
    }


def verdict(s: dict) -> str:
    if s.get("trades", 0) < 30:
        return "INCONCLUSIVE: fewer than 30 trades. Widen --days / --symbols or lower --min-score."
    lo, hi = s["expectancy_R_95ci"]
    if lo > 0:
        return "EDGE: expectancy is positive after costs with 95% confidence. Paper-trade it before going live."
    if hi < 0:
        return "NO EDGE: expectancy is negative after costs with 95% confidence. Do not trade this live."
    return "UNPROVEN: expectancy is not distinguishable from zero after costs. Do not trade this live yet."


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*", help="Delta perpetual symbols, e.g. XRPUSD DOGEUSD")
    ap.add_argument("--top", type=int, default=10, help="If no --symbols: use top-N perpetuals by turnover")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--min-score", type=float, default=100.0, help="Scanner score needed to enter (max ~145)")
    ap.add_argument("--csv", help="Write every trade to this CSV")
    args = ap.parse_args()

    symbols = args.symbols or top_perpetuals(args.top)
    print(f"Costs per side: taker+GST {TAKER_FEE_PCT*100:.4f}%, slippage {ENTRY_SLIPPAGE_PCT*100:.3f}% entry / {EXIT_SLIPPAGE_PCT*100:.3f}% exit")
    all_trades: list[Trade] = []
    for sym in symbols:
        try:
            h1 = fetch_hourly_candles(sym, args.days + 60)  # +60d warm-up for daily EMA50
        except Exception as e:
            print(f"  {sym}: data error ({e})")
            continue
        if len(h1) < 24 * 70:
            print(f"  {sym}: not enough history ({len(h1)} hourly bars)")
            continue
        sig = compute_signals(h1)
        cutoff = h1.index[-1] - pd.Timedelta(days=args.days)
        sig.loc[sig.index < cutoff, "score"] = np.nan
        t = simulate(sym, h1, sig, args.min_score)
        all_trades.extend(t)
        s = summarize(t)
        print(f"  {sym:12s} trades={s.get('trades', 0):4d}  win%={s.get('win_rate_pct', '-')}  expR={s.get('expectancy_R', '-')}  totalR={s.get('total_R', '-')}")

    total = summarize(all_trades)
    print("\n=== ALL SYMBOLS ===")
    print(json.dumps(total, indent=2))
    print("\nVERDICT:", verdict(total))
    if args.csv and all_trades:
        pd.DataFrame([asdict(t) for t in all_trades]).to_csv(args.csv, index=False)
        print(f"Trades written to {args.csv}")


if __name__ == "__main__":
    main()

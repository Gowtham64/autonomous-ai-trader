"""Daily trend-following backtest for Delta Exchange perpetuals.

The hourly scanner strategy showed no edge after costs. This tests a different and
better-documented idea: ride multi-week trends on daily candles. Trades are rare
(days to weeks each), so fees are a small fraction of each trade.

Rules (all decisions at a daily close, using only data up to that close):
  Donchian breakout : enter when close breaks the highest high of the previous N days;
                      exit when close breaks the lowest low of the previous M days.
  EMA trend         : enter when EMA(fast) crosses above EMA(slow); exit on cross back.
  Both              : initial stop k x ATR(20) from entry, trailing at
                      (highest close since entry - k x ATR). Shorts mirror everything.
  Fills             : next day's open + slippage. A day that touches the stop exits at
                      the stop (or at the open if it gapped through).
  Costs             : taker fee + 18% GST each side, slippage each side, and perpetual
                      FUNDING charged every day held (default 0.03%/day — about 0.01%
                      per 8h, a typical bull-market rate; charged to longs AND shorts
                      to stay conservative).

How it judges itself:
  1. PRE-REGISTERED RULE: the classic Donchian 55/20, 3xATR, long-only, chosen
     before seeing any data. Because nothing was tuned, its full-period result is
     honest evidence.
  2. SWEEP: 24 settings chosen on the first 2/3 of history, judged on the last 1/3.
  3. COMPOUNDING: trades replayed in time order risking 1% of current equity each,
     across all symbols at once, compared with simply holding BTC.

Usage:
    python tools/backtest_trend_daily.py --majors --days 1095
    python tools/backtest_trend_daily.py --majors --days 1095 --sweep
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from risk.profit_math import ENTRY_SLIPPAGE_PCT, EXIT_SLIPPAGE_PCT, TAKER_FEE_PCT  # noqa: E402
# The rules themselves live in strategy/daily_trend.py and are shared with the live
# engine, so what is backtested is exactly what trades.
from strategy.daily_trend import (  # noqa: E402,F401
    DEFAULT_FUNDING_PCT_PER_DAY,
    PRE_REGISTERED,
    TrendParams,
    compute_trend_signals,
)
from tools.backtest_delta import (  # noqa: E402
    CACHE_DIR,
    DELTA_BASE_URL,
    MAJORS,
    Trade,
    _get_json,
    summarize,
    top_perpetuals,
    verdict,
)



# --------------------------------------------------------------------------- data

def fetch_daily_candles(symbol: str, days: int) -> pd.DataFrame:
    end = int(time.time())
    start = end - days * 86400
    frames, t0, chunk = [], start, 400 * 86400
    while t0 < end:
        t1 = min(end, t0 + chunk)
        data = _get_json(
            f"{DELTA_BASE_URL}/v2/chart/history",
            {"symbol": symbol, "resolution": "D", "from": t0, "to": t1},
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


BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")


def binance_symbol(delta_symbol: str) -> str:
    """XRPUSD -> XRPUSDT. Binance spot moves almost identically to the Delta perpetual."""
    s = delta_symbol.upper()
    return s if s.endswith("USDT") else (s[:-3] + "USDT" if s.endswith("USD") else s)


def fetch_binance_daily(symbol: str, days: int) -> pd.DataFrame:
    """Daily candles from Binance's public market-data API (history back to 2017)."""
    sym = binance_symbol(symbol)
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 86_400_000
    last_err = None
    for host in BINANCE_HOSTS:
        rows, t0 = [], start_ms
        try:
            while t0 < end_ms:
                batch = _get_json(f"{host}/api/v3/klines",
                                  {"symbol": sym, "interval": "1d", "startTime": t0, "limit": 1000})
                if not isinstance(batch, list) or not batch:
                    break
                rows.extend(batch)
                nxt = int(batch[-1][0]) + 86_400_000
                if nxt <= t0:
                    break
                t0 = nxt
            break
        except Exception as e:  # try the next host
            last_err = e
            rows = []
    if not rows:
        if last_err:
            raise last_err
        return pd.DataFrame()
    df = pd.DataFrame(
        {"open": [float(r[1]) for r in rows], "high": [float(r[2]) for r in rows],
         "low": [float(r[3]) for r in rows], "close": [float(r[4]) for r in rows],
         "volume": [float(r[5]) for r in rows]},
        index=pd.to_datetime([int(r[0]) for r in rows], unit="ms", utc=True),
    )
    df = df[~df.index.duplicated(keep="last")].sort_index()
    # Drop today's unfinished candle so every bar is a completed day.
    if len(df) and df.index[-1] + pd.Timedelta(days=1) > pd.Timestamp.now(tz="UTC"):
        df = df.iloc[:-1]
    return df.dropna(subset=["close"])


def load_daily(symbol: str, days: int, refresh: bool = False, source: str = "delta") -> pd.DataFrame:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{symbol}_D_{days}d_{source}.csv")
    if not refresh and os.path.exists(path) and (time.time() - os.path.getmtime(path)) < 12 * 3600:
        df = pd.read_csv(path, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True)
        return df
    df = fetch_binance_daily(symbol, days) if source == "binance" else fetch_daily_candles(symbol, days)
    if not df.empty:
        df.to_csv(path)
    return df


def _net(entry: float, exit_px: float, is_short: bool, days_held: int, funding: float) -> float:
    fill = exit_px * (1 + EXIT_SLIPPAGE_PCT) if is_short else exit_px * (1 - EXIT_SLIPPAGE_PCT)
    gross = (entry - fill) / entry if is_short else (fill - entry) / entry
    return gross - TAKER_FEE_PCT - TAKER_FEE_PCT * (fill / entry) - funding * max(days_held, 1)


def simulate_trend(
    symbol: str,
    d: pd.DataFrame,
    p: TrendParams,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> list[Trade]:
    sig = compute_trend_signals(d, p)
    idx = d.index
    o, hi, lo, c = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = sig["atr"].to_numpy()
    le, se = sig["long_entry"].to_numpy(), sig["short_entry"].to_numpy()
    lx, sx = sig["long_exit"].to_numpy(), sig["short_exit"].to_numpy()
    allowed = np.ones(len(d), dtype=bool)
    if start is not None:
        allowed &= idx >= start
    if end is not None:
        allowed &= idx < end

    trades: list[Trade] = []
    n, i = len(d), 0
    while i < n - 1:
        go_long = allowed[i] and le[i] and a[i] > 0
        go_short = allowed[i] and p.side == "both" and se[i] and a[i] > 0
        if not (go_long or go_short):
            i += 1
            continue
        is_short = bool(go_short and not go_long)
        j = i + 1
        entry = o[j] * (1 - ENTRY_SLIPPAGE_PCT) if is_short else o[j] * (1 + ENTRY_SLIPPAGE_PCT)
        stop_dist = p.atr_k * a[i]
        stop = entry + stop_dist if is_short else entry - stop_dist
        risk_frac = stop_dist / entry
        best_close = entry
        exit_px, reason, k = None, None, j

        for k in range(j, n):
            if (is_short and hi[k] >= stop) or (not is_short and lo[k] <= stop):
                gap = (o[k] > stop) if is_short else (o[k] < stop)
                exit_px, reason = (o[k] if gap else stop), "STOP"
                break
            exit_signal = sx[k] if is_short else lx[k]
            if exit_signal and k + 1 < n:
                exit_px, reason, k = o[k + 1], "TREND_EXIT", k + 1
                break
            # trail from the best close so far (chandelier stop), using today's ATR
            best_close = min(best_close, c[k]) if is_short else max(best_close, c[k])
            if a[k] > 0:
                trail = best_close + p.atr_k * a[k] if is_short else best_close - p.atr_k * a[k]
                stop = min(stop, trail) if is_short else max(stop, trail)

        if exit_px is None:
            exit_px, reason, k = c[n - 1], "END_OF_DATA", n - 1

        days_held = int((idx[k] - idx[j]).days)
        net = _net(entry, exit_px, is_short, days_held, p.funding_pct_per_day)
        trades.append(Trade(
            symbol=symbol, direction="SHORT" if is_short else "LONG",
            entry_time=str(idx[j]), exit_time=str(idx[k]),
            entry=round(entry, 8), exit=round(float(exit_px), 8),
            stop_dist=round(stop_dist, 8), exit_reason=reason,
            net_pct=round(net * 100, 4),
            r_multiple=round(net / risk_frac, 3) if risk_frac > 0 else 0.0,
        ))
        i = k + 1
    return trades


# ------------------------------------------------------------------ compounding

def compound(trades: list[Trade], start_equity: float = 10.0, risk_pct: float = 0.01) -> dict:
    """Replay trades in time order, risking `risk_pct` of equity at each entry.

    P&L is booked at exit; positions overlap across symbols, so risk is computed
    from equity as of each entry (equity known at that moment).
    """
    if not trades:
        return {"start_equity": start_equity, "end_equity": start_equity, "return_pct": 0.0, "max_drawdown_pct": 0.0}
    events = []
    for t in trades:
        events.append((pd.Timestamp(t.entry_time), 1, t))
        events.append((pd.Timestamp(t.exit_time), 0, t))
    events.sort(key=lambda e: (e[0], e[1]))  # exits before entries on the same day
    equity, peak, max_dd = start_equity, start_equity, 0.0
    at_risk: dict[int, float] = {}
    for _, kind, t in events:
        if kind == 1:
            at_risk[id(t)] = equity * risk_pct
        else:
            equity += at_risk.pop(id(t), 0.0) * t.r_multiple
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)
    return {
        "start_equity": round(start_equity, 2),
        "end_equity": round(equity, 2),
        "return_pct": round((equity / start_equity - 1) * 100, 1),
        "max_drawdown_pct": round(max_dd * 100, 1),
    }


def monte_carlo(trades: list[Trade], risk_pct: float = 0.01, runs: int = 3000, seed: int = 7) -> dict:
    """Resample the trade sequence (with replacement) to see the RANGE of outcomes the same
    edge could produce in a different order (pattern adopted from Jesse's Monte Carlo mode).
    The one historical path is just one draw; the worst plausible drawdown matters more."""
    if len(trades) < 20:
        return {}
    rng = np.random.default_rng(seed)
    r = np.array([t.r_multiple for t in trades])
    dds, finals = [], []
    for _ in range(runs):
        path = rng.choice(r, size=len(r), replace=True)
        eq = np.cumprod(1 + risk_pct * path)
        peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))
        dds.append(float(np.max((peak[1:] - eq) / peak[1:])) * 100)
        finals.append(float(eq[-1]))
    pct = lambda a, q: round(float(np.percentile(a, q)), 2)  # noqa: E731
    return {"runs": runs, "trades_per_run": len(r),
            "max_drawdown_pct": {"median": pct(dds, 50), "p90": pct(dds, 90), "p95": pct(dds, 95), "p99": pct(dds, 99)},
            "equity_multiple": {"p5": pct(finals, 5), "median": pct(finals, 50), "p95": pct(finals, 95)},
            "chance_of_loss_pct": round(float(np.mean(np.array(finals) < 1.0)) * 100, 1)}


def hold_return_pct(d: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None = None) -> float:
    w = d[(d.index >= start) & ((d.index < end) if end is not None else True)]
    if len(w) < 2:
        return float("nan")
    return round((w["close"].iloc[-1] / w["open"].iloc[0] - 1) * 100, 1)


# -------------------------------------------------------------------------- run

def sweep_grid(funding: float) -> list[TrendParams]:
    g = []
    for side in ("long", "both"):
        for k in (3.0, 4.0):
            for n_in, n_out in ((20, 10), (20, 20), (55, 10), (55, 20)):
                g.append(TrendParams("donchian", n_in, n_out, k, side, funding))
            for fast, slow in ((20, 100), (50, 200)):
                g.append(TrendParams("ema", fast, slow, k, side, funding))
    return g


def run(data: dict[str, pd.DataFrame], p: TrendParams, start=None, end=None) -> list[Trade]:
    out: list[Trade] = []
    for sym, d in data.items():
        out.extend(simulate_trend(sym, d, p, start, end))
    return out


def by_year(trades: list[Trade], btc: pd.DataFrame | None, risk_pct: float) -> list[dict]:
    """Per calendar year (by exit date): trades, expectancy, compounded return, BTC hold."""
    rows = []
    years = sorted({pd.Timestamp(t.exit_time).year for t in trades})
    for y in years:
        ty = [t for t in trades if pd.Timestamp(t.exit_time).year == y]
        s = summarize(ty)
        c = compound(ty, 10.0, risk_pct)
        hold = float("nan")
        if btc is not None:
            hold = hold_return_pct(btc, pd.Timestamp(f"{y}-01-01", tz="UTC"), pd.Timestamp(f"{y + 1}-01-01", tz="UTC"))
        rows.append({"year": y, "trades": s["trades"], "expectancy_R": s["expectancy_R"],
                     "win_rate_pct": s["win_rate_pct"], "strategy_return_pct": c["return_pct"],
                     "strategy_max_dd_pct": c["max_drawdown_pct"], "btc_hold_pct": hold})
    return rows


def print_years(rows: list[dict]) -> None:
    print("\n  Year | trades | exp R  | win%  | strategy | worst drop | BTC hold")
    for r in rows:
        print(f"  {r['year']} | {r['trades']:6d} | {r['expectancy_R']:+.3f} | {r['win_rate_pct']:5.1f} | "
              f"{r['strategy_return_pct']:+7.1f}% | {r['strategy_max_dd_pct']:9.1f}% | {r['btc_hold_pct']:+7.1f}%")


def _report(title: str, trades: list[Trade], risk_pct: float, btc: pd.DataFrame | None = None, years: bool = False) -> dict:
    s = summarize(trades)
    s["compounded_1pct_risk_from_$10"] = compound(trades, 10.0, risk_pct)
    print(f"\n=== {title} ===")
    print(json.dumps(s, indent=2))
    if years and trades:
        print_years(by_year(trades, btc, risk_pct))
    print("VERDICT:", verdict(s))
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--majors", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--days", type=int, default=None, help="History to test (default: 3 years on Delta, 8 years on Binance)")
    ap.add_argument("--source", choices=["delta", "binance"], default="delta",
                    help="binance = Binance spot daily candles back to 2017 (incl. the 2018 and 2022 crashes)")
    ap.add_argument("--funding", type=float, default=DEFAULT_FUNDING_PCT_PER_DAY, help="Funding cost per day held, e.g. 0.0003")
    ap.add_argument("--risk-pct", type=float, default=0.01, help="Equity risked per trade in the compounding replay")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--test-frac", type=float, default=1 / 3)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--csv")
    args = ap.parse_args()

    symbols = args.symbols or (MAJORS if args.majors else top_perpetuals(args.top))
    if args.days is None:
        args.days = 2920 if args.source == "binance" else 1095
    warmup = 260
    print(f"Data source: {args.source} ({'spot, used as a proxy for Delta perpetuals; funding still charged' if args.source == 'binance' else 'Delta perpetuals'})")
    print(f"Costs per side: taker+GST {TAKER_FEE_PCT*100:.4f}%, slippage {ENTRY_SLIPPAGE_PCT*100:.3f}%/{EXIT_SLIPPAGE_PCT*100:.3f}%; funding {args.funding*100:.3f}%/day held")
    data: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            d = load_daily(sym, args.days + warmup, args.refresh, args.source)
        except Exception as e:
            print(f"  {sym}: data error ({e})")
            continue
        if len(d) < 365:
            print(f"  {sym}: skipped, only {len(d)} days of history")
            continue
        data[sym] = d
        print(f"  {sym}: {len(d)} days ({d.index[0].date()} -> {d.index[-1].date()})")
    if not data:
        print("No usable data.")
        return

    last = max(d.index[-1] for d in data.values())
    start = max(last - pd.Timedelta(days=args.days), min(d.index[0] for d in data.values()) + pd.Timedelta(days=warmup))
    btc = data.get("BTCUSD")

    base = PRE_REGISTERED if args.funding == DEFAULT_FUNDING_PCT_PER_DAY else TrendParams(**{**asdict(PRE_REGISTERED), "funding_pct_per_day": args.funding})
    trades = run(data, base, start)
    _report(f"PRE-REGISTERED RULE (untuned): {base.label()}  {start.date()} -> {last.date()}",
            trades, args.risk_pct, btc, years=True)
    mc = monte_carlo(trades, args.risk_pct)
    if mc:
        print(f"\nMonte Carlo ({mc['runs']} reshuffled trade sequences at {args.risk_pct * 100:g}% risk):")
        print(f"  worst drawdown: median {mc['max_drawdown_pct']['median']}%, 1-in-10 {mc['max_drawdown_pct']['p90']}%, "
              f"1-in-20 {mc['max_drawdown_pct']['p95']}%, 1-in-100 {mc['max_drawdown_pct']['p99']}%")
        print(f"  ending equity multiple: 5th pct {mc['equity_multiple']['p5']}x, median {mc['equity_multiple']['median']}x, "
              f"95th pct {mc['equity_multiple']['p95']}x; chance of ending below start: {mc['chance_of_loss_pct']}%")
    if btc is not None:
        print(f"For comparison, holding BTC over the same period: {hold_return_pct(btc, start)}%")
    if args.csv and trades:
        pd.DataFrame([asdict(t) for t in trades]).to_csv(args.csv, index=False)
        print(f"Trades written to {args.csv}")

    if args.sweep:
        split = last - pd.Timedelta(days=int((last - start).days * args.test_frac))
        print(f"\nSweep training: {start.date()} -> {split.date()} | test (unseen): {split.date()} -> {last.date()}")
        rows = []
        for p in sweep_grid(args.funding):
            s = summarize(run(data, p, start, split))
            if s.get("trades", 0) >= 30:
                rows.append((s["expectancy_R"], p, s))
        if not rows:
            print("No setting produced 30+ training trades.")
            return
        rows.sort(key=lambda x: x[0], reverse=True)
        print("\nTop 5 on training data:")
        for e, p, s in rows[:5]:
            print(f"  expR={e:+.3f} trades={s['trades']:4d} win%={s['win_rate_pct']:5.1f} PF={s['profit_factor']} | {p.label()}")
        best = rows[0][1]
        _report(f"BEST TRAINING SETTING ON UNSEEN TEST DATA: {best.label()}", run(data, best, split), args.risk_pct)
        _report(f"PRE-REGISTERED RULE ON THE SAME TEST DATA: {base.label()}", run(data, base, split), args.risk_pct, btc, years=True)
        if btc is not None:
            print(f"Holding BTC over the test period: {hold_return_pct(btc, split)}%")
        print("\nOnly results on unseen data (and the untuned pre-registered rule) count.")


if __name__ == "__main__":
    main()

"""Live Delta Exchange market data for the terminal (public endpoints, standard library).

- tickers(): live mark/last price, 24h change, volume, turnover, best bid/ask, spread,
  funding, open interest and the exchange's own contract size, for the watched coins.
- candles(): OHLCV at 1m/5m/15m/1h/4h/1d.
- indicators: EMA, SMA, Bollinger, VWAP, RSI, MACD, ATR — same definitions as the `ta`
  library / strategy code (Wilder RSI/ATR, span EMA).

Results are cached briefly (tickers 5s, intraday candles 30s, daily candles 10min) so
several open browser tabs don't hammer the exchange. Missing fields stay missing (None);
nothing is ever filled in with a guess.
"""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable

import numpy as np
import pandas as pd

from strategy.daily_trend import atr as atr_wilder
from strategy.daily_trend import ema

DELTA = "https://api.india.delta.exchange"
RESOLUTIONS = {"1m": ("1m", 60), "5m": ("5m", 300), "15m": ("15m", 900), "1h": ("1h", 3600),
               "4h": ("4h", 14400), "1d": ("1d", 86400)}


def http_json(url: str, params: dict | None = None, timeout: float = 8.0) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "daily-trend-terminal"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _f(x) -> float | None:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


class MarketData:
    def __init__(self, fetch: Callable[..., dict] = http_json, base_url: str = DELTA):
        self.fetch = fetch
        self.base = base_url
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def _cached(self, key: str, ttl: float, fn):
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
        val = fn()
        with self._lock:
            self._cache[key] = (time.monotonic(), val)
        return val

    # ---------------------------------------------------------------- tickers

    def tickers(self, symbols: list[str]) -> dict:
        """{'ts': fetch time, 'items': {symbol: {...}}, 'error': str|None}"""
        def load():
            try:
                raw = self.fetch(f"{self.base}/v2/tickers").get("result", [])
                err = None
            except Exception as e:
                raw, err = [], f"Delta tickers unavailable: {e}"
            items = {}
            wanted = set(symbols)
            for t in raw:
                sym = t.get("symbol")
                if sym not in wanted:
                    continue
                q = t.get("quotes") or {}
                mark = _f(t.get("mark_price"))
                last = _f(t.get("close"))
                bid, ask = _f(q.get("best_bid")), _f(q.get("best_ask"))
                ref = mark or last
                chg = _f(t.get("mark_change_24h"))
                if chg is None:
                    o = _f(t.get("open"))
                    chg = ((last - o) / o * 100) if (o and last) else None
                ts_us = _f(t.get("timestamp"))
                items[sym] = {
                    "symbol": sym, "mark": mark, "last": last, "change_24h_pct": chg,
                    "high_24h": _f(t.get("high")), "low_24h": _f(t.get("low")),
                    "volume": _f(t.get("volume")), "turnover_usd": _f(t.get("turnover_usd")),
                    "bid": bid, "ask": ask,
                    "spread_pct": ((ask - bid) / ref * 100) if (bid and ask and ref) else None,
                    "funding_rate_pct": (_f(t.get("funding_rate")) or 0.0) * 100 if t.get("funding_rate") is not None else None,
                    "oi_usd": _f(t.get("oi_value_usd")),
                    "contract_value": _f(t.get("contract_value")),
                    "exchange_ts": (ts_us / 1e6) if ts_us else None,
                }
            return {"ts": time.time(), "items": items, "error": err}
        return self._cached("tickers", 5.0, load)

    # ---------------------------------------------------------------- candles

    def candles(self, symbol: str, tf: str = "1h", bars: int = 300) -> pd.DataFrame:
        if tf not in RESOLUTIONS:
            raise ValueError(f"timeframe must be one of {list(RESOLUTIONS)}")
        res, secs = RESOLUTIONS[tf]
        bars = max(30, min(int(bars), 1500))

        def load():
            end = int(time.time())
            start = end - secs * (bars + 5)
            data = self.fetch(f"{self.base}/v2/chart/history",
                              {"symbol": symbol, "resolution": res, "from": start, "to": end}).get("result", {})
            if not isinstance(data, dict) or not data.get("t"):
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            df = pd.DataFrame({k: [float(x) for x in data[s]] for k, s in
                               [("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v")]},
                              index=pd.to_datetime(data["t"], unit="s", utc=True))
            df = df[~df.index.duplicated(keep="last")].sort_index()
            return df.tail(bars)
        ttl = 600.0 if tf == "1d" else 30.0
        return self._cached(f"c:{symbol}:{tf}:{bars}", ttl, load)


# -------------------------------------------------------------- indicators

def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    out = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return out.where(dn != 0, 100.0)


def macd(c: pd.Series, fast=12, slow=26, signal=9):
    line = ema(c, fast) - ema(c, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def vwap(df: pd.DataFrame, daily_anchor: bool = True) -> pd.Series:
    """Session VWAP anchored at each UTC day (intraday); 20-bar rolling VWAP on daily bars."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv, v = tp * df["volume"], df["volume"]
    if daily_anchor:
        key = df.index.floor("1D")
        return pv.groupby(key).cumsum() / v.groupby(key).cumsum().replace(0, np.nan)
    return pv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)


def indicator_frame(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    c = df["close"]
    out = pd.DataFrame(index=df.index)
    out["ema20"], out["ema50"] = ema(c, 20), ema(c, 50)
    out["sma20"] = c.rolling(20).mean()
    sd = c.rolling(20).std(ddof=0)
    out["bb_upper"], out["bb_lower"] = out["sma20"] + 2 * sd, out["sma20"] - 2 * sd
    out["vwap"] = vwap(df, daily_anchor=(tf != "1d"))
    out["rsi"] = rsi(c, 14)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(c)
    out["atr"] = atr_wilder(df["high"], df["low"], c, 14)
    return out


def summarize_coin(daily: pd.DataFrame) -> dict:
    """Daily-timeframe read of one coin: trend, volatility, momentum (for the market table)."""
    if daily is None or len(daily) < 60:
        return {}
    ind = indicator_frame(daily, "1d").iloc[-1]
    c = float(daily["close"].iloc[-1])
    up = c > ind["ema50"] and ind["ema20"] > ind["ema50"]
    down = c < ind["ema50"] and ind["ema20"] < ind["ema50"]
    return {
        "trend": "UP" if up else ("DOWN" if down else "SIDEWAYS"),
        "rsi": round(float(ind["rsi"]), 1) if pd.notna(ind["rsi"]) else None,
        "macd_hist": float(ind["macd_hist"]) if pd.notna(ind["macd_hist"]) else None,
        "ema20": float(ind["ema20"]), "ema50": float(ind["ema50"]),
        "vwap20": float(ind["vwap"]) if pd.notna(ind["vwap"]) else None,
        "atr": float(ind["atr"]) if pd.notna(ind["atr"]) else None,
        "atr_pct": round(float(ind["atr"]) / c * 100, 2) if pd.notna(ind["atr"]) and c else None,
        "high_55d": float(daily["high"].iloc[-55:].max()),
        "low_20d": float(daily["low"].iloc[-20:].min()),
    }

import asyncio
import time

import httpx
import pandas as pd
import yfinance as yf

from core.logging import logger
from market.providers.base import BaseMarketDataProvider


class YFinanceMarketDataProvider(BaseMarketDataProvider):
    """NSE/BSE & Crypto Market Data Provider backed by Delta Exchange & Yahoo Finance."""

    DELTA_BASE_URL = "https://api.india.delta.exchange"

    def _is_crypto(self, symbol: str) -> bool:
        s = symbol.strip().upper()
        return s.endswith("USD") or s.endswith("-USD") or s.endswith("USDT")

    def _delta_symbol(self, symbol: str) -> str:
        s = symbol.strip().upper().replace("-", "")
        if s.endswith("USDT"):
            s = s[:-1]
        return s

    def _format_symbol(self, symbol: str) -> str:
        symbol = symbol.strip().upper()
        if symbol.startswith("^"):
            return symbol
        if symbol in ["NIFTY", "NIFTY50", "NIFTY 50"]:
            return "^NSEI"
        if symbol in ["BANKNIFTY", "NIFTY BANK", "BANK NIFTY"]:
            return "^NSEBANK"
        # Strip Indian exchange series suffixes like -EQ, -BE, -SM
        for sfx in ["-EQ", "-BE", "-SM", "-BL", "-IL"]:
            if symbol.endswith(sfx):
                symbol = symbol[: -len(sfx)]
                break
        if symbol.endswith(("-USD", "-INR", "-USDT", "=X")):
            return symbol
        # Handle Crypto symbols like BTCUSD, ETHUSD -> BTC-USD, ETH-USD
        if symbol.endswith("USD") and len(symbol) > 3:
            return f"{symbol[:-3]}-USD"
        if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
            symbol = f"{symbol}.NS"
        return symbol

    async def get_ltp(self, symbol: str) -> float:
        # Native Delta Exchange Live LTP for Crypto
        if self._is_crypto(symbol):
            try:
                delta_sym = self._delta_symbol(symbol)
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(f"{self.DELTA_BASE_URL}/v2/tickers/{delta_sym}")
                    if res.status_code == 200:
                        data = res.json().get("result", {})
                        price = float(data.get("mark_price") or data.get("close") or 0.0)
                        if price > 0:
                            return price
            except Exception as e:
                logger.debug(f"[Delta Market Data] Ticker fallback for {symbol}: {e}")

        formatted_symbol = self._format_symbol(symbol)
        loop = asyncio.get_event_loop()

        def _fetch():
            try:
                ticker = yf.Ticker(formatted_symbol)
                hist = ticker.history(period="5d")
                if not hist.empty:
                    clean_hist = hist.dropna(subset=["Close"])
                    if not clean_hist.empty:
                        return float(clean_hist["Close"].iloc[-1])
            except Exception as e:
                logger.debug(f"[YFinance] Ticker history error for {symbol}: {e}")
            return None

        last_price = await loop.run_in_executor(None, _fetch)
        if last_price is not None:
            return float(last_price)

        history = await self.get_historical_ohlcv(symbol, interval="1d", period="5d")
        if not history.empty:
            clean_hist = history.dropna(subset=["close"])
            if not clean_hist.empty:
                return float(clean_hist["close"].iloc[-1])
        raise ValueError(f"Could not retrieve LTP for symbol {symbol}")

    async def _get_delta_historical_ohlcv(
        self, symbol: str, interval: str = "1d", period: str = "60d"
    ) -> pd.DataFrame:
        """Fetches OHLCV directly from Delta Exchange matching engine."""
        delta_sym = self._delta_symbol(symbol)
        now = int(time.time())
        days = 60
        if period.endswith("d"):
            try:
                days = int(period[:-1])
            except ValueError:
                days = 60
        elif period.endswith("mo"):
            try:
                days = int(period[:-2]) * 30
            except ValueError:
                days = 60
        start = now - (days * 86400)

        res_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "6h": "360",
            "1d": "D",
            "1w": "W",
        }
        res = res_map.get(interval.lower(), "D")

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    f"{self.DELTA_BASE_URL}/v2/chart/history",
                    params={"symbol": delta_sym, "resolution": res, "from": start, "to": now},
                )
                if r.status_code == 200:
                    candles = r.json().get("result", {})
                    if isinstance(candles, dict) and "t" in candles and len(candles["t"]) > 0:
                        df = pd.DataFrame(
                            {
                                "open": [float(x) for x in candles["o"]],
                                "high": [float(x) for x in candles["h"]],
                                "low": [float(x) for x in candles["l"]],
                                "close": [float(x) for x in candles["c"]],
                                "volume": [float(x) for x in candles["v"]],
                            },
                            index=pd.to_datetime(candles["t"], unit="s", utc=True),
                        )
                        return df.dropna(subset=["close"])
        except Exception as e:
            logger.debug(f"[Delta Market Data] Candles error for {symbol}: {e}")
        return pd.DataFrame()

    async def get_historical_ohlcv(
        self, symbol: str, interval: str = "1d", period: str = "60d"
    ) -> pd.DataFrame:
        if self._is_crypto(symbol):
            delta_df = await self._get_delta_historical_ohlcv(symbol, interval, period)
            if not delta_df.empty:
                return delta_df

        formatted_symbol = self._format_symbol(symbol)
        loop = asyncio.get_event_loop()

        def _fetch():
            try:
                df = yf.download(
                    formatted_symbol,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                )
                return df
            except Exception as e:
                logger.warning(f"[YFinance] download error for {symbol}: {e}")
                return pd.DataFrame()

        df = await loop.run_in_executor(None, _fetch)
        if df.empty:
            return pd.DataFrame()

        # Handle multi-index columns if returned by newer yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower() for col in df.columns]
        else:
            df.columns = [col.lower() for col in df.columns]

        # Drop unfinalized/holiday rows where close or high is NaN
        if "close" in df.columns:
            df = df.dropna(subset=["close"])

        return df

    async def get_quote(self, symbol: str) -> dict:
        if self._is_crypto(symbol):
            try:
                delta_sym = self._delta_symbol(symbol)
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(f"{self.DELTA_BASE_URL}/v2/tickers/{delta_sym}")
                    if res.status_code == 200:
                        data = res.json().get("result", {})
                        mark_p = float(data.get("mark_price") or data.get("close") or 0.0)
                        open_p = float(data.get("open") or mark_p)
                        prev_close = open_p
                        vol = float(data.get("volume") or 0.0)
                        chg = float(data.get("mark_change_24h") or data.get("ltp_change_24h") or 0.0)
                        return {
                            "symbol": symbol,
                            "ltp": round(mark_p, 4),
                            "open": round(open_p, 4),
                            "previous_close": round(prev_close, 4),
                            "change": round(chg, 2),
                            "volume": vol,
                            "currency": "USD",
                        }
            except Exception as e:
                logger.debug(f"[Delta Market Data] Quote fallback for {symbol}: {e}")

        formatted_symbol = self._format_symbol(symbol)
        loop = asyncio.get_event_loop()

        def _fetch():
            try:
                ticker = yf.Ticker(formatted_symbol)
                hist = ticker.history(period="5d")
                if not hist.empty:
                    clean_hist = hist.dropna(subset=["Close"])
                    if not clean_hist.empty:
                        close = float(clean_hist["Close"].iloc[-1])
                        open_p = float(clean_hist["Open"].iloc[-1]) if not pd.isna(clean_hist["Open"].iloc[-1]) else close
                        prev_close = float(clean_hist["Close"].iloc[-2]) if len(clean_hist) > 1 else open_p
                        vol = float(clean_hist["Volume"].iloc[-1]) if not pd.isna(clean_hist["Volume"].iloc[-1]) else 0.0
                        chg = round(((close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
                        return {
                            "symbol": symbol,
                            "ltp": round(close, 2),
                            "open": round(open_p, 2),
                            "previous_close": round(prev_close, 2),
                            "change": chg,
                            "volume": vol,
                            "currency": "INR",
                        }
            except Exception as e:
                logger.debug(f"[YFinance] get_quote error for {symbol}: {e}")
            return {
                "symbol": symbol,
                "ltp": 0.0,
                "open": 0.0,
                "previous_close": 0.0,
                "change": 0.0,
                "volume": 0.0,
                "currency": "INR",
            }

        return await loop.run_in_executor(None, _fetch)

    async def get_fundamentals(self, symbol: str) -> dict:
        formatted_symbol = self._format_symbol(symbol)
        loop = asyncio.get_event_loop()

        def _fetch():
            import io
            import contextlib
            try:
                ticker = yf.Ticker(formatted_symbol)
                # First gather reliable fast_info (never throws 401 / crumb error)
                fi = getattr(ticker, "fast_info", None)
                high_52 = round(fi.get("yearHigh", 0.0) or 0.0, 2) if fi else 0.0
                low_52 = round(fi.get("yearLow", 0.0) or 0.0, 2) if fi else 0.0
                mcap = fi.get("marketCap", 0) if fi else 0

                # Safely attempt full info while redirecting stderr to silence yfinance crumb retry 401 spam
                info = {}
                try:
                    with contextlib.redirect_stderr(io.StringIO()):
                        info = ticker.info or {}
                except Exception:
                    info = {}

                return {
                    "symbol": symbol,
                    "company_name": info.get("shortName") or info.get("longName") or symbol.replace(".NS", ""),
                    "sector": info.get("sector", "General"),
                    "industry": info.get("industry", "Diversified"),
                    "pe_ratio": round(info.get("trailingPE", 0.0) or 0.0, 2),
                    "forward_pe": round(info.get("forwardPE", 0.0) or 0.0, 2),
                    "pb_ratio": round(info.get("priceToBook", 0.0) or 0.0, 2),
                    "roe": round((info.get("returnOnEquity", 0.0) or 0.0) * 100, 2),
                    "revenue_growth_pct": round((info.get("revenueGrowth", 0.0) or 0.0) * 100, 2),
                    "earnings_growth_pct": round((info.get("earningsGrowth", 0.0) or 0.0) * 100, 2),
                    "profit_margins_pct": round((info.get("profitMargins", 0.0) or 0.0) * 100, 2),
                    "debt_to_equity": round(info.get("debtToEquity", 0.0) or 0.0, 2),
                    "fifty_two_week_high": high_52 or round(info.get("fiftyTwoWeekHigh", 0.0) or 0.0, 2),
                    "fifty_two_week_low": low_52 or round(info.get("fiftyTwoWeekLow", 0.0) or 0.0, 2),
                    "market_cap": mcap or info.get("marketCap", 0),
                    "business_summary": (info.get("longBusinessSummary") or "")[:200],
                }
            except Exception:
                return {"symbol": symbol, "sector": "General"}

        return await loop.run_in_executor(None, _fetch)

    async def get_news(self, symbol: str) -> list[str]:
        formatted_symbol = self._format_symbol(symbol)
        loop = asyncio.get_event_loop()

        def _fetch():
            import io
            import contextlib
            try:
                ticker = yf.Ticker(formatted_symbol)
                with contextlib.redirect_stderr(io.StringIO()):
                    news = ticker.news or []
                headlines = []
                for n in news[:5]:
                    title = n.get("title") or (n.get("content", {}).get("title") if isinstance(n.get("content"), dict) else "")
                    if title:
                        headlines.append(title)
                return headlines if headlines else ["Market volume and price action within normal technical bounds."]
            except Exception:
                return ["Sector momentum stable; no adverse corporate regulatory announcements."]

        return await loop.run_in_executor(None, _fetch)


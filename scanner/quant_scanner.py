import asyncio

import pandas as pd
import ta

from core.domain.models import MarketRegime
from core.logging import logger
from core.schemas.trade import CandidateSignal
from market.providers.base import BaseMarketDataProvider
from scanner.regime import MarketRegimeDetector

# Predefined Universes for Indian Markets (NSE Equities)
NIFTY_50_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "TATACOMM.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "AXISBANK.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "NTPC.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "POWERGRID.NS", "TATASTEEL.NS",
    "M&M.NS", "ASIANPAINT.NS", "BAJAJFINSV.NS", "HCLTECH.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "NESTLEIND.NS", "JSWSTEEL.NS", "GRASIM.NS", "TECHM.NS",
    "HINDALCO.NS", "CIPLA.NS", "DRREDDY.NS", "APOLLOHOSP.NS", "EICHERMOT.NS",
    "BPCL.NS", "BRITANNIA.NS", "TATACONSUM.NS", "DIVISLAB.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "HEROMOTOCO.NS", "SHREECEM.NS", "BEL.NS", "TRENT.NS"
]

NIFTY_NEXT_50_UNIVERSE = [
    "CHOLAFIN.NS", "HAVELLS.NS", "PIDILITIND.NS", "IOC.NS", "GAIL.NS",
    "VEDL.NS", "SIEMENS.NS", "ABB.NS", "HAL.NS", "BANKBARODA.NS",
    "PNB.NS", "CANBK.NS", "DLF.NS", "GODREJCP.NS", "DABUR.NS",
    "AMBUJACEM.NS", "INDIGO.NS", "TVSMOTOR.NS", "BAJAJ-AUTO.NS", "BOSCHLTD.NS",
    "IRCTC.NS", "JIOFIN.NS", "VBL.NS", "TORNTPHARM.NS", "ZYDUSLIFE.NS",
    "PERSISTENT.NS", "POLYCAB.NS", "CUMMINSIND.NS", "COLPAL.NS",
    "RECLTD.NS", "PFC.NS", "IRFC.NS", "BHEL.NS", "NHPC.NS",
    "RVNL.NS", "UNIONBANK.NS", "IOB.NS", "INDIANB.NS", "IDFCFIRSTB.NS",
    "FEDERALBNK.NS", "AUROPHARMA.NS", "LUPIN.NS", "BIOCON.NS", "ALKEM.NS",
    "JINDALSTEL.NS", "NMDC.NS", "SAIL.NS", "NATIONALUM.NS", "HINDPETRO.NS"
]

NIFTY_100_UNIVERSE = list(dict.fromkeys(NIFTY_50_UNIVERSE + NIFTY_NEXT_50_UNIVERSE))


NIFTY_MIDCAP_MOMENTUM_UNIVERSE = [
    "MRF.NS", "BALKRISIND.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "BHARATFORG.NS",
    "MOTHERSON.NS", "EXIDEIND.NS", "CONCOR.NS", "JSWENERGY.NS", "TATAPOWER.NS",
    "ADANIGREEN.NS", "ADANIPOWER.NS", "TORNTPOWER.NS", "SUZLON.NS", "IREDA.NS",
    "KPITTECH.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS", "TATAELXSI.NS",
    "DIXON.NS", "KAYNES.NS", "ASTRAL.NS", "SUPREMEIND.NS", "VOLTAS.NS",
    "BLUESTARCO.NS", "CROMPTON.NS", "WHIRLPOOL.NS", "DEEPAKNTR.NS", "TATACHEM.NS",
    "PIIND.NS", "SRF.NS", "NAVINFLUOR.NS", "UPL.NS", "ATUL.NS",
    "PRESTIGE.NS", "OBEROIRLTY.NS", "GODREJPROP.NS", "BRIGADE.NS", "PHOENIXLTD.NS",
    "JUBLFOOD.NS", "DEVYANI.NS", "WESTLIFE.NS", "PAGEIND.NS", "MANYAVAR.NS",
    "METROBRAND.NS", "BATAINDIA.NS", "KALYANKJIL.NS", "MAZDOCK.NS", "COCHINSHIP.NS",
    "GRSE.NS", "BDL.NS", "BEML.NS", "HUDCO.NS", "NBCC.NS", "SJVN.NS", "IRCON.NS",
    "OIL.NS", "CASTROLIND.NS", "MANAPPURAM.NS", "ABCAPITAL.NS", "LICHSGFIN.NS",
    "MUTHOOTFIN.NS", "CESC.NS", "HAPPSTMNDS.NS", "CYIENT.NS",
    "SONACOMS.NS", "TIINDIA.NS", "RADICO.NS", "UNITDSPR.NS", "CHAMBLFERT.NS",
    "GNFC.NS", "COROMANDEL.NS", "FACT.NS", "RCF.NS", "GSFC.NS", "DEEPAKFERT.NS",
    "CENTURYPLY.NS", "CERA.NS", "FINCABLES.NS", "KEI.NS",
    "RRKABEL.NS", "TRIDENT.NS", "RAYMOND.NS", "WELSPUNLIV.NS", "ALOKINDS.NS"
]

BOOTSTRAP_ACTIONABLE_UNIVERSE = [
    # PSU & Private Banking (< ₹570)
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "PNB.NS", "CANBK.NS", "BANKBARODA.NS",
    "UNIONBANK.NS", "IOB.NS", "INDIANB.NS", "ABCAPITAL.NS", "MANAPPURAM.NS",
    "LICI.NS", "BANDHANBNK.NS",
    # Power, Energy & Utilities (< ₹570)
    "POWERGRID.NS", "COALINDIA.NS", "ONGC.NS", "NTPC.NS", "IOC.NS",
    "GAIL.NS", "BPCL.NS", "HINDPETRO.NS", "TATAPOWER.NS", "NHPC.NS",
    "SJVN.NS", "SUZLON.NS", "IREDA.NS", "CESC.NS", "OIL.NS",
    # Metals & Mining (< ₹570)
    "TATASTEEL.NS", "SAIL.NS", "NATIONALUM.NS", "NMDC.NS", "VEDL.NS",
    # Defense, Railway & Capital Goods (< ₹570)
    "BEL.NS", "BHEL.NS", "HUDCO.NS", "NBCC.NS", "IRCON.NS", "RVNL.NS", "IRFC.NS",
    # Auto Ancillaries, Logistics & Infra (< ₹570)
    "ASHOKLEY.NS", "EXIDEIND.NS", "MOTHERSON.NS", "CASTROLIND.NS", "GMRAIRPORT.NS",
    # Tech, Telecom & Media (< ₹570)
    "WIPRO.NS", "HFCL.NS", "ZEEL.NS",
    # FMCG & Healthcare (< ₹570)
    "ITC.NS", "DABUR.NS", "BIOCON.NS", "HDFCLIFE.NS", "DEVYANI.NS",
    # Fertilizers & Agro-Chemicals (< ₹570)
    "FACT.NS", "RCF.NS", "CHAMBLFERT.NS", "GSFC.NS", "DEEPAKFERT.NS"
]

DELTA_CRYPTO_BOOTSTRAP_UNIVERSE = [
    # High-liquidity, micro-notional contracts (< .50 unit cost) safe for micro bootstrap accounts
    "ADAUSD", "SUIUSD", "XRPUSD", "NEARUSD", "DOGEUSD"
]

DELTA_CRYPTO_FULL_UNIVERSE = [
    "BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "DOGEUSD",
    "ADAUSD", "AVAXUSD", "LINKUSD", "SUIUSD", "NEARUSD", "APTUSD",
    "RENDERUSD", "DOTUSD", "LTCUSD", "BCHUSD", "UNIUSD", "ATOMUSD",
    "ICPUSD", "FILUSD", "ARBUSD", "OPUSD", "INJUSD", "TIAUSD",
    "FETUSD", "SEIUSD", "GALAUSD", "PEPEUSD", "SHIBUSD", "AAVEUSD", "TRXUSD"
]

DELTA_CRYPTO_UNIVERSE = DELTA_CRYPTO_FULL_UNIVERSE

NIFTY_500_UNIVERSE = list(dict.fromkeys(
    NIFTY_50_UNIVERSE + NIFTY_NEXT_50_UNIVERSE + NIFTY_MIDCAP_MOMENTUM_UNIVERSE
))

DEFAULT_NSE_UNIVERSE = NIFTY_500_UNIVERSE

UNIVERSE_MAP = {
    "default": BOOTSTRAP_ACTIONABLE_UNIVERSE,
    "bootstrap": BOOTSTRAP_ACTIONABLE_UNIVERSE,
    "affordable": BOOTSTRAP_ACTIONABLE_UNIVERSE,
    "actionable": BOOTSTRAP_ACTIONABLE_UNIVERSE,
    "nifty50": NIFTY_50_UNIVERSE,
    "nifty100": list(dict.fromkeys(NIFTY_50_UNIVERSE + NIFTY_NEXT_50_UNIVERSE)),
    "nifty200": NIFTY_500_UNIVERSE,
    "nifty500": NIFTY_500_UNIVERSE,
    "all": NIFTY_500_UNIVERSE,
    "crypto": DELTA_CRYPTO_UNIVERSE,
    "delta": DELTA_CRYPTO_UNIVERSE,
    "delta_crypto": DELTA_CRYPTO_UNIVERSE,
}


class QuantMarketScanner:
    """Multi-Factor Quant Scanner analyzing 200+ liquid NSE equities with dynamic profit ranking."""

    def __init__(
        self,
        provider: BaseMarketDataProvider,
        universe: list[str] | str | None = None,
        max_concurrency: int = 25,
    ):
        self.provider = provider
        self.universe_name = universe if isinstance(universe, str) else None
        if isinstance(universe, str):
            self.universe = UNIVERSE_MAP.get(universe.lower(), NIFTY_500_UNIVERSE)
        else:
            self.universe = universe or NIFTY_500_UNIVERSE
        self.max_concurrency = max_concurrency
        self._rotation_index = 0

    @staticmethod
    async def get_live_delta_perpetuals(
        min_turnover_usd: float = 10000.0,
        available_capital: float | None = None,
        max_symbols: int = 40,
    ) -> list[str]:
        """Dynamically fetches active liquid perpetual contracts directly from Delta Exchange API,
        filtered by account capital affordability and ranked by 24h market turnover.
        """
        try:
            from portfolio.position_sizer import get_delta_contract_multiplier
            from core.config.settings import settings
            crypto_lev = getattr(settings, "DELTA_MAX_LEVERAGE", 5.0)

            import httpx
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get("https://api.india.delta.exchange/v2/tickers")
                if r.status_code == 200:
                    data = r.json().get("result", [])
                    operational = [
                        t for t in data
                        if t.get("contract_type") == "perpetual_futures"
                        and t.get("product_trading_status") == "operational"
                        and float(t.get("turnover_usd") or 0.0) >= min_turnover_usd
                    ]
                    
                    # Filter dynamically based on account capital (select all affordable crypto from entire market)
                    if available_capital is not None and available_capital > 0:
                        max_unit_margin = min(available_capital * 0.45, available_capital - 0.50) if available_capital < 25.0 else available_capital
                        eligible = []
                        for t in operational:
                            sym = t.get("symbol", "")
                            mark_price = float(t.get("mark_price") or t.get("close") or 0.0)
                            if mark_price <= 0:
                                continue
                            raw_mult = get_delta_contract_multiplier(sym)
                            mult = raw_mult if (raw_mult is not None and raw_mult > 0) else 1.0
                            unit_margin = (mark_price * mult) / crypto_lev
                            if 0 < unit_margin <= max_unit_margin:
                                eligible.append(t)
                        if eligible:
                            operational = eligible

                    # Sort by 24h turnover descending so highest liquidity is scanned first
                    operational.sort(key=lambda t: float(t.get("turnover_usd") or 0.0), reverse=True)
                    symbols = [t["symbol"] for t in operational[:max_symbols]]
                    if symbols:
                        logger.info(
                            f"⚡ [Delta Complete Market Scanner] Evaluated full exchange ({len(data)} markets) -> "
                            f"Selected {len(symbols)} liquid, affordable perpetuals for capital (${available_capital or 0.0:.2f})"
                        )
                        return symbols
        except Exception as e:
            logger.debug(f"Error fetching live Delta tickers: {e}")
        return DELTA_CRYPTO_FULL_UNIVERSE

    async def scan_symbol(self, symbol: str) -> CandidateSignal | None:
        try:
            df = await self.provider.get_historical_ohlcv(symbol, interval="1d", period="60d")
            if df.empty or len(df) < 20:
                return None

            close = df["close"]
            high = df["high"]
            low = df["low"]
            volume = df["volume"]

            ltp = float(close.iloc[-1])
            curr_volume = float(volume.iloc[-1])
            # BUG-08 FIX: Exclude incomplete current daily bar from 20-day historical baseline
            closed_volume = volume.iloc[:-1] if len(volume) > 20 else volume
            avg_volume_20 = float(closed_volume.tail(20).mean())
            rel_volume = curr_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0

            # Volatility (ATR 14)
            atr_series = ta.volatility.average_true_range(high, low, close, window=14)
            atr_14 = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else (ltp * 0.015)

            # Momentum (RSI 14 + EMA 20/50 + MACD)
            rsi_series = ta.momentum.rsi(close, window=14)
            rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0

            ema_20 = ta.trend.ema_indicator(close, window=20).iloc[-1]
            ema_50 = ta.trend.ema_indicator(close, window=min(50, len(df))).iloc[-1]

            # Multi-Factor Profit Expectancy Score (0 to 100)
            momentum_score = 0.0
            if ltp > ema_20:
                momentum_score += 25.0
            if ema_20 > ema_50:
                momentum_score += 25.0
            # RSI sweet spot: healthy bull pullbacks (40-60) get max score
            if 40.0 <= rsi <= 65.0:
                momentum_score += 30.0
            elif 30.0 <= rsi < 40.0:  # Oversold bounce potential
                momentum_score += 20.0
            elif 65.0 < rsi <= 75.0:  # Strong trend
                momentum_score += 15.0

            if rel_volume > 1.2:
                momentum_score += 20.0
            elif rel_volume > 0.8:
                momentum_score += 10.0

            regime = MarketRegimeDetector.detect_regime(df)
            is_crypto = symbol.upper().endswith("USD") or symbol.upper().endswith("-USD") or "USD" in symbol.upper()

            # Multi-Timeframe Trend Confirmation (Vojtko & Mesíček, Sharpe 3.39)
            is_daily_uptrend = (ltp > ema_50) and (ema_20 > ema_50)
            is_daily_downtrend = (ltp < ema_50) and (ema_20 < ema_50)

            # 1. Bullish Setup Momentum Score (0 to 100)
            bull_score = 0.0
            if ltp > ema_20:
                bull_score += 25.0
            if ema_20 > ema_50:
                bull_score += 25.0
            if 40.0 <= rsi <= 65.0:
                bull_score += 30.0
            elif 30.0 <= rsi < 40.0:
                bull_score += 20.0
            elif 65.0 < rsi <= 75.0:
                bull_score += 15.0

            if rel_volume > 1.2:
                bull_score += 20.0
            elif rel_volume > 0.8:
                bull_score += 10.0

            if is_daily_uptrend:
                bull_score += 15.0
            elif is_daily_downtrend:
                bull_score -= 25.0

            # 2. Bearish Setup Momentum Score (0 to 100) (For Shorting Breakdown/Distribution)
            bear_score = 0.0
            if ltp < ema_20:
                bear_score += 25.0
            if ema_20 < ema_50:
                bear_score += 25.0
            if 35.0 <= rsi <= 55.0:
                bear_score += 30.0
            elif rsi < 35.0:
                bear_score += 25.0
            elif 55.0 < rsi <= 65.0:
                bear_score += 10.0

            if rel_volume > 1.2:
                bear_score += 20.0
            elif rel_volume > 0.8:
                bear_score += 10.0

            if is_daily_downtrend:
                bear_score += 15.0
            elif is_daily_uptrend:
                bear_score -= 25.0

            # Hourly Momentum Confirmation for Crypto Assets
            if is_crypto:
                try:
                    df_1h = await self.provider.get_historical_ohlcv(symbol, interval="1h", period="7d")
                    if not df_1h.empty and len(df_1h) >= 20:
                        c_1h = df_1h["close"]
                        ema9_1h = float(ta.trend.ema_indicator(c_1h, window=9).iloc[-1])
                        ema21_1h = float(ta.trend.ema_indicator(c_1h, window=21).iloc[-1])
                        rsi_1h_series = ta.momentum.rsi(c_1h, window=14)
                        rsi_1h = float(rsi_1h_series.iloc[-1]) if not pd.isna(rsi_1h_series.iloc[-1]) else 50.0
                        ltp_1h = float(c_1h.iloc[-1])

                        # Bullish MTF alignment
                        if ltp_1h > ema21_1h and ema9_1h >= ema21_1h and (45.0 <= rsi_1h <= 75.0):
                            if is_daily_uptrend:
                                bull_score += 35.0
                                logger.info(f"🌟 [MTF Bull Confluence | Sharpe 3.39] {symbol}: Daily 20/50 + Hourly 9/21 Momentum ALIGNED (+35 pts)")
                            else:
                                bull_score += 15.0
                        elif ltp_1h < ema21_1h and ema9_1h < ema21_1h:
                            bull_score -= 20.0

                        # Bearish MTF alignment (Short Breakdown Confluence)
                        if ltp_1h < ema21_1h and ema9_1h <= ema21_1h and (25.0 <= rsi_1h <= 55.0):
                            if is_daily_downtrend:
                                bear_score += 35.0
                                logger.info(f"⚡ [MTF Bear Confluence | Short Breakdown] {symbol}: Daily Downtrend + Hourly 9/21 Breakdown ALIGNED (+35 pts)")
                            else:
                                bear_score += 15.0
                        elif ltp_1h > ema21_1h and ema9_1h > ema21_1h:
                            bear_score -= 20.0
                except Exception as mtf_err:
                    logger.debug(f"MTF 1h check note for {symbol}: {mtf_err}")

            # Directional Determination for Derivatives
            if is_crypto and bear_score > bull_score and bear_score >= 30.0:
                setup_direction = "SHORT"
                momentum_score = bear_score
                if regime in [MarketRegime.SIDEWAYS_RANGING, MarketRegime.BULLISH_TREND]:
                    regime = MarketRegime.BEARISH_TREND
            else:
                setup_direction = "LONG"
                momentum_score = bull_score

            # Turnover check (LTP * Avg Volume >= 1M INR for broad universe liquidity, $10K USD for crypto)
            min_turnover = 10000.0 if is_crypto else 1000000.0
            if (ltp * avg_volume_20) < min_turnover:
                return None

            atr_prec = 6 if ltp < 0.10 else (4 if ltp < 10.0 else 2)
            return CandidateSignal(
                symbol=symbol,
                exchange="DELTA" if is_crypto else "NSE",
                ltp=ltp,
                volume=curr_volume,
                avg_volume_20d=avg_volume_20,
                relative_volume=round(rel_volume, 2),
                momentum_score=round(momentum_score, 2),
                atr_14=round(atr_14, atr_prec),
                regime=regime,
                sector="Crypto Derivatives" if is_crypto else "Indian Equities",
                setup_direction=setup_direction,
            )
        except Exception as e:
            logger.debug(f"Scan note on {symbol}: {e}")
            return None

    async def scan_all_candidates(
        self,
        symbols: list[str] | None = None,
        available_capital: float | None = None,
    ) -> list[CandidateSignal]:
        """Scans all stocks/cryptos in parallel using bounded concurrency."""
        target_symbols = symbols or self.universe

        # If scanning crypto, dynamically pull ALL operational perpetuals on Delta Exchange filtered by capital!
        if not symbols and (self.universe_name in ["crypto", "delta", "delta_crypto"] or (self.universe and self.universe[0].endswith("USD"))):
            live_symbols = await self.get_live_delta_perpetuals(available_capital=available_capital)
            if live_symbols:
                target_symbols = live_symbols

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _bounded_scan(sym: str) -> CandidateSignal | None:
            async with semaphore:
                return await self.scan_symbol(sym)

        tasks = [_bounded_scan(sym) for sym in target_symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        candidates: list[CandidateSignal] = []
        for res in results:
            if isinstance(res, CandidateSignal):
                candidates.append(res)
            elif isinstance(res, Exception):
                logger.debug(f"Scan exception on candidate: {res}")

        # Rank candidates by momentum score and relative volume descending
        candidates.sort(
            key=lambda s: (s.momentum_score, s.relative_volume),
            reverse=True,
        )
        return candidates

    async def get_top_candidates(
        self,
        top_n: int = 10,
        symbols: list[str] | None = None,
        max_price: float | None = None,
        available_capital: float | None = None,
    ) -> list[CandidateSignal]:
        candidates = await self.scan_all_candidates(symbols=symbols, available_capital=available_capital)
        if max_price is not None and max_price > 0:
            candidates = [c for c in candidates if c.ltp <= max_price]

        # Filter out exchange surveillance / cautionary listings
        from execution.brokers.angelone import AngelOneBroker
        candidates = [c for c in candidates if c.symbol not in AngelOneBroker.CAUTIONARY_SYMBOLS]

        if not candidates:
            return []

        # For crypto, ensure balanced representation of BOTH top LONG and top SHORT candidates
        is_crypto_universe = (self.universe_name in ["crypto", "delta", "delta_crypto"]) or (candidates and candidates[0].exchange == "DELTA")
        if is_crypto_universe and len(candidates) > top_n:
            long_cands = [c for c in candidates if getattr(c, "setup_direction", "LONG") == "LONG"]
            short_cands = [c for c in candidates if getattr(c, "setup_direction", "LONG") == "SHORT"]

            balanced: list[CandidateSignal] = []
            half_n = max(2, top_n // 2)
            balanced.extend(long_cands[:half_n])
            balanced.extend(short_cands[:half_n])

            # Fill any remaining slots with highest momentum regardless of direction
            for c in candidates:
                if c not in balanced and len(balanced) < top_n:
                    balanced.append(c)
            return balanced[:top_n]

        # Rotate through the candidate pool across cycles for diverse multi-stock coverage
        pool_size = len(candidates)
        if pool_size <= top_n:
            return candidates

        # Cycle offset shifts by 3 stocks each scan to discover new explosive setups continuously
        start_idx = self._rotation_index % pool_size
        self._rotation_index = (self._rotation_index + 3) % pool_size

        rotated = candidates[start_idx:] + candidates[:start_idx]
        return rotated[:top_n]


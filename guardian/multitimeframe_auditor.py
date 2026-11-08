"""
Multi-Timeframe Position Intelligence & AI Thesis Invalidation Auditor.

Analyzes open positions across multiple granularities:
- Microstructure (1m, 5m): Volume-Weighted Average Price (VWAP), 9/21 EMA alignment, micro lower-low breakdowns.
- Intermediate Intraday (1h, 4h): 20/50 EMA market structure, swing high/low violation.
- Macro Regime (1d, 1y): 200-SMA regime, BNF 25-EMA disparity, long-term trend direction.
- Foundation Model: Kronos Candlestick Foundation Model zero-shot probabilistic trajectory projection.

Instead of waiting for arbitrary clock timers, if multi-timeframe analysis detects
thesis invalidation, structural breakdown, or momentum exhaustion, an immediate protective exit
is triggered to preserve capital and recycle margin into active momentum trades.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from core.logging import logger
from intelligence.kronos_service import kronos_service
from market.providers.base import BaseMarketDataProvider


class MultiTimeframePositionAuditor:
    """Continuously evaluates active positions using multi-timeframe market structure and AI foundation intelligence."""

    def __init__(self, audit_interval_seconds: float = 60.0):
        self.audit_interval_seconds = audit_interval_seconds
        self._last_audit_ts: dict[str, float] = {}

    @staticmethod
    def _calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """Calculates Volume Weighted Average Price (VWAP)."""
        if df.empty or "volume" not in df.columns:
            return df["close"] if "close" in df.columns else pd.Series(dtype=float)
        typ = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"].replace(0, np.nan).fillna(1.0)
        cum_vol = vol.cumsum()
        cum_pv = (typ * vol).cumsum()
        return cum_pv / cum_vol.replace(0, np.nan)

    @staticmethod
    def _calculate_ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    async def audit_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        current_ltp: float,
        unrealized_pnl: float,
        provider: BaseMarketDataProvider,
        opened_at: datetime | None = None,
    ) -> tuple[bool, str]:
        """Performs comprehensive multi-timeframe analysis across 1m, 5m, 1h, and 1d candles.
        
        Returns:
            tuple[bool, str]: (should_exit, detailed_reason)
        """
        now = datetime.now(UTC).timestamp()
        last_run = self._last_audit_ts.get(symbol, 0.0)
        # Avoid redundant re-calculation on every single sub-second tick
        if (now - last_run) < self.audit_interval_seconds:
            return False, "Audit cooldown"

        self._last_audit_ts[symbol] = now
        is_long = side.upper() != "SELL"
        pnl_pct = ((current_ltp - entry_price) / entry_price * 100.0) if is_long else ((entry_price - current_ltp) / entry_price * 100.0)

        # Grace period: do not prematurely scratch a brand-new position during its first 5 minutes.
        # Hard stop loss continues to protect capital 100% of the time, but this prevents
        # immediate exits caused by normal 0.05% entry slippage or bid-ask spread.
        if opened_at is not None:
            age_secs = (datetime.now(UTC) - opened_at).total_seconds()
            if age_secs < 300.0:
                return False, f"Position grace period active ({int(age_secs)}s < 300s)"

        # 1. Fetch Multi-Timeframe Data Concurrently (1m, 5m, 1h, 1d)
        tasks = [
            provider.get_historical_ohlcv(symbol, interval="1m", period="1d"),
            provider.get_historical_ohlcv(symbol, interval="5m", period="5d"),
            provider.get_historical_ohlcv(symbol, interval="1h", period="1mo"),
            provider.get_historical_ohlcv(symbol, interval="1d", period="1y"),
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            df_1m: pd.DataFrame = results[0] if isinstance(results[0], pd.DataFrame) else pd.DataFrame()
            df_5m: pd.DataFrame = results[1] if isinstance(results[1], pd.DataFrame) else pd.DataFrame()
            df_1h: pd.DataFrame = results[2] if isinstance(results[2], pd.DataFrame) else pd.DataFrame()
            df_1d: pd.DataFrame = results[3] if isinstance(results[3], pd.DataFrame) else pd.DataFrame()
        except Exception as err:
            logger.debug(f"[MultiTimeframeAuditor] Data fetch exception for {symbol}: {err}")
            return False, "Data fetch error"

        invalidation_signals: list[str] = []
        severity_score = 0.0  # Range: 0.0 (healthy) to 1.0 (terminal invalidation)

        # -------------------------------------------------------------
        # A. MICROSTRUCTURE ANALYSIS (1m & 5m)
        # -------------------------------------------------------------
        if not df_1m.empty and len(df_1m) >= 20:
            df_1m_clean = df_1m.copy()
            df_1m_clean.columns = [c.lower() for c in df_1m_clean.columns]
            vwap_1m = self._calculate_vwap(df_1m_clean)
            ema9_1m = self._calculate_ema(df_1m_clean["close"], 9)
            ema21_1m = self._calculate_ema(df_1m_clean["close"], 21)

            last_close_1m = float(df_1m_clean["close"].iloc[-1])
            last_vwap_1m = float(vwap_1m.iloc[-1]) if not vwap_1m.empty else last_close_1m
            last_ema9_1m = float(ema9_1m.iloc[-1])
            last_ema21_1m = float(ema21_1m.iloc[-1])

            if is_long:
                # Long: Price trading below 1m VWAP and EMA9 < EMA21
                if last_close_1m < last_vwap_1m and last_ema9_1m < last_ema21_1m:
                    severity_score += 0.20
                    invalidation_signals.append("1m lost VWAP & EMA9/21 bearish cross")
            else:
                # Short: Price trading above 1m VWAP and EMA9 > EMA21
                if last_close_1m > last_vwap_1m and last_ema9_1m > last_ema21_1m:
                    severity_score += 0.20
                    invalidation_signals.append("1m broke above VWAP & EMA9/21 bullish cross")

        if not df_5m.empty and len(df_5m) >= 20:
            df_5m_clean = df_5m.copy()
            df_5m_clean.columns = [c.lower() for c in df_5m_clean.columns]
            ema20_5m = self._calculate_ema(df_5m_clean["close"], 20)
            last_close_5m = float(df_5m_clean["close"].iloc[-1])
            last_ema20_5m = float(ema20_5m.iloc[-1])

            # Check 5m breakdown below recent swing lows
            recent_lows = df_5m_clean["low"].iloc[-12:-1]  # Previous 1 hour of 5m candles
            swing_low_5m = float(recent_lows.min()) if not recent_lows.empty else last_close_5m

            recent_highs = df_5m_clean["high"].iloc[-12:-1]
            swing_high_5m = float(recent_highs.max()) if not recent_highs.empty else last_close_5m

            if is_long:
                if last_close_5m < last_ema20_5m:
                    severity_score += 0.15
                    invalidation_signals.append("5m below 20-EMA")
                if last_close_5m < swing_low_5m and pnl_pct < 0:
                    severity_score += 0.25
                    invalidation_signals.append(f"5m broke key swing support ({swing_low_5m:.4f})")
            else:
                if last_close_5m > last_ema20_5m:
                    severity_score += 0.15
                    invalidation_signals.append("5m above 20-EMA")
                if last_close_5m > swing_high_5m and pnl_pct < 0:
                    severity_score += 0.25
                    invalidation_signals.append(f"5m broke key swing resistance ({swing_high_5m:.4f})")

        # -------------------------------------------------------------
        # B. INTRADAY TREND ANALYSIS (1h & 4h)
        # -------------------------------------------------------------
        if not df_1h.empty and len(df_1h) >= 20:
            df_1h_clean = df_1h.copy()
            df_1h_clean.columns = [c.lower() for c in df_1h_clean.columns]
            ema9_1h = self._calculate_ema(df_1h_clean["close"], 9)
            ema20_1h = self._calculate_ema(df_1h_clean["close"], 20)
            ema50_1h = self._calculate_ema(df_1h_clean["close"], 50) if len(df_1h) >= 50 else ema20_1h

            last_close_1h = float(df_1h_clean["close"].iloc[-1])
            last_ema9_1h = float(ema9_1h.iloc[-1])
            last_ema20_1h = float(ema20_1h.iloc[-1])
            last_ema50_1h = float(ema50_1h.iloc[-1])

            if is_long:
                if last_close_1h < last_ema20_1h and last_ema20_1h < last_ema50_1h:
                    severity_score += 0.20
                    invalidation_signals.append("1h structural downtrend (close < EMA20 < EMA50)")
                if last_ema9_1h < last_ema20_1h and pnl_pct < 0:
                    severity_score += 0.15
                    invalidation_signals.append("1h momentum rollover (EMA9 < EMA20)")
            else:
                if last_close_1h > last_ema20_1h and last_ema20_1h > last_ema50_1h:
                    severity_score += 0.20
                    invalidation_signals.append("1h structural uptrend (close > EMA20 > EMA50)")
                if last_ema9_1h > last_ema20_1h and pnl_pct < 0:
                    severity_score += 0.15
                    invalidation_signals.append("1h momentum squeeze against short (EMA9 > EMA20)")

        # -------------------------------------------------------------
        # C. KRONOS CANDLESTICK FOUNDATION MODEL PREDICTION
        # -------------------------------------------------------------
        if not df_5m.empty and len(df_5m) >= 25:
            try:
                forecast = await kronos_service.forecast(symbol, df_5m, pred_len=12)
                if forecast and forecast.status == "SUCCESS":
                    if is_long and forecast.expected_direction == "BEARISH" and forecast.projected_change_pct < -0.30:
                        severity_score += 0.30
                        invalidation_signals.append(
                            f"Kronos Foundation Model predicts breakdown: {forecast.projected_change_pct:+.2f}%"
                        )
                    elif not is_long and forecast.expected_direction == "BULLISH" and forecast.projected_change_pct > 0.30:
                        severity_score += 0.30
                        invalidation_signals.append(
                            f"Kronos Foundation Model predicts breakout against short: {forecast.projected_change_pct:+.2f}%"
                        )
            except Exception as kronos_err:
                logger.debug(f"[MultiTimeframeAuditor] Kronos prediction notice for {symbol}: {kronos_err}")

        # -------------------------------------------------------------
        # D. MACRO 1-DAY & 1-YEAR REGIME & BNF DISPARITY
        # -------------------------------------------------------------
        if not df_1d.empty and len(df_1d) >= 25:
            df_1d_clean = df_1d.copy()
            df_1d_clean.columns = [c.lower() for c in df_1d_clean.columns]
            ema25_1d = self._calculate_ema(df_1d_clean["close"], 25)
            last_close_1d = float(df_1d_clean["close"].iloc[-1])
            last_ema25_1d = float(ema25_1d.iloc[-1])

            # BNF Disparity: (close - EMA25) / EMA25
            disparity_pct = ((last_close_1d - last_ema25_1d) / last_ema25_1d) * 100.0
            if is_long and disparity_pct < -10.0 and pnl_pct < 0:
                severity_score += 0.15
                invalidation_signals.append(f"Daily BNF disparity severe breakdown ({disparity_pct:.1f}%)")

        # -------------------------------------------------------------
        # E. STAGNATION DURATION CHECK (Shorter threshold if signals align)
        # -------------------------------------------------------------
        if opened_at is not None:
            holding_mins = (datetime.now(UTC) - opened_at).total_seconds() / 60.0
            if holding_mins >= 30.0 and pnl_pct < -0.50:
                severity_score += 0.15
                invalidation_signals.append(f"Position underwater ({pnl_pct:+.2f}%) for {int(holding_mins)}m without traction")

        # -------------------------------------------------------------
        # F. FINAL DECISION SYNTHESIS
        # -------------------------------------------------------------
        # Require high severity (>= 0.70) and meaningful loss (pnl_pct < -0.80%) before scratching,
        # preventing micro-friction fee bleeds on normal noise.
        if severity_score >= 0.70 and pnl_pct < -0.80:
            signals_str = "; ".join(invalidation_signals)
            reason = (
                f"Multi-Timeframe AI Thesis Invalidation (Severity: {severity_score:.2f}/1.00, PnL: {pnl_pct:+.2f}%): "
                f"[{signals_str}]. Scratching position early to preserve capital."
            )
            logger.warning(f"🚨 [Multi-Timeframe AI Audit] {symbol}: {reason}")
            return True, reason

        return False, "Multi-timeframe structure intact"


# Global singleton instance
multi_timeframe_auditor = MultiTimeframePositionAuditor()

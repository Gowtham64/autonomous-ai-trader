import pandas as pd
import ta

from core.domain.models import MarketRegime


class MarketRegimeDetector:
    """Classifies market environment into Bullish, Bearish, Sideways, or High Volatility."""

    @staticmethod
    def detect_regime(df: pd.DataFrame) -> MarketRegime:
        if df.empty or len(df) < 20:
            return MarketRegime.SIDEWAYS_RANGING

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # 1. Trend indicators (SMA 20 vs SMA 50)
        sma_20 = ta.trend.sma_indicator(close, window=20)
        sma_50 = ta.trend.sma_indicator(close, window=min(50, len(df)))

        current_close = close.iloc[-1]
        current_sma_20 = sma_20.iloc[-1]
        current_sma_50 = sma_50.iloc[-1]

        # 2. Volatility (ATR % & Bollinger Band width)
        atr = ta.volatility.average_true_range(high, low, close, window=14)
        atr_pct = (atr.iloc[-1] / current_close) * 100.0 if current_close > 0 else 0.0

        # 3. ADX for Trend Strength
        adx_series = ta.trend.adx(high, low, close, window=14)
        current_adx = adx_series.iloc[-1] if not adx_series.empty and not pd.isna(adx_series.iloc[-1]) else 15.0

        # Classification Logic
        if atr_pct > 3.5:
            return MarketRegime.HIGH_VOLATILITY

        if current_adx > 25:
            if current_close > current_sma_20 > current_sma_50:
                return MarketRegime.BULLISH_TREND
            elif current_close < current_sma_20 < current_sma_50:
                return MarketRegime.BEARISH_TREND

        if atr_pct < 1.0:
            return MarketRegime.LOW_VOLATILITY

        return MarketRegime.SIDEWAYS_RANGING

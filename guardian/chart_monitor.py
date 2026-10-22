"""
AI Trade Guardian — Real-Time Live Chart & Candlestick Profit-Taking Engine
Monitors 5-minute price action, candlestick exhaustion patterns, VWAP / 9-EMA breakdown,
and RSI overbought rollovers to take profit dynamically at the right moment
instead of waiting for clock times or arbitrary static targets.
"""

import pandas as pd
from core.logging import logger


class ChartProfitTaker:
    """Evaluates real-time 5-minute chart structure to trigger dynamic, high-conviction profit-taking."""

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calculates standard RSI for a pandas price series."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        return 100 - (100 / (1 + rs))

    @classmethod
    def evaluate_chart_profit_exit(
        cls,
        df_5m: pd.DataFrame,
        entry_price: float,
        current_ltp: float,
        highest_price_seen: float,
        require_closed_candle: bool = False,
    ) -> tuple[bool, str]:
        """
        Examines 5-minute candles to detect:
        1. Shooting Star / Severe Upper Shadow Exhaustion Wicks
        2. Breakdown below previous 5-minute candle's low (Structural Trailing Stop)
        3. Fast 9-EMA Breakdown after a profitable thrust
        4. Intraday VWAP Breakdown
        5. Bearish Engulfing Reversal Pattern
        6. RSI-14 Overbought Rollover
        """
        if df_5m is None or df_5m.empty or len(df_5m) < 3:
            return False, "Insufficient chart candles"

        # Normalize column names to lowercase
        df = df_5m.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower() for col in df.columns]
        else:
            df.columns = [col.lower() for col in df.columns]

        pnl_pct = ((current_ltp - entry_price) / entry_price) * 100.0 if entry_price > 0 else 0.0
        peak_gain_pct = ((highest_price_seen - entry_price) / entry_price) * 100.0 if entry_price > 0 else 0.0

        # Only evaluate chart-based profit exits if the position has built minimum momentum
        # (Must be up >= +0.25% currently, or had peaked at >= +0.45%)
        if pnl_pct < 0.25 and peak_gain_pct < 0.45:
            return False, "Position has not reached profit threshold for chart profit-taking"

        # Get latest candles
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]

        c = float(last_candle["close"])
        h = float(last_candle["high"])
        l = float(last_candle["low"])
        o = float(last_candle["open"])

        prev_c = float(prev_candle["close"])
        prev_h = float(prev_candle["high"])
        prev_l = float(prev_candle["low"])
        prev_o = float(prev_candle["open"])

        # -------------------------------------------------------------
        # 1. SHOOTING STAR / UPPER WICK REJECTION (Institutional Selling)
        # -------------------------------------------------------------
        # Long upper shadow >= 55% of the candle's total range at session highs
        # When require_closed_candle is True, only confirmed closed candles are accepted
        # to prevent momentary intraday wick fluctuations from prematurely killing winning trades.
        if not require_closed_candle:
            candle_range = h - l
            if candle_range > 0:
                upper_wick = h - max(o, c)
                upper_wick_ratio = upper_wick / candle_range
                # If current candle showed high upper wick rejection
                if upper_wick_ratio >= 0.55 and pnl_pct >= 0.30 and current_ltp < h:
                    return True, (
                        f"Chart Exhaustion: Shooting Star / Rejection Wick ({upper_wick_ratio*100:.0f}% upper shadow) "
                        f"at {h:.2f}. Sellers actively capping breakout. Taking profit (+{pnl_pct:.2f}%)."
                    )

        prev_range = prev_h - prev_l
        if prev_range > 0:
            prev_upper_wick = prev_h - max(prev_o, prev_c)
            prev_wick_ratio = prev_upper_wick / prev_range
            if prev_wick_ratio >= 0.60 and pnl_pct >= 0.30 and c < prev_c:
                return True, (
                    f"Chart Exhaustion: Confirmed previous candle Shooting Star ({prev_wick_ratio*100:.0f}% wick at {prev_h:.2f}). "
                    f"Price failing follow-through. Taking profit (+{pnl_pct:.2f}%)."
                )

        # -------------------------------------------------------------
        # 2. PREVIOUS 5-MIN CANDLE LOW BREAKDOWN (Structural Trailing Stop)
        # -------------------------------------------------------------
        # Once up >= +0.50%, any drop below the prior 5-minute candle's low signals a trend pause / reversal
        if peak_gain_pct >= 0.50 and current_ltp < prev_l and pnl_pct > 0.15:
            return True, (
                f"Chart Structure Break: Price ₹{current_ltp:.2f} broke below previous 5m candle low ₹{prev_l:.2f} "
                f"after reaching +{peak_gain_pct:.2f}% peak. Banking profit (+{pnl_pct:.2f}%)."
            )

        # -------------------------------------------------------------
        # 3. FAST 9-EMA BREAKDOWN (Loss of Dynamic Support)
        # -------------------------------------------------------------
        if len(df) >= 9:
            ema_9 = df["close"].ewm(span=9, adjust=False).mean()
            current_ema9 = float(ema_9.iloc[-1])
            prev_ema9 = float(ema_9.iloc[-2])
            # If price was riding above EMA-9 and now closes / trades below it while in profit
            if pnl_pct >= 0.30 and current_ltp < current_ema9 and prev_c >= prev_ema9:
                return True, (
                    f"Chart Momentum Breakdown: Price ₹{current_ltp:.2f} dropped below 5m 9-EMA (₹{current_ema9:.2f}). "
                    f"Dynamic trend support broken. Securing profit (+{pnl_pct:.2f}%)."
                )

        # -------------------------------------------------------------
        # 4. INTRADAY VWAP BREAKDOWN
        # -------------------------------------------------------------
        if "volume" in df.columns and df["volume"].sum() > 0:
            typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
            cum_vol_price = (typical_price * df["volume"]).cumsum()
            cum_vol = df["volume"].cumsum()
            vwap = cum_vol_price / cum_vol.replace(0, 1e-9)
            current_vwap = float(vwap.iloc[-1])
            if pnl_pct >= 0.30 and current_ltp < current_vwap and highest_price_seen > current_vwap:
                return True, (
                    f"Chart Trend Invalidation: Price ₹{current_ltp:.2f} crossed below Intraday VWAP (₹{current_vwap:.2f}). "
                    f"Institutional buying flow halted. Taking profit (+{pnl_pct:.2f}%)."
                )

        # -------------------------------------------------------------
        # 5. BEARISH ENGULFING CANDLE
        # -------------------------------------------------------------
        is_prev_green = prev_c > prev_o
        is_curr_red = c < o
        if is_prev_green and is_curr_red and c < prev_o and o >= prev_c and pnl_pct >= 0.30:
            return True, (
                f"Chart Reversal Pattern: 5m Bearish Engulfing candle detected. "
                f"Sellers erased previous bull bar. Securing profit (+{pnl_pct:.2f}%)."
            )

        # -------------------------------------------------------------
        # 6. RSI-14 OVERBOUGHT ROLLOVER
        # -------------------------------------------------------------
        if len(df) >= 15:
            rsi_series = cls.calculate_rsi(df["close"], period=14).dropna()
            if len(rsi_series) >= 2:
                current_rsi = float(rsi_series.iloc[-1])
                recent_max_rsi = float(rsi_series.iloc[-4:].max()) if len(rsi_series) >= 4 else current_rsi
                if recent_max_rsi >= 70.0 and (recent_max_rsi - current_rsi) >= 5.0 and pnl_pct >= 0.30:
                    return True, (
                        f"Chart Momentum Exhaustion: 5m RSI rolled over from Overbought {recent_max_rsi:.1f} to {current_rsi:.1f}. "
                        f"Bullish momentum dissipated. Banking profit (+{pnl_pct:.2f}%)."
                    )

        return False, "Chart structure intact and supportive of trend"

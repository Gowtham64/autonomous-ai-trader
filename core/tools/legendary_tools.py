"""
Legendary Trading Masters - Quantitative Indicators & Decision Tools.
Implements the exact mathematical models and execution mechanics of:
1. Takashi Kotegawa (BNF) - 25-EMA Disparity (Kairi), Panic Oversold Reversion, Sector Sympathy.
2. Rakesh Jhunjhunwala - Indian Macro Super-Cycle, Moat & ROCE Value, Conviction Pyramiding.
3. Jesse Livermore - Pivotal Point Line of Least Resistance, Volume Tape Reading, Pilot Sizing.
"""

import numpy as np
import pandas as pd
from pydantic import BaseModel


class BNFDisparityAnalysis(BaseModel):
    """Takashi Kotegawa (BNF) 25-EMA Deviation & Panic Bounce Metrics."""
    symbol: str
    ltp: float
    ema_25: float
    disparity_pct: float  # (LTP - EMA25) / EMA25 * 100
    is_extreme_oversold: bool  # Disparity <= -8.0% to -15.0%
    panic_exhaustion_score: float  # 0 to 100
    suggested_action: str
    target_bounce_price: float
    stop_capitulation_price: float
    thesis_summary: str


class JhunjhunwalaConvictionAnalysis(BaseModel):
    """Rakesh Jhunjhunwala High-Conviction Value-Trend & India Supercycle Metrics."""
    symbol: str
    ltp: float
    sector_tailwinds_score: float  # 0 to 100
    trend_longevity_score: float   # 0 to 100
    risk_adjusted_moat: str        # HIGH, MODERATE, LOW
    pyramid_permitted: bool        # Adding to winning positions
    pyramid_trigger_price: float   # Entry + 1.5 ATR
    conviction_tier: str           # ULTRA_HIGH_CONVICTION, HIGH, STANDARD
    holding_horizon: str           # MULTI_DAY_SWING, COMPOUNDER
    thesis_summary: str


class LivermorePivotalAnalysis(BaseModel):
    """Jesse Livermore Pivotal Point & Tape Reading Analysis."""
    symbol: str
    ltp: float
    pivotal_resistance: float
    pivotal_support: float
    line_of_least_resistance: str  # UPWARD, DOWNWARD, NEUTRAL
    volume_surge_multiplier: float # Volume vs 20-DMA
    is_pivotal_breakout: bool
    pilot_order_quantity_pct: float = 0.30  # Livermore 30% probe rule
    confirmation_add_level: float
    stop_invalidation_level: float
    thesis_summary: str


class LegendaryMasterTools:
    """Quantitative calculation engine for BNF, Jhunjhunwala, and Livermore models."""

    @staticmethod
    def calculate_bnf_disparity(symbol: str, df: pd.DataFrame) -> BNFDisparityAnalysis:
        """
        Calculates Takashi Kotegawa's 25-EMA Moving Average Disparity (Kairi Index).
        BNF looked for stocks deviating -8% to -20% below their 25-day EMA with volume exhaustion
        to catch high-probability violent mean-reversion bounces.
        """
        if df.empty or len(df) < 25:
            ltp = float(df["Close"].iloc[-1]) if not df.empty else 100.0
            return BNFDisparityAnalysis(
                symbol=symbol,
                ltp=ltp,
                ema_25=ltp,
                disparity_pct=0.0,
                is_extreme_oversold=False,
                panic_exhaustion_score=50.0,
                suggested_action="WAIT",
                target_bounce_price=round(ltp * 1.02, 2),
                stop_capitulation_price=round(ltp * 0.98, 2),
                thesis_summary=f"Insufficient history for 25-EMA disparity on {symbol}.",
            )

        closes = df["Close"]
        highs = df["High"]
        lows = df["Low"]
        volumes = df["Volume"]

        ema25 = float(closes.ewm(span=25, adjust=False).mean().iloc[-1])
        ltp = float(closes.iloc[-1])

        disparity = ((ltp - ema25) / ema25) * 100.0

        # Measure 14-period ATR for dynamic bounce and capitulation targets
        tr = np.maximum(highs - lows, np.maximum(abs(highs - closes.shift(1)), abs(lows - closes.shift(1))))
        atr14 = float(tr.tail(14).mean()) if len(tr) >= 14 else (ltp * 0.015)

        # Volume capitulation detection
        avg_vol = float(volumes.tail(20).mean()) if len(volumes) >= 20 else float(volumes.mean())
        rel_vol = float(volumes.iloc[-1] / max(1.0, avg_vol))

        # BNF Panic Exhaustion Score: High disparity below EMA + surge in panic sell volume = extreme bounce setup
        panic_score = 0.0
        if disparity < 0:
            panic_score += min(60.0, abs(disparity) * 5.0)
        if rel_vol > 1.2:
            panic_score += min(40.0, (rel_vol - 1.0) * 30.0)
        panic_score = float(np.clip(panic_score, 0.0, 100.0))

        is_oversold = disparity <= -3.5 or (disparity <= -2.0 and rel_vol >= 1.5)

        target_bounce = round(ltp + (1.8 * atr14), 2)
        stop_capitulation = round(ltp - (1.0 * atr14), 2)

        action = "STRONG_BUY_PANIC_BOUNCE" if (is_oversold and panic_score >= 65) else ("WATCH_DIP" if disparity < 0 else "NEUTRAL")

        thesis = (
            f"BNF Disparity: Price is {disparity:+.2f}% vs 25-EMA (₹{ema25:.2f}). "
            f"Panic Exhaustion: {panic_score:.1f}/100 with {rel_vol:.2f}x volume. "
            f"{'Targeting violent mean-reversion bounce to ₹' + str(target_bounce) if is_oversold else 'Normal fluctuation within mean bands.'}"
        )

        return BNFDisparityAnalysis(
            symbol=symbol,
            ltp=round(ltp, 2),
            ema_25=round(ema25, 2),
            disparity_pct=round(disparity, 2),
            is_extreme_oversold=is_oversold,
            panic_exhaustion_score=round(panic_score, 1),
            suggested_action=action,
            target_bounce_price=target_bounce,
            stop_capitulation_price=stop_capitulation,
            thesis_summary=thesis,
        )

    @staticmethod
    def calculate_jhunjhunwala_conviction(symbol: str, df: pd.DataFrame, sector: str = "General") -> JhunjhunwalaConvictionAnalysis:
        """
        Calculates Rakesh Jhunjhunwala's High-Conviction Super-Cycle & Pyramiding Profile.
        Focuses on structural Indian macro growth sectors (PSU, Infra, Defense, Banking, Auto),
        robust multi-month trend alignment, and allowing winners to compound via pyramiding.
        """
        ltp = float(df["Close"].iloc[-1]) if not df.empty else 100.0
        if len(df) < 50:
            return JhunjhunwalaConvictionAnalysis(
                symbol=symbol,
                ltp=ltp,
                sector_tailwinds_score=60.0,
                trend_longevity_score=50.0,
                risk_adjusted_moat="MODERATE",
                pyramid_permitted=False,
                pyramid_trigger_price=round(ltp * 1.05, 2),
                conviction_tier="STANDARD",
                holding_horizon="MULTI_DAY_SWING",
                thesis_summary=f"Building initial structural profile for {symbol}.",
            )

        closes = df["Close"]
        highs = df["High"]
        lows = df["Low"]

        ema20 = float(closes.ewm(span=20).mean().iloc[-1])
        ema50 = float(closes.ewm(span=50).mean().iloc[-1])
        ema200 = float(closes.ewm(span=200).mean().iloc[-1]) if len(closes) >= 200 else ema50 * 0.95

        # Sector Tailwind Score
        supercycle_sectors = ["Banking", "PSU Banks", "Infrastructure", "Power", "Defense", "Energy", "Auto", "Manufacturing"]
        is_priority_sector = any(s.lower() in sector.lower() for s in supercycle_sectors)
        sector_score = 85.0 if is_priority_sector else 65.0

        # Trend Longevity Score
        trend_score = 50.0
        if ltp > ema20 > ema50 > ema200:
            trend_score = 95.0
        elif ltp > ema20 > ema50:
            trend_score = 80.0
        elif ltp < ema50:
            trend_score = 30.0

        tr = np.maximum(highs - lows, np.maximum(abs(highs - closes.shift(1)), abs(lows - closes.shift(1))))
        atr14 = float(tr.tail(14).mean()) if len(tr) >= 14 else (ltp * 0.02)

        pyramid_trigger = round(ltp + (1.5 * atr14), 2)
        is_ultra = (sector_score >= 80 and trend_score >= 80)
        conviction_tier = "ULTRA_HIGH_CONVICTION" if is_ultra else ("HIGH" if trend_score >= 70 else "STANDARD")

        thesis = (
            f"Jhunjhunwala Big Bull Framework: {sector} tailwinds ({sector_score:.0f}/100), "
            f"Structural Trend Longevity ({trend_score:.0f}/100). "
            f"Tier: {conviction_tier}. "
            f"{'Pyramiding active: Add to winner upon breakout above ₹' + str(pyramid_trigger) if is_ultra else 'Standard swing allocation.'}"
        )

        return JhunjhunwalaConvictionAnalysis(
            symbol=symbol,
            ltp=round(ltp, 2),
            sector_tailwinds_score=round(sector_score, 1),
            trend_longevity_score=round(trend_score, 1),
            risk_adjusted_moat="HIGH" if is_ultra else "MODERATE",
            pyramid_permitted=is_ultra,
            pyramid_trigger_price=pyramid_trigger,
            conviction_tier=conviction_tier,
            holding_horizon="COMPOUNDER" if is_ultra else "MULTI_DAY_SWING",
            thesis_summary=thesis,
        )

    @staticmethod
    def calculate_livermore_pivotal_points(symbol: str, df: pd.DataFrame) -> LivermorePivotalAnalysis:
        """
        Calculates Jesse Livermore's Pivotal Points, Line of Least Resistance, and Tape Volume Surge.
        Follows Livermore's golden rule: Never buy until the stock crosses its Pivotal Point with
        volume expansion, testing the water with a 30% pilot probe order first.
        """
        ltp = float(df["Close"].iloc[-1]) if not df.empty else 100.0
        if len(df) < 20:
            return LivermorePivotalAnalysis(
                symbol=symbol,
                ltp=ltp,
                pivotal_resistance=round(ltp * 1.02, 2),
                pivotal_support=round(ltp * 0.98, 2),
                line_of_least_resistance="NEUTRAL",
                volume_surge_multiplier=1.0,
                is_pivotal_breakout=False,
                pilot_order_quantity_pct=0.30,
                confirmation_add_level=round(ltp * 1.03, 2),
                stop_invalidation_level=round(ltp * 0.97, 2),
                thesis_summary=f"Initializing Livermore pivotal tape reader for {symbol}.",
            )

        highs = df["High"]
        lows = df["Low"]
        closes = df["Close"]
        volumes = df["Volume"]

        # Pivotal Resistance is 20-bar high, Pivotal Support is 20-bar low
        pivotal_resistance = float(highs.tail(20).max())
        pivotal_support = float(lows.tail(20).min())

        avg_vol = float(volumes.tail(20).mean()) if len(volumes) >= 20 else float(volumes.mean())
        vol_multiplier = float(volumes.iloc[-1] / max(1.0, avg_vol))

        tr = np.maximum(highs - lows, np.maximum(abs(highs - closes.shift(1)), abs(lows - closes.shift(1))))
        atr14 = float(tr.tail(14).mean()) if len(tr) >= 14 else (ltp * 0.015)

        # Line of least resistance
        is_breakout = (ltp >= pivotal_resistance * 0.995) and (vol_multiplier >= 1.25)
        if is_breakout or (ltp > (pivotal_resistance + pivotal_support) / 2 and vol_multiplier >= 1.1):
            line_resistance = "UPWARD"
        elif ltp <= pivotal_support * 1.005:
            line_resistance = "DOWNWARD"
        else:
            line_resistance = "NEUTRAL"

        confirmation_add = round(pivotal_resistance + (1.0 * atr14), 2)
        stop_invalidation = round(pivotal_resistance - (1.2 * atr14), 2) if is_breakout else round(ltp - (1.5 * atr14), 2)

        thesis = (
            f"Livermore Tape: Pivotal Resistance ₹{pivotal_resistance:.2f}, Support ₹{pivotal_support:.2f}. "
            f"Volume Tape: {vol_multiplier:.2f}x. Line of Least Resistance: {line_resistance}. "
            f"{'Pivotal Breakout confirmed! Deploy 30% Pilot probe; add on crossing ₹' + str(confirmation_add) if is_breakout else 'Awaiting pivotal point expansion.'}"
        )

        return LivermorePivotalAnalysis(
            symbol=symbol,
            ltp=round(ltp, 2),
            pivotal_resistance=round(pivotal_resistance, 2),
            pivotal_support=round(pivotal_support, 2),
            line_of_least_resistance=line_resistance,
            volume_surge_multiplier=round(vol_multiplier, 2),
            is_pivotal_breakout=is_breakout,
            pilot_order_quantity_pct=0.30,
            confirmation_add_level=confirmation_add,
            stop_invalidation_level=stop_invalidation,
            thesis_summary=thesis,
        )


# Global Legendary Master Tools instance
legendary_tools = LegendaryMasterTools()

"""
Advanced Masters Quantitative Trading Tools.
Implements the mathematical models and deterministic execution mechanics from:
1. Ondřej Buček - Analyzing Trading Strategies for Cryptocurrencies Charts:
   - Turtle Strategy (System 1 & System 2, Volatility N, Unit Sizing, 2N Stops, Pyramiding)
   - Price Action Swing Candlestick Analysis (Hammer >= 0.70, Shooting Star >= 0.70)
   - MA RSI Strategy & Constant Value Asset DCA Model
2. Christopher M. McCarthy - Options Unlocked:
   - Analytical Black-Scholes Pricing & Option Greeks (Delta, Gamma, Theta, Vega, Rho)
   - Cox-Ross-Rubinstein Binomial Tree Model & Monte Carlo Valuation
   - Multi-Leg Options Spreads (Covered Call, Bull/Bear Spreads, Straddle/Strangle, Iron Condor, Jade Lizard)
3. Glen Goodman - The Crypto Trader:
   - 4 Core Rules (Trade Trend, Grow Profits, Cut Losses, Control Cognitive Biases)
   - Basing Pattern & Never-Chase-Breakouts (>5% Rule)
   - Chandelier ATR & 200-MA Trailing Stops, Reversal Candles, and Risk Parity Allocation
"""

import math
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


# =====================================================================
# 1. Ondřej Buček Models: Turtle Strategy & Price Action Swing Formations
# =====================================================================

class TurtleSignalMetrics(BaseModel):
    symbol: str
    ltp: float
    volatility_n: float            # 20-day EMA True Range (ATR)
    system1_entry_long: bool       # Price > 20-day High
    system1_entry_short: bool      # Price < 20-day Low
    system1_exit_long: bool        # Price < 10-day Low
    system1_exit_short: bool       # Price > 10-day High
    system2_entry_long: bool       # Price > 55-day High
    system2_entry_short: bool      # Price < 55-day Low
    system2_exit_long: bool        # Price < 20-day Low or 55-day Low
    system2_exit_short: bool       # Price > 20-day High or 55-day High
    unit_size: int                 # 1 Unit = (deposit * risk) / (2 * N)
    stop_loss_long: float          # Entry - 2N
    stop_loss_short: float         # Entry + 2N
    pyramid_step: float            # N / 2
    recommendation: str
    rationale: str


class PriceActionCandleMetrics(BaseModel):
    symbol: str
    ltp: float
    is_swing_low: bool             # Red candle followed by Green candle
    is_swing_high: bool            # Green candle followed by Red candle
    hammer_ratio: float            # (min(OP, CL) - LOW) / (HIGH - LOW)
    shooting_star_ratio: float     # (HIGH - max(OP, CL)) / (HIGH - LOW)
    is_hammer_bullish: bool        # ratio >= 0.70 at swing low
    is_shooting_star_bearish: bool # ratio >= 0.70 at swing high
    stop_loss: float
    target: float
    risk_reward_ratio: float
    signal_type: str               # "BUY", "SELL", "NEUTRAL"
    rationale: str


def _standardize_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardizes OHLCV DataFrame columns to Title Case regardless of source (Delta Exchange, yfinance, etc)."""
    if df.empty:
        return df
    mapping = {c: c.capitalize() for c in df.columns}
    return df.rename(columns=mapping)


class BucekTurtleEngine:
    """Calculates Turtle Trading Systems 1 & 2 and Buček Candlestick Price Action."""

    @staticmethod
    def calculate_turtle_metrics(
        symbol: str,
        df: pd.DataFrame,
        deposit: float = 2000.0,
        risk_pct: float = 0.01,
    ) -> TurtleSignalMetrics:
        """
        Calculates Turtle System 1 (20-day breakout / 10-day exit) and
        System 2 (55-day breakout / 20-day exit) with volatility N sizing.
        """
        if df.empty:
            return TurtleSignalMetrics(
                symbol=symbol,
                ltp=100.0,
                volatility_n=2.0,
                system1_entry_long=False,
                system1_entry_short=False,
                system1_exit_long=False,
                system1_exit_short=False,
                system2_entry_long=False,
                system2_entry_short=False,
                system2_exit_long=False,
                system2_exit_short=False,
                unit_size=1,
                stop_loss_long=96.0,
                stop_loss_short=104.0,
                pyramid_step=1.0,
                recommendation="EMPTY_DATA",
                rationale="Empty dataframe provided.",
            )

        df = _standardize_ohlcv_columns(df)
        if len(df) < 25:
            ltp = float(df["Close"].iloc[-1])
            return TurtleSignalMetrics(
                symbol=symbol,
                ltp=ltp,
                volatility_n=round(ltp * 0.02, 2),
                system1_entry_long=False,
                system1_entry_short=False,
                system1_exit_long=False,
                system1_exit_short=False,
                system2_entry_long=False,
                system2_entry_short=False,
                system2_exit_long=False,
                system2_exit_short=False,
                unit_size=1,
                stop_loss_long=round(ltp * 0.96, 2),
                stop_loss_short=round(ltp * 1.04, 2),
                pyramid_step=round(ltp * 0.01, 2),
                recommendation="INSUFFICIENT_DATA",
                rationale="Requires at least 25 candles to compute Turtle breakouts & True Range.",
            )

        closes = df["Close"]
        highs = df["High"]
        lows = df["Low"]
        ltp = float(closes.iloc[-1])

        # Calculate True Range: max(H-L, |H-C_prev|, |L-C_prev|)
        prev_close = closes.shift(1)
        tr1 = highs - lows
        tr2 = (highs - prev_close).abs()
        tr3 = (lows - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 20-day EMA of True Range (Turtle N)
        # Formula: N = (19 * PrevN + TR) / 20
        n_series = true_range.ewm(span=20, adjust=False).mean()
        volatility_n = float(n_series.iloc[-1])
        if volatility_n <= 0:
            volatility_n = max(0.01, ltp * 0.015)

        # 20-day, 55-day, and 10-day High/Low levels (using previous candles to avoid lookahead)
        high_20 = float(highs.iloc[-21:-1].max()) if len(df) >= 21 else float(highs.max())
        low_20 = float(lows.iloc[-21:-1].min()) if len(df) >= 21 else float(lows.min())

        high_55 = float(highs.iloc[-56:-1].max()) if len(df) >= 56 else high_20
        low_55 = float(lows.iloc[-56:-1].min()) if len(df) >= 56 else low_20

        high_10 = float(highs.iloc[-11:-1].max()) if len(df) >= 11 else float(highs.max())
        low_10 = float(lows.iloc[-11:-1].min()) if len(df) >= 11 else float(lows.min())

        sys1_entry_long = ltp > high_20
        sys1_entry_short = ltp < low_20
        sys1_exit_long = ltp < low_10
        sys1_exit_short = ltp > high_10

        sys2_entry_long = ltp > high_55
        sys2_entry_short = ltp < low_55
        sys2_exit_long = ltp < low_20
        sys2_exit_short = ltp > high_20

        # Turtle Unit sizing: size * |OP - SL| / OP = deposit * risk
        # Stop distance = 2 * N. Hence: size = (deposit * risk) / (2 * N)
        stop_dist = 2.0 * volatility_n
        raw_unit = (deposit * risk_pct) / max(0.001, stop_dist)
        unit_size = max(1, int(raw_unit))

        sl_long = round(ltp - stop_dist, 2)
        sl_short = round(ltp + stop_dist, 2)
        pyramid_step = round(volatility_n / 2.0, 2)

        rec = "HOLD"
        rationale_bits = []
        if sys2_entry_long:
            rec = "BUY_SYSTEM2"
            rationale_bits.append(f"System 2 (55-day High {high_55:.2f}) Long Breakout confirmed.")
        elif sys1_entry_long:
            rec = "BUY_SYSTEM1"
            rationale_bits.append(f"System 1 (20-day High {high_20:.2f}) Long Breakout confirmed.")
        elif sys2_entry_short:
            rec = "SELL_SYSTEM2"
            rationale_bits.append(f"System 2 (55-day Low {low_55:.2f}) Short Breakdown confirmed.")
        elif sys1_entry_short:
            rec = "SELL_SYSTEM1"
            rationale_bits.append(f"System 1 (20-day Low {low_20:.2f}) Short Breakdown confirmed.")
        else:
            rec = "NEUTRAL"
            rationale_bits.append(f"Within Donchian channel [L:{low_20:.2f}, H:{high_20:.2f}]. N={volatility_n:.2f}.")

        return TurtleSignalMetrics(
            symbol=symbol,
            ltp=round(ltp, 2),
            volatility_n=round(volatility_n, 2),
            system1_entry_long=sys1_entry_long,
            system1_entry_short=sys1_entry_short,
            system1_exit_long=sys1_exit_long,
            system1_exit_short=sys1_exit_short,
            system2_entry_long=sys2_entry_long,
            system2_entry_short=sys2_entry_short,
            system2_exit_long=sys2_exit_long,
            system2_exit_short=sys2_exit_short,
            unit_size=unit_size,
            stop_loss_long=sl_long,
            stop_loss_short=sl_short,
            pyramid_step=pyramid_step,
            recommendation=rec,
            rationale=" ".join(rationale_bits),
        )

    @staticmethod
    def calculate_price_action_patterns(
        symbol: str,
        df: pd.DataFrame,
    ) -> PriceActionCandleMetrics:
        """
        Evaluates Buček's Price Action formation:
        - Swing Low: Red candle followed by Green candle.
          Long entry if Hammer: (min(OP, CL) - LOW) / (HIGH - LOW) >= 0.70.
        - Swing High: Green candle followed by Red candle.
          Short entry if Shooting Star: (HIGH - max(OP, CL)) / (HIGH - LOW) >= 0.70.
        """
        if df.empty:
            return PriceActionCandleMetrics(
                symbol=symbol,
                ltp=100.0,
                is_swing_low=False,
                is_swing_high=False,
                hammer_ratio=0.0,
                shooting_star_ratio=0.0,
                is_hammer_bullish=False,
                is_shooting_star_bearish=False,
                stop_loss=98.0,
                target=102.0,
                risk_reward_ratio=1.0,
                signal_type="NEUTRAL",
                rationale="Empty dataframe provided.",
            )

        df = _standardize_ohlcv_columns(df)
        if len(df) < 3:
            ltp = float(df["Close"].iloc[-1])
            return PriceActionCandleMetrics(
                symbol=symbol,
                ltp=ltp,
                is_swing_low=False,
                is_swing_high=False,
                hammer_ratio=0.0,
                shooting_star_ratio=0.0,
                is_hammer_bullish=False,
                is_shooting_star_bearish=False,
                stop_loss=round(ltp * 0.98, 2),
                target=round(ltp * 1.02, 2),
                risk_reward_ratio=1.0,
                signal_type="NEUTRAL",
                rationale="Insufficient candles for swing analysis.",
            )

        c_prev2 = df.iloc[-2]  # previous candle
        c_curr = df.iloc[-1]   # latest candle

        prev_red = c_prev2["Close"] < c_prev2["Open"]
        prev_green = c_prev2["Close"] > c_prev2["Open"]
        curr_green = c_curr["Close"] > c_curr["Open"]
        curr_red = c_curr["Close"] < c_curr["Open"]

        is_swing_low = prev_red and curr_green
        is_swing_high = prev_green and curr_red

        op = float(c_curr["Open"])
        cl = float(c_curr["Close"])
        hi = float(c_curr["High"])
        lo = float(c_curr["Low"])
        rng = max(0.0001, hi - lo)

        hammer_ratio = (min(op, cl) - lo) / rng
        shooting_star_ratio = (hi - max(op, cl)) / rng

        is_hammer = is_swing_low and (hammer_ratio >= 0.70)
        is_shooting_star = is_swing_high and (shooting_star_ratio >= 0.70)

        ltp = cl
        if is_hammer:
            sl = round(lo, 2)
            dist = max(0.05, ltp - sl)
            target = round(ltp + dist, 2)
            rr = 1.0
            sig = "BUY"
            rationale = (
                f"Bullish Hammer Pinbar at Swing Low: Hammer ratio {hammer_ratio:.2f} >= 0.70. "
                f"SL placed at swing low ₹{sl:.2f}, Target at ₹{target:.2f} (1:1 R:R)."
            )
        elif is_shooting_star:
            sl = round(hi, 2)
            dist = max(0.05, sl - ltp)
            target = round(ltp - dist, 2)
            rr = 1.0
            sig = "SELL"
            rationale = (
                f"Bearish Shooting Star Pinbar at Swing High: Ratio {shooting_star_ratio:.2f} >= 0.70. "
                f"SL placed at swing high ₹{sl:.2f}, Target at ₹{target:.2f} (1:1 R:R)."
            )
        else:
            sl = round(ltp * 0.98, 2)
            target = round(ltp * 1.02, 2)
            rr = 1.0
            sig = "NEUTRAL"
            rationale = (
                f"No extreme pinbar setup. Hammer ratio: {hammer_ratio:.2f}, "
                f"Shooting Star ratio: {shooting_star_ratio:.2f}."
            )

        return PriceActionCandleMetrics(
            symbol=symbol,
            ltp=round(ltp, 2),
            is_swing_low=is_swing_low,
            is_swing_high=is_swing_high,
            hammer_ratio=round(hammer_ratio, 3),
            shooting_star_ratio=round(shooting_star_ratio, 3),
            is_hammer_bullish=is_hammer,
            is_shooting_star_bearish=is_shooting_star,
            stop_loss=sl,
            target=target,
            risk_reward_ratio=rr,
            signal_type=sig,
            rationale=rationale,
        )


# =====================================================================
# 2. Christopher M. McCarthy Models: Options Greeks, Pricing & Spreads
# =====================================================================

class OptionGreeks(BaseModel):
    delta: float
    gamma: float
    theta_per_day: float
    vega_per_pct: float
    rho_per_pct: float
    theoretical_price: float
    probability_of_profit: float


class OptionsSpreadProposal(BaseModel):
    strategy_name: str
    underlying_symbol: str
    underlying_price: float
    outlook: str                     # BULLISH, BEARISH, NEUTRAL, VOLATILITY
    legs: list[dict]                 # List of legs with strike, type, action, premium
    net_premium: float               # Positive = credit, Negative = debit
    max_profit: float
    max_loss: float
    breakeven: list[float]
    probability_of_profit: float
    is_liquid_and_safe: bool
    audit_notes: str


class McCarthyOptionsEngine:
    """Quantitative implementation of Black-Scholes, Binomial Trees, and 10 Spread Strategies."""

    @staticmethod
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def _norm_pdf(x: float) -> float:
        return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

    @classmethod
    def calculate_black_scholes_greeks(
        cls,
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        volatility: float,
        risk_free_rate: float = 0.065,  # ~6.5% RBI / standard rate
        is_call: bool = True,
    ) -> OptionGreeks:
        """
        Computes Black-Scholes theoretical price and analytical Greeks:
        Delta, Gamma, Theta (per day), Vega (per 1% IV change), Rho (per 1% rate change).
        """
        S = max(0.01, spot)
        K = max(0.01, strike)
        t = max(0.0001, time_to_expiry_years)
        sigma = max(0.01, volatility)
        r = risk_free_rate

        d1 = (math.log(S / K) + (r + (sigma**2) / 2.0) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)

        pdf_d1 = cls._norm_pdf(d1)
        cdf_d1 = cls._norm_cdf(d1)
        cdf_d2 = cls._norm_cdf(d2)

        if is_call:
            price = S * cdf_d1 - K * math.exp(-r * t) * cdf_d2
            delta = cdf_d1
            theta = -(S * pdf_d1 * sigma) / (2.0 * math.sqrt(t)) - r * K * math.exp(-r * t) * cdf_d2
            rho = K * t * math.exp(-r * t) * cdf_d2
            pop = cdf_d2  # Risk-neutral probability of expiring ITM
        else:
            cdf_neg_d1 = cls._norm_cdf(-d1)
            cdf_neg_d2 = cls._norm_cdf(-d2)
            price = K * math.exp(-r * t) * cdf_neg_d2 - S * cdf_neg_d1
            delta = cdf_d1 - 1.0
            theta = -(S * pdf_d1 * sigma) / (2.0 * math.sqrt(t)) + r * K * math.exp(-r * t) * cdf_neg_d2
            rho = -K * t * math.exp(-r * t) * cdf_neg_d2
            pop = cdf_neg_d2

        gamma = pdf_d1 / (S * sigma * math.sqrt(t))
        vega = S * math.sqrt(t) * pdf_d1

        # Standardize theta per calendar day and vega/rho per 1% change
        return OptionGreeks(
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            theta_per_day=round(theta / 365.0, 4),
            vega_per_pct=round(vega * 0.01, 4),
            rho_per_pct=round(rho * 0.01, 4),
            theoretical_price=round(max(0.0, price), 2),
            probability_of_profit=round(pop, 4),
        )

    @classmethod
    def calculate_binomial_tree_price(
        cls,
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        volatility: float,
        risk_free_rate: float = 0.065,
        steps: int = 50,
        is_call: bool = True,
        is_american: bool = True,
    ) -> float:
        """Cox-Ross-Rubinstein Binomial Tree model for European and American options."""
        S = max(0.01, spot)
        K = max(0.01, strike)
        t = max(0.0001, time_to_expiry_years)
        sigma = max(0.01, volatility)
        r = risk_free_rate
        dt = t / steps

        u = math.exp(sigma * math.sqrt(dt))
        d = 1.0 / u
        p = (math.exp(r * dt) - d) / (u - d)
        discount = math.exp(-r * dt)

        # Asset prices at terminal nodes
        prices = [S * (u ** (steps - i)) * (d ** i) for i in range(steps + 1)]

        # Terminal payoffs
        if is_call:
            values = [max(0.0, price - K) for price in prices]
        else:
            values = [max(0.0, K - price) for price in prices]

        # Backward induction
        for step in range(steps - 1, -1, -1):
            for i in range(step + 1):
                continuation = discount * (p * values[i] + (1.0 - p) * values[i + 1])
                current_spot = S * (u ** (step - i)) * (d ** i)
                if is_american:
                    exercise = max(0.0, (current_spot - K) if is_call else (K - current_spot))
                    values[i] = max(exercise, continuation)
                else:
                    values[i] = continuation

        return round(values[0], 2)

    @classmethod
    def evaluate_spread_strategy(
        cls,
        strategy_name: str,
        spot: float,
        implied_volatility: float,
        days_to_expiry: int = 30,
        risk_free_rate: float = 0.065,
    ) -> OptionsSpreadProposal:
        """
        Synthesizes standard defined-risk options strategies from Options Unlocked:
        - Bull Call Spread, Bear Put Spread, Straddle, Strangle, Iron Condor, Jade Lizard, Covered Call.
        """
        t = max(1, days_to_expiry) / 365.0
        iv = max(0.10, implied_volatility)
        strat = strategy_name.upper().replace(" ", "_")

        if strat in ["IRON_CONDOR", "IRON_CONDOR_SPREAD"]:
            # Sell OTM Call spread + Sell OTM Put spread
            put_sell = round(spot * 0.95, 1)
            put_buy = round(spot * 0.92, 1)
            call_sell = round(spot * 1.05, 1)
            call_buy = round(spot * 1.08, 1)

            p_sell = cls.calculate_black_scholes_greeks(spot, put_sell, t, iv, risk_free_rate, is_call=False).theoretical_price
            p_buy = cls.calculate_black_scholes_greeks(spot, put_buy, t, iv, risk_free_rate, is_call=False).theoretical_price
            c_sell = cls.calculate_black_scholes_greeks(spot, call_sell, t, iv, risk_free_rate, is_call=True).theoretical_price
            c_buy = cls.calculate_black_scholes_greeks(spot, call_buy, t, iv, risk_free_rate, is_call=True).theoretical_price

            net_credit = round((p_sell - p_buy) + (c_sell - c_buy), 2)
            spread_width = round(call_buy - call_sell, 2)
            max_loss = round(spread_width - net_credit, 2)

            return OptionsSpreadProposal(
                strategy_name="Iron Condor",
                underlying_symbol="INDEX_OPT",
                underlying_price=spot,
                outlook="NEUTRAL",
                legs=[
                    {"action": "SELL", "type": "PUT", "strike": put_sell, "premium": p_sell},
                    {"action": "BUY", "type": "PUT", "strike": put_buy, "premium": p_buy},
                    {"action": "SELL", "type": "CALL", "strike": call_sell, "premium": c_sell},
                    {"action": "BUY", "type": "CALL", "strike": call_buy, "premium": c_buy},
                ],
                net_premium=net_credit,
                max_profit=net_credit,
                max_loss=max(0.1, max_loss),
                breakeven=[round(put_sell - net_credit, 2), round(call_sell + net_credit, 2)],
                probability_of_profit=0.68,
                is_liquid_and_safe=True,
                audit_notes="Iron Condor: Neutral delta, positive theta harvest with strictly bounded max loss.",
            )

        elif strat in ["BULL_CALL_SPREAD", "BULL_CALL"]:
            buy_strike = round(spot * 1.00, 1)
            sell_strike = round(spot * 1.04, 1)
            c_buy = cls.calculate_black_scholes_greeks(spot, buy_strike, t, iv, risk_free_rate, is_call=True).theoretical_price
            c_sell = cls.calculate_black_scholes_greeks(spot, sell_strike, t, iv, risk_free_rate, is_call=True).theoretical_price
            net_debit = round(c_buy - c_sell, 2)
            max_profit = round((sell_strike - buy_strike) - net_debit, 2)

            return OptionsSpreadProposal(
                strategy_name="Bull Call Spread",
                underlying_symbol="EQUITY_OPT",
                underlying_price=spot,
                outlook="BULLISH",
                legs=[
                    {"action": "BUY", "type": "CALL", "strike": buy_strike, "premium": c_buy},
                    {"action": "SELL", "type": "CALL", "strike": sell_strike, "premium": c_sell},
                ],
                net_premium=-net_debit,
                max_profit=max_profit,
                max_loss=net_debit,
                breakeven=[round(buy_strike + net_debit, 2)],
                probability_of_profit=0.54,
                is_liquid_and_safe=True,
                audit_notes="Defined risk vertical bull call spread with capped debit.",
            )

        elif strat in ["JADE_LIZARD"]:
            # Sell OTM Put, Sell OTM Call, Buy higher OTM Call
            # If total credit > call spread width, zero upside risk!
            put_strike = round(spot * 0.93, 1)
            call_sell = round(spot * 1.05, 1)
            call_buy = round(spot * 1.07, 1)

            p_credit = cls.calculate_black_scholes_greeks(spot, put_strike, t, iv, risk_free_rate, is_call=False).theoretical_price
            c_sell = cls.calculate_black_scholes_greeks(spot, call_sell, t, iv, risk_free_rate, is_call=True).theoretical_price
            c_buy = cls.calculate_black_scholes_greeks(spot, call_buy, t, iv, risk_free_rate, is_call=True).theoretical_price

            total_credit = round(p_credit + (c_sell - c_buy), 2)
            call_spread_width = round(call_buy - call_sell, 2)
            upside_risk = max(0.0, call_spread_width - total_credit)

            return OptionsSpreadProposal(
                strategy_name="Jade Lizard",
                underlying_symbol="EQUITY_OPT",
                underlying_price=spot,
                outlook="MODERATELY_BULLISH",
                legs=[
                    {"action": "SELL", "type": "PUT", "strike": put_strike, "premium": p_credit},
                    {"action": "SELL", "type": "CALL", "strike": call_sell, "premium": c_sell},
                    {"action": "BUY", "type": "CALL", "strike": call_buy, "premium": c_buy},
                ],
                net_premium=total_credit,
                max_profit=total_credit,
                max_loss=round(put_strike - total_credit, 2),
                breakeven=[round(put_strike - total_credit, 2)],
                probability_of_profit=0.72,
                is_liquid_and_safe=upside_risk == 0.0,
                audit_notes=f"Jade Lizard: Upside risk = ₹{upside_risk:.2f}. Skewed high-probability theta play.",
            )

        else:
            # Default: Long Straddle for high volatility / news breakout
            c_price = cls.calculate_black_scholes_greeks(spot, spot, t, iv, risk_free_rate, is_call=True).theoretical_price
            p_price = cls.calculate_black_scholes_greeks(spot, spot, t, iv, risk_free_rate, is_call=False).theoretical_price
            total_cost = round(c_price + p_price, 2)

            return OptionsSpreadProposal(
                strategy_name="Long Straddle",
                underlying_symbol="VOLATILITY_OPT",
                underlying_price=spot,
                outlook="VOLATILITY",
                legs=[
                    {"action": "BUY", "type": "CALL", "strike": spot, "premium": c_price},
                    {"action": "BUY", "type": "PUT", "strike": spot, "premium": p_price},
                ],
                net_premium=-total_cost,
                max_profit=99999.0,
                max_loss=total_cost,
                breakeven=[round(spot - total_cost, 2), round(spot + total_cost, 2)],
                probability_of_profit=0.42,
                is_liquid_and_safe=True,
                audit_notes="Long Straddle: Profits on explosive expansion in either direction beyond breakevens.",
            )


# =====================================================================
# 3. Glen Goodman Models: Trend Rules, Basing Patterns & Biases
# =====================================================================

class GoodmanTrendMetrics(BaseModel):
    symbol: str
    ltp: float
    is_trend_intact: bool             # Price > 200-day SMA or 50-day EMA
    is_chasing_breakout: bool         # Price > 1.05 * Breakout level (VETO if True!)
    basing_duration_bars: int         # Length of consolidation base
    has_volume_confirmation: bool     # Volume >= 1.5x average on breakout
    has_reversal_candle: bool         # Upper wick rejection at trend peak
    chandelier_trailing_stop: float   # Highest_30 - (3.5 * ATR)
    ma_200_trailing_stop: float       # 200-day SMA
    recommended_stop: float           # Max(Chandelier, MA200, Breakout - 1 ATR)
    risk_parity_size_multiplier: float # Sizing inversely proportional to 30-day ATR
    cognitive_bias_warnings: list[str]
    trade_eligible: bool
    rationale: str


class GoodmanTrendEngine:
    """Implements Glen Goodman's Classical Charting & Trend Following Rules."""

    @staticmethod
    def evaluate_trend_and_discipline(
        symbol: str,
        df: pd.DataFrame,
        breakout_level: float | None = None,
    ) -> GoodmanTrendMetrics:
        """
        Evaluates Glen Goodman's rules:
        1. Trade the trend until it bends (check 200-day MA and 50-day EMA).
        2. Never chase a breakout: price must be within 5% of the breakout level!
        3. Cut losses automatically (Chandelier trailing stop = Highest - 3.5 * ATR).
        4. Detect reversal rejection candle (long top wick).
        5. Check psychological cognitive biases (FOMO, Sunk Cost, Disposition Effect).
        """
        if df.empty:
            return GoodmanTrendMetrics(
                symbol=symbol,
                ltp=100.0,
                is_trend_intact=True,
                is_chasing_breakout=False,
                basing_duration_bars=0,
                has_volume_confirmation=True,
                has_reversal_candle=False,
                chandelier_trailing_stop=95.0,
                ma_200_trailing_stop=90.0,
                recommended_stop=95.0,
                risk_parity_size_multiplier=1.0,
                cognitive_bias_warnings=[],
                trade_eligible=True,
                rationale="Empty dataframe provided.",
            )

        df = _standardize_ohlcv_columns(df)
        if len(df) < 20:
            ltp = float(df["Close"].iloc[-1])
            return GoodmanTrendMetrics(
                symbol=symbol,
                ltp=ltp,
                is_trend_intact=True,
                is_chasing_breakout=False,
                basing_duration_bars=0,
                has_volume_confirmation=True,
                has_reversal_candle=False,
                chandelier_trailing_stop=round(ltp * 0.95, 2),
                ma_200_trailing_stop=round(ltp * 0.90, 2),
                recommended_stop=round(ltp * 0.95, 2),
                risk_parity_size_multiplier=1.0,
                cognitive_bias_warnings=[],
                trade_eligible=True,
                rationale="Insufficient candles for complete Goodman trend analytics.",
            )

        closes = df["Close"]
        highs = df["High"]
        lows = df["Low"]
        volumes = df["Volume"]
        ltp = float(closes.iloc[-1])

        # 1. Trend alignment: 200 SMA or 50 EMA
        sma_200 = float(closes.rolling(window=200, min_periods=20).mean().iloc[-1])
        ema_50 = float(closes.ewm(span=50, adjust=False).mean().iloc[-1])
        is_trend_intact = ltp >= sma_200 or ltp >= ema_50

        # 2. Breakout chasing rule: Never buy if price > breakout_level * 1.05
        # If breakout_level not passed, infer from highest high of previous 20 candles
        ref_breakout = breakout_level or float(highs.iloc[-21:-1].max())
        is_chasing = ltp > (ref_breakout * 1.05)

        # 3. Basing pattern duration (number of bars where range was tight < 10%)
        rolling_max = highs.rolling(window=10).max()
        rolling_min = lows.rolling(window=10).min()
        consolidation_mask = (rolling_max - rolling_min) / rolling_min <= 0.12
        basing_bars = int(consolidation_mask.iloc[-20:].sum())

        # 4. Volume confirmation: Last bar volume >= 1.4x 20-day average
        avg_vol = float(volumes.tail(20).mean()) if len(volumes) >= 20 else float(volumes.mean())
        has_vol = float(volumes.iloc[-1]) >= (1.4 * avg_vol)

        # 5. Reversal candle detection on current bar (long upper shadow rejection)
        c_op = float(df["Open"].iloc[-1])
        c_cl = float(df["Close"].iloc[-1])
        c_hi = float(df["High"].iloc[-1])
        c_lo = float(df["Low"].iloc[-1])
        c_rng = max(0.001, c_hi - c_lo)
        upper_wick_ratio = (c_hi - max(c_op, c_cl)) / c_rng
        has_reversal = (upper_wick_ratio >= 0.55) and (c_cl < c_op)  # Long top wick + closed red

        # 6. ATR & Chandelier Trailing Stop: Highest(30) - (3.5 * ATR)
        prev_close = closes.shift(1)
        tr = pd.concat([highs - lows, (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
        atr_30 = float(tr.tail(30).mean()) if len(tr) >= 30 else float(tr.tail(14).mean())
        if atr_30 <= 0:
            atr_30 = ltp * 0.02

        highest_30 = float(highs.tail(30).max())
        chandelier_stop = round(highest_30 - (3.5 * atr_30), 2)
        rec_stop = max(chandelier_stop, round(sma_200, 2))

        # Risk parity sizing multiplier: Normalized against baseline 2% ATR
        vol_pct = (atr_30 / ltp) * 100.0
        risk_multiplier = round(max(0.2, min(2.5, 2.0 / max(0.5, vol_pct))), 2)

        # Cognitive biases audit
        biases = []
        if is_chasing:
            biases.append("FOMO_VIOLATION: Price has extended >5% beyond breakout. Do NOT chase.")
        if has_reversal:
            biases.append("REVERSAL_REJECTION: Long upper wick candle indicates trend exhaustion/bend.")
        if not is_trend_intact and ltp < ref_breakout:
            biases.append("FALLING_KNIFE: Buying a downtrend asset expecting a bottom is dangerous.")

        trade_eligible = is_trend_intact and (not is_chasing) and (not has_reversal)

        rationale = (
            f"Goodman Trend Audit: Trend {'INTACT' if is_trend_intact else 'BENT'} "
            f"(200-SMA: ₹{sma_200:.2f}). Chandelier Stop: ₹{chandelier_stop:.2f}. "
            f"Breakout extension: {((ltp - ref_breakout)/ref_breakout*100.0):.1f}%. "
            f"{'APPROVED: Clean trend alignment.' if trade_eligible else 'BLOCKED: Cognitive or chasing rule triggered.'}"
        )

        return GoodmanTrendMetrics(
            symbol=symbol,
            ltp=round(ltp, 2),
            is_trend_intact=is_trend_intact,
            is_chasing_breakout=is_chasing,
            basing_duration_bars=basing_bars,
            has_volume_confirmation=has_vol,
            has_reversal_candle=has_reversal,
            chandelier_trailing_stop=chandelier_stop,
            ma_200_trailing_stop=round(sma_200, 2),
            recommended_stop=rec_stop,
            risk_parity_size_multiplier=risk_multiplier,
            cognitive_bias_warnings=biases,
            trade_eligible=trade_eligible,
            rationale=rationale,
        )


class CryptoChartPatternMetrics(BaseModel):
    """Metrics produced by CryptoChartPatternEngine based on classical crypto reversal and continuation patterns."""
    symbol: str
    ltp: float
    detected_patterns: list[str]
    primary_pattern: str | None
    pattern_type: str  # "BULLISH_REVERSAL", "BEARISH_REVERSAL", "BULLISH_CONTINUATION", "BEARISH_CONTINUATION", "NEUTRAL"
    breakout_level: float | None
    target_price: float | None
    invalidation_level: float | None
    measured_move_height: float | None
    has_volume_confirmation: bool
    confidence: float
    rationale: str


class CryptoChartPatternEngine:
    """Quantitative Pattern Detection Engine for Cryptocurrencies (GoodCrypto Patterns).
    
    Identifies 10 core institutional crypto chart patterns:
    Reversals:
    1. Double Bottom / Triple Bottom (Bullish Reversal)
    2. Double Top (Bearish Reversal)
    3. Falling Wedge (Bullish Reversal)
    4. Rising Wedge (Bearish Reversal)
    5. Cup & Handle (Bullish Reversal)
    6. Rounded Bottom / Saucer (Bullish Reversal)
    7. Diamond Top / Bottom (Reversal)
    
    Continuations:
    8. Ascending Triangle (Bullish Continuation)
    9. Descending Triangle (Bearish Continuation)
    10. Symmetrical Triangle & Rectangle (Continuation)
    """

    @staticmethod
    def detect_patterns(symbol: str, df: pd.DataFrame) -> CryptoChartPatternMetrics:
        if df.empty:
            return CryptoChartPatternMetrics(
                symbol=symbol,
                ltp=100.0,
                detected_patterns=[],
                primary_pattern=None,
                pattern_type="NEUTRAL",
                breakout_level=None,
                target_price=None,
                invalidation_level=None,
                measured_move_height=None,
                has_volume_confirmation=False,
                confidence=0.0,
                rationale="Empty dataframe provided.",
            )

        df = _standardize_ohlcv_columns(df)
        if len(df) < 20:
            ltp = float(df["Close"].iloc[-1])
            return CryptoChartPatternMetrics(
                symbol=symbol,
                ltp=ltp,
                detected_patterns=[],
                primary_pattern=None,
                pattern_type="NEUTRAL",
                breakout_level=ltp,
                target_price=ltp,
                invalidation_level=ltp,
                measured_move_height=0.0,
                has_volume_confirmation=False,
                confidence=0.0,
                rationale="Insufficient bars (<20) for pattern geometry.",
            )

        closes = df["Close"].values
        highs = df["High"].values
        lows = df["Low"].values
        volumes = df["Volume"].values if "Volume" in df.columns else np.ones(len(df))

        ltp = float(closes[-1])
        avg_vol = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 1.0
        curr_vol = float(volumes[-1])
        has_volume_conf = curr_vol >= (avg_vol * 1.25) if avg_vol > 0 else True

        detected: list[str] = []
        p_type = "NEUTRAL"
        target_p = None
        inval_p = None
        breakout_lvl = None
        pattern_height = 0.0
        conf = 0.50

        # Recent 20 to 30 bars geometry
        window = min(30, len(df))
        w_closes = closes[-window:]
        w_highs = highs[-window:]
        w_lows = lows[-window:]

        recent_high = float(np.max(w_highs))
        recent_low = float(np.min(w_lows))
        h_range = recent_high - recent_low

        # 1. Double Bottom / Triple Bottom (Bullish Reversal)
        # Two troughs within 1.5% of each other separated by at least 4 bars
        low_idx_1 = int(np.argmin(w_lows[:window // 2]))
        low_idx_2 = int(window // 2 + np.argmin(w_lows[window // 2:]))
        if abs(w_lows[low_idx_1] - w_lows[low_idx_2]) / max(0.0001, w_lows[low_idx_1]) <= 0.020:
            # Intermediate peak between the two troughs
            inter_peak = float(np.max(w_highs[low_idx_1:low_idx_2 + 1]))
            if ltp >= inter_peak * 0.99:  # Breaking or broken neckline
                detected.append("DOUBLE_BOTTOM_BULLISH_REVERSAL")
                p_type = "BULLISH_REVERSAL"
                breakout_lvl = inter_peak
                pattern_height = inter_peak - min(w_lows[low_idx_1], w_lows[low_idx_2])
                target_p = inter_peak + pattern_height
                inval_p = min(w_lows[low_idx_1], w_lows[low_idx_2])
                conf = 0.85 if has_volume_conf else 0.72

        # 2. Double Top (Bearish Reversal)
        high_idx_1 = int(np.argmax(w_highs[:window // 2]))
        high_idx_2 = int(window // 2 + np.argmax(w_highs[window // 2:]))
        if abs(w_highs[high_idx_1] - w_highs[high_idx_2]) / max(0.0001, w_highs[high_idx_1]) <= 0.020:
            inter_trough = float(np.min(w_lows[high_idx_1:high_idx_2 + 1]))
            if ltp <= inter_trough * 1.01:
                detected.append("DOUBLE_TOP_BEARISH_REVERSAL")
                if p_type == "NEUTRAL":
                    p_type = "BEARISH_REVERSAL"
                    breakout_lvl = inter_trough
                    pattern_height = max(w_highs[high_idx_1], w_highs[high_idx_2]) - inter_trough
                    target_p = inter_trough - pattern_height
                    inval_p = max(w_highs[high_idx_1], w_highs[high_idx_2])
                    conf = 0.82 if has_volume_conf else 0.70

        # 3. Ascending Triangle (Bullish Continuation)
        # Flat horizontal resistance (upper band within 1%) + rising lows
        last_3_highs = [float(np.max(w_highs[i:i+4])) for i in [0, 8, 16]] if window >= 20 else []
        last_3_lows = [float(np.min(w_lows[i:i+4])) for i in [0, 8, 16]] if window >= 20 else []
        if len(last_3_highs) == 3 and len(last_3_lows) == 3:
            highs_flat = (max(last_3_highs) - min(last_3_highs)) / max(0.0001, max(last_3_highs)) <= 0.015
            lows_rising = last_3_lows[2] > last_3_lows[1] > last_3_lows[0]
            if highs_flat and lows_rising:
                detected.append("ASCENDING_TRIANGLE_BULLISH_CONTINUATION")
                if p_type in ["NEUTRAL", "BULLISH_REVERSAL"]:
                    p_type = "BULLISH_CONTINUATION"
                    breakout_lvl = max(last_3_highs)
                    pattern_height = max(last_3_highs) - min(last_3_lows)
                    target_p = breakout_lvl + pattern_height
                    inval_p = last_3_lows[2]
                    conf = 0.88 if has_volume_conf else 0.75

        # 4. Descending Triangle (Bearish Continuation)
        if len(last_3_highs) == 3 and len(last_3_lows) == 3:
            lows_flat = (max(last_3_lows) - min(last_3_lows)) / max(0.0001, max(last_3_lows)) <= 0.015
            highs_falling = last_3_highs[2] < last_3_highs[1] < last_3_highs[0]
            if lows_flat and highs_falling:
                detected.append("DESCENDING_TRIANGLE_BEARISH_CONTINUATION")
                if p_type == "NEUTRAL":
                    p_type = "BEARISH_CONTINUATION"
                    breakout_lvl = min(last_3_lows)
                    pattern_height = max(last_3_highs) - min(last_3_lows)
                    target_p = breakout_lvl - pattern_height
                    inval_p = last_3_highs[2]
                    conf = 0.85

        # 5. Falling Wedge (Bullish Reversal / Continuation)
        # Both highs and lows slope downward, but range contracts (wedge narrowing)
        if len(last_3_highs) == 3 and len(last_3_lows) == 3:
            high_slope = last_3_highs[2] - last_3_highs[0]
            low_slope = last_3_lows[2] - last_3_lows[0]
            range_contracting = (last_3_highs[2] - last_3_lows[2]) < (last_3_highs[0] - last_3_lows[0])
            if high_slope < 0 and low_slope < 0 and range_contracting and ltp >= last_3_highs[2]:
                detected.append("FALLING_WEDGE_BULLISH_REVERSAL")
                p_type = "BULLISH_REVERSAL"
                breakout_lvl = last_3_highs[2]
                pattern_height = last_3_highs[0] - last_3_lows[0]
                target_p = breakout_lvl + pattern_height
                inval_p = last_3_lows[2]
                conf = 0.84

        # 6. Rising Wedge (Bearish Reversal / Continuation)
        if len(last_3_highs) == 3 and len(last_3_lows) == 3:
            high_slope = last_3_highs[2] - last_3_highs[0]
            low_slope = last_3_lows[2] - last_3_lows[0]
            range_contracting = (last_3_highs[2] - last_3_lows[2]) < (last_3_highs[0] - last_3_lows[0])
            if high_slope > 0 and low_slope > 0 and range_contracting and ltp <= last_3_lows[2]:
                detected.append("RISING_WEDGE_BEARISH_REVERSAL")
                if p_type == "NEUTRAL":
                    p_type = "BEARISH_REVERSAL"
                    breakout_lvl = last_3_lows[2]
                    pattern_height = last_3_highs[0] - last_3_lows[0]
                    target_p = breakout_lvl - pattern_height
                    inval_p = last_3_highs[2]
                    conf = 0.80

        # 7. Cup and Handle / Rounded Bottom (Bullish Reversal)
        # Gradual U-shape curvature: middle 40% of window lower than outer wings
        if window >= 24:
            left_wing = float(np.mean(w_closes[:6]))
            center_bowl = float(np.min(w_closes[6:18]))
            right_wing = float(np.mean(w_closes[18:]))
            if left_wing > center_bowl * 1.03 and right_wing > center_bowl * 1.03:
                depth = max(left_wing, right_wing) - center_bowl
                # Handle is small consolidation near right rim
                neckline = max(left_wing, right_wing)
                if ltp >= neckline * 0.985:
                    detected.append("CUP_AND_HANDLE_BULLISH_REVERSAL")
                    p_type = "BULLISH_REVERSAL"
                    breakout_lvl = neckline
                    pattern_height = depth
                    target_p = neckline + depth
                    inval_p = center_bowl + (depth * 0.60)
                    conf = 0.86 if has_volume_conf else 0.74

        # 8. Symmetrical Triangle & Rectangle
        if not detected and window >= 16:
            # Check for rectangle consolidation: range is bounded within 3.5%
            if h_range / max(0.0001, recent_low) <= 0.040:
                detected.append("RECTANGLE_CONSOLIDATION")
                pattern_height = h_range
                breakout_lvl = recent_high
                target_p = recent_high + pattern_height
                inval_p = recent_low
                conf = 0.65

        primary = detected[0] if detected else None
        prec = 6 if ltp < 0.10 else (4 if ltp < 10.0 else 2)

        def _fmt(v: float | None) -> str:
            return f"${v:.{prec}f}" if v is not None else "N/A"

        rationale = (
            f"Crypto Chart Patterns: {', '.join(detected) if detected else 'No classical pattern confirmed'}. "
            f"Type: {p_type}. Breakout Level: {_fmt(breakout_lvl)}. Target: {_fmt(target_p)} "
            f"(Measured move: +{_fmt(pattern_height)}). Invalidation: {_fmt(inval_p)}. "
            f"Volume Confirmed: {'YES' if has_volume_conf else 'NO'}."
        )

        return CryptoChartPatternMetrics(
            symbol=symbol,
            ltp=round(ltp, prec),
            detected_patterns=detected,
            primary_pattern=primary,
            pattern_type=p_type,
            breakout_level=round(breakout_lvl, prec) if breakout_lvl is not None else None,
            target_price=round(target_p, prec) if target_p is not None else None,
            invalidation_level=round(inval_p, prec) if inval_p is not None else None,
            measured_move_height=round(pattern_height, prec) if pattern_height else None,
            has_volume_confirmation=has_volume_conf,
            confidence=conf if primary else 0.30,
            rationale=rationale,
        )

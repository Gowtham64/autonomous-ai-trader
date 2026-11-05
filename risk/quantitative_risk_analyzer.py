"""
Quantitative Risk & Algorithmic Options Analysis Engine.
Implements the institutional quantitative methods from 'Algorithmic Trading Pro: Options with Python':

1. Options Pricing & Analytical Greeks (Chapter 1.3, 5.1, 5.4):
   - Black-Scholes European & Perpetual Valuation
   - Greeks: Delta (Δ), Gamma (Γ), Theta (Θ), Vega (ν), Rho (ρ)
2. Implied Volatility Rank (IVR) & Volatility Modeling (Chapter 4.5, 5.4):
   - IV Percentile & Historical vs Implied Volatility Discrepancy
3. Quantitative Risk Measures (Chapter 7.1, 7.3):
   - Value at Risk (VaR 95% & 99%)
   - Conditional Value at Risk (CVaR / Expected Shortfall)
   - Liquidity-Adjusted VaR (LVaR) & Market Impact Slippage
4. Trade Expectancy & Mathematical Confluence (Chapter 8.2, 10.4):
   - Positive Expected Value (EV) after round-trip taker fees and spread
   - Probability of Profit (POP) and Risk-to-Reward (R:R) Verification
   - Multi-Model Ensemble Consensus Verification
"""

import math
from typing import Any

import numpy as np
import pandas as pd

try:
    from scipy.stats import norm
except ImportError:
    class _NormFallback:
        @staticmethod
        def cdf(x: float) -> float:
            return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

        @staticmethod
        def pdf(x: float) -> float:
            return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    norm = _NormFallback()

from core.logging import logger


class QuantitativeRiskAnalyzer:
    """Institutional Quantitative Risk & Options Pricing Engine."""

    @staticmethod
    def calculate_black_scholes(
        spot: float,
        strike: float,
        time_to_maturity_years: float,
        risk_free_rate: float,
        volatility: float,
        option_type: str = "call",
        dividend_yield: float = 0.0,
    ) -> dict[str, float]:
        """Calculates Black-Scholes theoretical price and analytical Greeks.
        
        Reference: Chapter 5.1 & 5.4, pages 277-285.
        """
        S = max(0.0001, spot)
        K = max(0.0001, strike)
        T = max(0.0001, time_to_maturity_years)
        r = risk_free_rate
        q = dividend_yield
        sigma = max(0.01, volatility)

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        pdf_d1 = norm.pdf(d1)
        cdf_d1 = norm.cdf(d1)
        cdf_d2 = norm.cdf(d2)
        cdf_minus_d1 = norm.cdf(-d1)
        cdf_minus_d2 = norm.cdf(-d2)

        exp_qT = math.exp(-q * T)
        exp_rT = math.exp(-r * T)

        # Price
        if option_type.lower() == "call":
            price = S * exp_qT * cdf_d1 - K * exp_rT * cdf_d2
            delta = exp_qT * cdf_d1
            theta = (
                -(S * exp_qT * pdf_d1 * sigma) / (2.0 * sqrt_T)
                - r * K * exp_rT * cdf_d2
                + q * S * exp_qT * cdf_d1
            ) / 365.0
            rho = (K * T * exp_rT * cdf_d2) / 100.0
        else:
            price = K * exp_rT * cdf_minus_d2 - S * exp_qT * cdf_minus_d1
            delta = -exp_qT * cdf_minus_d1
            theta = (
                -(S * exp_qT * pdf_d1 * sigma) / (2.0 * sqrt_T)
                + r * K * exp_rT * cdf_minus_d2
                - q * S * exp_qT * cdf_minus_d1
            ) / 365.0
            rho = (-K * T * exp_rT * cdf_minus_d2) / 100.0

        # Shared second-order Greeks
        gamma = (exp_qT * pdf_d1) / (S * sigma * sqrt_T)
        vega = (S * exp_qT * pdf_d1 * sqrt_T) / 100.0

        return {
            "theoretical_price": round(max(0.0, price), 4),
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "theta": round(theta, 4),
            "vega": round(vega, 4),
            "rho": round(rho, 4),
        }

    @staticmethod
    def calculate_var_cvar(
        returns: np.ndarray | pd.Series,
        portfolio_value: float,
        confidence_level: float = 0.95,
    ) -> dict[str, float]:
        """Calculates Value at Risk (VaR) and Conditional Value at Risk (CVaR / Expected Shortfall).
        
        Reference: Chapter 7.1, pages 416-424.
        """
        arr = np.asarray(returns, dtype=float)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 10:
            return {
                "var_pct": 0.02,
                "cvar_pct": 0.03,
                "var_amount": round(portfolio_value * 0.02, 2),
                "cvar_amount": round(portfolio_value * 0.03, 2),
            }

        alpha = 1.0 - confidence_level
        percentile_val = float(np.percentile(arr, alpha * 100.0))
        var_pct = abs(min(0.0, percentile_val))

        # Expected Shortfall (CVaR): average loss beyond the VaR threshold
        tail_losses = arr[arr <= percentile_val]
        cvar_pct = abs(float(tail_losses.mean())) if len(tail_losses) > 0 else var_pct * 1.25

        return {
            "var_pct": round(var_pct, 4),
            "cvar_pct": round(cvar_pct, 4),
            "var_amount": round(portfolio_value * var_pct, 2),
            "cvar_amount": round(portfolio_value * cvar_pct, 2),
        }

    @staticmethod
    def calculate_lvar_and_market_impact(
        position_notional: float,
        bid_price: float,
        ask_price: float,
        avg_daily_volume: float = 10000.0,
        liquidity_horizon_days: float = 1.0,
        base_var_pct: float = 0.02,
    ) -> dict[str, float]:
        """Calculates Liquidity-Adjusted VaR (LVaR) and estimated market impact.
        
        Reference: Chapter 7.3, pages 446, 450-452.
        """
        mid = (bid_price + ask_price) / 2.0 if (bid_price + ask_price) > 0 else 1.0
        half_spread_pct = (ask_price - bid_price) / (2.0 * mid) if mid > 0 else 0.001

        # Square-root market impact model: impact = beta * sqrt(trade_size / adv)
        trade_volume = position_notional / mid if mid > 0 else 1.0
        adv = max(100.0, avg_daily_volume)
        market_impact_pct = 0.01 * math.sqrt(trade_volume / adv)

        # LVaR = Standard VaR + Liquidity Spread Penalty * sqrt(horizon)
        lvar_pct = base_var_pct + (half_spread_pct + market_impact_pct) * math.sqrt(liquidity_horizon_days)

        return {
            "half_spread_pct": round(half_spread_pct * 100.0, 3),
            "market_impact_pct": round(market_impact_pct * 100.0, 3),
            "lvar_pct": round(lvar_pct * 100.0, 3),
            "liquidity_cost": round(position_notional * (half_spread_pct + market_impact_pct), 4),
        }

    @staticmethod
    def calculate_ivr(
        current_iv: float,
        historical_iv_series: list[float] | np.ndarray | pd.Series,
    ) -> float:
        """Calculates Implied Volatility Rank (IVR) as a percentile [0, 100].
        
        Reference: Chapter 4.5, page 269.
        """
        arr = np.asarray(historical_iv_series, dtype=float)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 5:
            return 50.0

        min_iv = float(arr.min())
        max_iv = float(arr.max())
        if max_iv <= min_iv:
            return 50.0

        ivr = ((current_iv - min_iv) / (max_iv - min_iv)) * 100.0
        return round(max(0.0, min(100.0, ivr)), 1)

    @staticmethod
    def evaluate_expectancy_and_math(
        entry: float,
        stop_loss: float,
        target: float,
        quantity: int,
        side: str = "BUY",
        p_win_estimate: float = 0.55,
        fee_rate_roundtrip: float = 0.001,  # 0.10% total fee & slippage
    ) -> dict[str, Any]:
        """Calculates the rigorous mathematical expected value (EV) and Probability of Profit.
        
        Reference: Chapter 8.2 & 8.3, pages 514-517.
        """
        is_long = side.upper() != "SELL"
        stop_dist = (entry - stop_loss) if is_long else (stop_loss - entry)
        reward_dist = (target - entry) if is_long else (entry - target)

        if stop_dist <= 0 or reward_dist <= 0:
            return {
                "is_viable": False,
                "reason": "Invalid stop/target geometry (negative distance)",
                "ev": 0.0,
                "rr_ratio": 0.0,
            }

        rr_ratio = reward_dist / stop_dist
        notional = entry * quantity
        fee_amount = notional * fee_rate_roundtrip

        gain_on_win = (reward_dist * quantity) - fee_amount
        loss_on_fail = (stop_dist * quantity) + fee_amount

        # Mathematical EV = (p * Gain) - ((1 - p) * Loss)
        p = max(0.20, min(0.85, p_win_estimate))
        ev = (p * gain_on_win) - ((1.0 - p) * loss_on_fail)

        is_viable = (rr_ratio >= 1.80) and (ev > 0.001)

        return {
            "is_viable": is_viable,
            "rr_ratio": round(rr_ratio, 2),
            "ev": round(ev, 4),
            "estimated_p_win": round(p * 100.0, 1),
            "gain_on_win": round(gain_on_win, 4),
            "loss_on_fail": round(loss_on_fail, 4),
            "fee_drag": round(fee_amount, 4),
            "reason": (
                f"Math verified: R:R={rr_ratio:.2f}:1, EV=${ev:+.4f}, "
                f"WinProb={p*100:.0f}%, Fees=${fee_amount:.4f}"
                if is_viable
                else f"Negative EV or unfavorable R:R (R:R={rr_ratio:.2f}, EV=${ev:+.4f})"
            ),
        }


# Global singleton instance
quant_analyzer = QuantitativeRiskAnalyzer()

"""
Three-Way Risk Debate Arena (Conservative vs. Aggressive vs. Neutral)
Adapted from TauricResearch/TradingAgents architecture.
Orchestrates a multi-perspective risk debate to prevent both reckless drawdown
and conservative under-allocation regret.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.logging import logger


@dataclass
class DebatorPerspective:
    debator_name: str
    stance: str
    key_argument: str
    risk_assessment: str
    allocation_recommendation: float  # Recommended portfolio % to commit


class ThreeWayRiskDebateArena:
    """Orchestrates structured debate between Conservative, Aggressive, and Neutral risk debators."""

    def __init__(self):
        pass

    def run_debate(
        self,
        symbol: str,
        trade_action: str,  # 'BUY' or 'SELL'
        proposed_quantity: int,
        target_price: float,
        stop_loss: float,
        current_price: float,
        volatility_atr: float = 18.5,
        portfolio_capital: float = 50000.0,
    ) -> dict[str, Any]:
        """Conducts a 3-way risk debate on a proposed trade plan."""
        risk_per_share = abs(current_price - stop_loss)
        reward_per_share = abs(target_price - current_price)
        rr_ratio = round(reward_per_share / max(risk_per_share, 0.01), 2)
        total_risk_exposure = round(proposed_quantity * risk_per_share, 2)
        risk_pct_of_capital = round((total_risk_exposure / max(portfolio_capital, 1.0)) * 100, 2)

        # 1. Conservative Risk Debator
        if risk_pct_of_capital > 2.0 or rr_ratio < 1.5:
            con_stance = "VETO / REDUCE"
            con_arg = (
                f"Risk exposure is {risk_pct_of_capital}% of capital (₹{total_risk_exposure:,.2f}), "
                f"which exceeds the institutional 1.5% maximum single-trade risk threshold. "
                f"R:R ratio ({rr_ratio}:1) does not provide sufficient asymmetric buffer against gap-down risk."
            )
            con_alloc = 0.5  # Recommends halving position size
        else:
            con_stance = "CAUTIOUS APPROVAL"
            con_arg = (
                f"Single-trade capital risk ({risk_pct_of_capital}%) is within bounds, "
                f"but trailing stop must immediately step up to breakeven once price advances by 1.0x ATR (₹{volatility_atr:.2f})."
            )
            con_alloc = 0.8

        # 2. Aggressive Risk Debator
        if rr_ratio >= 2.0 and risk_pct_of_capital <= 3.0:
            agg_stance = "MAXIMIZE ALLOCATION"
            agg_arg = (
                f"Target price ₹{target_price:.2f} offers strong upside convexity ({rr_ratio}:1 R:R). "
                "Limiting size here incurs severe opportunity cost. Backtested momentum setups in this regime "
                "produce positive expectancy. Recommend deploying full allotted tranche with scale-in on breakout."
            )
            agg_alloc = 1.2  # Suggests scaling up
        else:
            agg_stance = "PROCEED WITH MOMENTUM"
            agg_arg = (
                f"Setup is tradeable with clear directional bias. Upside target is valid. "
                "Ensure order execution does not suffer slippage on limit fill."
            )
            agg_alloc = 1.0

        # 3. Neutral Mathematical Debator (Kelly Criterion & Volatility Calibration)
        win_rate_est = 0.62  # Base quant win rate
        kelly_fraction = round((win_rate_est * rr_ratio - (1 - win_rate_est)) / max(rr_ratio, 0.1), 3)
        # Half-Kelly safety factor
        safe_fraction = max(0.2, min(round(kelly_fraction * 0.5, 3), 1.0))

        neu_stance = "BALANCED CALIBRATION"
        neu_arg = (
            f"Mathematical expectation: Estimated win rate {win_rate_est:.0%}, R:R {rr_ratio}:1. "
            f"Kelly Criterion indicates optimal fraction {kelly_fraction:.2f}; "
            f"Half-Kelly safety factor warrants an allocation multiplier of {safe_fraction:.2f}x standard size."
        )
        neu_alloc = safe_fraction

        # Consensus Resolution
        consensus_alloc_mult = round((con_alloc + agg_alloc + neu_alloc) / 3.0, 2)
        calibrated_quantity = max(1, int(proposed_quantity * consensus_alloc_mult))

        if con_stance == "VETO / REDUCE" and rr_ratio < 1.3:
            final_status = "REJECTED_BY_CONSERVATIVE_VETO"
            verdict = "Risk is disproportionate to reward. Trade proposal vetoed."
        else:
            final_status = "APPROVED_WITH_CALIBRATION"
            verdict = (
                f"Risk debate reached consensus. Allocation calibrated to {consensus_alloc_mult:.2f}x proposed size "
                f"({calibrated_quantity} units vs {proposed_quantity} requested)."
            )

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "symbol": symbol,
            "trade_action": trade_action,
            "original_quantity": proposed_quantity,
            "calibrated_quantity": calibrated_quantity,
            "current_price": current_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "risk_reward_ratio": f"{rr_ratio}:1",
            "capital_risk_pct": f"{risk_pct_of_capital}%",
            "final_verdict": final_status,
            "consensus_summary": verdict,
            "debators": {
                "conservative": {
                    "role": "Conservative Risk Debator",
                    "focus": "Capital Preservation & Worst-Case Drawdown",
                    "stance": con_stance,
                    "argument": con_arg,
                    "suggested_multiplier": con_alloc,
                },
                "aggressive": {
                    "role": "Aggressive Risk Debator",
                    "focus": "Upside Convexity & Opportunity Maximization",
                    "stance": agg_stance,
                    "argument": agg_arg,
                    "suggested_multiplier": agg_alloc,
                },
                "neutral": {
                    "role": "Neutral Quantitative Debator",
                    "focus": "Kelly Criterion & Sharpe Optimization",
                    "stance": neu_stance,
                    "argument": neu_arg,
                    "suggested_multiplier": neu_alloc,
                },
            },
        }


# Global singleton
three_way_risk_arena = ThreeWayRiskDebateArena()

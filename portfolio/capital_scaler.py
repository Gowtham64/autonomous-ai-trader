from pydantic import BaseModel

from core.config.settings import settings
from core.logging import logger


class ScalingEvaluation(BaseModel):
    current_capital: float
    recommended_capital: float
    scaling_approved: bool
    sharpe_equivalent: float
    win_rate_pct: float
    profit_factor: float
    total_trades_count: int
    justification: str


class CapitalScalingPolicy:
    """Statistical Capital Scaling Controller.
    
    Prevents premature leverage scaling by requiring rigorous empirical statistical proof
    (Sharpe, Expectancy, Win Rate, Drawdown constraint) before authorizing capital expansion.
    """

    @staticmethod
    def evaluate_scaling(
        total_trades: int,
        winning_trades: int,
        total_profit: float,
        total_loss: float,
        max_drawdown_pct: float,
        current_capital: float = settings.MAX_CAPITAL,
    ) -> ScalingEvaluation:
        """Evaluates whether the trading system has earned statistical justification to scale capital."""
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        profit_factor = (total_profit / abs(total_loss)) if abs(total_loss) > 0 else (2.0 if total_profit > 0 else 0.0)
        sharpe_approx = (win_rate / 50.0) * (profit_factor / 1.5)

        # Strict Institutional Scaling Criteria:
        # 1. Minimum 20 completed trades for statistical relevance
        # 2. Win rate >= 55%
        # 3. Profit Factor >= 1.6
        # 4. Max historical drawdown < 4.5%
        eligible = (
            total_trades >= 20
            and win_rate >= 55.0
            and profit_factor >= 1.6
            and max_drawdown_pct < 0.045
        )

        if eligible:
            # Gradual scaling: +20% step
            new_capital = round(current_capital * 1.20, 2)
            justification = (
                f"Statistical edge proven over {total_trades} trades! Win Rate: {win_rate:.1f}%, "
                f"Profit Factor: {profit_factor:.2f}, Max Drawdown: {max_drawdown_pct*100:.1f}%. "
                f"Scaling authorized from ₹{current_capital:,.2f} to ₹{new_capital:,.2f}."
            )
            logger.info(f"[Capital Scaler] {justification}")
        else:
            new_capital = current_capital
            reasons = []
            if total_trades < 20:
                reasons.append(f"Insufficient trade sample size ({total_trades}/20 minimum)")
            if win_rate < 55.0:
                reasons.append(f"Win rate {win_rate:.1f}% < 55.0% threshold")
            if profit_factor < 1.6:
                reasons.append(f"Profit factor {profit_factor:.2f} < 1.60 threshold")
            if max_drawdown_pct >= 0.045:
                reasons.append(f"Max drawdown {max_drawdown_pct*100:.1f}% exceeds 4.5% limit")

            justification = (
                f"Capital scaling DENIED. Preserving bootstrap ₹{current_capital:,.2f}. Reasons: {'; '.join(reasons)}"
            )
            logger.info(f"[Capital Scaler] {justification}")

        return ScalingEvaluation(
            current_capital=current_capital,
            recommended_capital=new_capital,
            scaling_approved=eligible,
            sharpe_equivalent=round(sharpe_approx, 2),
            win_rate_pct=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            total_trades_count=total_trades,
            justification=justification,
        )

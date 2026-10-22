from enum import Enum

from pydantic import BaseModel

from core.domain.models import MarketRegime
from core.schemas.trade import CandidateSignal


class StrategyType(str, Enum):
    MOMENTUM_BREAKOUT = "MOMENTUM_BREAKOUT"
    TREND_FOLLOWING = "TREND_FOLLOWING"
    MEAN_REVERSION_VWAP = "MEAN_REVERSION_VWAP"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"
    BNF_OVERSOLD_DISPARITY = "BNF_OVERSOLD_DISPARITY"
    JHUNJHUNWALA_SUPER_TREND = "JHUNJHUNWALA_SUPER_TREND"
    LIVERMORE_PIVOTAL_BREAKOUT = "LIVERMORE_PIVOTAL_BREAKOUT"
    MULTI_DAY_SWING = "MULTI_DAY_SWING"
    CRYPTO_PERPETUAL_MOMENTUM = "CRYPTO_PERPETUAL_MOMENTUM"
    TURTLE_TREND_SYSTEM = "TURTLE_TREND_SYSTEM"
    GOODMAN_BREAKOUT_TREND = "GOODMAN_BREAKOUT_TREND"
    BUCEK_PRICE_ACTION_SWING = "BUCEK_PRICE_ACTION_SWING"
    OPTIONS_DEFINED_RISK_SPREAD = "OPTIONS_DEFINED_RISK_SPREAD"
    DEFENSIVE_PRESERVATION = "DEFENSIVE_PRESERVATION"


class StrategyEvaluationResult(BaseModel):
    strategy_name: str
    suitable: bool
    score: float
    regime_match: bool
    rationale: str


class MultiStrategyEngine:
    """Evaluates multiple algorithmic & legendary master strategies against detected market regimes and signal metrics."""

    @staticmethod
    def evaluate_strategies(
        signal: CandidateSignal,
        is_survival_mode: bool = False,
    ) -> StrategyEvaluationResult:
        """Selects and scores the most suitable strategy for the current market candidate."""
        # In survival mode, strictly allow only high-quality Trend Following & Capital Preservation
        if is_survival_mode:
            is_crypto = (signal.exchange.upper() in ["DELTA", "CRYPTO"]) or ("USD" in signal.symbol.upper())
            if is_crypto and signal.momentum_score >= 40:
                return StrategyEvaluationResult(
                    strategy_name=StrategyType.CRYPTO_PERPETUAL_MOMENTUM.value,
                    suitable=True,
                    score=round(signal.momentum_score + 8.0, 1),
                    regime_match=True,
                    rationale=f"Survival Alpha: Directional perpetual momentum on {signal.symbol} ({signal.momentum_score}/100) to rebuild capital.",
                )
            if signal.regime == MarketRegime.BULLISH_TREND and signal.momentum_score >= 70:
                return StrategyEvaluationResult(
                    strategy_name=StrategyType.TREND_FOLLOWING.value,
                    suitable=True,
                    score=85.0,
                    regime_match=True,
                    rationale="Survival Mode: Conservative Trend Following on prime bullish setup only.",
                )
            return StrategyEvaluationResult(
                strategy_name=StrategyType.DEFENSIVE_PRESERVATION.value,
                suitable=False,
                score=10.0,
                regime_match=False,
                rationale="Survival Mode: Skipping marginal candidate to preserve scarce capital.",
            )

        # 0. Crypto Perpetual Futures Strategy (Delta Exchange 24/7 Perps)
        is_crypto = (signal.exchange.upper() in ["DELTA", "CRYPTO"]) or ("USD" in signal.symbol.upper())
        if is_crypto:
            if signal.momentum_score >= 40 and signal.regime in [MarketRegime.BULLISH_TREND, MarketRegime.BEARISH_TREND, MarketRegime.HIGH_VOLATILITY]:
                return StrategyEvaluationResult(
                    strategy_name=StrategyType.CRYPTO_PERPETUAL_MOMENTUM.value,
                    suitable=True,
                    score=round(signal.momentum_score + 12.0, 1),
                    regime_match=True,
                    rationale=f"AstraQuant Crypto Perpetual Momentum: 24/7 directional momentum ({signal.momentum_score}/100) on {signal.symbol} with multi-factor direction & bracket protection.",
                )
            elif signal.regime in [MarketRegime.SIDEWAYS_RANGING, MarketRegime.LOW_VOLATILITY] and signal.momentum_score >= 35:
                return StrategyEvaluationResult(
                    strategy_name=StrategyType.CRYPTO_PERPETUAL_MOMENTUM.value,
                    suitable=True,
                    score=round(signal.momentum_score + 5.0, 1),
                    regime_match=True,
                    rationale=f"Kaufman Volatility Compression: Mean-reverting perpetual squeeze on {signal.symbol} targeting value band expansion.",
                )
            else:
                return StrategyEvaluationResult(
                    strategy_name=StrategyType.CRYPTO_PERPETUAL_MOMENTUM.value,
                    suitable=True,
                    score=round(signal.momentum_score, 1),
                    regime_match=True,
                    rationale=f"Active Perpetual Strategy: Momentum setup on {signal.symbol} with score {signal.momentum_score}/100.",
                )

        # 1. Jesse Livermore Pivotal Breakout Strategy
        if signal.momentum_score >= 65 and signal.relative_volume >= 1.25 and signal.regime in [MarketRegime.BULLISH_TREND, MarketRegime.HIGH_VOLATILITY]:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.LIVERMORE_PIVOTAL_BREAKOUT.value,
                suitable=True,
                score=round(signal.momentum_score + 10.0, 1),
                regime_match=True,
                rationale=f"Jesse Livermore Pivotal Breakout: Line of Least Resistance UPWARD with {signal.relative_volume}x tape volume surge.",
            )

        # 2. Multi-Day Swing Strategy (for low-beta, high-stability equities like Coal India, GAIL, ITC, NTPC)
        atr_pct = (signal.atr_14 / signal.ltp * 100.0) if (signal.atr_14 and signal.ltp > 0) else 1.5
        if atr_pct < 1.0 and signal.regime in [MarketRegime.BULLISH_TREND, MarketRegime.SIDEWAYS_RANGING] and signal.momentum_score >= 40:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.MULTI_DAY_SWING.value,
                suitable=True,
                score=round(signal.momentum_score + 8.0, 1),
                regime_match=True,
                rationale=f"Multi-Day Swing: Low-beta asset (ATR: {atr_pct:.2f}%) requires multi-session holding for target expansion. Routed to DELIVERY.",
            )

        # 2.5. Rakesh Jhunjhunwala Structural Super-Trend Strategy
        supercycle_sectors = ["Banking", "PSU Banks", "Infrastructure", "Power", "Defense", "Energy", "Auto", "Manufacturing"]
        is_supercycle = any(s.lower() in signal.sector.lower() for s in supercycle_sectors)
        if signal.regime == MarketRegime.BULLISH_TREND and is_supercycle and signal.momentum_score >= 45:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.JHUNJHUNWALA_SUPER_TREND.value,
                suitable=True,
                score=round(signal.momentum_score + 15.0, 1),
                regime_match=True,
                rationale=f"Rakesh Jhunjhunwala Big Bull Super-Trend: Structural tailwinds in {signal.sector} with robust trend alignment.",
            )

        # 3. Takashi Kotegawa (BNF) Oversold Disparity Reversion Strategy
        if signal.regime in [MarketRegime.BEARISH_TREND, MarketRegime.HIGH_VOLATILITY] and signal.relative_volume >= 1.4:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.BNF_OVERSOLD_DISPARITY.value,
                suitable=True,
                score=round(75.0 + (signal.relative_volume * 10.0), 1),
                regime_match=True,
                rationale=f"Takashi Kotegawa (BNF) Panic Bounce: Extreme capitulation volume ({signal.relative_volume}x) primed for mean-reversion snapback.",
            )

        # 4. Glen Goodman Breakout & Trend Strategy (Never-Chase <= 5% rule)
        if signal.momentum_score >= 55 and signal.relative_volume >= 1.35 and signal.regime in [MarketRegime.BULLISH_TREND, MarketRegime.HIGH_VOLATILITY]:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.GOODMAN_BREAKOUT_TREND.value,
                suitable=True,
                score=round(signal.momentum_score + 8.0, 1),
                regime_match=True,
                rationale=f"Glen Goodman Trend Breakout: Established trend with {signal.relative_volume}x volume confirmation. Chandelier stop & anti-chase guard active.",
            )

        # 5. Turtle Trend System (Richard Dennis & Ondřej Buček System 1 & 2)
        if signal.regime in [MarketRegime.BULLISH_TREND, MarketRegime.BEARISH_TREND] and signal.momentum_score >= 50:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.TURTLE_TREND_SYSTEM.value,
                suitable=True,
                score=round(signal.momentum_score + 6.0, 1),
                regime_match=True,
                rationale=f"Turtle Trend System: Donchian breakout channel alignment in {signal.regime.value} with 2N stop loss & volatility N unit sizing.",
            )

        # 6. McCarthy Options Defined-Risk Spreads (Derivatives / High Volatility / Neutral theta Regimes)
        is_option_symbol = "OPT" in signal.symbol.upper() or signal.symbol.upper().endswith(("CE", "PE"))
        if is_option_symbol and signal.regime in [MarketRegime.HIGH_VOLATILITY, MarketRegime.SIDEWAYS_RANGING, MarketRegime.BULLISH_TREND]:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.OPTIONS_DEFINED_RISK_SPREAD.value,
                suitable=True,
                score=round(max(75.0, signal.momentum_score + 10.0), 1),
                regime_match=True,
                rationale="McCarthy Defined-Risk Options Spread: Capitalizing on implied volatility and positive theta decay via bounded credit/debit vertical.",
            )

        # 7. Buček Price Action Swing Strategy (Hammer / Shooting Star pinbar)
        if signal.regime in [MarketRegime.SIDEWAYS_RANGING, MarketRegime.LOW_VOLATILITY] and signal.momentum_score >= 35:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.BUCEK_PRICE_ACTION_SWING.value,
                suitable=True,
                score=round(signal.momentum_score + 4.0, 1),
                regime_match=True,
                rationale="Buček Price Action Swing: Swing-point pinbar candidate with strict 1:1 risk-reward target.",
            )

        # 8. Momentum Breakout Strategy
        if signal.momentum_score >= 60 and signal.relative_volume >= 1.2:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.MOMENTUM_BREAKOUT.value,
                suitable=True,
                score=round(signal.momentum_score, 1),
                regime_match=signal.regime in [MarketRegime.BULLISH_TREND, MarketRegime.HIGH_VOLATILITY],
                rationale=f"High momentum ({signal.momentum_score}/100) supported by strong relative volume ({signal.relative_volume}x).",
            )

        # 9. Trend Following Strategy
        if signal.regime == MarketRegime.BULLISH_TREND and signal.momentum_score >= 40:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.TREND_FOLLOWING.value,
                suitable=True,
                score=round(signal.momentum_score + 5.0, 1),
                regime_match=True,
                rationale=f"Established bullish regime with positive momentum ({signal.momentum_score}/100).",
            )

        # 10. Mean Reversion Strategy
        if signal.regime == MarketRegime.SIDEWAYS_RANGING and signal.momentum_score >= 35:
            return StrategyEvaluationResult(
                strategy_name=StrategyType.MEAN_REVERSION_VWAP.value,
                suitable=True,
                score=round(signal.momentum_score, 1),
                regime_match=True,
                rationale="Sideways ranging regime: Range-bound mean reversion setup.",
            )

        # Default fallback
        return StrategyEvaluationResult(
            strategy_name=StrategyType.DEFENSIVE_PRESERVATION.value,
            suitable=False,
            score=30.0,
            regime_match=False,
            rationale="Insufficient edge across quantitative and legendary strategies.",
        )

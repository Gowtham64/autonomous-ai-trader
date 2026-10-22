import pandas as pd

from core.logging import logger
from core.schemas.trade import AnalystReport, CandidateSignal
from intelligence.kronos_service import kronos_service


class KronosAnalystAgent:
    """Specialist Foundation Model Analyst powered by Tsinghua AAAI 2026 Kronos.
    
    Generates zero-shot probabilistic candlestick forecasts and projected price trajectories
    to evaluate breakout durability, target reachability, and predictive stop losses.
    """

    def __init__(self):
        self.agent_name = "Kronos Foundation Forecaster"

    async def analyze(
        self,
        signal: CandidateSignal,
        df: pd.DataFrame | None = None,
        forecast_horizon_bars: int = 15,
    ) -> AnalystReport:
        logger.info(f"🔮 [Kronos Analyst] Running candlestick foundation model forecast on {signal.symbol}...")

        # If historical DataFrame not provided, fetch via default provider
        if df is None or df.empty:
            try:
                from market.providers.yfinance_provider import YFinanceMarketDataProvider
                provider = YFinanceMarketDataProvider()
                # Crypto symbols arrive as e.g. "APTUSD" (no dash) — the old '-USD' check missed
                # them, so forecasts ran on DAILY bars (a 15-DAY projection) while trades were
                # placed with intraday 1.5% stops. Use 15m bars for all crypto pairs.
                is_crypto_pair = signal.symbol.upper().endswith(("USD", "-USD", "USDT")) or (signal.exchange or "").upper() in ["DELTA", "CRYPTO"]
                df = await provider.get_historical_ohlcv(signal.symbol, interval="15m" if is_crypto_pair else "1d", period="7d" if is_crypto_pair else "30d")
            except Exception as e:
                logger.warning(f"[Kronos Analyst] Error fetching bars for {signal.symbol}: {e}")
                df = pd.DataFrame()

        # Run Kronos Forecast
        res = await kronos_service.forecast(
            symbol=signal.symbol,
            df=df,
            pred_len=forecast_horizon_bars,
            sample_count=3,
            temperature=0.80,
        )

        currency_sym = "$" if ("-USD" in signal.symbol or signal.exchange == "CRYPTO") else "₹"
        
        key_obs = [
            f"Kronos Zero-Shot Model ({res.model_name}): Projected {res.expected_direction} trajectory over next {res.forecast_horizon_bars} bars.",
            f"Price Trajectory: {currency_sym}{res.last_price:.2f} ➔ {currency_sym}{res.projected_price:.2f} ({res.projected_change_pct:+.2f}% expected return).",
            f"Projected Volatility Cone: Low {currency_sym}{res.projected_low:.2f} to High {currency_sym}{res.projected_high:.2f}.",
            f"Inference Mode: {res.status} ({res.notes})",
        ]

        risk_warns = []
        if res.expected_direction == "BEARISH":
            risk_warns.append(f"Kronos neural decoder predicts price breakdown of {res.projected_change_pct:.2f}%.")
        elif res.expected_direction == "SIDEWAYS":
            risk_warns.append("Kronos projects range-bound consolidation with insufficient directional velocity.")
        
        if abs(res.projected_change_pct) < 0.3:
            risk_warns.append("Stagnation risk: Predicted trajectory lacks momentum expansion for standard 1:2 R:R.")

        stance_val = "NEUTRAL" if res.expected_direction == "SIDEWAYS" else res.expected_direction
        if stance_val not in ["BULLISH", "BEARISH", "NEUTRAL"]:
            stance_val = "NEUTRAL"

        return AnalystReport(
            agent_name=self.agent_name,
            symbol=signal.symbol,
            stance=stance_val,
            confidence=res.confidence_score,
            key_observations=key_obs,
            risk_warnings=risk_warns,
            suggested_entry=res.last_price,
            suggested_stop=res.recommended_stop_loss,
            suggested_target=res.recommended_target,
        )


kronos_analyst = KronosAnalystAgent()

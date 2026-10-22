import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import numpy as np
import pandas as pd
import torch

from core.logging import logger
from intelligence.kronos import Kronos, KronosPredictor, KronosTokenizer


@dataclass
class KronosForecastResult:
    symbol: str
    last_price: float
    projected_price: float
    projected_change_pct: float
    projected_high: float
    projected_low: float
    expected_direction: Literal["BULLISH", "BEARISH", "SIDEWAYS"]
    confidence_score: float
    recommended_stop_loss: float
    recommended_target: float
    forecast_horizon_bars: int
    predicted_candles: pd.DataFrame
    model_name: str
    device: str
    status: Literal["SUCCESS", "FALLBACK"]
    notes: str

    @property
    def predicted_bars(self) -> list[dict]:
        if self.predicted_candles is None or self.predicted_candles.empty:
            return []
        bars = []
        for idx, row in self.predicted_candles.reset_index().iterrows():
            bars.append({
                "step": idx + 1,
                "open": float(row.get("open", row.get("close", 0.0))),
                "high": float(row.get("high", row.get("close", 0.0))),
                "low": float(row.get("low", row.get("close", 0.0))),
                "close": float(row.get("close", 0.0)),
                "volume": float(row.get("volume", 0.0)),
            })
        return bars

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "last_price": self.last_price,
            "projected_price": self.projected_price,
            "projected_change_pct": self.projected_change_pct,
            "projected_high": self.projected_high,
            "projected_low": self.projected_low,
            "expected_direction": self.expected_direction,
            "confidence_score": self.confidence_score,
            "recommended_stop_loss": self.recommended_stop_loss,
            "recommended_target": self.recommended_target,
            "forecast_horizon_bars": self.forecast_horizon_bars,
            "model_name": self.model_name,
            "device": self.device,
            "status": self.status,
            "notes": self.notes,
            "predicted_bars": self.predicted_bars,
        }


class KronosForecastService:
    """Production Service wrapping the Kronos Candlestick Foundation Model (AAAI 2026).
    
    Provides zero-shot probabilistic K-line forecasting, trajectory projection,
    and foundation-model-driven stop-loss / target optimization.
    """

    def __init__(
        self,
        model_name: str = "NeoQuasar/Kronos-mini",
        tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-2k",
        device: str | None = None,
        max_context: int = 512,
    ):
        self.model_name = model_name
        self.tokenizer_name = tokenizer_name
        self.max_context = max_context
        
        # Select device: Metal (mps) for Mac, CUDA for Nvidia, or CPU
        if device is None:
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        self.model = None
        self.tokenizer = None
        self.predictor = None
        self._load_lock = asyncio.Lock()
        self._inference_lock = asyncio.Lock()
        self._is_initialized = False

    async def ensure_loaded(self) -> bool:
        """Lazily loads the Kronos model and tokenizer into memory."""
        if self._is_initialized:
            return True

        async with self._load_lock:
            if self._is_initialized:
                return True

            logger.info(f"⏳ [Kronos Foundation Model] Initializing {self.model_name} on {self.device.upper()}...")
            loop = asyncio.get_event_loop()

            def _load():
                try:
                    import warnings
                    warnings.filterwarnings("ignore")
                    try:
                        import huggingface_hub.utils.logging as hf_logging
                        hf_logging.set_verbosity_error()
                    except Exception:
                        pass

                    token = os.getenv("HF_TOKEN")
                    kwargs = {"token": token} if token else {}
                    
                    # Try local cache first to prevent unauthenticated network calls and warnings
                    try:
                        tokenizer = KronosTokenizer.from_pretrained(self.tokenizer_name, local_files_only=True, **kwargs)
                        model = Kronos.from_pretrained(self.model_name, local_files_only=True, **kwargs)
                    except Exception:
                        tokenizer = KronosTokenizer.from_pretrained(self.tokenizer_name, **kwargs)
                        model = Kronos.from_pretrained(self.model_name, **kwargs)

                    model.to(self.device)
                    model.eval()
                    predictor = KronosPredictor(model, tokenizer, max_context=self.max_context, device=self.device)
                    return tokenizer, model, predictor
                except Exception as e:
                    logger.warning(f"⚠️ [Kronos Model Load Warning] Could not load {self.model_name}: {e}")
                    return None, None, None

            tokenizer, model, predictor = await loop.run_in_executor(None, _load)

            if model is not None and predictor is not None:
                self.tokenizer = tokenizer
                self.model = model
                self.predictor = predictor
                self._is_initialized = True
                logger.info(f"✅ [Kronos Foundation Model] {self.model_name} successfully loaded on {self.device.upper()}!")
                return True
            else:
                logger.warning("⚠️ [Kronos Foundation Model] Operating in statistical fallback mode.")
                return False

    async def forecast(
        self,
        symbol: str,
        df: pd.DataFrame,
        pred_len: int = 15,
        sample_count: int = 3,
        temperature: float = 0.85,
    ) -> KronosForecastResult:
        """Generates zero-shot probabilistic K-line forecasts for an equity or crypto asset."""
        if df.empty or len(df) < 20:
            return self._generate_fallback(symbol, df, pred_len, reason="Insufficient history bars (< 20)")

        # Prepare normalized DataFrame
        df_clean = df.copy()
        
        # Ensure column names are lowercase
        df_clean.columns = [str(c).lower() for c in df_clean.columns]
        
        # Required columns: open, high, low, close
        for col in ["open", "high", "low", "close"]:
            if col not in df_clean.columns:
                return self._generate_fallback(symbol, df, pred_len, reason=f"Missing column '{col}'")

        if "volume" not in df_clean.columns:
            df_clean["volume"] = 1000.0

        if "amount" not in df_clean.columns:
            df_clean["amount"] = df_clean["close"] * df_clean["volume"]

        # Ensure datetime index / timestamps
        if not isinstance(df_clean.index, pd.DatetimeIndex):
            if "timestamp" in df_clean.columns:
                timestamps = pd.Series(pd.to_datetime(df_clean["timestamp"]))
            elif "timestamps" in df_clean.columns:
                timestamps = pd.Series(pd.to_datetime(df_clean["timestamps"]))
            else:
                timestamps = pd.Series(pd.date_range(end=datetime.now(UTC), periods=len(df_clean), freq="15min"))
        else:
            timestamps = pd.Series(df_clean.index)

        # Build future timestamps
        if len(timestamps) >= 2:
            freq = timestamps.iloc[-1] - timestamps.iloc[-2]
            if freq.total_seconds() <= 0:
                freq = timedelta(minutes=15)
        else:
            freq = timedelta(minutes=15)

        last_ts = timestamps.iloc[-1]
        future_timestamps = pd.Series([last_ts + (i + 1) * freq for i in range(pred_len)])

        # Attempt Kronos Neural Model Inference
        is_ready = await self.ensure_loaded()
        if is_ready and self.predictor is not None:
            try:
                loop = asyncio.get_event_loop()

                lookback = min(len(df_clean), self.max_context - pred_len)
                x_df = df_clean.iloc[-lookback:][["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True)
                x_ts = timestamps.iloc[-lookback:].reset_index(drop=True)

                def _predict():
                    return self.predictor.predict(
                        df=x_df,
                        x_timestamp=x_ts,
                        y_timestamp=future_timestamps,
                        pred_len=pred_len,
                        T=temperature,
                        top_p=0.90,
                        sample_count=sample_count,
                        verbose=False,
                    )

                async with self._inference_lock:
                    pred_df = await loop.run_in_executor(None, _predict)

                # Extract Key Metrics from Forecast
                last_price = float(df_clean["close"].iloc[-1])
                final_pred_price = float(pred_df["close"].iloc[-1])
                proj_change_pct = round(((final_pred_price - last_price) / max(0.01, last_price)) * 100.0, 2)
                
                proj_high = float(pred_df["high"].max())
                proj_low = float(pred_df["low"].min())

                # Direction classification
                if proj_change_pct >= 0.40:
                    direction = "BULLISH"
                elif proj_change_pct <= -0.40:
                    direction = "BEARISH"
                else:
                    direction = "SIDEWAYS"

                # Dynamic Stop Loss & Target Sizing
                # If Bullish: SL below projected low, Target at or above projected high
                if direction == "BULLISH":
                    stop_loss = round(min(last_price * 0.99, proj_low * 0.998), 2)
                    target = round(max(last_price * 1.015, proj_high), 2)
                    confidence = min(0.95, max(0.55, 0.60 + abs(proj_change_pct) * 0.08))
                elif direction == "BEARISH":
                    stop_loss = round(max(last_price * 1.01, proj_high * 1.002), 2)
                    target = round(min(last_price * 0.985, proj_low), 2)
                    confidence = min(0.95, max(0.55, 0.60 + abs(proj_change_pct) * 0.08))
                else:
                    stop_loss = round(last_price * 0.992, 2)
                    target = round(last_price * 1.012, 2)
                    confidence = 0.50

                return KronosForecastResult(
                    symbol=symbol,
                    last_price=last_price,
                    projected_price=final_pred_price,
                    projected_change_pct=proj_change_pct,
                    projected_high=proj_high,
                    projected_low=proj_low,
                    expected_direction=direction,
                    confidence_score=round(confidence, 2),
                    recommended_stop_loss=stop_loss,
                    recommended_target=target,
                    forecast_horizon_bars=pred_len,
                    predicted_candles=pred_df,
                    model_name=self.model_name,
                    device=self.device,
                    status="SUCCESS",
                    notes=f"Kronos zero-shot autoregressive forecast ({pred_len} bars ahead). Projected {direction} trajectory.",
                )

            except Exception as e:
                logger.warning(f"⚠️ [Kronos Inference Error] Falling back to statistical engine: {e}")

        # Fallback
        return self._generate_fallback(symbol, df_clean, pred_len, reason="Neural model fallback")

    def _generate_fallback(self, symbol: str, df: pd.DataFrame, pred_len: int, reason: str) -> KronosForecastResult:
        """Autoregressive drift-diffusion fallback when foundation weights are offline."""
        last_price = float(df["close"].iloc[-1]) if not df.empty else 100.0
        
        # Simple statistical momentum
        if len(df) >= 10:
            recent_returns = df["close"].pct_change().dropna().tail(10)
            drift = float(recent_returns.mean())
            volatility = float(recent_returns.std()) if not pd.isna(recent_returns.std()) else 0.005
        else:
            drift = 0.0005
            volatility = 0.005

        simulated_prices = [last_price]
        for _ in range(pred_len):
            nxt = simulated_prices[-1] * (1.0 + drift + np.random.normal(0, volatility * 0.5))
            simulated_prices.append(nxt)

        final_price = round(simulated_prices[-1], 2)
        proj_change = round(((final_price - last_price) / max(0.01, last_price)) * 100.0, 2)
        proj_high = round(max(simulated_prices), 2)
        proj_low = round(min(simulated_prices), 2)

        direction = "BULLISH" if proj_change >= 0.3 else ("BEARISH" if proj_change <= -0.3 else "SIDEWAYS")

        return KronosForecastResult(
            symbol=symbol,
            last_price=last_price,
            projected_price=final_price,
            projected_change_pct=proj_change,
            projected_high=proj_high,
            projected_low=proj_low,
            expected_direction=direction,
            confidence_score=0.55,
            recommended_stop_loss=round(last_price * 0.99, 2),
            recommended_target=round(last_price * 1.02, 2),
            forecast_horizon_bars=pred_len,
            predicted_candles=pd.DataFrame({"close": simulated_prices[1:]}),
            model_name="Kronos-Statistical-Fallback",
            device=self.device,
            status="FALLBACK",
            notes=f"Statistical drift-diffusion projection ({reason}).",
        )


kronos_service = KronosForecastService()

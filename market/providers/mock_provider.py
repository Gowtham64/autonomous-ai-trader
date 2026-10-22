from datetime import UTC, datetime

import numpy as np
import pandas as pd

from market.providers.base import BaseMarketDataProvider


class MockMarketDataProvider(BaseMarketDataProvider):
    """Deterministic Mock Market Data Provider for high-speed testing and simulations."""

    def __init__(self, base_price: float = 2500.0, trend: str = "bullish"):
        self.base_price = base_price
        self.trend = trend
        self._current_ltp = base_price

    def set_ltp(self, price: float):
        self._current_ltp = price

    async def get_ltp(self, symbol: str) -> float:
        return self._current_ltp

    async def get_historical_ohlcv(
        self, symbol: str, interval: str = "1d", period: str = "60d"
    ) -> pd.DataFrame:
        dates = pd.date_range(end=datetime.now(UTC), periods=60, freq="D")
        np.random.seed(42)

        if self.trend == "bullish":
            returns = np.random.normal(0.003, 0.015, size=60)
        elif self.trend == "bearish":
            returns = np.random.normal(-0.003, 0.015, size=60)
        else:
            returns = np.random.normal(0.000, 0.01, size=60)

        price_series = self.base_price * np.cumprod(1 + returns)
        highs = price_series * (1 + np.abs(np.random.normal(0, 0.008, size=60)))
        lows = price_series * (1 - np.abs(np.random.normal(0, 0.008, size=60)))
        opens = price_series * (1 + np.random.normal(0, 0.004, size=60))
        closes = price_series
        volumes = np.random.randint(500000, 2000000, size=60)

        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            },
            index=dates,
        )
        return df

    async def get_quote(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "ltp": self._current_ltp,
            "open": self._current_ltp * 0.995,
            "previous_close": self._current_ltp * 0.99,
            "volume": 1250000.0,
            "currency": "INR",
        }

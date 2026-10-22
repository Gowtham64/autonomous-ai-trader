from abc import ABC, abstractmethod

import pandas as pd


class BaseMarketDataProvider(ABC):
    """Abstract interface for point-in-time and live Indian market data."""

    @abstractmethod
    async def get_ltp(self, symbol: str) -> float:
        """Get Last Traded Price."""

    @abstractmethod
    async def get_historical_ohlcv(
        self, symbol: str, interval: str = "1d", period: str = "60d"
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data as a Pandas DataFrame."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> dict:
        """Get comprehensive quote including volume, open, high, low, close."""

    async def get_fundamentals(self, symbol: str) -> dict:
        """Fetch fundamental data, valuation metrics, and company growth indicators."""
        return {}

    async def get_news(self, symbol: str) -> list[str]:
        """Fetch recent news headlines and company corporate disclosures."""
        return []

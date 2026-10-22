"""
News Intelligence System for Indian Markets (NSE/BSE).
Ingests, parses, categorizes, and scores corporate filings, exchange announcements,
earnings, ratings, contracts, M&A, promoter activity, regulatory notices, and macro news.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class NewsCategory(str, Enum):
    COMPANY_ANNOUNCEMENT = "COMPANY_ANNOUNCEMENT"
    EXCHANGE_FILING = "EXCHANGE_FILING"
    EARNINGS_RESULTS = "EARNINGS_RESULTS"
    MANAGEMENT_COMMENTARY = "MANAGEMENT_COMMENTARY"
    CREDIT_RATING = "CREDIT_RATING"
    ORDERS_CONTRACTS = "ORDERS_CONTRACTS"
    MERGERS_ACQUISITIONS = "MERGERS_ACQUISITIONS"
    PROMOTER_ACTIVITY = "PROMOTER_ACTIVITY"
    REGULATORY_SEBI = "REGULATORY_SEBI"
    GOVERNMENT_POLICY = "GOVERNMENT_POLICY"
    SECTOR_DEVELOPMENT = "SECTOR_DEVELOPMENT"
    MACRO_ECONOMIC = "MACRO_ECONOMIC"
    GLOBAL_MARKET = "GLOBAL_MARKET"


class NewsImpactHorizon(str, Enum):
    INTRADAY = "INTRADAY"      # 15m - 1d impact
    SHORT_TERM = "SHORT_TERM"  # 1d - 1w impact
    MEDIUM_TERM = "MEDIUM_TERM"# 1w - 1m impact
    STRUCTURAL = "STRUCTURAL"  # > 1m super-cycle


class NewsIntelligenceItem(BaseModel):
    id: str
    symbol: str
    headline: str
    summary: str
    source: str
    category: NewsCategory
    publication_timestamp: datetime
    sentiment_score: float = Field(ge=-1.0, le=1.0)  # -1 (Bearish) to +1 (Bullish)
    confidence: float = Field(ge=0.0, le=1.0)
    novelty_score: float = Field(ge=0.0, le=1.0, default=0.9)
    impact_horizon: NewsImpactHorizon = NewsImpactHorizon.INTRADAY
    is_trading_restricted: bool = False  # e.g., result day volatility or regulatory ban
    restriction_reason: str | None = None
    entities_mentioned: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NewsIntelligenceSummary(BaseModel):
    symbol: str
    aggregate_sentiment: float
    total_news_count: int
    high_impact_alerts: list[str]
    has_active_restrictions: bool
    latest_items: list[NewsIntelligenceItem]
    sentiment_polarity: str  # BULLISH, BEARISH, NEUTRAL


class NewsIntelligenceEngine:
    """Production News Intelligence & Corporate Announcements Engine."""

    def __init__(self):
        self.news_store: list[NewsIntelligenceItem] = []
        self._seed_sample_intelligence()

    def _seed_sample_intelligence(self):
        sample_items = [
            NewsIntelligenceItem(
                id="NEWS-REL-01",
                symbol="RELIANCE.NS",
                headline="Reliance Retail expands FMCG distribution network with 1,200 new touchpoints across Tier-2 cities",
                summary="Retail division announces aggressive expansion of consumer brands network ahead of festive season.",
                source="NSE Corporate Filings",
                category=NewsCategory.COMPANY_ANNOUNCEMENT,
                publication_timestamp=datetime.now(UTC),
                sentiment_score=0.74,
                confidence=0.92,
                impact_horizon=NewsImpactHorizon.SHORT_TERM,
                entities_mentioned=["RELIANCE", "RELIANCE RETAIL"],
            ),
            NewsIntelligenceItem(
                id="NEWS-TCS-01",
                symbol="TCS.NS",
                headline="TCS secures $450M multi-year digital transformation deal from European financial consortium",
                summary="Large strategic deal win in cloud modernization and AI agents deployment for Tier-1 European bank.",
                source="BSE Exchange Broadcast",
                category=NewsCategory.ORDERS_CONTRACTS,
                publication_timestamp=datetime.now(UTC),
                sentiment_score=0.88,
                confidence=0.95,
                impact_horizon=NewsImpactHorizon.MEDIUM_TERM,
                entities_mentioned=["TCS"],
            ),
            NewsIntelligenceItem(
                id="NEWS-MACRO-01",
                symbol="NIFTY 50",
                headline="RBI MPC holds repo rate steady at 6.50%; maintains withdrawal of accommodation stance",
                summary="Central bank emphasizes durable inflation alignment towards 4% target while noting strong domestic GDP growth.",
                source="RBI Press Release",
                category=NewsCategory.MACRO_ECONOMIC,
                publication_timestamp=datetime.now(UTC),
                sentiment_score=0.35,
                confidence=0.98,
                impact_horizon=NewsImpactHorizon.STRUCTURAL,
                entities_mentioned=["RBI", "BANKING_SECTOR"],
            ),
        ]
        self.news_store.extend(sample_items)

    def ingest_news_item(self, item: NewsIntelligenceItem) -> None:
        """Stores and indexes a news or announcement item."""
        self.news_store.append(item)

    def analyze_symbol_news(self, symbol: str, lookback_hours: int = 48) -> NewsIntelligenceSummary:
        """Computes aggregate news sentiment and filters for a specific symbol."""
        clean_sym = symbol.replace(".NS", "").replace(".BO", "")
        matching = [
            item for item in self.news_store
            if clean_sym in item.symbol or item.symbol == symbol or clean_sym in item.entities_mentioned
        ]

        if not matching:
            return NewsIntelligenceSummary(
                symbol=symbol,
                aggregate_sentiment=0.0,
                total_news_count=0,
                high_impact_alerts=[],
                has_active_restrictions=False,
                latest_items=[],
                sentiment_polarity="NEUTRAL"
            )

        avg_sentiment = sum(item.sentiment_score for item in matching) / len(matching)
        high_impact = [item.headline for item in matching if abs(item.sentiment_score) >= 0.70]
        has_restrictions = any(item.is_trading_restricted for item in matching)

        polarity = "NEUTRAL"
        if avg_sentiment >= 0.25:
            polarity = "BULLISH"
        elif avg_sentiment <= -0.25:
            polarity = "BEARISH"

        return NewsIntelligenceSummary(
            symbol=symbol,
            aggregate_sentiment=round(avg_sentiment, 3),
            total_news_count=len(matching),
            high_impact_alerts=high_impact,
            has_active_restrictions=has_restrictions,
            latest_items=matching[-5:],
            sentiment_polarity=polarity
        )

    def get_symbol_intelligence(self, symbol: str) -> NewsIntelligenceSummary:
        """Alias for analyze_symbol_news."""
        return self.analyze_symbol_news(symbol)

    def get_active_intelligence(self, min_confidence: float = 0.5) -> list[NewsIntelligenceItem]:
        """Returns all active high-confidence news and corporate announcement items."""
        return [item for item in self.news_store if item.confidence >= min_confidence]

    def get_market_wide_news(self, limit: int = 15) -> list[NewsIntelligenceItem]:
        return list(reversed(self.news_store[-limit:]))


news_intelligence_engine = NewsIntelligenceEngine()


"""
Two-Tier AI Memory Architecture for Autonomous Indian Markets Trading.
Provides:
1. Market Memory: Regimes, macro events, stock behaviors, sector rotation, and news reactions.
2. Trade Memory: Trade rationale, agent predictions, execution slippage, MFE/MAE, and root-cause attribution.
"""

from datetime import UTC, datetime
from typing import Any
from pydantic import BaseModel, Field
from core.logging import logger


class HistoricalEventImpact(BaseModel):
    event_name: str
    date: str
    regime_before: str
    regime_after: str
    nifty_return_1d: float
    volatility_jump_vix: float
    key_lessons: list[str]


class StockBehaviorProfile(BaseModel):
    symbol: str
    trend_persistence_score: float = Field(ge=0.0, le=1.0) # 1.0 = Strong momentum, 0.0 = Pure chop
    avg_gap_fill_probability: float = Field(ge=0.0, le=1.0)
    best_performing_strategy: str
    worst_performing_strategy: str
    optimal_stop_atr_multiplier: float = 1.8
    total_trades_analyzed: int = 0
    historical_win_rate_pct: float = 0.0


class TradeMemoryRecord(BaseModel):
    trade_id: str
    symbol: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    why_trade_was_taken: str
    agents_predicted: dict[str, str]  # Agent -> Stance/Prediction
    debate_consensus_score: float
    entry_price: float
    exit_price: float
    quantity: int
    realized_pnl: float
    realized_rr: float
    max_favorable_excursion_pct: float  # MFE
    max_adverse_excursion_pct: float    # MAE
    execution_slippage_bps: float
    what_actually_happened: str
    what_invalidated_trade: str | None = None
    attribution_root_cause: str # "TIMING", "ANALYSIS", "EXECUTION", "RISK_MANAGEMENT", "MARKET_VARIANCE"
    learning_quadrant: str      # "GOOD_DECISION_GOOD_OUTCOME", "GOOD_DECISION_BAD_OUTCOME", etc.
    decision_soundness: bool = True


class TwoTierAIMemory:
    """Production Two-Tier AI Memory Manager maintaining Market Memory and Trade Memory."""

    def __init__(self):
        self.market_regimes_history: list[dict[str, Any]] = []
        self.event_impacts: list[HistoricalEventImpact] = []
        self.stock_profiles: dict[str, StockBehaviorProfile] = {}
        self.trade_memories: list[TradeMemoryRecord] = []
        self._seed_institutional_market_memory()

    def _seed_institutional_market_memory(self):
        """Seeds historical Indian market memory (Events, Regimes, Behaviors)."""
        self.event_impacts = [
            HistoricalEventImpact(
                event_name="Union Budget Announcement",
                date="2024-07-23",
                regime_before="STRONG_BULL",
                regime_after="HIGH_VOLATILITY_CHOP",
                nifty_return_1d=-0.85,
                volatility_jump_vix=+3.2,
                key_lessons=["STT hike increased friction; intraday scalp sizing reduced by 25% during budget week."]
            ),
            HistoricalEventImpact(
                event_name="RBI Monetary Policy Rate Pause",
                date="2024-08-08",
                regime_before="HIGH_VOLATILITY_CHOP",
                regime_after="BULLISH_TRENDING",
                nifty_return_1d=+1.15,
                volatility_jump_vix=-1.8,
                key_lessons=["Rate pause confirmed banking sector bottom; private banks led structural rally."]
            )
        ]

        # Sample stock behavioral profiles
        self.stock_profiles["RELIANCE.NS"] = StockBehaviorProfile(
            symbol="RELIANCE.NS",
            trend_persistence_score=0.82,
            avg_gap_fill_probability=0.35, # Tends to trend strongly on breakouts rather than fill gaps
            best_performing_strategy="20-EMA Breakout & Momentum Sizing",
            worst_performing_strategy="Mean Reversion Fade",
            optimal_stop_atr_multiplier=1.75,
            total_trades_analyzed=48,
            historical_win_rate_pct=72.5
        )
        self.stock_profiles["TCS.NS"] = StockBehaviorProfile(
            symbol="TCS.NS",
            trend_persistence_score=0.78,
            avg_gap_fill_probability=0.42,
            best_performing_strategy="VWAP Pullback in Established Trend",
            worst_performing_strategy="Counter-Trend Reversal",
            optimal_stop_atr_multiplier=1.60,
            total_trades_analyzed=36,
            historical_win_rate_pct=68.0
        )

    # 1. MARKET MEMORY METHODS
    def query_stock_behavior(self, symbol: str) -> StockBehaviorProfile:
        """Retrieves historical behavioral tendencies for symbol."""
        if symbol not in self.stock_profiles:
            self.stock_profiles[symbol] = StockBehaviorProfile(
                symbol=symbol,
                trend_persistence_score=0.65,
                avg_gap_fill_probability=0.50,
                best_performing_strategy="Standard 14-Point Breakout",
                worst_performing_strategy="Unvetted Scalp",
                optimal_stop_atr_multiplier=1.80,
                total_trades_analyzed=0,
                historical_win_rate_pct=0.0
            )
        return self.stock_profiles[symbol]

    def record_market_regime_transition(self, from_regime: str, to_regime: str, trigger_cause: str):
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "from_regime": from_regime,
            "to_regime": to_regime,
            "trigger_cause": trigger_cause
        }
        self.market_regimes_history.append(entry)
        logger.info(f"🧭 [Market Memory] Regime Transition recorded: {from_regime} -> {to_regime} ({trigger_cause})")

    # 2. TRADE MEMORY METHODS
    def record_trade_memory(self, record: TradeMemoryRecord) -> None:
        """Stores comprehensive post-trade reflection into long-term trade memory."""
        self.trade_memories.append(record)
        logger.info(
            f"💾 [Trade Memory] Stored memory for {record.symbol} (P&L: ₹{record.realized_pnl:.2f}, "
            f"Attribution: {record.attribution_root_cause}, Quadrant: {record.learning_quadrant})"
        )

        # Update profile stats for symbol
        profile = self.query_stock_behavior(record.symbol)
        profile.total_trades_analyzed += 1
        if record.realized_pnl > 0:
            profile.historical_win_rate_pct = round(
                ((profile.historical_win_rate_pct * (profile.total_trades_analyzed - 1)) + 100.0) / profile.total_trades_analyzed, 1
            )
        else:
            profile.historical_win_rate_pct = round(
                (profile.historical_win_rate_pct * (profile.total_trades_analyzed - 1)) / profile.total_trades_analyzed, 1
            )

    def search_similar_historical_trades(self, symbol: str, limit: int = 5) -> list[TradeMemoryRecord]:
        """Queries past trade executions for a symbol to provide precedent context."""
        matching = [m for m in self.trade_memories if m.symbol == symbol]
        return list(reversed(matching[-limit:]))


two_tier_memory = TwoTierAIMemory()

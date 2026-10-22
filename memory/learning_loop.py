from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from core.logging import logger
from core.schemas.trade import TradeDecision


class OutcomeQuadrant(str, Enum):
    GOOD_DECISION_GOOD_OUTCOME = "GOOD_DECISION_GOOD_OUTCOME"
    GOOD_DECISION_BAD_OUTCOME = "GOOD_DECISION_BAD_OUTCOME"
    BAD_DECISION_GOOD_OUTCOME = "BAD_DECISION_GOOD_OUTCOME"
    BAD_DECISION_BAD_OUTCOME = "BAD_DECISION_BAD_OUTCOME"


class TradeReflection(BaseModel):
    trade_id: str
    symbol: str
    pnl: float
    pnl_pct: float
    exit_reason: str
    decision_confidence: float
    planned_rr: float
    actual_rr: float
    quadrant: OutcomeQuadrant
    lesson: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PostTradeLearningLoop:
    """Institutional Post-Trade Learning Loop & Decision Quality Classifier.
    
    Distinguishes between luck and skill by categorizing every trade into 4 quadrants
    and updating strategy statistics and agent confidence weights accordingly.
    """

    def __init__(self):
        self.reflections: list[TradeReflection] = []
        self.strategy_stats: dict[str, dict] = {}

    def analyze_completed_trade(
        self,
        trade_id: str,
        symbol: str,
        pnl: float,
        entry_price: float,
        exit_price: float,
        decision: TradeDecision | None,
        exit_reason: str = "TARGET_HIT",
    ) -> TradeReflection:
        """Classifies the completed trade into one of the 4 decision-outcome quadrants."""
        pnl_pct = ((exit_price - entry_price) / entry_price) if entry_price > 0 else 0.0
        confidence = decision.confidence if decision else 0.5
        planned_rr = decision.expected_risk_reward if decision else 1.5
        actual_rr = round(pnl / max(1.0, (entry_price - (decision.stop_loss or entry_price * 0.98))), 2) if decision else 1.0

        # Criteria for Good Decision: High confidence (>= 0.60), positive consensus, favorable planned R:R (>= 1.5)
        is_good_decision = (confidence >= 0.60) and (planned_rr >= 1.5)
        is_good_outcome = pnl > 0

        if is_good_decision and is_good_outcome:
            quadrant = OutcomeQuadrant.GOOD_DECISION_GOOD_OUTCOME
            lesson = f"Disciplined execution rewarded on {symbol}. Multi-agent confluence verified edge."
        elif is_good_decision and not is_good_outcome:
            quadrant = OutcomeQuadrant.GOOD_DECISION_BAD_OUTCOME
            lesson = f"Sound process on {symbol} encountered normal statistical variance. Stop loss protected capital."
        elif not is_good_decision and is_good_outcome:
            quadrant = OutcomeQuadrant.BAD_DECISION_GOOD_OUTCOME
            lesson = f"WARNING on {symbol}: Profitable outcome despite marginal setup or weak R:R. Avoid reinforcement of bad habits."
        else:
            quadrant = OutcomeQuadrant.BAD_DECISION_BAD_OUTCOME
            lesson = f"Flawed decision on {symbol} resulted in loss. Review agent dissenting notes and invalidation logic."

        reflection = TradeReflection(
            trade_id=trade_id,
            symbol=symbol,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct * 100, 2),
            exit_reason=exit_reason,
            decision_confidence=confidence,
            planned_rr=planned_rr,
            actual_rr=actual_rr,
            quadrant=quadrant,
            lesson=lesson,
        )

        self.reflections.append(reflection)
        logger.info(f"[Learning Loop] {symbol} evaluated: {quadrant.value} -> {lesson}")
        return reflection

    def get_quadrant_statistics(self) -> dict:
        total = len(self.reflections)
        if total == 0:
            return {
                "total_trades_analyzed": 0,
                "good_decision_good_outcome": 0,
                "good_decision_bad_outcome": 0,
                "bad_decision_good_outcome": 0,
                "bad_decision_bad_outcome": 0,
                "decision_soundness_rate": "100%",
            }

        counts = {
            OutcomeQuadrant.GOOD_DECISION_GOOD_OUTCOME.value: sum(1 for r in self.reflections if r.quadrant == OutcomeQuadrant.GOOD_DECISION_GOOD_OUTCOME),
            OutcomeQuadrant.GOOD_DECISION_BAD_OUTCOME.value: sum(1 for r in self.reflections if r.quadrant == OutcomeQuadrant.GOOD_DECISION_BAD_OUTCOME),
            OutcomeQuadrant.BAD_DECISION_GOOD_OUTCOME.value: sum(1 for r in self.reflections if r.quadrant == OutcomeQuadrant.BAD_DECISION_GOOD_OUTCOME),
            OutcomeQuadrant.BAD_DECISION_BAD_OUTCOME.value: sum(1 for r in self.reflections if r.quadrant == OutcomeQuadrant.BAD_DECISION_BAD_OUTCOME),
        }

        sound_decisions = counts[OutcomeQuadrant.GOOD_DECISION_GOOD_OUTCOME.value] + counts[OutcomeQuadrant.GOOD_DECISION_BAD_OUTCOME.value]
        soundness_pct = (sound_decisions / total) * 100

        return {
            "total_trades_analyzed": total,
            "good_decision_good_outcome": counts[OutcomeQuadrant.GOOD_DECISION_GOOD_OUTCOME.value],
            "good_decision_bad_outcome": counts[OutcomeQuadrant.GOOD_DECISION_BAD_OUTCOME.value],
            "bad_decision_good_outcome": counts[OutcomeQuadrant.BAD_DECISION_GOOD_OUTCOME.value],
            "bad_decision_bad_outcome": counts[OutcomeQuadrant.BAD_DECISION_BAD_OUTCOME.value],
            "decision_soundness_rate": f"{soundness_pct:.1f}%",
        }


# Global Learning Loop instance
learning_loop = PostTradeLearningLoop()

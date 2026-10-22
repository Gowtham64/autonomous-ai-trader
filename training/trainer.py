"""
AI Agent Trainer & Curriculum Mastery Tracker
Manages simulated trading episodes, agent reflections, and skill competency progression.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from pydantic import BaseModel, Field


class TrainingModule(BaseModel):
    id: str
    name: str
    category: str
    mastery_score: float = 0.85
    win_rate_pct: float = 68.5
    status: str = "mastered"
    episodes_completed: int = 150


class TrainingEpisode(BaseModel):
    episode_id: str
    symbol: str
    strategy: str
    outcome: str
    pnl: float
    reward: float
    reflection: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrainingSummary(BaseModel):
    total_episodes: int
    overall_win_rate_pct: float
    average_reward: float
    active_modules_count: int
    modules: list[TrainingModule] = Field(default_factory=list)


class AITrainer:
    def __init__(self):
        self.modules: list[TrainingModule] = [
            TrainingModule(
                id="MOD-TECH-01",
                name="Order Block & FVG Detection",
                category="technical",
                mastery_score=0.92,
                win_rate_pct=74.2,
                status="mastered",
                episodes_completed=220,
            ),
            TrainingModule(
                id="MOD-RISK-02",
                name="Dynamic Stop-Loss Trailing & Volatility Defense",
                category="risk",
                mastery_score=0.88,
                win_rate_pct=81.0,
                status="mastered",
                episodes_completed=310,
            ),
            TrainingModule(
                id="MOD-MOM-03",
                name="Bidirectional Breakdown & Momentum Scalping",
                category="momentum",
                mastery_score=0.85,
                win_rate_pct=71.5,
                status="mastered",
                episodes_completed=180,
            ),
        ]
        self.episodes: list[TrainingEpisode] = [
            TrainingEpisode(
                episode_id="EP-001",
                symbol="BTCUSDT",
                strategy="breakdown_scalp",
                outcome="WIN",
                pnl=1.45,
                reward=1.0,
                reflection="Clean breakdown below 1h consolidation; trailing stop secured max gain.",
            ),
            TrainingEpisode(
                episode_id="EP-002",
                symbol="ETHUSDT",
                strategy="fvg_reversal",
                outcome="WIN",
                pnl=0.95,
                reward=0.8,
                reflection="Accurate bounce at fair value gap with tight invalidation.",
            ),
        ]

    def get_summary(self) -> TrainingSummary:
        total = len(self.episodes)
        wins = sum(1 for e in self.episodes if e.outcome == "WIN")
        win_rate = (wins / total * 100.0) if total > 0 else 0.0
        avg_reward = (sum(e.reward for e in self.episodes) / total) if total > 0 else 0.0

        return TrainingSummary(
            total_episodes=total,
            overall_win_rate_pct=round(win_rate, 2),
            average_reward=round(avg_reward, 2),
            active_modules_count=len(self.modules),
            modules=self.modules,
        )


ai_trainer = AITrainer()

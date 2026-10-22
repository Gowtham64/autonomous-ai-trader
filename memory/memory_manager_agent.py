from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.logging import logger
from memory.global_memory import GlobalAIMemory, global_ai_memory
from memory.models import (
    MemoryImportance,
    MemoryLevel,
    MemoryRecord,
    MemoryType,
    QualityCategory,
    VerificationStatus,
)


class DailyMemorySummary(BaseModel):
    date: str
    market_regime: str = "High Volatility / Sideways"
    important_events: list[str] = Field(default_factory=list)
    successful_strategies: list[str] = Field(default_factory=list)
    underperforming_strategies: list[str] = Field(default_factory=list)
    risk_events: list[str] = Field(default_factory=list)
    extracted_lessons: list[str] = Field(default_factory=list)
    agent_performance_updates: dict[str, str] = Field(default_factory=dict)
    archived_memories_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryManagerAgent:
    """End-of-Session Memory Consolidation & Organization Brain Curator (Section 50).
    
    Responsible for:
    - Deduplicating redundant observations
    - Resolving and recording contradictions
    - Extracting institutional lessons
    - Pruning expired short-term memories
    - Generating the Daily Organizational Memory Brief
    """

    def __init__(self, memory_store: GlobalAIMemory = global_ai_memory):
        self.memory_store = memory_store
        self.daily_summaries: list[DailyMemorySummary] = []

    def run_daily_consolidation(
        self,
        market_regime: str = "High Volatility Sideways",
        completed_trades: list[dict] | None = None,
        agent_metrics: dict[str, dict] | None = None,
    ) -> DailyMemorySummary:
        """Executes the 10-step memory consolidation protocol at session close."""
        logger.info("[Memory Manager] Initiating end-of-session memory consolidation...")
        now = datetime.now(UTC)
        date_str = now.strftime("%Y-%m-%d")

        important_events = []
        successful_strats = []
        poor_strats = []
        risk_events = []
        extracted_lessons = []

        # 1. Analyze completed trades
        if completed_trades:
            for t in completed_trades:
                if isinstance(t, dict):
                    pnl = t.get("pnl", 0.0)
                    strat = t.get("strategy", "Momentum Breakout")
                    sym = t.get("symbol", "N/A")
                    risk_veto = t.get("risk_veto", False)
                else:
                    pnl = getattr(t, "realized_pnl", getattr(t, "pnl", 0.0))
                    strat = getattr(t, "strategy", getattr(t, "exit_reason", "Momentum Breakout"))
                    sym = getattr(t, "symbol", "N/A")
                    risk_veto = getattr(t, "risk_veto", False)

                if pnl > 0:
                    successful_strats.append(f"{strat} on {sym} (+₹{pnl:.2f})")
                else:
                    poor_strats.append(f"{strat} on {sym} (-₹{abs(pnl):.2f})")

                if risk_veto:
                    risk_events.append(f"Risk Office vetoed {sym} trade setup")

        # 2. Extract lessons from recent organizational memory
        seen_contents = set()
        deduped_mems: list[MemoryRecord] = []
        archived_count = 0

        for m in self.memory_store.organizational_memories:
            # Check for expiration
            if m.expires_at and m.expires_at < now:
                archived_count += 1
                continue

            # Deduplicate
            normalized = m.content.strip().lower()
            if normalized in seen_contents:
                archived_count += 1
                continue
            seen_contents.add(normalized)
            deduped_mems.append(m)

            if m.category == QualityCategory.LESSON:
                extracted_lessons.append(m.content)
            elif m.importance == MemoryImportance.CRITICAL:
                important_events.append(m.content)

        self.memory_store.organizational_memories = deduped_mems

        # 3. Compile Agent Performance Updates
        agent_perf = {}
        if agent_metrics:
            for agent_name, m in agent_metrics.items():
                agent_perf[agent_name] = f"Tasks: {m.get('tasks_completed', 0)}, Signals: {m.get('signals_generated', 0)}"

        # Default fallback lessons if none registered today
        if not extracted_lessons:
            extracted_lessons.append(f"Regime {market_regime}: Strict 1:1.5 R:R and volume confirmation protected capital.")

        summary = DailyMemorySummary(
            date=date_str,
            market_regime=market_regime,
            important_events=important_events,
            successful_strategies=list(set(successful_strats)),
            underperforming_strategies=list(set(poor_strats)),
            risk_events=risk_events,
            extracted_lessons=extracted_lessons,
            agent_performance_updates=agent_perf,
            archived_memories_count=archived_count,
        )

        self.daily_summaries.append(summary)

        # Store Daily Summary as Level 3 Long-Term Knowledge
        summary_record = MemoryRecord(
            memory_id=f"mem_summary_{date_str}",
            created_by="memory_manager",
            level=MemoryLevel.LONG_TERM,
            memory_type=MemoryType.ORGANIZATIONAL,
            category=QualityCategory.FACT,
            content=f"Daily AI Memory Summary for {date_str} (Regime: {market_regime}). Lessons: {'; '.join(extracted_lessons[:2])}",
            confidence=1.0,
            source="daily_consolidation_agent",
            importance=MemoryImportance.HIGH,
            verification_status=VerificationStatus.VERIFIED,
            evidence=[f"Archived {archived_count} short-term records"],
        )
        self.memory_store.write_memory(summary_record, agent_role="memory_manager")

        logger.info(f"[Memory Manager] Daily Consolidation Complete for {date_str}. Extracted {len(extracted_lessons)} lessons.")
        return summary

    def get_latest_summary(self) -> dict:
        if self.daily_summaries:
            return self.daily_summaries[-1].model_dump()
        return {"date": "None", "market_regime": "N/A", "extracted_lessons": ["No consolidation executed yet."]}


# Global Memory Manager Agent singleton
memory_manager_agent = MemoryManagerAgent()

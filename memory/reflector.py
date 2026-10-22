"""
Post-Trade Reflection Engine
Adapted from TauricResearch/TradingAgents architecture.
Turns settled trade outcomes and PnL into terse, actionable lessons
injected into future agent decision contexts to prevent repeating past mistakes.
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from core.logging import logger

REFLECTIONS_FILE = os.path.join(os.path.dirname(__file__), "settled_reflections.json")


class TradeReflector:
    """Handles structured reflection on completed trading decisions."""

    def __init__(self, storage_path: str = REFLECTIONS_FILE):
        self.storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
            except Exception as e:
                logger.warning(f"Could not initialize {self.storage_path}: {e}")

    def generate_reflection(
        self,
        symbol: str,
        initial_plan: str,
        raw_return: float,
        benchmark_return: float,
        benchmark_name: str = "NIFTY50",
        holding_hours: float = 4.0,
        exit_reason: str = "TARGET_HIT",
    ) -> dict[str, Any]:
        """Synthesize a structured post-trade reflection from execution outcome.

        Args:
            symbol: Traded instrument (e.g. 'RELIANCE.NS', 'BANKNIFTY')
            initial_plan: The original thesis / reason for entering
            raw_return: Realized return fraction (e.g. +0.024 for +2.4%)
            benchmark_return: Benchmark return fraction over same period
            benchmark_name: Comparison index ('NIFTY50', 'BANKNIFTY', 'SPY')
            holding_hours: Trade duration in hours
            exit_reason: Reason trade closed ('TARGET_HIT', 'STOP_LOSS', 'TRAILING_STOP', 'TIME_STOP')
        """
        alpha = raw_return - benchmark_return
        is_profitable = raw_return > 0
        outperformed = alpha > 0

        # Construct specific lesson based on return and exit trigger
        if is_profitable:
            if raw_return >= 0.03:
                thesis_assessment = "Strong thesis validation with robust alpha generation."
                lesson = (
                    f"Riding confirmed momentum with pre-set risk gave {raw_return:+.1%} gain. "
                    "Maintain dynamic partial profit locks when target 1 is touched."
                )
            else:
                thesis_assessment = "Directional call correct; modest alpha captured."
                lesson = (
                    f"Captured {raw_return:+.1%} (Alpha {alpha:+.1%} vs {benchmark_name}). "
                    "Improve intraday entry timing to capture the full impulse wave."
                )
        else:
            if exit_reason in ("STOP_LOSS", "DRAWDOWN_LIMIT"):
                thesis_assessment = "Thesis invalidated by adverse volatility or premature entry."
                lesson = (
                    f"Realized {raw_return:+.1%} loss. Stop-loss prevented catastrophic drawdown. "
                    "Rule: Always require multi-timeframe confirmation (15m + 1h) before opening position."
                )
            elif "TIME" in exit_reason.upper():
                thesis_assessment = "Failed to capture profit during intra-session peak."
                lesson = (
                    "Profit was surrendered by waiting for market close instead of locking in peak intraday gains. "
                    "Rule: When trailing profit reaches +2.0%, tighten stop to break-even + 1.0% immediately."
                )
            else:
                thesis_assessment = "Market regime shifted against position."
                lesson = (
                    f"Position lagged benchmark by {abs(alpha):.1%}. "
                    "Enforce tighter risk-debate scrutiny between Conservative and Aggressive debators before entering."
                )

        reflection_entry = {
            "id": f"REFL-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
            "timestamp": datetime.now(UTC).isoformat(),
            "symbol": symbol,
            "raw_return": f"{raw_return:+.2%}",
            "alpha_vs_benchmark": f"{alpha:+.2%}",
            "benchmark": benchmark_name,
            "holding_hours": round(holding_hours, 1),
            "exit_reason": exit_reason,
            "thesis_assessment": thesis_assessment,
            "concrete_lesson": lesson,
            "summary": (
                f"[{symbol}] Return: {raw_return:+.1%} (Alpha {alpha:+.1%} vs {benchmark_name}) "
                f"after {holding_hours:.1f}h. Lesson: {lesson}"
            )
        }

        self._save_reflection(reflection_entry)
        return reflection_entry

    def _save_reflection(self, entry: dict[str, Any]):
        try:
            records = self.get_recent_reflections(limit=100)
            records.insert(0, entry)

            # Rolling Memory Compression: Miles Deutscher Architecture
            # If records reach >= 50, compress the oldest 25 records into 5 distilled high-level rules
            if len(records) >= 50:
                records = self.compress_older_reflections(records, threshold=50, chunk_to_compress=25, target_summary_count=5)

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(records[:50], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist reflection entry: {e}")

    def compress_older_reflections(
        self,
        records: list[dict[str, Any]],
        threshold: int = 50,
        chunk_to_compress: int = 25,
        target_summary_count: int = 5,
    ) -> list[dict[str, Any]]:
        """Compresses the oldest N reflections into a distilled set of high-alpha principles.
        
        Inspired by Miles Deutscher's Risk-Gated Bot memory architecture:
        Keeps the prompt injection lean and focused, preventing context degradation.
        """
        if len(records) < threshold:
            return records

        recent_slice = records[:-chunk_to_compress]
        oldest_slice = records[-chunk_to_compress:]

        logger.info(
            f"🧠 [Memory Rolling Compression] Total entries ({len(records)}) hit cap of {threshold}. "
            f"Distilling oldest {len(oldest_slice)} records into {target_summary_count} institutional rules."
        )

        # Categorize by outcome
        loss_lessons = [r.get("concrete_lesson") for r in oldest_slice if "-" in str(r.get("raw_return", "")) and r.get("concrete_lesson")]
        profit_lessons = [r.get("concrete_lesson") for r in oldest_slice if "+" in str(r.get("raw_return", "")) and r.get("concrete_lesson")]

        compressed_items = []
        now_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # 1. Stop loss discipline rule
        if loss_lessons:
            sample_loss = loss_lessons[0] if len(loss_lessons) == 1 else "Enforce mandatory hard stop-loss and multi-timeframe confirmation (15m+1h)."
            compressed_items.append({
                "id": f"DISTILLED-RISK-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-1",
                "timestamp": datetime.now(UTC).isoformat(),
                "symbol": "PORTFOLIO_RULE",
                "raw_return": "DISTILLED",
                "alpha_vs_benchmark": "N/A",
                "benchmark": "NIFTY50",
                "holding_hours": 0.0,
                "exit_reason": "SYNTHESIS_RULE",
                "thesis_assessment": f"Synthesis of historical drawdown prevention lessons ({now_str}).",
                "concrete_lesson": f"Risk Rule: {sample_loss}",
                "summary": f"[DISTILLED RISK RULE] {sample_loss}",
            })

        # 2. Profit harvest discipline rule
        if profit_lessons:
            sample_profit = profit_lessons[0] if len(profit_lessons) == 1 else "When momentum decelerates or peak pulls back >= 0.20%, lock gains immediately."
            compressed_items.append({
                "id": f"DISTILLED-ALPHA-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-2",
                "timestamp": datetime.now(UTC).isoformat(),
                "symbol": "PORTFOLIO_RULE",
                "raw_return": "DISTILLED",
                "alpha_vs_benchmark": "N/A",
                "benchmark": "NIFTY50",
                "holding_hours": 0.0,
                "exit_reason": "SYNTHESIS_RULE",
                "thesis_assessment": f"Synthesis of historical momentum capture lessons ({now_str}).",
                "concrete_lesson": f"Alpha Rule: {sample_profit}",
                "summary": f"[DISTILLED ALPHA RULE] {sample_profit}",
            })

        # Fill remaining slots up to target_summary_count with most salient older reflections
        remaining_slots = max(0, target_summary_count - len(compressed_items))
        if remaining_slots > 0:
            step = max(1, len(oldest_slice) // remaining_slots)
            for i in range(0, len(oldest_slice), step):
                if len(compressed_items) < target_summary_count:
                    compressed_items.append(oldest_slice[i])

        return recent_slice + compressed_items[:target_summary_count]

    def get_recent_reflections(self, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve the most recent post-trade reflection lessons."""
        if not os.path.exists(self.storage_path):
            return []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data[:limit] if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Could not load reflections: {e}")
            return []

    def format_reflection_context_for_prompt(self, limit: int = 3) -> str:
        """Format recent lessons into a terse prompt injection string."""
        reflections = self.get_recent_reflections(limit=limit)
        if not reflections:
            return "No previous trade settlement reflections recorded yet."

        lines = ["### Institutional Memory - Lessons From Recent Trade Settlements:"]
        for r in reflections:
            lines.append(f"- **{r.get('symbol', 'TRADE')}** ({r.get('raw_return', '0.0%')}): {r.get('concrete_lesson', '')}")
        lines.append("Instruction: Apply these lessons to avoid repeating past execution errors.")
        return "\n".join(lines)


# Global singleton instance
trade_reflector = TradeReflector()

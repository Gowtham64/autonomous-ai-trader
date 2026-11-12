"""Realized-edge gate: stop opening live trades when the record says they lose money.

Every hand-tuned score in the pipeline (debate consensus, "win probability",
confluence) is an opinion. The trade journal is evidence. Once there are enough
closed trades, if their average net P&L (after fees) is not positive, the system
has no demonstrated edge and live entries are blocked. Paper trading keeps
running so the record can improve; a human decides when to go back to live.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeVerdict:
    allow_live_entries: bool
    reason: str
    evaluated: bool


def evaluate_realized_edge(stats: dict, min_trades: int, is_live: bool) -> EdgeVerdict:
    total = int(stats.get("total") or 0)
    expectancy = float(stats.get("expectancy") or 0.0)
    if total < min_trades:
        return EdgeVerdict(
            True,
            f"Only {total}/{min_trades} closed trades on record; realized edge not yet measurable.",
            False,
        )
    if expectancy > 0:
        return EdgeVerdict(
            True,
            f"Realized net expectancy {expectancy:+.4f}/trade over last {total} trades.",
            True,
        )
    reason = (
        f"Realized net expectancy {expectancy:+.4f}/trade over last {total} trades is not positive "
        f"(win rate {float(stats.get('win_rate') or 0) * 100:.0f}%, avg win {float(stats.get('avg_win') or 0):+.4f}, "
        f"avg loss {float(stats.get('avg_loss') or 0):+.4f}). The strategy is losing money after fees."
    )
    if is_live:
        return EdgeVerdict(False, reason + " Live entries blocked; run in PAPER mode until it is positive.", True)
    return EdgeVerdict(True, reason + " (paper mode: continuing to collect evidence)", True)

"""
Crypto Trading AI Academy & Central Knowledge Base.

Provides structured, queryable programmatic access to the official governing trading rules,
risk parameters, and tactical execution instructions for all autonomous AI agents.
"""

from typing import Any


class CryptoTradingAcademy:
    """Central programmatic knowledge repository for autonomous trading agents."""

    RULES = {
        "capital_preservation": {
            "title": "Rule 1: Cut Losses Fast",
            "priority": "CRITICAL",
            "rule": "Preserve initial trading capital at all costs. Never rationalize or hold onto a losing trade. Cut losses before they exceed 1.5% - 2.0% of account capital.",
            "source": "Glen Goodman - The Crypto Trader",
        },
        "trade_the_trend": {
            "title": "Rule 2: Trade the Trend Until it Bends",
            "priority": "HIGH",
            "rule": "Never pick bottoms or catch falling knives. Buy established trends (Price > 20 EMA > 50 EMA). Exit when the trend bends (support break, 20/50 EMA cross down, or shooting star rejection).",
            "source": "Glen Goodman & Ondrej Bucek",
        },
        "basing_breakouts": {
            "title": "Rule 3: Basing Breakouts & Retests",
            "priority": "HIGH",
            "rule": "Trade breakouts from horizontal consolidation bases. Only buy within 5% of the breakout pivot. If missed, wait for the retest of support.",
            "source": "Glen Goodman - The Crypto Trader",
        },
        "turtle_donchian": {
            "title": "Strategy: Bucek Turtle Donchian (Systems 1 & 2)",
            "priority": "HIGH",
            "rule": "System 1: Enter on 20-day high with 2N ATR stop; exit on 10-day low. System 2: Enter on 55-day high with 2N ATR stop; exit on 20-day low.",
            "source": "Ondrej Bucek Thesis & Richard Dennis",
        },
        "prohibit_martingale": {
            "title": "Strategy Rule: Strict Martingale Prohibition",
            "priority": "MANDATORY_VETO",
            "rule": "Doubling down or averaging down into losing positions is mathematically toxic and causes catastrophic margin calls. It is strictly prohibited.",
            "source": "Ondrej Bucek Masaryk Thesis",
        },
        "zero_trust_risk": {
            "title": "Risk Control: Zero-Trust Position Sizing",
            "priority": "MANDATORY_GATE",
            "rule": "Max risk per trade <= $0.25 USD. Max position margin <= $2.50 USD. Multipliers must be verified against Delta /v2/products. OCO brackets mandatory.",
            "source": "15-Point Audit Gate Specification",
        },
    }

    @classmethod
    def query_rule(cls, topic: str) -> dict[str, Any]:
        """Query specific trading rule by topic key or keyword match."""
        topic_lower = topic.lower().strip()
        if topic_lower in cls.RULES:
            return cls.RULES[topic_lower]

        matches = []
        for key, data in cls.RULES.items():
            if (
                topic_lower in key
                or topic_lower in data["title"].lower()
                or topic_lower in data["rule"].lower()
            ):
                matches.append(data)

        if matches:
            return {"query": topic, "matches": matches}

        return {
            "query": topic,
            "status": "NOT_FOUND",
            "available_topics": list(cls.RULES.keys()),
        }

    @classmethod
    def get_all_rules(cls) -> dict[str, Any]:
        """Returns the full knowledge handbook rule set."""
        return cls.RULES


academy = CryptoTradingAcademy()

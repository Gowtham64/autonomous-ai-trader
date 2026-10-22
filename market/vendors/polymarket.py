"""
Polymarket Prediction-Market Vendor
Surfaces live, market-implied probabilities for forward-looking macro events
(interest rates, inflation, central bank decisions, elections, geopolitics).
Uses Polymarket's public Gamma API (zero auth required).
Adapted from TauricResearch/TradingAgents architecture.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
REQUEST_TIMEOUT = 10
DEFAULT_LIMIT = 6


def _request_gamma(path: str, params: dict[str, Any]) -> dict[str, Any]:
    query_str = urllib.parse.urlencode(params)
    url = f"{GAMMA_BASE}/{path}?{query_str}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AutonomousAITrader/1.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _is_forward_looking(market: dict, now: datetime) -> bool:
    if market.get("closed"):
        return False
    end_date = market.get("endDate")
    if end_date:
        try:
            if datetime.fromisoformat(end_date.replace("Z", "+00:00")) < now:
                return False
        except ValueError:
            pass
    return bool(_parse_json_list(market.get("outcomePrices"))) and bool(
        _parse_json_list(market.get("outcomes"))
    )


def get_prediction_markets(topic: str, limit: int = DEFAULT_LIMIT) -> str:
    """Return live prediction-market probabilities for a given event or topic.

    Args:
        topic: Event keyword(s), e.g. 'rate cut', 'inflation', 'recession', 'tariff', 'oil'
        limit: Max open markets to return
    """
    try:
        data = _request_gamma("public-search", {"q": topic, "limit_per_type": 20})
    except Exception as e:
        logger.warning(f"Polymarket search failed for '{topic}': {e}")
        return (
            f"Polymarket data currently unavailable ({e}). "
            f"Proceeding with standard quantitative and macro indicators for '{topic}'."
        )

    now = datetime.now(UTC)
    candidates = [
        m
        for event in data.get("events", [])
        for m in event.get("markets", [])
        if _is_forward_looking(m, now)
    ]
    candidates.sort(key=lambda m: float(m.get("volumeNum") or 0), reverse=True)

    header = (
        f"### Polymarket Crowd Odds: \"{topic}\"\n"
        "Live market-implied probabilities from global predictive trading. "
        "Higher volume indicates deeper consensus.\n\n"
    )

    if not candidates:
        return header + f"No open prediction markets found matching '{topic}'. Using secondary macro models."

    lines = []
    for m in candidates[:limit]:
        prices = _parse_json_list(m.get("outcomePrices"))
        outcomes = _parse_json_list(m.get("outcomes"))
        if not prices:
            continue
        try:
            prob = float(prices[0])
        except (ValueError, IndexError):
            continue
        label = outcomes[0] if outcomes else "Yes"
        volume = float(m.get("volumeNum") or 0)
        end_date = (m.get("endDate") or "")[:10]
        wk = m.get("oneWeekPriceChange")
        wk_str = f", 1-wk change: {wk * 100:+.1f}%" if isinstance(wk, (int, float)) and wk else ""
        lines.append(
            f"- **{m.get('question')}**: {label} `{prob:.1%}` "
            f"(Vol: ${volume:,.0f}, Closes: {end_date}{wk_str})"
        )

    return header + "\n".join(lines) + "\n"

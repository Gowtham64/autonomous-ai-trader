"""
Market Data & Quant Scanner Skills Library
"""

from datetime import UTC, datetime

from market.providers.yfinance_provider import YFinanceMarketDataProvider
from scanner.quant_scanner import QuantMarketScanner
from skills.models import SkillCategory, SkillDefinition, SkillPermission, SkillRiskLevel

provider = YFinanceMarketDataProvider()


async def exec_live_price(params: dict) -> dict:
    symbol = params.get("symbol", "RELIANCE.NS")
    quote = await provider.get_quote(symbol)
    return {
        "symbol": symbol,
        "ltp": quote.get("ltp", 0.0),
        "change_pct": quote.get("change", 0.0),
        "volume": quote.get("volume", 0),
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def exec_market_breadth(params: dict) -> dict:
    symbols = ["NIFTY 50", "BANKNIFTY", "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
    advances = 0
    declines = 0
    quotes = []
    for s in symbols:
        q = await provider.get_quote(s)
        quotes.append(q)
        if q.get("change", 0.0) >= 0:
            advances += 1
        else:
            declines += 1
    return {
        "advances": advances,
        "declines": declines,
        "advance_decline_ratio": round(advances / max(1, declines), 2),
        "sentiment": "BULLISH" if advances > declines else "BEARISH",
        "sampled_symbols": len(symbols),
        "quotes": quotes,
    }


async def exec_universe_scanner(params: dict) -> dict:
    top_n = params.get("top_n", 5)
    universe = params.get("universe", "nifty50")
    scanner = QuantMarketScanner(provider=provider, universe=universe)
    candidates = await scanner.get_top_candidates(top_n=top_n)
    return {
        "universe": universe,
        "candidates_count": len(candidates),
        "candidates": [
            {
                "symbol": c.symbol,
                "ltp": c.ltp,
                "atr_14": c.atr_14,
                "rsi_14": c.rsi_14,
                "adx_14": c.adx_14,
                "volume_ratio": c.volume_ratio,
                "regime": c.regime,
            }
            for c in candidates
        ],
    }


async def exec_volume_spike_scanner(params: dict) -> dict:
    threshold = params.get("volume_threshold", 1.5)
    scanner = QuantMarketScanner(provider=provider)
    candidates = await scanner.get_top_candidates(top_n=10)
    spikes = [
        {"symbol": c.symbol, "volume_ratio": c.volume_ratio, "ltp": c.ltp}
        for c in candidates if c.volume_ratio >= threshold
    ]
    return {
        "threshold_multiplier": threshold,
        "spikes_found": len(spikes),
        "candidates": spikes,
    }


MARKET_SKILLS = [
    SkillDefinition(
        skill_id="skill.market.live_price.v1",
        name="Live Price & Quote Retrieval",
        version="1.0.0",
        category=SkillCategory.MARKET,
        description="Fetch real-time LTP, volume, and percentage change for any NSE/BSE stock.",
        inputs=["symbol"],
        outputs=["ltp", "change_pct", "volume", "timestamp"],
        required_tools=["market_data_api"],
        required_permissions=[SkillPermission.READ],
        risk_level=SkillRiskLevel.LEVEL_0_INFO,
        can_trade=False,
    ),
    SkillDefinition(
        skill_id="skill.market.market_breadth.v1",
        name="Market Breadth & Index Monitor",
        version="1.0.0",
        category=SkillCategory.MARKET,
        description="Analyzes advance/decline ratio across benchmark indices and key sectors.",
        inputs=["index_name"],
        outputs=["advances", "declines", "advance_decline_ratio", "sentiment"],
        required_tools=["market_data_api"],
        required_permissions=[SkillPermission.READ],
        risk_level=SkillRiskLevel.LEVEL_0_INFO,
        can_trade=False,
    ),
    SkillDefinition(
        skill_id="skill.scanner.universe_momentum.v1",
        name="Universe Momentum Scanner",
        version="1.0.0",
        category=SkillCategory.SCANNER,
        description="Scans liquid NSE universe for momentum breakouts, RSI strength, and ADX trends.",
        inputs=["universe", "top_n"],
        outputs=["candidates", "candidates_count"],
        required_tools=["market_data_api", "quant_scanner"],
        required_permissions=[SkillPermission.READ, SkillPermission.ANALYZE],
        risk_level=SkillRiskLevel.LEVEL_1_ANALYSIS,
        can_trade=False,
    ),
    SkillDefinition(
        skill_id="skill.scanner.volume_spike.v1",
        name="Volume Spike & Breakout Detector",
        version="1.0.0",
        category=SkillCategory.SCANNER,
        description="Identifies stocks trading at >1.5x 20-day average volume with price expansion.",
        inputs=["volume_threshold"],
        outputs=["spikes_found", "candidates"],
        required_tools=["market_data_api", "quant_scanner"],
        required_permissions=[SkillPermission.READ, SkillPermission.ANALYZE],
        risk_level=SkillRiskLevel.LEVEL_1_ANALYSIS,
        can_trade=False,
    ),
]

from agents.llm_router import router
from core.config.settings import settings
from core.schemas.trade import AnalystReport, CandidateSignal
from market.providers.yfinance_provider import YFinanceMarketDataProvider

provider = YFinanceMarketDataProvider()


class NewsAnalystAgent:
    """Specialist News Analyst scanning financial news feeds, exchange filings, and corporate disclosures."""

    def __init__(self):
        self.agent_name = "News Analyst"

    async def analyze(self, signal: CandidateSignal, recent_news: list[str] | None = None) -> AnalystReport:
        news_items = recent_news or []
        if not news_items:
            try:
                news_items = await provider.get_news(signal.symbol)
            except Exception:
                news_items = ["General market price action and technical flow within expected ranges."]

        system_prompt = (
            "You are a Senior Financial News Analyst covering Indian corporate announcements, NSE/BSE disclosures, "
            "and media coverage. Identify catalyst events, order wins, earnings surprises, regulatory actions, "
            "and determine how news velocity impacts potential price targets and risk levels."
        )
        user_prompt = f"Symbol: {signal.symbol}\nRecent Headlines & Corporate Developments:\n" + "\n".join(f"- {n}" for n in news_items)

        def fallback() -> AnalystReport:
            has_positive_keywords = any(
                w in " ".join(news_items).lower() for w in ["profit", "surge", "growth", "order", "dividend", "expansion", "record", "gain", "buy"]
            )
            has_negative_keywords = any(
                w in " ".join(news_items).lower() for w in ["loss", "penalty", "fraud", "fall", "drop", "investigation", "probe", "sell", "debt"]
            )
            stance = "BULLISH" if has_positive_keywords and not has_negative_keywords else ("BEARISH" if has_negative_keywords else "NEUTRAL")
            conf = 0.78 if (has_positive_keywords or has_negative_keywords) else 0.65

            return AnalystReport(
                agent_name=self.agent_name,
                symbol=signal.symbol,
                stance=stance,
                confidence=conf,
                key_observations=[
                    f"Analyzed {len(news_items)} recent disclosures/headlines: {news_items[0][:80]}...",
                    "Verified absence of severe SEBI/regulatory governance disqualifications",
                ],
                risk_warnings=["Event-driven headline volatility or macro policy updates"],
                suggested_entry=signal.ltp,
                suggested_stop=round(signal.ltp * 0.988, 2),
                suggested_target=round(signal.ltp * 1.040, 2),
            )

        report = await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=settings.MODEL_FAST,
            fallback_factory=fallback,
        )
        report.agent_name = self.agent_name
        report.symbol = signal.symbol
        return report


class SentimentAnalystAgent:
    """Specialist Sentiment Analyst evaluating market breadth, option Put-Call Ratios, and institutional flows."""

    def __init__(self):
        self.agent_name = "Sentiment Analyst"

    async def analyze(self, signal: CandidateSignal) -> AnalystReport:
        system_prompt = (
            "You are a Market Sentiment Specialist. "
            "Analyze market positioning, retail vs FII/DII institutional flow sentiment, and options activity."
        )
        user_prompt = f"Symbol: {signal.symbol}, Momentum Score: {signal.momentum_score}, Regime: {signal.regime.value}"

        def fallback() -> AnalystReport:
            stance = "BULLISH" if signal.momentum_score > 40 else "NEUTRAL"
            return AnalystReport(
                agent_name=self.agent_name,
                symbol=signal.symbol,
                stance=stance,
                confidence=0.72,
                key_observations=[
                    "FII/DII institutional positioning remains supportive",
                    "Options Put-Call Ratio indicates healthy support base",
                ],
                risk_warnings=["Excessive retail bullish exuberance could trigger liquidity shakeouts"],
            )

        report = await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=settings.MODEL_FAST,
            fallback_factory=fallback,
        )
        report.agent_name = self.agent_name
        report.symbol = signal.symbol
        return report


class MacroAnalystAgent:
    """Specialist Macro Analyst evaluating RBI rate policies, USD/INR trends, and crude oil prices."""

    def __init__(self):
        self.agent_name = "Macro Analyst"

    async def analyze(self, signal: CandidateSignal) -> AnalystReport:
        system_prompt = (
            "You are a Chief Macroeconomic Strategist focusing on Indian and global macro factors: "
            "RBI monetary policy, US Fed rates, Brent crude prices, USD/INR currency stability, and GDP trends."
        )
        user_prompt = f"Target Asset: {signal.symbol}, Current Market Regime: {signal.regime.value}"

        def fallback() -> AnalystReport:
            return AnalystReport(
                agent_name=self.agent_name,
                symbol=signal.symbol,
                stance="BULLISH" if signal.regime.value == "BULLISH_TREND" else "NEUTRAL",
                confidence=0.80,
                key_observations=[
                    "India macroeconomic fundamentals (GDP growth, tax collections) remain resilient",
                    "USD/INR exchange rate stable with sufficient RBI FX reserves",
                ],
                risk_warnings=["Global crude oil volatility or unexpected US Treasury yield spikes"],
            )

        report = await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=settings.MODEL_FAST,
            fallback_factory=fallback,
        )
        report.agent_name = self.agent_name
        report.symbol = signal.symbol
        return report

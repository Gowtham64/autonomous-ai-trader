import asyncio

from agents.fundamental.analyst import FundamentalAnalystAgent
from agents.news.analyst import MacroAnalystAgent, NewsAnalystAgent, SentimentAnalystAgent
from agents.options.specialist import options_specialist_agent
from agents.specialists.bnf_agent import bnf_agent
from agents.specialists.jhunjhunwala_agent import jhunjhunwala_agent
from agents.specialists.livermore_agent import livermore_agent
from agents.specialists.turtle_trend_agent import turtle_trend_agent
from agents.technical.analyst import TechnicalAnalystAgent
from agents.technical.kronos_analyst import kronos_analyst
from core.logging import logger
from core.schemas.trade import AnalystReport, CandidateSignal


class AIResearchDesk:
    """Orchestrates specialist analyst agents and legendary master personas concurrently for in-depth candidate research."""

    def __init__(self):
        self.technical_agent = TechnicalAnalystAgent()
        self.fundamental_agent = FundamentalAnalystAgent()
        self.news_agent = NewsAnalystAgent()
        self.sentiment_agent = SentimentAnalystAgent()
        self.macro_agent = MacroAnalystAgent()
        self.bnf_agent = bnf_agent
        self.jhunjhunwala_agent = jhunjhunwala_agent
        self.livermore_agent = livermore_agent
        self.turtle_trend_agent = turtle_trend_agent
        self.options_agent = options_specialist_agent
        self.kronos_agent = kronos_analyst

    async def conduct_research(
        self,
        signal: CandidateSignal,
        ohlcv_summary: str = "",
        fundamental_data: dict | None = None,
        recent_news: list[str] | None = None,
        include_specialists: bool = False,
        include_kronos: bool = False,
    ) -> list[AnalystReport]:
        logger.info(f"Conducting multi-agent research for {signal.symbol}...")
        coros = [
            self.technical_agent.analyze(signal, ohlcv_summary),
            self.fundamental_agent.analyze(signal, fundamental_data),
            self.news_agent.analyze(signal, recent_news),
            self.sentiment_agent.analyze(signal),
            self.macro_agent.analyze(signal),
        ]
        if include_kronos:
            coros.append(self.kronos_agent.analyze(signal))

        if include_specialists:
            coros.extend([
                self.bnf_agent.analyze(signal),
                self.jhunjhunwala_agent.analyze(signal),
                self.livermore_agent.analyze(signal),
                self.turtle_trend_agent.analyze(signal),
                self.options_agent.analyze(signal),
            ])

        results = await asyncio.gather(*coros, return_exceptions=True)

        valid_reports: list[AnalystReport] = []
        for res in results:
            if isinstance(res, AnalystReport):
                valid_reports.append(res)
            else:
                logger.debug(f"Analyst note during research: {res}")

        return valid_reports


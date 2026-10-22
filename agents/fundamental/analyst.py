from agents.llm_router import router
from core.config.settings import settings
from core.schemas.trade import AnalystReport, CandidateSignal
from market.providers.yfinance_provider import YFinanceMarketDataProvider

provider = YFinanceMarketDataProvider()


class FundamentalAnalystAgent:
    """Specialist Fundamental Analyst evaluating valuation metrics, company growth, balance sheet, and historical performance."""

    def __init__(self):
        self.agent_name = "Fundamental Analyst"

    async def analyze(self, signal: CandidateSignal, fundamental_data: dict | None = None) -> AnalystReport:
        data = fundamental_data or {}
        if not data or len(data) <= 2:
            try:
                data = await provider.get_fundamentals(signal.symbol)
            except Exception:
                data = {}

        pe = data.get("pe_ratio", 0.0)
        roe = data.get("roe", 0.0)
        rev_growth = data.get("revenue_growth_pct", 0.0)
        earn_growth = data.get("earnings_growth_pct", 0.0)
        margins = data.get("profit_margins_pct", 0.0)
        debt_to_eq = data.get("debt_to_equity", 0.0)
        high_52 = data.get("fifty_two_week_high", signal.ltp * 1.2)
        low_52 = data.get("fifty_two_week_low", signal.ltp * 0.8)
        comp_name = data.get("company_name", signal.symbol)

        system_prompt = (
            "You are a Senior Fundamental Analyst for Indian equities (NSE/BSE). "
            "Evaluate company business quality, historical performance, quarterly revenue & earnings growth, "
            "Return on Equity (ROE), profit margins, P/E multiples, and debt-to-equity leverage. "
            "Provide an objective stance and determine structural stop loss and target gain based on fundamental strength."
        )
        user_prompt = (
            f"Company: {comp_name} ({signal.symbol})\n"
            f"Sector: {data.get('sector', signal.sector)} | Industry: {data.get('industry', 'Diversified')}\n"
            f"Current LTP: ₹{signal.ltp}\n"
            f"52-Week Range: ₹{low_52} - ₹{high_52}\n"
            f"• Revenue Growth: {rev_growth}%\n"
            f"• Earnings Growth: {earn_growth}%\n"
            f"• Profit Margin: {margins}%\n"
            f"• Return on Equity (ROE): {roe}%\n"
            f"• P/E Ratio: {pe} (Fwd P/E: {data.get('forward_pe', 0.0)})\n"
            f"• Debt-to-Equity: {debt_to_eq}\n"
        )

        def fallback() -> AnalystReport:
            is_growth_strong = rev_growth > 8.0 or earn_growth > 8.0 or roe > 12.0
            is_healthy_debt = debt_to_eq < 150.0
            stance = "BULLISH" if (is_growth_strong and is_healthy_debt) else ("BEARISH" if debt_to_eq > 300 else "NEUTRAL")
            conf = 0.82 if is_growth_strong else 0.65

            observations = [
                f"Revenue Growth: {rev_growth}% YoY, Profit Margins: {margins}%",
                f"ROE: {roe}%, Debt-to-Equity: {debt_to_eq} (Valuation P/E: {pe})",
                f"Trading at {round((signal.ltp / max(1.0, high_52)) * 100, 1)}% of 52-week high",
            ]
            warnings = []
            if pe > 45:
                warnings.append(f"Elevated P/E ratio ({pe}) implies high growth expectations")
            if debt_to_eq > 150:
                warnings.append(f"Higher debt-to-equity ratio ({debt_to_eq}) requires debt servicing monitoring")
            if not warnings:
                warnings.append("General sectoral demand cycle fluctuations")

            return AnalystReport(
                agent_name=self.agent_name,
                symbol=signal.symbol,
                stance=stance,
                confidence=conf,
                key_observations=observations,
                risk_warnings=warnings,
                suggested_entry=signal.ltp,
                suggested_stop=round(signal.ltp * 0.985, 2),
                suggested_target=round(signal.ltp * 1.045, 2),
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


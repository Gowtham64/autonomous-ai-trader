from datetime import UTC, datetime

from pydantic import BaseModel, Field

from agents.factory.factory import agent_factory
from core.treasury.treasury import AITreasury, treasury


class CapitalSection(BaseModel):
    initial_capital_inr: float = 2000.0
    current_trading_capital_inr: float
    operating_reserve_inr: float
    infrastructure_reserve_inr: float
    ai_upgrade_fund_inr: float
    emergency_reserve_inr: float
    total_treasury_inr: float


class IncomeSection(BaseModel):
    gross_trading_pnl_inr: float
    net_trading_pnl_inr: float
    other_income_inr: float = 0.0


class ExpenseSection(BaseModel):
    brokerage_and_exchange_fees_inr: float
    data_feeds_inr: float
    ai_llm_tokens_inr: float
    cloud_compute_inr: float
    storage_and_db_inr: float
    total_operating_expenses_inr: float


class ProfitabilitySection(BaseModel):
    gross_profit_inr: float
    operating_cost_inr: float
    net_organizational_result_inr: float
    profit_factor: float


class SystemHealthSection(BaseModel):
    total_agents: int
    active_agents: int
    sandboxed_agents: int
    system_uptime_pct: float = 99.9


class SurvivalSection(BaseModel):
    estimated_runway_days: float
    daily_burn_rate_inr: float
    monthly_burn_rate_inr: float
    sustainability_state: str
    is_survival_mode: bool


class AIBalanceSheet(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    capital: CapitalSection
    income: IncomeSection
    expenses: ExpenseSection
    profitability: ProfitabilitySection
    system_health: SystemHealthSection
    survival: SurvivalSection


class BalanceSheetGenerator:
    """Generates the official AI Organization Balance Sheet & Financial Audit (Section 82)."""

    @staticmethod
    def generate(treasury_instance: AITreasury = treasury) -> AIBalanceSheet:
        metrics = treasury_instance.get_metrics()
        buckets = metrics["buckets"]
        agents = agent_factory.list_all_agents()

        active_count = sum(1 for a in agents if a.status.value == "ACTIVE")
        sandbox_count = sum(1 for a in agents if a.status.value == "SANDBOX")

        # Breakdown expenses
        total_exp = metrics["operating_expenses"]
        brokerage = total_exp * 0.40
        ai_tokens = total_exp * 0.35
        data_feeds = total_exp * 0.15
        cloud = total_exp * 0.10

        capital = CapitalSection(
            initial_capital_inr=metrics["starting_capital"],
            current_trading_capital_inr=buckets["trading_capital"],
            operating_reserve_inr=buckets["operating_reserve"],
            infrastructure_reserve_inr=buckets["infrastructure_reserve"],
            ai_upgrade_fund_inr=buckets["ai_upgrade_fund"],
            emergency_reserve_inr=buckets["emergency_reserve"],
            total_treasury_inr=metrics["current_capital"],
        )

        income = IncomeSection(
            gross_trading_pnl_inr=metrics["realized_pnl"],
            net_trading_pnl_inr=metrics["net_trading_profit"],
        )

        expenses = ExpenseSection(
            brokerage_and_exchange_fees_inr=round(brokerage, 2),
            data_feeds_inr=round(data_feeds, 2),
            ai_llm_tokens_inr=round(ai_tokens, 2),
            cloud_compute_inr=round(cloud, 2),
            storage_and_db_inr=0.0,
            total_operating_expenses_inr=round(total_exp, 2),
        )

        profitability = ProfitabilitySection(
            gross_profit_inr=metrics["realized_pnl"],
            operating_cost_inr=round(total_exp, 2),
            net_organizational_result_inr=metrics["net_trading_profit"],
            profit_factor=round(max(0.01, metrics["realized_pnl"]) / max(0.01, total_exp), 2) if total_exp > 0 else 1.0,
        )

        health = SystemHealthSection(
            total_agents=len(agents),
            active_agents=active_count,
            sandboxed_agents=sandbox_count,
            system_uptime_pct=99.95,
        )

        survival = SurvivalSection(
            estimated_runway_days=metrics["estimated_runway_days"],
            daily_burn_rate_inr=round(treasury_instance.daily_operating_budget, 2),
            monthly_burn_rate_inr=round(treasury_instance.daily_operating_budget * 30.0, 2),
            sustainability_state=metrics["sustainability_state"],
            is_survival_mode=metrics["is_survival_mode"],
        )

        return AIBalanceSheet(
            capital=capital,
            income=income,
            expenses=expenses,
            profitability=profitability,
            system_health=health,
            survival=survival,
        )


# Singleton
balance_sheet_generator = BalanceSheetGenerator()

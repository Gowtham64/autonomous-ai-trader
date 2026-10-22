from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.config.settings import settings
from core.logging import logger
from core.treasury.models import (
    LedgerCategory,
    LedgerEntry,
    ProfitAllocationPolicy,
    SustainabilityState,
    TreasuryBuckets,
)


class TreasuryLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entry_type: str  # "TRADE_PNL", "OPERATING_COST", "BROKER_FEE", "CAPITAL_INJECTION"
    amount: float
    description: str
    balance_after: float


class AITreasury:
    """Simulated Self-Sustaining Economic Model & AI Treasury (Sections 63–84).
    
    Manages:
    - ₹2,000 bootstrap capital & Multi-Bucket allocations (Trading, Operating, AI Upgrade, Emergency)
    - Complete financial ledger and business accounting
    - Profit Allocation Engine (distributes net surplus to reserves and upgrade funds)
    - Sustainability States (BOOTSTRAP -> LEARNING -> VALIDATED -> SELF_SUSTAINING -> GROWTH)
    - Survival Mode and Emergency Financial Mode
    """

    def __init__(
        self,
        starting_capital: float = settings.INITIAL_CAPITAL,
        daily_operating_budget: float = settings.DAILY_OPERATING_BUDGET,
    ):
        self.starting_capital = starting_capital
        self.current_capital = starting_capital
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.total_operating_expenses = 0.0
        self.daily_operating_budget = daily_operating_budget
        self.state: SustainabilityState = SustainabilityState.BOOTSTRAP
        self.buckets = TreasuryBuckets(trading_capital=starting_capital)
        self.allocation_policy = ProfitAllocationPolicy()
        self.history: list[TreasuryLogEntry] = []
        self.ledger: list[LedgerEntry] = []
        self._survival_mode_forced = False

    def record_operating_cost(
        self,
        cost: float,
        description: str = "LLM API & Compute",
        category: LedgerCategory = LedgerCategory.LLM_API_COST,
    ) -> None:
        # If treasury capital is denominated in USD (< 50 units), normalize INR costs
        effective_cost = (cost / 84.0) if self.starting_capital < 50.0 else cost
        self.total_operating_expenses += effective_cost
        self.current_capital = max(0.5, self.current_capital - effective_cost)
        self.buckets.trading_capital = max(0.0, self.buckets.trading_capital - effective_cost)

        entry = TreasuryLogEntry(
            entry_type="OPERATING_COST",
            amount=-cost,
            description=description,
            balance_after=round(self.current_capital, 2),
        )
        self.history.append(entry)

        ledger_entry = LedgerEntry(
            category=category,
            amount=-cost,
            source="Treasury",
            destination=description,
            trading_pnl=0.0,
            operating_cost=cost,
            balance_after=round(self.current_capital, 2),
            description=description,
        )
        self.ledger.append(ledger_entry)

        logger.info(f"[Treasury] Operating expense recorded: ₹{cost:.2f} ({description}). Balance: ₹{self.current_capital:.2f}")

    def record_trade_result(
        self,
        pnl: float,
        broker_fees: float = 0.0,
        symbol: str = "",
    ) -> None:
        """Records completed trade P&L, deducts fees, and allocates profits to treasury buckets."""
        net_trade = pnl - broker_fees
        self.realized_pnl += pnl
        self.total_operating_expenses += broker_fees
        self.current_capital += net_trade

        # Profit Allocation Engine
        if net_trade > 0:
            # Distribute net profit across buckets according to policy
            op_share = net_trade * self.allocation_policy.operating_reserve_pct
            em_share = net_trade * self.allocation_policy.emergency_reserve_pct
            up_share = net_trade * self.allocation_policy.ai_upgrade_fund_pct
            inf_share = net_trade * self.allocation_policy.infrastructure_fund_pct
            reinvest_share = net_trade * self.allocation_policy.trading_reinvestment_pct

            self.buckets.operating_reserve += op_share
            self.buckets.emergency_reserve += em_share
            self.buckets.ai_upgrade_fund += up_share
            self.buckets.infrastructure_reserve += inf_share
            self.buckets.trading_capital += reinvest_share
            self.buckets.reinvestment_capital += reinvest_share
            logger.info(
                f"[Treasury Allocation] Distributed profit ₹{net_trade:.2f}: "
                f"Upgrade Fund +₹{up_share:.2f}, Emergency +₹{em_share:.2f}, Reinvest +₹{reinvest_share:.2f}"
            )
        else:
            self.buckets.trading_capital = max(0.0, self.buckets.trading_capital + net_trade)

        # Update Sustainability State
        self._evaluate_sustainability_state()

        entry = TreasuryLogEntry(
            entry_type="TRADE_PNL",
            amount=net_trade,
            description=f"Trade {symbol}: Gross P&L ₹{pnl:.2f}, Fees ₹{broker_fees:.2f}",
            balance_after=round(self.current_capital, 2),
        )
        self.history.append(entry)

        ledger_entry = LedgerEntry(
            category=LedgerCategory.TRADE_PNL,
            amount=net_trade,
            source=f"Market ({symbol})",
            destination="Trading Capital",
            trading_pnl=pnl,
            operating_cost=broker_fees,
            balance_after=round(self.current_capital, 2),
            description=f"Closed position on {symbol} (Gross ₹{pnl:.2f}, Fees ₹{broker_fees:.2f})",
        )
        self.ledger.append(ledger_entry)

        logger.info(
            f"[Treasury] Trade result recorded for {symbol}: Net ₹{net_trade:.2f}. "
            f"Current Capital: ₹{self.current_capital:.2f}"
        )

    def _evaluate_sustainability_state(self) -> None:
        """Determines the current organizational financial state based on performance and runway."""
        if self.current_capital < (self.starting_capital * 0.80):
            self.state = SustainabilityState.BOOTSTRAP
        elif self.net_trading_profit > 100.0 and self.buckets.operating_reserve > 50.0:
            self.state = SustainabilityState.SELF_SUSTAINING
        elif self.net_trading_profit > 0:
            self.state = SustainabilityState.VALIDATED
        else:
            self.state = SustainabilityState.LEARNING

    def set_unrealized_pnl(self, unrealized: float) -> None:
        self.unrealized_pnl = unrealized

    @property
    def net_trading_profit(self) -> float:
        """Net Trading Profit = Realized P&L - Operating Expenses."""
        return self.realized_pnl - self.total_operating_expenses

    @property
    def total_equity(self) -> float:
        return self.current_capital + self.unrealized_pnl

    @property
    def is_survival_mode(self) -> bool:
        """Determines if system must enter Survival Mode (low capital / high expenses)."""
        if self._survival_mode_forced:
            return True
        if self.starting_capital <= 0:
            return False
        capital_ratio = self.total_equity / self.starting_capital
        # Trigger survival mode only upon severe drawdown (> 40% capital loss)
        return capital_ratio < 0.60

    def force_survival_mode(self, enabled: bool = True) -> None:
        self._survival_mode_forced = enabled
        logger.warning(f"[Treasury] Survival Mode state manually updated: {enabled}")

    @property
    def estimated_runway_days(self) -> float:
        """Calculates days of operational runway remaining at current daily operating burn rate."""
        if self.daily_operating_budget <= 0:
            return 999.0
        return max(0.0, self.current_capital / self.daily_operating_budget)

    def get_metrics(self) -> dict:
        return {
            "starting_capital": round(self.starting_capital, 2),
            "current_capital": round(self.current_capital, 2),
            "total_equity": round(self.total_equity, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "operating_expenses": round(self.total_operating_expenses, 2),
            "net_trading_profit": round(self.net_trading_profit, 2),
            "sustainability_state": self.state.value,
            "buckets": {
                "trading_capital": round(self.buckets.trading_capital, 2),
                "operating_reserve": round(self.buckets.operating_reserve, 2),
                "infrastructure_reserve": round(self.buckets.infrastructure_reserve, 2),
                "ai_upgrade_fund": round(self.buckets.ai_upgrade_fund, 2),
                "emergency_reserve": round(self.buckets.emergency_reserve, 2),
                "reinvestment_capital": round(self.buckets.reinvestment_capital, 2),
            },
            "is_survival_mode": self.is_survival_mode,
            "estimated_runway_days": round(self.estimated_runway_days, 1),
            "survival_threshold": round(self.starting_capital * settings.SURVIVAL_MODE_THRESHOLD_PCT, 2),
            "history_count": len(self.history),
            "ledger_count": len(self.ledger),
        }

    def get_recent_ledger(self, limit: int = 25) -> list[dict]:
        return [entry.model_dump() for entry in self.ledger[-limit:]]


# Global AI Treasury instance
treasury = AITreasury()

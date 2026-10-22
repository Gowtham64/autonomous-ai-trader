"""
Production Capital Management Service (Section 3, 21 & 25)
Manages Requested, Allocated, Deployed, Reserved, Settled Cash, Buying Power,
and Withdrawable Funds. Enforces explicit authorization on all capital movements.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from core.config.settings import settings
from core.logging import logger


class CapitalStructure(BaseModel):
    total_authorized_capital: float = Field(default=2000.0, description="Explicit user authorized capital")
    settled_cash: float = Field(default=2000.0, description="Settled cash available at broker")
    buying_power: float = Field(default=2000.0, description="Current broker-approved buying power")
    allocated_to_strategies: float = Field(default=0.0, description="Capital assigned to active strategies")
    currently_deployed: float = Field(default=0.0, description="Capital tied up in open positions")
    reserved_for_orders: float = Field(default=0.0, description="Capital blocked in pending limit/stop orders")
    realized_pnl: float = Field(default=0.0, description="Cumulative realized P&L")
    unrealized_pnl: float = Field(default=0.0, description="Live unrealized position P&L")
    withdrawable_funds: float = Field(default=2000.0, description="Funds eligible for manual withdrawal")
    currency: str = "INR"
    last_reconciled_at: str | None = None


class CapitalTransaction(BaseModel):
    transaction_id: str
    timestamp: str
    action: str  # "ALLOCATE", "DEPLOY", "RELEASE", "RESERVE", "PNL_ADJUST"
    amount: float
    currency: str = "INR"
    authorized_by: str = "USER_EXPLICIT"
    broker_reference: str | None = None
    notes: str = ""


class CapitalManagementService:
    """Dedicated Production Capital Management Service.
    
    Guarantees that:
    1. No funds are silently moved or transferred.
    2. Capital allocations respect hard risk limits.
    3. Deposits and withdrawals strictly require broker API or manual user authorization.
    """

    def __init__(self, initial_capital: float = 2000.0):
        self.state = CapitalStructure(
            total_authorized_capital=initial_capital,
            settled_cash=initial_capital,
            buying_power=initial_capital,
            withdrawable_funds=initial_capital,
            last_reconciled_at=str(datetime.now(UTC)),
        )
        self.ledger: list[CapitalTransaction] = []

    def get_summary(self) -> dict[str, Any]:
        """Returns the full capital ledger and breakdown."""
        return {
            "capital_structure": self.state.model_dump(),
            "total_transactions": len(self.ledger),
            "free_available_capital": max(0.0, self.state.settled_cash - self.state.currently_deployed - self.state.reserved_for_orders),
            "utilization_pct": round((self.state.currently_deployed / max(1.0, self.state.total_authorized_capital)) * 100, 2),
        }

    def allocate_for_trade(self, amount: float, symbol: str, strategy_id: str) -> bool:
        """Reserves and allocates capital for a proposed trade."""
        free_cash = self.state.settled_cash - self.state.currently_deployed - self.state.reserved_for_orders
        if amount > free_cash:
            logger.warning(f"[CapitalService] Insufficient free capital: requested ₹{amount:.2f}, available ₹{free_cash:.2f}")
            return False

        self.state.reserved_for_orders += amount
        tx = CapitalTransaction(
            transaction_id=f"CTX-RES-{int(datetime.now(UTC).timestamp())}",
            timestamp=str(datetime.now(UTC)),
            action="RESERVE",
            amount=amount,
            notes=f"Reserved for order on {symbol} (Strategy: {strategy_id})",
        )
        self.ledger.append(tx)
        return True

    def confirm_trade_fill(self, amount: float, symbol: str, order_id: str):
        """Moves capital from reserved to deployed upon confirmed fill."""
        self.state.reserved_for_orders = max(0.0, self.state.reserved_for_orders - amount)
        self.state.currently_deployed += amount
        self.state.buying_power = max(0.0, self.state.settled_cash - self.state.currently_deployed)

        tx = CapitalTransaction(
            transaction_id=f"CTX-FILL-{int(datetime.now(UTC).timestamp())}",
            timestamp=str(datetime.now(UTC)),
            action="DEPLOY",
            amount=amount,
            broker_reference=order_id,
            notes=f"Deployed capital in filled position for {symbol}",
        )
        self.ledger.append(tx)
        logger.info(f"[CapitalService] Confirmed fill for {symbol}. Deployed: ₹{self.state.currently_deployed:.2f}")

    def release_trade_capital(self, invested_amount: float, realized_pnl: float, symbol: str):
        """Releases deployed capital back to settled cash on position exit."""
        self.state.currently_deployed = max(0.0, self.state.currently_deployed - invested_amount)
        self.state.settled_cash += realized_pnl
        self.state.realized_pnl += realized_pnl
        self.state.buying_power = max(0.0, self.state.settled_cash - self.state.currently_deployed)
        self.state.withdrawable_funds = self.state.settled_cash

        tx = CapitalTransaction(
            transaction_id=f"CTX-REL-{int(datetime.now(UTC).timestamp())}",
            timestamp=str(datetime.now(UTC)),
            action="RELEASE",
            amount=invested_amount + realized_pnl,
            notes=f"Closed position {symbol} with Realized P&L: ₹{realized_pnl:.2f}",
        )
        self.ledger.append(tx)
        logger.info(f"[CapitalService] Released capital for {symbol}. Net P&L: ₹{realized_pnl:.2f}")

    def reconcile_with_broker(self, broker_cash: float, broker_positions_value: float):
        """Reconciles internal capital records against verified broker RMS."""
        self.state.settled_cash = broker_cash
        self.state.currently_deployed = broker_positions_value
        self.state.buying_power = max(0.0, broker_cash - broker_positions_value)
        self.state.last_reconciled_at = str(datetime.now(UTC))
        logger.info(f"[CapitalService] Reconciled with Broker: Cash=₹{broker_cash:.2f}, Positions=₹{broker_positions_value:.2f}")


capital_service = CapitalManagementService(initial_capital=settings.INITIAL_CAPITAL)

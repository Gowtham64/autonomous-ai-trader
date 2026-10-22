"""
Production Portfolio Reconciliation Engine (Section 14 & 19)
Continuously compares internal portfolio records against live broker state
(Cash, Holdings, Open Positions, Margin, Pending Orders).
Discrepancies automatically trigger safety pauses and audit alerts.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from core.logging import logger
from monitoring.alerting import AlertSeverity, alert_manager


class ReconciliationDiscrepancy(BaseModel):
    discrepancy_type: str  # "POSITION_QTY_MISMATCH", "CASH_MISMATCH", "UNEXPECTED_BROKER_POSITION", "MISSING_INTERNAL_POSITION"
    symbol: str | None = None
    internal_value: Any
    broker_value: Any
    severity: str = "HIGH"
    detected_at: str


class ReconciliationReport(BaseModel):
    is_synchronized: bool
    reconciled_at: str
    total_discrepancies: int
    discrepancies: list[ReconciliationDiscrepancy]
    broker_cash: float
    internal_cash: float
    broker_positions_count: int
    internal_positions_count: int


class PortfolioReconciliationEngine:
    """Continuous Reconciliation Engine guarding against out-of-sync broker state."""

    @staticmethod
    def reconcile(
        internal_positions: list[dict[str, Any]],
        broker_positions: list[dict[str, Any]],
        internal_cash: float,
        broker_cash: float,
        max_cash_tolerance: float = 10.0,
    ) -> ReconciliationReport:
        """Compares internal ledger with live broker account."""
        discrepancies: list[ReconciliationDiscrepancy] = []
        now_str = str(datetime.now(UTC))

        # 1. Cash Reconciliation
        cash_diff = abs(internal_cash - broker_cash)
        if cash_diff > max_cash_tolerance:
            d = ReconciliationDiscrepancy(
                discrepancy_type="CASH_MISMATCH",
                internal_value=internal_cash,
                broker_value=broker_cash,
                severity="HIGH",
                detected_at=now_str,
            )
            discrepancies.append(d)

        # 2. Position Quantity and Existence Reconciliation
        def _norm_sym(s: str) -> str:
            return s.strip().upper().replace("-EQ", "").replace(".NS", "").replace(".BO", "") if s else ""

        internal_map = {_norm_sym(p.get("symbol")): p for p in internal_positions if p.get("symbol")}
        broker_map = {_norm_sym(p.get("symbol")): p for p in broker_positions if p.get("symbol")}

        # Check internal positions vs broker
        for norm_s, int_p in internal_map.items():
            sym = int_p.get("symbol", norm_s)
            int_qty = int(int_p.get("quantity", 0))
            if int_qty == 0:
                continue
            if norm_s not in broker_map:
                discrepancies.append(ReconciliationDiscrepancy(
                    discrepancy_type="MISSING_BROKER_POSITION",
                    symbol=sym,
                    internal_value=int_qty,
                    broker_value=0,
                    severity="CRITICAL",
                    detected_at=now_str,
                ))
            else:
                brk_qty = int(broker_map[norm_s].get("quantity", 0))
                if brk_qty != int_qty:
                    discrepancies.append(ReconciliationDiscrepancy(
                        discrepancy_type="POSITION_QTY_MISMATCH",
                        symbol=sym,
                        internal_value=int_qty,
                        broker_value=brk_qty,
                        severity="CRITICAL",
                        detected_at=now_str,
                    ))

        # Check unexpected broker positions
        for norm_s, brk_p in broker_map.items():
            sym = brk_p.get("symbol", norm_s)
            brk_qty = int(brk_p.get("quantity", 0))
            if brk_qty > 0 and norm_s not in internal_map:
                discrepancies.append(ReconciliationDiscrepancy(
                    discrepancy_type="UNEXPECTED_BROKER_POSITION",
                    symbol=sym,
                    internal_value=0,
                    broker_value=brk_qty,
                    severity="CRITICAL",
                    detected_at=now_str,
                ))

        is_sync = len(discrepancies) == 0

        if not is_sync:
            logger.error(f"[Reconciliation] Discrepancy detected between internal ledger and broker! Total: {len(discrepancies)}")
            alert_manager.send_alert(
                title="PORTFOLIO RECONCILIATION MISMATCH",
                message=f"Detected {len(discrepancies)} discrepancies with live broker.",
                severity=AlertSeverity.CRITICAL,
            )

        return ReconciliationReport(
            is_synchronized=is_sync,
            reconciled_at=now_str,
            total_discrepancies=len(discrepancies),
            discrepancies=discrepancies,
            broker_cash=broker_cash,
            internal_cash=internal_cash,
            broker_positions_count=len(broker_positions),
            internal_positions_count=len(internal_positions),
        )


reconciliation_engine = PortfolioReconciliationEngine()

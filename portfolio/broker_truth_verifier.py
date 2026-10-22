"""
Broker Truth Verifier — Out-of-Band Ground Truth Ledger Engine
Inspired by Black Box Research Labs & ImmortalDemonGod/money-agent.

THE INVARIANT:
"The AI Agent produces CLAIMS. A verifier it cannot forge produces FACTS.
When the internal narrative and the broker ledger disagree, the broker ledger wins by construction."

This module fetches unalterable account facts directly from the primary broker API (Angel One SmartAPI)
and computes the exact gap between internal trade claims and verified cash reality.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.config.settings import settings
from core.logging import logger
from execution.interface import BaseBroker

TRUTH_FILE = Path("reports/truth.json")


class GroundTruthLedger(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    broker_name: str = "AngelOne SmartAPI"
    client_code: str = ""
    verified_available_margin: float = 0.0
    verified_cash_balance: float = 0.0
    verified_open_positions_count: int = 0
    internal_claimed_pnl: float = 0.0
    verified_net_account_change: float = 0.0
    estimated_statutory_and_broker_fees: float = 0.0
    electricity_and_compute_drag: float = 0.0
    ground_truth_net_pnl: float = 0.0
    claim_vs_truth_discrepancy: float = 0.0  # Verification Theater Gap
    is_verified: bool = False
    verification_source: str = "unverified"
    notes: list[str] = Field(default_factory=list)


class BrokerTruthVerifier:
    """Out-of-band Verifier: computes ground truth from the real broker API."""

    @classmethod
    async def compute_and_record_truth(
        cls,
        broker: BaseBroker,
        internal_claimed_pnl: float = 0.0,
        baseline_capital: float | None = None,
        electricity_drag: float = 1.50,
    ) -> GroundTruthLedger:
        """Pulls primary account data from broker and writes the unforgeable truth ledger."""
        TRUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        notes: list[str] = []

        try:
            is_crypto = getattr(broker, "DEFAULT_PROD_URL", None) is not None or "DELTA" in broker.__class__.__name__.upper()
            curr_sym = "$" if is_crypto else "₹"
            drag = 0.05 if is_crypto else electricity_drag
            funds = await broker.get_funds()
            avail_margin = float(funds.get("available_margin", 0.0))
            cash_bal = float(funds.get("net_cash", avail_margin))
            positions = await broker.get_positions()
            active_positions = [p for p in positions if p.is_active and p.quantity > 0]

            total_equity = float(funds.get("total_capital", avail_margin))
            baseline = baseline_capital if baseline_capital is not None else settings.INITIAL_CAPITAL
            net_change = round(total_equity - baseline, 2)
            net_after_drag = round(net_change - drag, 2)
            discrepancy = round(internal_claimed_pnl - net_change, 2)

            if abs(discrepancy) > 1.0:
                notes.append(
                    f"Verification Theater Alert: Internal claim deviates from broker reality by ₹{discrepancy:+.2f}."
                )

            client_code = "DELTA_INDIA" if is_crypto else getattr(settings, "ANGELONE_CLIENT_CODE", "AACJ120032")
            ledger = GroundTruthLedger(
                broker_name=broker.__class__.__name__,
                client_code=client_code,
                verified_available_margin=avail_margin,
                verified_cash_balance=cash_bal,
                verified_open_positions_count=len(active_positions),
                internal_claimed_pnl=internal_claimed_pnl,
                verified_net_account_change=net_change,
                electricity_and_compute_drag=drag,
                ground_truth_net_pnl=net_after_drag,
                claim_vs_truth_discrepancy=discrepancy,
                is_verified=True,
                verification_source="broker-direct-api",
                notes=notes,
            )

            # Write broker-specific truth file atomically
            broker_key = "delta" if is_crypto else "angelone"
            broker_truth_file = Path(f"reports/truth_{broker_key}.json")
            temp_file = broker_truth_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(ledger.model_dump(), indent=2))
            temp_file.replace(broker_truth_file)

            # Also update standard reports/truth.json
            temp_file_global = TRUTH_FILE.with_suffix(".tmp")
            temp_file_global.write_text(json.dumps(ledger.model_dump(), indent=2))
            temp_file_global.replace(TRUTH_FILE)

            logger.info(
                f"🛡️ [Broker Truth Invariant] Ground Truth Ledger Updated ({broker.__class__.__name__}): "
                f"Margin: {curr_sym}{avail_margin:,.2f} | Net Change: {curr_sym}{net_change:+.2f} | Discrepancy: {curr_sym}{discrepancy:+.2f}"
            )
            return ledger

        except Exception as e:
            logger.error(f"[Broker Truth Verifier Error] {e}")
            fallback = GroundTruthLedger(
                is_verified=False,
                verification_source="error-fallback",
                notes=[f"Failed to fetch ground truth: {e}"],
            )
            return fallback

    @classmethod
    def read_latest_truth(cls) -> GroundTruthLedger | None:
        """Reads latest verified truth.json from disk."""
        if not TRUTH_FILE.exists():
            return None
        try:
            data = json.loads(TRUTH_FILE.read_text())
            return GroundTruthLedger(**data)
        except Exception:
            return None

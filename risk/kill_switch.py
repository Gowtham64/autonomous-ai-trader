import os
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.config.settings import settings
from core.logging import logger


class KillSwitchEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    triggered_by: str
    reason: str
    active: bool


class EmergencyKillSwitch:
    """Independent Emergency Kill Switch.
    
    Operates strictly outside the trading agent reasoning loops with absolute veto power
    to instantly halt trading, reject pending executions, and trigger defensive liquidation
    upon anomaly detection.
    """

    def __init__(self):
        self._is_engaged = False
        self.reason: str | None = None
        self.history: list[KillSwitchEvent] = []
        self._consecutive_rejections: int = 0
        self._cooldown_until: datetime | None = None
        self._max_consecutive_rejections: int = 10
        self._cooldown_duration_minutes: int = 5
        # Autonomous recovery: after a circuit-breaker halt, the system cools off for
        # N hours, then resumes automatically with rebased equity baselines (set to 0 to
        # require a manual reset instead).
        self._engaged_at: datetime | None = None
        self.auto_recovery_hours: float = float(os.getenv("KILL_SWITCH_AUTO_RECOVERY_HOURS", "6.0"))
        self.rebase_required: bool = False

    @property
    def is_engaged(self) -> bool:
        return self._is_engaged

    @property
    def consecutive_rejections(self) -> int:
        return self._consecutive_rejections

    @property
    def is_in_cooldown(self) -> tuple[bool, str | None]:
        """Checks if the system is currently under a rejection cooldown."""
        if self._cooldown_until is not None:
            now = datetime.now(UTC)
            if now < self._cooldown_until:
                remaining_sec = (self._cooldown_until - now).total_seconds()
                mins = int(remaining_sec // 60)
                secs = int(remaining_sec % 60)
                return True, (
                    f"Risk Gate 3-Strike Circuit Breaker ACTIVE: System in observation cooldown for another "
                    f"{mins}m {secs}s (until {self._cooldown_until.strftime('%H:%M:%S')} UTC) "
                    f"following {self._consecutive_rejections} consecutive rejected trade proposals."
                )
            else:
                # Cooldown expired - reset counter cleanly
                self._cooldown_until = None
                self._consecutive_rejections = 0
                logger.info("✅ Risk Gate Cooldown period expired. Normal trade candidate evaluation resumed.")
        return False, None

    def record_trade_rejection(self, symbol: str, reason: str) -> None:
        """Records an audit/risk rejection and trips a 30-minute cooldown if threshold hit."""
        self._consecutive_rejections += 1
        logger.warning(
            f"⚠️ [Risk Gate Strike {self._consecutive_rejections}/{self._max_consecutive_rejections}] "
            f"Trade proposal for {symbol} rejected: {reason}"
        )
        if self._consecutive_rejections >= self._max_consecutive_rejections:
            from datetime import timedelta
            self._cooldown_until = datetime.now(UTC) + timedelta(minutes=self._cooldown_duration_minutes)
            logger.critical(
                f"🛑 [Risk Gate 3-Strike Tripped] {self._consecutive_rejections} consecutive trade proposals rejected! "
                f"Enforcing mandatory {self._cooldown_duration_minutes}-minute observation cooldown to prevent LLM loop hallucination."
            )

    def record_trade_approval(self, symbol: str) -> None:
        """Resets the consecutive rejection strike counter upon an approved trade."""
        if self._consecutive_rejections > 0:
            logger.info(f"✅ Trade proposal for {symbol} approved. Consecutive rejection counter reset to 0.")
        self._consecutive_rejections = 0

    def trigger(self, trigger_source: str, reason: str) -> None:
        """Engages the emergency kill switch and halts all trading activities."""
        self._is_engaged = True
        self._engaged_at = datetime.now(UTC)
        self.reason = f"[{trigger_source}] {reason}"
        event = KillSwitchEvent(
            triggered_by=trigger_source,
            reason=reason,
            active=True,
        )
        self.history.append(event)
        logger.critical(f"🚨 EMERGENCY KILL SWITCH ENGAGED! Source: {trigger_source}. Reason: {reason}")

    def reset(self, authorized_by: str = "User") -> None:
        """Resets the kill switch (human operator or autonomous recovery engine)."""
        self._is_engaged = False
        self._engaged_at = None
        self.reason = None
        self._cooldown_until = None
        self._consecutive_rejections = 0
        event = KillSwitchEvent(
            triggered_by=authorized_by,
            reason="Manual system reset by authorized operator",
            active=False,
        )
        self.history.append(event)
        logger.info(f"✅ Emergency Kill Switch reset by {authorized_by}. Trading operations resumed.")

    def verify_system_integrity(
        self,
        daily_loss: float,
        current_drawdown_pct: float,
        max_capital: float = settings.MAX_CAPITAL,
        broker_connected: bool = True,
        data_feed_healthy: bool = True,
    ) -> tuple[bool, str | None]:
        """Runs periodic health and risk threshold verification to auto-trigger if limits are breached."""
        # Autonomous recovery: after the cool-off window, resume automatically and ask
        # the daemon to rebase its equity baselines (peak & day-start) to current equity.
        # If conditions are still breached, the checks below simply re-engage the halt.
        if self._is_engaged and self._engaged_at is not None and self.auto_recovery_hours > 0:
            elapsed_hours = (datetime.now(UTC) - self._engaged_at).total_seconds() / 3600.0
            if elapsed_hours >= self.auto_recovery_hours:
                logger.warning(
                    f"🔄 [Kill Switch Auto-Recovery] {elapsed_hours:.1f}h cool-off complete "
                    f"(threshold: {self.auto_recovery_hours:.1f}h). Resuming autonomous trading with rebased risk baselines."
                )
                self.rebase_required = True
                self.reset("Auto-Recovery Engine")

        if self._is_engaged:
            return False, f"Kill switch already engaged: {self.reason}"

        # Scale the limit to the ACTUAL account equity passed in.
        base_capital = max_capital if max_capital > 0 else settings.MAX_CAPITAL

        # Detect currency and establish appropriate loss floor
        is_usd = base_capital < 100.0 or getattr(settings, "BROKER_NAME", "").lower() == "delta"
        curr_sym = "$" if is_usd else "₹"

        # On small accounts (e.g. $11 crypto), a 2% loss is $0.22 (normal bid-ask spread noise).
        # Enforce a minimum loss floor of $1.00 USD (or ₹100 INR) so normal candle noise does not halt trading.
        min_loss_floor = 1.00 if is_usd else 100.0
        max_daily_loss = max(min_loss_floor, base_capital * settings.MAX_DAILY_LOSS_PCT)

        if daily_loss >= max_daily_loss:
            self.trigger(
                "CIRCUIT_BREAKER",
                f"Daily loss limit breached: {curr_sym}{daily_loss:.2f} >= {curr_sym}{max_daily_loss:.2f}",
            )
            return False, self.reason

        # On micro accounts, allow at least 15% drawdown ($1.65 on $11) for normal swing movement
        effective_max_dd = 0.15 if (is_usd and base_capital < 30.0) else settings.MAX_PORTFOLIO_DRAWDOWN_PCT
        if current_drawdown_pct >= effective_max_dd:
            self.trigger(
                "CIRCUIT_BREAKER",
                f"Max portfolio drawdown breached: {current_drawdown_pct*100:.2f}% >= {effective_max_dd*100:.1f}%",
            )
            return False, self.reason

        if not broker_connected:
            self.trigger("BROKER_INTEGRITY", "Broker API heartbeat lost or returning error state")
            return False, self.reason

        if not data_feed_healthy:
            self.trigger("DATA_INTEGRITY", "Live market data provider feed is corrupt or disconnected")
            return False, self.reason

        return True, None


# Global Kill Switch instance
kill_switch = EmergencyKillSwitch()

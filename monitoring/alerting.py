"""
Production Multi-Channel Alerting & Incident Notification Engine (Section 17)
Dispatches urgent operational, risk, broker, and market alerts across:
- Dashboard Event Bus (WebSocket broadcast)
- Telegram Bot (if configured in .env)
- Institutional Incident Logger
"""

import json
import urllib.request
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from core.config.settings import settings
from core.logging import logger
from orchestration.event_bus import SystemEventType, realtime_event_bus


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertEvent(BaseModel):
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    timestamp: str
    source: str = "PRODUCTION_MONITOR"
    metadata: dict[str, Any] = {}


class AlertManager:
    """Dispatches operational alerts to operators via WebSocket and Telegram."""

    def __init__(self):
        self.alert_history: list[AlertEvent] = []

    def send_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.INFO,
        source: str = "PRODUCTION_MONITOR",
        metadata: dict[str, Any] | None = None,
    ) -> AlertEvent:
        """Publishes an alert to all configured channels."""
        now_ts = int(datetime.now(UTC).timestamp())
        event = AlertEvent(
            alert_id=f"ALT-{now_ts}-{len(self.alert_history)+1}",
            title=title,
            message=message,
            severity=severity,
            timestamp=str(datetime.now(UTC)),
            source=source,
            metadata=metadata or {},
        )
        self.alert_history.append(event)

        # 1. Log with appropriate log level
        if severity == AlertSeverity.CRITICAL:
            logger.error(f"🚨 [CRITICAL ALERT] {title}: {message}")
        elif severity == AlertSeverity.HIGH or severity == AlertSeverity.WARNING:
            logger.warning(f"⚠️ [ALERT] {title}: {message}")
        else:
            logger.info(f"ℹ️ [ALERT] {title}: {message}")

        # 2. Publish to Realtime Event Bus
        realtime_event_bus.publish_event(
            SystemEventType.TREASURY_WARNING if severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH] else SystemEventType.PRICE_MOVEMENT,
            source=source,
            symbol=metadata.get("symbol", "N/A") if metadata else "N/A",
            payload=event.model_dump(),
        )

        # 3. Dispatch to Telegram asynchronously (if tokens provided)
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            self._dispatch_telegram(title, message, severity)

        return event

    def _dispatch_telegram(self, title: str, message: str, severity: AlertSeverity):
        """Dispatches an alert message to Telegram chat via Bot API."""
        try:
            token = settings.TELEGRAM_BOT_TOKEN
            chat_id = settings.TELEGRAM_CHAT_ID
            text = f"🚨 *{severity.value} - {title}*\n\n{message}\n\n_Time: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}_"
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3.0)
        except Exception as e:
            logger.warning(f"[AlertManager] Failed to dispatch Telegram alert: {e}")

    def list_recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        """Returns the most recent alerts."""
        return [a.model_dump() for a in reversed(self.alert_history)][:limit]


alert_manager = AlertManager()

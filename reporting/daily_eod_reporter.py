"""
Daily End-Of-Day (EOD) Reporter Module
Generates and serves daily forensic audit summaries, PnL reports, and historical execution stats.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import logger

REPORTS_DIR = Path("reports/daily")


class DailyEODReporter:
    def __init__(self, reports_dir: Path = REPORTS_DIR):
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def get_available_dates(self) -> list[str]:
        """Returns all available EOD report dates from reports/daily/ directory."""
        if not self.reports_dir.exists():
            return []
        dates: list[str] = []
        for p in self.reports_dir.glob("EOD_Report_*.json"):
            # Format: EOD_Report_YYYY-MM-DD.json
            name = p.stem.replace("EOD_Report_", "")
            if name and name not in dates:
                dates.append(name)
        dates.sort(reverse=True)
        return dates

    def get_report_by_date(self, report_date: str) -> dict[str, Any] | None:
        """Loads a specific historical report JSON safely without path traversal."""
        safe_file = self.reports_dir / f"EOD_Report_{report_date}.json"
        try:
            resolved = safe_file.resolve()
            if not resolved.is_relative_to(self.reports_dir.resolve()):
                return None
            if resolved.exists():
                return json.loads(resolved.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug(f"[DailyEODReporter] Error reading report for {report_date}: {e}")
        return None

    async def generate_daily_report(self, broker: Any = None, provider: Any = None) -> dict[str, Any]:
        """Generates a daily summary report snapshot from current broker and truth files."""
        now_utc = datetime.now(UTC)
        today_str = now_utc.strftime("%Y-%m-%d")

        funds = {}
        if broker and hasattr(broker, "get_funds"):
            try:
                funds = await broker.get_funds()
            except Exception as e:
                logger.debug(f"[DailyEODReporter] Funds fetch note: {e}")

        # Check truth.json
        truth_file = Path("reports/truth.json")
        truth_data = {}
        if truth_file.exists():
            try:
                truth_data = json.loads(truth_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        report_payload = {
            "date": today_str,
            "generated_at": now_utc.isoformat(),
            "available_margin": float(funds.get("available_margin", 0.0)),
            "total_capital": float(funds.get("total_capital", 0.0)),
            "unrealized_pnl": float(funds.get("unrealized_pnl", 0.0)),
            "realized_pnl": float(truth_data.get("ground_truth_net_pnl", 0.0)),
            "status": "COMPLETED",
        }

        # Persist latest.json
        latest_json = self.reports_dir / "latest.json"
        latest_json.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

        # Persist dated JSON
        dated_json = self.reports_dir / f"EOD_Report_{today_str}.json"
        dated_json.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

        # Persist Markdown summary
        md_content = f"""# Daily EOD Trading Report — {today_str}
- **Generated At**: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Total Capital**: ${report_payload['total_capital']:.2f}
- **Available Margin**: ${report_payload['available_margin']:.2f}
- **Realized PnL**: ${report_payload['realized_pnl']:+.2f}
- **Unrealized PnL**: ${report_payload['unrealized_pnl']:+.2f}
"""
        latest_md = self.reports_dir / "latest.md"
        latest_md.write_text(md_content, encoding="utf-8")
        dated_md = self.reports_dir / f"EOD_Report_{today_str}.md"
        dated_md.write_text(md_content, encoding="utf-8")

        return report_payload


daily_eod_reporter = DailyEODReporter()

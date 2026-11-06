from datetime import UTC, datetime, timedelta

from risk.go_live_gate import score_go_live


def _trades(wins, losses):
    start = datetime(2026, 11, 7, tzinfo=UTC)
    rows = []
    for idx in range(wins):
        rows.append({"net_pnl": 1.0, "timestamp": (start + timedelta(hours=idx)).isoformat()})
    for idx in range(losses):
        rows.append({"net_pnl": -0.4, "timestamp": (start + timedelta(hours=wins + idx)).isoformat()})
    return rows


def test_three_day_window_collects_before_it_decides():
    now = datetime(2026, 11, 8, tzinfo=UTC)
    result = score_go_live(
        now=now,
        started_at=datetime(2026, 11, 7, tzinfo=UTC),
        trades=_trades(12, 4),
        drawdown_pct=1.0,
    )
    assert result["decision"] == "COLLECTING"
    assert result["live_trading_enabled"] is False
    assert result["window_complete"] is False


def test_a_passing_record_asks_for_a_person_and_stays_paper():
    start = datetime(2026, 11, 1, tzinfo=UTC)
    result = score_go_live(
        now=start + timedelta(hours=72),
        started_at=start,
        trades=_trades(16, 4),
        drawdown_pct=1.0,
    )
    assert result["closed_trades"] == 20
    assert result["decision"] == "READY_FOR_MANUAL_REVIEW"
    assert result["live_trading_enabled"] is False


def test_a_weak_record_is_no_go():
    start = datetime(2026, 11, 1, tzinfo=UTC)
    result = score_go_live(
        now=start + timedelta(days=4),
        started_at=start,
        trades=_trades(4, 16),
        drawdown_pct=1.0,
    )
    assert result["decision"] == "NO_GO"
    assert result["live_trading_enabled"] is False

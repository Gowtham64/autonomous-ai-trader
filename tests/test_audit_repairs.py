"""Regression checks for the November 2026 integrity repairs."""

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from apps.api.request_guards import clamp_limit, price_decimals, validate_public_bridge_url
from core.config.settings import settings
from risk.kill_switch import kill_switch


def _request(method: str, path: str, **kwargs):
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(_run())


def test_private_bridge_urls_are_rejected():
    for raw in (
        "http://169.254.169.254/latest/meta-data",
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "file:///etc/passwd",
        "http://user:secret@example.com",
    ):
        with pytest.raises(ValueError):
            validate_public_bridge_url(raw)


def test_public_ip_bridge_url_is_allowed():
    assert validate_public_bridge_url("https://1.1.1.1:443/api/tags") == "https://1.1.1.1:443"


def test_ollama_register_blocks_metadata_address():
    res = _request("POST", "/api/ollama/register", json={"url": "http://169.254.169.254/latest/meta-data"})
    assert res.status_code == 400


def test_ollama_register_requires_bridge_token(monkeypatch):
    monkeypatch.delenv("OLLAMA_BRIDGE_TOKEN", raising=False)
    res = _request("POST", "/api/ollama/register", json={"url": "https://1.1.1.1"})
    assert res.status_code == 403
    assert "OLLAMA_BRIDGE_TOKEN" in res.json()["detail"]


def test_quotes_do_not_ship_seeded_equity_prices():
    res = _request("GET", "/api/market/quotes")
    assert res.status_code == 200
    symbols = {row["symbol"] for row in res.json()["quotes"]}
    assert "RELIANCE" not in symbols
    assert "NIFTY 50" not in symbols
    for row in res.json()["quotes"]:
        assert row.get("source") == "delta"
        assert float(row["ltp"]) > 0


def test_market_symbol_injection_is_rejected():
    res = _request("GET", "/api/market/candles", params={"symbol": "../../etc/passwd", "interval": "5m"})
    assert res.status_code == 400
    trades = _request("GET", "/api/market/trades", params={"symbol": "BTCUSDT&limit=1", "limit": 99999})
    assert trades.status_code == 400


def test_trade_limit_is_clamped():
    assert clamp_limit(10_000, maximum=100) == 100
    assert clamp_limit(0, maximum=100) == 1
    assert price_decimals(0.08176) == 8
    assert price_decimals(67420) == 2


def test_evaluation_does_not_replay_old_soak_clock():
    res = _request("GET", "/api/evaluation/status")
    assert res.status_code == 200
    body = res.json()
    assert body["elapsed_seconds"] < 600
    criteria = {row["criterion"]: row["status"] for row in body["acceptance_criteria"]}
    assert criteria["System Stability"] == "PENDING"
    assert criteria["Completed round trips"] in {"PENDING", "OBSERVED"}


def test_startup_source_does_not_reset_kill_switch():
    source = Path("apps/api/main.py").read_text(encoding="utf-8")
    assert 'kill_switch.reset("API Cloud Daemon")' not in source
    kill_switch.trigger("audit-test", "must stay engaged")
    try:
        assert kill_switch.is_engaged is True
    finally:
        kill_switch.reset("audit-test-cleanup")


def test_agent_actions_are_not_preapproved():
    res = _request("GET", "/api/office/agent-actions")
    assert res.status_code == 200
    blob = " ".join(str(row.get("summary", "")) for row in res.json()["actions"])
    assert "Max Drawdown (1.94%" not in blob
    assert "Confluence score 82%" not in blob


def test_login_cookie_opens_the_dashboard(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "aitrader")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "desk-pass-92")

    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            blocked = await client.get("/", follow_redirects=False)
            assert blocked.status_code == 303
            assert blocked.headers["location"] == "/login"
            page = await client.get("/login")
            assert page.status_code == 200
            assert "Sign in" in page.text
            bad = await client.post("/api/auth/login", json={"username": "aitrader", "password": "wrong"})
            assert bad.status_code == 401
            ok = await client.post("/api/auth/login", json={"username": "aitrader", "password": "desk-pass-92"})
            assert ok.status_code == 200
            assert "access_token" in ok.cookies or "set-cookie" in {k.lower() for k in ok.headers}
            home = await client.get("/")
            assert home.status_code == 200
            assert "AI Trading Dashboard" in home.text
            health = await client.get("/health")
            assert health.status_code == 200

    asyncio.run(run())


def test_live_trading_stays_disabled():
    assert settings.LIVE_TRADING_ENABLED is False
    assert os.environ.get("LIVE_TRADING_ENABLED", "false").lower() != "true"


def test_guardian_timestamp_uses_completed_at():
    from apps.api.main import get_unified_trade_history
    from guardian.models import PostTradeQualityReport
    from guardian.trade_guardian import trade_guardian

    closed = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    report = PostTradeQualityReport(
        trade_id="audit-ts-1",
        symbol="BTCUSD",
        entry_price=100.0,
        exit_price=101.0,
        quantity=1,
        realized_pnl=0.5,
        realized_pnl_pct=0.5,
        exit_reason="TARGET_EXIT",
        completed_at=closed,
    )
    trade_guardian.completed_reports.append(report)
    try:
        rows = asyncio.run(get_unified_trade_history(include_historical_ledgers=False))
    finally:
        trade_guardian.completed_reports = [r for r in trade_guardian.completed_reports if r.trade_id != "audit-ts-1"]
    match = [row for row in rows if row["trade_id"] == "audit-ts-1"]
    assert match
    assert match[0]["timestamp"].startswith("2026-01-02")

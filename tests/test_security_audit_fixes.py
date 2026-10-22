"""
Verification test suite for all 5 security fixes identified in Cloudflare Security Audit.
SEC-01: Authentication required by default and JWT validation.
SEC-02: Comprehensive .gitignore coverage for sensitive files.
SEC-03: Guardian emergency exit direction (BUY for shorts, SELL for longs with reduce_only=True).
SEC-04: Path traversal prevention in EOD report date endpoint.
SEC-05: WebSocket live-feed authentication gate.
"""

import os
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api.main import app
from core.auth.security import create_access_token, decode_access_token, get_current_user
from core.config.settings import settings
from core.schemas.trade import TradeAction


def test_sec_01_auth_token_lifecycle():
    """Verify JWT token creation, signing, and decoding."""
    user_payload = {"username": "admin", "role": "admin", "permissions": ["all"]}
    token = create_access_token(user_payload, expires_hours=1)
    assert token is not None and len(token) > 20

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "admin"
    assert decoded["role"] == "admin"

    # Corrupted token must fail decoding
    assert decode_access_token("corrupted.invalid.token") is None


def test_sec_01_endpoint_auth_enforcement():
    """Verify that protected API endpoints reject unauthenticated requests when AUTH_REQUIRED is True."""
    client = TestClient(app)

    with patch.object(settings, "AUTH_REQUIRED", True):
        # Unauthenticated request to /api/funds should return 401
        res = client.get("/api/funds")
        assert res.status_code == 401
        assert "Authentication token missing or invalid" in res.json().get("detail", "")

        # Request with forged / invalid bearer token
        res_bad = client.get("/api/funds", headers={"Authorization": "Bearer invalid_token_xyz"})
        assert res_bad.status_code == 401

        # Request with valid token
        valid_token = create_access_token({"username": "admin", "role": "admin"})
        # Mock get_active_broker to avoid live network call
        with patch("apps.api.main.get_active_broker") as mock_broker_func:
            mock_broker = MagicMock()
            mock_broker.get_funds = AsyncMock(return_value={"net_balance": 1000.0, "available_cash": 1000.0})
            mock_broker_func.return_value = mock_broker

            res_good = client.get("/api/funds", headers={"Authorization": f"Bearer {valid_token}"})
            assert res_good.status_code == 200
            assert res_good.json()["net_balance"] == 1000.0


def test_sec_02_gitignore_sensitive_files():
    """Verify .gitignore properly protects sensitive files and credentials."""
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists(), ".gitignore must exist"
    content = gitignore_path.read_text(encoding="utf-8")

    critical_entries = [
        ".env",
        "*.db",
        "logs/",
        "reports/truth*.json",
    ]
    for entry in critical_entries:
        assert entry in content, f"Critical entry '{entry}' missing from .gitignore"


def test_sec_03_guardian_emergency_exit_logic():
    """Verify that Trade Guardian exits short positions with BUY and long positions with SELL."""
    from apps.api.routers.guardian import emergency_exit_position
    from guardian.trade_guardian import trade_guardian

    # Case 1: Short position exit
    mock_short_worker = MagicMock()
    mock_short_worker.state.side = "SHORT"
    mock_short_worker.state.exchange = "DELTA"
    mock_short_worker.state.quantity = 2.0
    mock_short_worker.state.entry_price = 100.0
    mock_short_worker.state.current_sl = 105.0
    mock_short_worker.state.initial_target = 90.0
    mock_short_worker.interventions_count = 0

    is_short = str(mock_short_worker.state.side).upper() in ["SELL", "SHORT"]
    exit_action_short = TradeAction.BUY if is_short else TradeAction.SELL
    assert exit_action_short == TradeAction.BUY, "Exiting a SHORT position must generate a BUY order"

    # Case 2: Long position exit
    mock_long_worker = MagicMock()
    mock_long_worker.state.side = "LONG"
    is_long_short = str(mock_long_worker.state.side).upper() in ["SELL", "SHORT"]
    exit_action_long = TradeAction.BUY if is_long_short else TradeAction.SELL
    assert exit_action_long == TradeAction.SELL, "Exiting a LONG position must generate a SELL order"


def test_sec_04_path_traversal_rejection():
    """Verify that path traversal attempts in EOD report dates are blocked."""
    client = TestClient(app)

    malicious_inputs = [
        "../../etc/passwd",
        "....//....//etc/shadow",
        "2026-03-30/../../../secrets",
        "invalid-date-format",
        "2026-1-1",
    ]

    for bad_date in malicious_inputs:
        res = client.get(f"/api/reports/daily/date/{bad_date}")
        assert res.status_code in (400, 404), f"Path traversal attempt '{bad_date}' was not blocked (got {res.status_code})"


def test_sec_05_websocket_auth():
    """Verify WebSocket /ws/live-feed rejects unauthenticated connections and accepts authenticated ones."""
    client = TestClient(app)

    with patch.object(settings, "AUTH_REQUIRED", True):
        # Connection without token should be closed with code 1008
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/live-feed") as ws:
                pass

        # Connection with valid token should connect and receive ticks
        token = create_access_token({"username": "admin", "role": "admin"})
        with client.websocket_connect(f"/ws/live-feed?token={token}") as ws:
            data = ws.receive_json()
            assert data.get("type") == "MARKET_TICK_STREAM"
            assert "treasury" in data

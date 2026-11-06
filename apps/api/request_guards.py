"""Request guards for public market routes and the optional Ollama bridge."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")
_INTERVALS = {"1m", "5m", "15m", "1h", "4h", "1d", "1D"}
_BLOCKED_HOSTS = {
    "localhost",
    "metadata",
    "metadata.google.internal",
    "instance-data",
}


def normalize_market_symbol(symbol: str) -> str:
    cleaned = (symbol or "").strip().upper()
    if not _SYMBOL_RE.match(cleaned):
        raise ValueError("Symbol must be 1-32 letters, numbers, dots, or dashes.")
    return cleaned


def normalize_candle_interval(interval: str) -> str:
    cleaned = (interval or "5m").strip()
    if cleaned not in _INTERVALS:
        raise ValueError("Interval is not supported.")
    return cleaned


def clamp_limit(limit: int, *, default: int = 30, maximum: int = 100) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return default
    return max(1, min(maximum, value))


def price_decimals(price: float) -> int:
    magnitude = abs(float(price or 0.0))
    if magnitude >= 100:
        return 2
    if magnitude >= 1:
        return 4
    if magnitude == 0:
        return 4
    return 8


def _reject_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("Bridge URL must be a public host.")


def validate_public_bridge_url(url: str) -> str:
    """Accept only public http(s) URLs. Rejects cloud-metadata and private targets."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Bridge URL must be http or https.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in the bridge URL are not allowed.")
    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS or host.endswith(".internal") or host.endswith(".local"):
        raise ValueError("Bridge host is not allowed.")
    port = parsed.port
    try:
        _reject_ip(ipaddress.ip_address(host))
    except ValueError as exc:
        if "not allowed" in str(exc) or "public host" in str(exc):
            raise
        try:
            infos = socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as dns_err:
            raise ValueError("Bridge host could not be resolved.") from dns_err
        if not infos:
            raise ValueError("Bridge host could not be resolved.")
        for info in infos:
            _reject_ip(ipaddress.ip_address(info[4][0]))
    base = f"{parsed.scheme}://{host}"
    if port:
        base += f":{port}"
    return base


def bridge_token_matches(provided: str | None) -> bool:
    expected = os.environ.get("OLLAMA_BRIDGE_TOKEN", "").strip()
    if not expected:
        return False
    return bool(provided) and provided.strip() == expected

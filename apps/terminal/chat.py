"""AI trading assistant grounded in the bot's real records (Google Gemini).

The model is given a JSON snapshot of the live system (positions revalued at current
exchange prices, risk, recent trades, orders, signals, events, strategy rules) and told
to answer ONLY from it, citing records. It has no tools and cannot place, change or
cancel anything — actions happen only through the terminal's buttons, which go to the
engine. If the data doesn't contain the answer, it must say so.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from apps.terminal.market import http_json

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = """You are the read-only assistant inside a crypto trading terminal for a bot that trades
Delta Exchange perpetual futures with ONE strategy: a daily Donchian trend rule (enter long when a completed
daily close breaks the prior 55-day high; initial stop 3 x ATR(20) below the fill, trailing up from the best
close; exit when a daily close breaks the prior 20-day low or the stop is hit; risk a fixed % of equity per trade).
It does not use AI agents to decide trades.

Rules:
- Answer ONLY from the JSON in DATA. Never invent prices, trades, orders, reasons, P&L or signals.
- If DATA does not contain what is needed, say exactly what is missing.
- Quote concrete values with their timestamps and IDs (trade_uid, client_order_id, event time) when you use them.
- Show the arithmetic for any calculation (e.g. P&L = (mark - entry) x qty x multiplier).
- You cannot place, modify or cancel orders. If asked, explain which terminal button does it.
- Mode matters: say whether figures are PAPER or LIVE.
- Be concise and plain-spoken. Use short paragraphs or a short list."""


def api_key() -> str | None:
    try:
        from core.config.settings import settings
        k = getattr(settings, "GEMINI_API_KEY", None)
    except Exception:
        k = None
    return k or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def model_name() -> str:
    try:
        from core.config.settings import settings
        default = getattr(settings, "MODEL_FAST", None) or "gemini-flash-latest"
    except Exception:
        default = "gemini-flash-latest"
    return os.getenv("TERMINAL_CHAT_MODEL", default)


def _post_json(url: str, body: dict, timeout: float = 60.0) -> dict:
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ask(question: str, context: dict, history: list[dict] | None = None,
        post: Callable[[str, dict], dict] = _post_json, key: str | None = None, model: str | None = None) -> dict:
    """Returns {"answer": str} or {"error": str}. Never raises for API problems."""
    key = key or api_key()
    if not key:
        return {"error": "No Gemini API key configured. Add GEMINI_API_KEY=... to .env and restart the terminal."}
    model = model or model_name()
    contents = []
    for h in (history or [])[-8:]:
        role = "model" if h.get("role") == "assistant" else "user"
        if h.get("text"):
            contents.append({"role": role, "parts": [{"text": str(h["text"])[:4000]}]})
    data = json.dumps(context, default=str)[:180_000]
    contents.append({"role": "user", "parts": [{"text": f"DATA:\n{data}\n\nQUESTION: {question[:2000]}"}]})
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1200},
    }
    url = GEMINI_URL.format(model=model) + f"?key={key}"
    try:
        res = post(url, body)
    except Exception as e:
        msg = str(e).replace(key, "***")
        return {"error": f"Gemini request failed: {msg}"}
    try:
        parts = res["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError):
        reason = (res.get("promptFeedback") or {}).get("blockReason") or res.get("error", {}).get("message") or "no answer"
        return {"error": f"Gemini returned no answer ({reason})."}
    return {"answer": text or "(empty answer)", "model": model}


# keep a reference so tests can stub the network uniformly
_http_json = http_json

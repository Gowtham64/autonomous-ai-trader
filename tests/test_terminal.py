"""Trading terminal: store, engine commands, analytics, market data, HTTP server, chat.

Paper trading only: every order goes to DeltaPaperBroker. No live orders are sent.
"""

import asyncio
import http.client
import json
import threading
import time

import numpy as np
import pandas as pd
import pytest

from apps.terminal import analytics
from apps.terminal.market import MarketData, indicator_frame, rsi
from apps.terminal.store import TradeStore
from risk.kill_switch import kill_switch
from tests.test_daily_trend_engine import Clock, _drive, _make_engine, _trending_market


@pytest.fixture(autouse=True)
def isolated_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(kill_switch, "_state_path", tmp_path / "ks.json")
    kill_switch._is_engaged = False
    kill_switch._engaged_kind = None
    kill_switch.reason = None
    kill_switch.rebase_required = False
    yield
    kill_switch._is_engaged = False
    kill_switch.reason = None


def _engine_with_position(tmp_path, capital=500.0):
    df = _trending_market()
    clock = Clock(df.index[0])
    eng = _make_engine(tmp_path, df, clock, [], capital=capital)
    for day in df.index[60:]:
        _drive(eng, df, clock, [day])
        if eng.state.positions:
            break
    assert eng.state.positions, "scenario should open a position"
    return eng, df, clock


def _cmd(eng, kind, payload):
    cid = eng.store.submit_command(kind, payload)
    asyncio.run(eng.process_commands())
    return eng.store.command(cid)


# ------------------------------------------------------------------ store

def test_command_lifecycle_is_atomic_idempotent_and_expires(tmp_path):
    st = TradeStore(tmp_path / "t.db")
    cid = st.submit_command("PAUSE_ENTRIES", {"paused": True}, command_id="abc")
    assert st.submit_command("PAUSE_ENTRIES", {"paused": False}, command_id="abc") == "abc"  # no duplicate
    assert len(st.query("SELECT * FROM commands")) == 1
    assert [c["id"] for c in st.claim_commands()] == [cid]
    assert st.claim_commands() == []  # already EXECUTING: never claimed twice
    assert st.requeue_stuck_commands() == 1 and st.command(cid)["status"] == "FAILED"  # crash mid-execution
    old = st.submit_command("PAUSE_ENTRIES", {"paused": True})
    with st.tx() as c:
        c.execute("UPDATE commands SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?", (old,))
    assert st.claim_commands() == [] and "expired" in st.command(old)["result"]["error"]
    with pytest.raises(ValueError):
        st.submit_command("SEND_ALL_MONEY", {})


def test_orders_and_trades_are_never_duplicated(tmp_path):
    st = TradeStore(tmp_path / "t.db")
    row = dict(client_order_id="X1", mode="PAPER", symbol="A", side="BUY", purpose="ENTRY", order_type="MARKET",
               quantity=1, status="FILLED")
    st.record_order(**row)
    st.record_order(**row)
    assert len(st.query("SELECT * FROM orders")) == 1


# ------------------------------------------------- engine executes commands

def test_engine_records_orders_trades_signals_events_equity(tmp_path):
    eng, df, clock = _engine_with_position(tmp_path)
    q = eng.store.query
    o = q("SELECT * FROM orders")[0]
    assert o["purpose"] == "ENTRY" and o["status"] == "FILLED" and json.loads(o["response_json"])["order_id"]
    # one signal row per coin per completed daily candle once 76 days of history exist
    assert q("SELECT COUNT(*) n FROM signals")[0]["n"] >= 1
    assert q("SELECT action FROM signals WHERE action='ENTERED'")
    assert q("SELECT * FROM events WHERE kind='ENTRY'")
    assert q("SELECT COUNT(*) n FROM equity")[0]["n"] > 0


def test_move_stop_rules(tmp_path):
    eng, df, clock = _engine_with_position(tmp_path)
    pos = eng.state.positions["XYZUSD"]
    mark = clock.mark
    r = _cmd(eng, "MOVE_STOP", {"symbol": "XYZUSD", "stop": mark * 1.05})
    assert r["status"] == "FAILED" and "wrong side" in r["result"]["error"]
    r = _cmd(eng, "MOVE_STOP", {"symbol": "XYZUSD", "stop": pos.initial_stop * 0.9})
    assert r["status"] == "FAILED" and "wider than the initial stop" in r["result"]["error"]
    new = (pos.stop + mark) / 2
    r = _cmd(eng, "MOVE_STOP", {"symbol": "XYZUSD", "stop": new})
    assert r["status"] == "DONE" and eng.state.positions["XYZUSD"].stop == pytest.approx(new)
    assert eng.state.positions["XYZUSD"].stop_source == "MANUAL"


def test_take_profit_set_trigger_and_clear(tmp_path):
    eng, df, clock = _engine_with_position(tmp_path)
    mark = clock.mark
    assert _cmd(eng, "SET_TAKE_PROFIT", {"symbol": "XYZUSD", "take_profit": mark * 0.9})["status"] == "FAILED"
    assert _cmd(eng, "SET_TAKE_PROFIT", {"symbol": "XYZUSD", "take_profit": mark * 1.02})["status"] == "DONE"
    assert _cmd(eng, "SET_TAKE_PROFIT", {"symbol": "XYZUSD", "take_profit": None})["status"] == "DONE"
    assert eng.state.positions["XYZUSD"].take_profit == 0.0
    _cmd(eng, "SET_TAKE_PROFIT", {"symbol": "XYZUSD", "take_profit": mark * 1.02})
    clock.mark = mark * 1.03
    clock.t += pd.Timedelta(minutes=15)
    asyncio.run(eng.run_cycle())
    assert "XYZUSD" not in eng.state.positions
    assert eng.store.query("SELECT exit_reason FROM trades")[-1]["exit_reason"] == "TAKE_PROFIT"


def test_partial_then_full_close_records_both_trades(tmp_path):
    eng, df, clock = _engine_with_position(tmp_path)
    qty = eng.state.positions["XYZUSD"].quantity
    r = _cmd(eng, "CLOSE_POSITION", {"symbol": "XYZUSD", "quantity": qty + 1})
    assert r["status"] == "FAILED" and "between 1 and" in r["result"]["error"]
    r = _cmd(eng, "CLOSE_POSITION", {"symbol": "XYZUSD", "quantity": 2})
    assert r["status"] == "DONE" and r["result"]["remaining"] == qty - 2
    assert eng.state.positions["XYZUSD"].quantity == qty - 2
    r = _cmd(eng, "CLOSE_POSITION", {"symbol": "XYZUSD"})
    assert r["status"] == "DONE" and "XYZUSD" not in eng.state.positions
    trades = eng.store.query("SELECT * FROM trades ORDER BY id")
    assert [t["quantity"] for t in trades] == [2, qty - 2]
    assert [t["exit_reason"] for t in trades] == ["MANUAL_PARTIAL_CLOSE", "MANUAL_CLOSE"]
    for t in trades:  # net = gross - fees, gross from fill prices
        unit = t["quantity"] * t["multiplier"]
        assert t["gross_pnl"] == pytest.approx((t["exit_price"] - t["entry_price"]) * unit, rel=1e-9)
        assert t["net_pnl"] == pytest.approx(t["gross_pnl"] - t["fees"], abs=1e-6)
    purposes = [o["purpose"] for o in eng.store.query("SELECT purpose FROM orders ORDER BY id")]
    assert purposes[-2:] == ["PARTIAL_EXIT", "EXIT"]


def test_rejected_exit_leaves_position_open(tmp_path):
    eng, df, clock = _engine_with_position(tmp_path)
    eng.broker.positions.clear()  # broker can't find the position -> reduce-only rejected
    eng.state.save(eng.state_path)
    r = _cmd(eng, "CLOSE_POSITION", {"symbol": "XYZUSD"})
    assert r["status"] == "FAILED" and "rejected" in r["result"]["error"]
    assert "XYZUSD" in eng.state.positions  # never shown closed without broker confirmation
    assert eng.store.query("SELECT * FROM events WHERE kind='ORDER_REJECTED'")


def test_risk_config_pause_and_kill_switch_commands(tmp_path):
    eng, df, clock = _engine_with_position(tmp_path)
    assert _cmd(eng, "UPDATE_RISK_CONFIG", {"changes": {"risk_pct": 0.5}})["status"] == "FAILED"  # engine re-validates
    assert _cmd(eng, "UPDATE_RISK_CONFIG", {"changes": {"risk_pct": 0.015, "max_positions": 5}})["status"] == "DONE"
    assert eng.cfg.risk_pct == 0.015 and eng.cfg.max_positions == 5
    assert _cmd(eng, "PAUSE_ENTRIES", {"paused": True})["status"] == "DONE"
    s = {"skipped": []}
    assert asyncio.run(eng._entries_allowed(s)) is False and "paused" in s["skipped"][0]
    assert _cmd(eng, "ENGAGE_KILL_SWITCH", {"reason": "test"})["status"] == "DONE" and kill_switch.is_engaged
    assert _cmd(eng, "RESET_KILL_SWITCH", {})["status"] == "DONE" and not kill_switch.is_engaged


def test_open_losses_count_toward_drawdown_in_paper_mode(tmp_path):
    """Regression: paper risk checks used cash only, so a big open loss never tripped the halt."""
    eng, df, clock = _engine_with_position(tmp_path)
    pos = eng.state.positions["XYZUSD"]
    eng.cfg.max_drawdown_pct = 0.05
    eng.cfg.save(eng.risk_path)
    pos.stop = 0.0001  # keep the position open while price collapses
    eng.state.save(eng.state_path)
    clock.mark = pos.entry_price * 0.4  # open loss ~ 60% of notional
    clock.t += pd.Timedelta(minutes=15)
    asyncio.run(eng.run_cycle())
    assert kill_switch.is_engaged and "Drawdown" in kill_switch.reason
    assert eng.store.query("SELECT * FROM events WHERE kind='RISK_HALT'")


# ---------------------------------------------------------------- analytics

def _t(sym, side, entry_t, exit_t, net, r, gross=None, fees=0.1):
    return {"symbol": sym, "side": side, "entry_time": entry_t, "exit_time": exit_t, "net_pnl": net,
            "gross_pnl": gross if gross is not None else net + fees, "fees": fees, "r_multiple": r, "exit_reason": "STOP"}


def test_analytics_summary_and_groups():
    trades = [_t("A", "BUY", "2026-01-01T00:00:00+00:00", "2026-01-03T00:00:00+00:00", 10, 2.0),
              _t("A", "BUY", "2026-01-05T00:00:00+00:00", "2026-01-06T00:00:00+00:00", -5, -1.0),
              _t("B", "SELL", "2026-02-01T00:00:00+00:00", "2026-02-02T00:00:00+00:00", -3, -0.6)]
    s = analytics.summary(trades, now=pd.Timestamp("2026-02-02T12:00:00+00:00"))
    assert (s["trades"], s["wins"], s["losses"]) == (3, 1, 2)
    assert s["profit_factor"] == pytest.approx(10 / 8) and s["expectancy"] == pytest.approx(2 / 3)
    assert s["avg_r"] == pytest.approx(0.4 / 3, abs=1e-3) and s["max_consecutive_losses"] == 2
    assert s["today_realized"] == -3
    g = analytics.grouped(trades)
    assert [r["key"] for r in g["monthly"]] == ["2026-01", "2026-02"]
    assert {r["key"]: r["net_pnl"] for r in g["by_side"]} == {"Long": 5, "Short": -3}


def test_equity_curve_drawdown_and_risk_view():
    c = analytics.equity_curve([{"ts": "2026-01-01T00:00:00+00:00", "equity": 100},
                                {"ts": "2026-01-02T00:00:00+00:00", "equity": 120},
                                {"ts": "2026-01-03T00:00:00+00:00", "equity": 90}])
    assert c["max_drawdown_pct"] == pytest.approx(25.0) and c["drawdown"][-1]["value"] == pytest.approx(-25.0)
    st = {"equity": 1000, "risk_config": {"risk_pct": 0.01, "max_positions": 5, "max_drawdown_pct": 0.25, "max_daily_loss_pct": 0.06},
          "positions": [{"symbol": "A", "side": "BUY", "qty": 10, "multiplier": 1.0, "entry": 100, "stop": 90, "mark": 110}]}
    r = analytics.risk_view(st, {"A": 110})
    assert r["exposure_usd"] == 1100 and r["capital_at_risk_usd"] == 200 and r["unrealized_usd"] == 100
    assert r["remaining_new_trade_risk_usd"] == 40 and r["effective_leverage"] == pytest.approx(1.1)


# ------------------------------------------------------------- market data

def _ticker_fetch(bid="99.9", ask="100.1"):
    def fetch(url, params=None, timeout=8):
        if url.endswith("/v2/tickers"):
            q = {"best_bid": bid, "best_ask": ask} if bid else {}
            return {"result": [{"symbol": "AUSD", "mark_price": "100", "close": "100.2", "open": "98", "quotes": q,
                                "turnover_usd": "5e6", "funding_rate": "0.0001", "contract_value": "1"},
                               {"symbol": "OTHER", "mark_price": "1"}]}
        n = 120
        t0 = int(params["from"])
        c = 100 + np.cumsum(np.random.default_rng(1).normal(0, 1, n))
        return {"result": {"t": [t0 + 86400 * i for i in range(n)], "o": list(c), "h": list(c + 1), "l": list(c - 1),
                           "c": list(c), "v": [1000.0] * n}}
    return fetch


def test_tickers_parse_and_never_invent_missing_quotes():
    m = MarketData(fetch=_ticker_fetch()).tickers(["AUSD"])
    a = m["items"]["AUSD"]
    assert set(m["items"]) == {"AUSD"} and a["spread_pct"] == pytest.approx(0.2) and a["funding_rate_pct"] == pytest.approx(0.01)
    b = MarketData(fetch=_ticker_fetch(bid=None)).tickers(["AUSD"])["items"]["AUSD"]
    assert b["bid"] is None and b["spread_pct"] is None  # no fake 0% spread
    err = MarketData(fetch=lambda *a, **k: (_ for _ in ()).throw(OSError("down"))).tickers(["AUSD"])
    assert err["items"] == {} and "unavailable" in err["error"]


def test_indicators_are_sane():
    df = MarketData(fetch=_ticker_fetch()).candles("AUSD", "1d", 120)
    ind = indicator_frame(df, "1d")
    r = ind["rsi"].dropna()
    assert ((r >= 0) & (r <= 100)).all()
    last = ind.iloc[-1]
    assert last["bb_lower"] < last["sma20"] < last["bb_upper"]
    assert rsi(pd.Series(np.arange(50.0))).iloc[-1] == 100.0


# ------------------------------------------------------------- HTTP server

@pytest.fixture
def server(tmp_path):
    from apps.terminal.server import Terminal, make_server
    eng, df, clock = _engine_with_position(tmp_path)
    (tmp_path / "daily_trend_heartbeat.json").write_text(json.dumps({"ts": pd.Timestamp.now(tz="UTC").isoformat(), "pid": 1}))
    calls = {}

    def fake_gemini(url, body):
        calls["url"], calls["body"] = url, body
        return {"candidates": [{"content": {"parts": [{"text": "Your XYZUSD position is open."}]}}]}

    def fetch(url, params=None, timeout=8):
        if url.endswith("/v2/tickers"):
            return {"result": [{"symbol": "XYZUSD", "mark_price": str(clock.mark), "close": str(clock.mark)}]}
        return {"result": {"t": [int(t.timestamp()) for t in df.index], "o": list(df.open), "h": list(df.high),
                           "l": list(df.low), "c": list(df.close), "v": list(df.volume)}}

    term = Terminal(tmp_path, MarketData(fetch=fetch), symbols=["XYZUSD"], chat_post=fake_gemini, chat_key="KEY")
    srv = make_server(term, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def req(method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        h = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", **(headers or {})}
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"null")

    auth = {"X-Terminal-Token": term.token, "Origin": f"http://127.0.0.1:{port}"}
    yield req, auth, term, eng, calls, port
    srv.shutdown()


def test_every_get_endpoint_responds(server):
    req, *_ = server
    for p in ["/api/state", "/api/markets", "/api/candles?symbol=XYZUSD&tf=1d&bars=200", "/api/orders", "/api/trades",
              "/api/analytics", "/api/signals", "/api/events", "/api/risk", "/api/strategy", "/api/system"]:
        code, body = req("GET", p)
        assert code == 200, (p, body)
    code, st = req("GET", "/api/state")
    assert st["mode"] == "PAPER" and len(st["positions"]) == 1 and st["health"]["engine_alive"]
    code, c = req("GET", "/api/candles?symbol=XYZUSD&tf=1d&bars=200")
    assert c["markers"] and {ln["title"] for ln in c["lines"]} >= {"Entry"}
    assert req("GET", "/api/candles?symbol=NOPE")[0] == 400


def test_security_guards(server):
    req, auth, term, eng, calls, port = server
    assert req("GET", "/api/state", headers={"Host": "evil.example"})[0] == 403  # DNS rebinding
    body = {"kind": "PAUSE_ENTRIES", "payload": {"paused": True}}
    assert req("POST", "/api/commands", body)[0] == 403  # no token
    assert req("POST", "/api/commands", body, {**auth, "Origin": "http://evil.example"})[0] == 403  # CSRF
    assert req("POST", "/api/commands", body, {**auth, "X-Terminal-Token": "wrong"})[0] == 403


def test_commands_are_validated_and_executed_by_the_engine(server):
    req, auth, term, eng, calls, port = server
    assert req("POST", "/api/commands", {"kind": "CLOSE_POSITION", "payload": {"symbol": "NOPE"}}, auth)[0] == 400
    assert req("POST", "/api/commands", {"kind": "UPDATE_RISK_CONFIG", "payload": {"changes": {"risk_pct": 9}}}, auth)[0] == 400
    code, r = req("POST", "/api/commands", {"kind": "CLOSE_POSITION", "payload": {"symbol": "XYZUSD", "quantity": 1}}, auth)
    assert code == 202 and r["status"] == "PENDING"
    assert req("GET", f"/api/commands/{r['id']}")[1]["status"] == "PENDING"  # nothing happens until the engine runs
    asyncio.run(eng.process_commands())
    done = req("GET", f"/api/commands/{r['id']}")[1]
    assert done["status"] == "DONE" and done["result"]["remaining"] >= 0


def test_commands_rejected_when_engine_is_down(server):
    req, auth, term, eng, calls, port = server
    (term.data / "daily_trend_heartbeat.json").write_text(json.dumps({"ts": "2000-01-01T00:00:00+00:00"}))
    code, r = req("POST", "/api/commands", {"kind": "PAUSE_ENTRIES", "payload": {"paused": True}}, auth)
    assert code == 503 and "not running" in r["error"]


def test_live_stream_pushes_state(server):
    req, auth, term, eng, calls, port = server
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", "/api/stream", headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    assert r.status == 200 and r.getheader("Content-Type") == "text/event-stream"
    buf = b""
    t0 = time.time()
    while b"event: state" not in buf and time.time() - t0 < 8:
        buf += r.fp.read1(65536)
    assert b"event: state" in buf and b'"positions"' in buf
    c.close()


def test_chat_is_grounded_in_real_records(server):
    req, auth, term, eng, calls, port = server
    code, r = req("POST", "/api/chat", {"message": "Why is XYZUSD open?", "history": []}, auth)
    assert code == 200 and r["answer"] == "Your XYZUSD position is open."
    sent = json.dumps(calls["body"])
    assert "XYZUSD" in sent and "recent_orders" in sent and "latest_signals" in sent
    assert "cannot place" in calls["body"]["system_instruction"]["parts"][0]["text"]
    assert req("POST", "/api/chat", {"message": ""}, auth)[0] == 400


def test_chat_without_key_explains_instead_of_failing():
    from apps.terminal import chat
    r = chat.ask("hi", {}, key=None, post=lambda *a: pytest.fail("must not call the API"))
    if r.get("error"):
        assert "GEMINI_API_KEY" in r["error"]
    r = chat.ask("hi", {}, key="K", post=lambda url, body: {"error": {"message": "quota"}})
    assert "quota" in r["error"]


def test_exchange_stop_exit_uses_actual_fills(tmp_path):
    """Live adoption of NautilusTrader-style fill reconciliation: when the exchange stop
    closes a position, record the real average fill, not an assumed fill at the stop."""
    eng, df, clock = _engine_with_position(tmp_path)
    pos = eng.state.positions["XYZUSD"]
    q = pos.quantity
    a, b = q // 2, q - q // 2

    async def fills(symbol, since=None):
        return [{"side": "SELL", "size": a, "price": pos.stop * 0.99, "created_at": "2026-01-02T00:00:01Z"},
                {"side": "SELL", "size": b, "price": pos.stop * 0.98, "created_at": "2026-01-02T00:00:02Z"},
                {"side": "BUY", "size": q, "price": pos.entry_price, "created_at": "2025-01-01T00:00:00Z"}]

    eng.broker.get_recent_fills = fills
    eng.broker.positions.clear()
    asyncio.run(eng._reconcile({"skipped": [], "exits": []}))
    t = eng.store.query("SELECT * FROM trades")[-1]
    expected = (a * pos.stop * 0.99 + b * pos.stop * 0.98) / q
    assert t["exit_price"] == pytest.approx(expected) and t["exit_reason"] == "EXCHANGE_STOP"

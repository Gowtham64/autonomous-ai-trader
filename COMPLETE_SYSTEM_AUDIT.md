# Complete System Audit

**Date:** 7 November 2026  
**Scope:** Local repository, local API on `127.0.0.1`, and read-only inspection of configuration.  
**Safety:** `LIVE_TRADING_ENABLED` stayed false. No live broker orders were sent. A short local paper process was started for verification and then stopped. Paper state files it touched were restored to the last committed copies.

This is not a claim that every screen, endpoint, and production dependency is proven. Items below are what was inspected and what was changed.

## Architecture in one pass

- **UI:** `apps/dashboard/` (vanilla JS, Lightweight Charts). Served by FastAPI at `/`.
- **API:** `apps/api/main.py` plus `apps/api/routers/`.
- **Trading loop:** `apps/daemon/state_machine.py`, started once from the API lifespan.
- **Paper execution:** `execution/broker_factory.py` forces `DeltaPaperBroker` or `PaperBroker` when live trading is off or mode is `PAPER`.
- **Risk:** `risk/engine.py`, `risk/audit_gate.py`, `risk/kill_switch.py`.
- **Database:** SQLite via async SQLAlchemy (`database/models/tables.py`). Render config in `render.yaml` does not provision Postgres.
- **Deploy:** `render.yaml` web service, Docker runtime, health check `/health`, `TRADING_MODE=PAPER`, `LIVE_TRADING_ENABLED=false`, `EXCHANGE=DELTA`.

## Confirmed defects that were fixed

| Severity | Defect | Fix |
| --- | --- | --- |
| Critical | API startup called `kill_switch.reset("API Cloud Daemon")`, which cleared an engaged halt. | Reset removed. Daemon startup logs that the switch was not cleared. |
| Critical | Two trading loops could run `run_single_cycle` together (lifespan loop ignored stop, and `/api/daemon/start` could launch a second loop). | One task, one `asyncio.Lock` around each cycle. Start returns already-running when that task is alive. Stop cancels it. |
| High | Agent loop published `APPROVED`, `PASSED`, and `ORDER_SUBMITTED` on a timer with a hardcoded BTC price and a fake 1.94% drawdown. | Loop now records observed quote, kill-switch, broker equity, and last cycle status. `ORDER_SUBMITTED` is used only when the last cycle reports a submitted order. |
| High | `/api/ollama/register` fetched any caller-supplied URL (cloud metadata / private network). | Public http(s) only. Private, loopback, and link-local addresses rejected. Tunnel is used only when `OLLAMA_BRIDGE_TOKEN` matches. Status no longer returns the tunnel URL. |
| High | Quote cache shipped fixed equity and crypto prices (NIFTY, RELIANCE, BTC 67,420.50). Dashboard HTML repeated those numbers and a 73% win rate. | Cache starts empty and fills from Delta. Placeholders are "—" until a live quote or candle arrives. Agent cards no longer state a win rate or a $1,000 balance. |
| High | Evaluation clock reused `data/phase4_heartbeat.json` from an October soak and added 15 seconds per loop. Acceptance rows were marked PASS with no measurement. | Current clock is `data/live_session_heartbeat.json`, and only if the last heartbeat is under 3 minutes old. Stability and profit factor stay PENDING. |
| Medium | Guardian closed trades were stamped with `now()`, so old exits counted as today. | Timestamp uses `completed_at`. |
| Medium | Candle prices were rounded to 4 decimals. Sub-dollar contracts collided. | Decimal places follow price size, up to 8. |
| Medium | Market symbol and candle interval were interpolated into outbound URLs. | Symbol and interval are allowlisted. Trade limit is capped at 100. |
| Medium | Order and position quantity columns were integers. | Model columns are floats so fractional paper contracts are not truncated in Python. Existing SQLite files are not rewritten. |
| Low | Markets table listed both `BTCUSD` and `BTCUSDT` for the same Delta mark. | Table shows `USDT` display symbols. |

## What was verified

- `pytest tests/test_audit_repairs.py tests/test_security_audit_fixes.py`: 18 passed.
- Valuation and risk modules (`test_valuation_and_risk_patch.py`, forensic regression, PnL mark reconciliation, mark-price gates, phase4a prelaunch, valuation defect reproduction): 49 passed.
- Local API, with `EXCHANGE=DELTA` and live trading forced off for that process only:
  - `/health` returned `PAPER`.
  - `/api/market/quotes` returned Delta marks (BTC about 75,798, ETH about 2,232, SOL about 90, XRP about 1.185, DOGE about 0.073). Source field was `delta`.
  - `/api/market/candles?symbol=BTCUSDT&interval=5m` returned 576 candles, last price about 75,800.
  - Malformed candle symbol and `http://169.254.169.254/` registration returned HTTP 400.
  - Evaluation elapsed time was a few seconds, not the old 6,249-second soak clock.
- Browser on `http://127.0.0.1:8766/`: Overview and Markets rendered. Markets showed the Delta marks above, paper mode, and live trading disabled. Equity on that screen came from the paper broker.

## Not verified

- The public Render URL was not redeployed. Production still runs the previous build until you deploy this commit.
- Authenticated office, kill-switch, and daemon buttons were not clicked. Those routes stay open while `AUTH_REQUIRED=false`.
- Full NSE scan, Angel One, Zerodha, and Fyers sessions were not exercised.
- Postgres, Redis, and Telegram were not connected in this run.
- A multi-day paper soak was not repeated.

## Residual risk

See `PRODUCTION_READINESS_REPORT.md`. The largest remaining item is that mutating API routes are reachable without a password when `AUTH_REQUIRED` is false, which is the value in `render.yaml`.

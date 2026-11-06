# Bug Fix Report

Each row was reproduced from source or from the local API. "Fixed" means the code change is in the tree and a test or a local request checked the behavior. Production on Render does not have these fixes until a deploy.

## Fixed

### Kill switch cleared on boot
- **Cause:** `live_trading_execution_daemon_task` called `kill_switch.reset("API Cloud Daemon")` before the first cycle.
- **Effect:** A halt did not survive a process restart.
- **Change:** That call is gone. `tests/test_audit_repairs.py::test_startup_source_does_not_reset_kill_switch` checks the source and that `trigger` still leaves the switch engaged.
- **Check:** Local startup log said the kill switch was not reset.

### Overlapping trading cycles
- **Cause:** The lifespan loop did not look at `_daemon_is_running`, and `/api/daemon/start` built a second `AutonomousTradingDaemon`.
- **Effect:** Two cycles could size and submit paper orders for the same signal.
- **Change:** `_run_guarded_cycle` holds `_cycle_lock`. Start reuses the lifespan task. Stop cancels that task.
- **Check:** Code path review. A second live loop was not started during the browser check.

### Fabricated agent approvals
- **Cause:** The agent task wrote APPROVED / PASSED / ORDER_SUBMITTED every cycle, including a fixed BTC price of 80,100 when the cache was empty.
- **Change:** Status values are WAITING, OBSERVED, ENGAGED, ARMED, IDLE, or SUBMITTED. Order events require `orders_submitted` or `executed` on the last cycle summary.
- **Check:** `test_agent_actions_are_not_preapproved`. Browser agent cards no longer show a 73% win rate or a $1,000 balance.

### Seeded market prices
- **Cause:** `_live_quotes_cache` and several HTML nodes were initialized with fixed prices and percent changes.
- **Change:** Cache starts empty. HTML uses "—". Quotes appear after the Delta poll. Candles use Delta history (576 rows, last price about 75,800 in the local check).
- **Check:** `test_quotes_do_not_ship_seeded_equity_prices`. Browser Markets tab showed BTC 75,892.83 from Delta, not 67,420.50.

### Evaluation clock inherited an old soak
- **Cause:** The agent task rewrote `data/phase4_heartbeat.json` (elapsed 6,249 seconds, status STOPPED, October timestamp) and the API treated that as the 3-day run. Missing files defaulted to 3,600 seconds. Criteria were hardcoded PASS.
- **Change:** Session file is `data/live_session_heartbeat.json`. Stale heartbeats count as zero elapsed and status IDLE. Drawdown and daily loss are compared with settings. Stability stays PENDING.
- **Check:** `test_evaluation_does_not_replay_old_soak_clock`. Local `/api/evaluation/status` elapsed was about 6 seconds.

### Ollama registration SSRF
- **Cause:** `POST /api/ollama/register` GET the caller URL with no host check, and a successful probe became the first LLM route.
- **Change:** `apps/api/request_guards.py` rejects non-public hosts. Inference stays off unless `OLLAMA_BRIDGE_TOKEN` matches. `scripts/auto_mac_bridge.py` sends that token when it is set.
- **Check:** Metadata URL returned 400. Public IP without the token returned 403.

### Guardian trade dates
- **Cause:** Unified history used `datetime.now()` for guardian exits.
- **Change:** Uses `PostTradeQualityReport.completed_at`.
- **Check:** `test_guardian_timestamp_uses_completed_at` expects `2026-01-02`.

### Candle precision and symbol injection
- **Cause:** OHLC rounded to 4 places. `symbol` was placed in the Delta query string.
- **Change:** `price_decimals` and `normalize_market_symbol`.
- **Check:** Unit test for 8 decimals under $1. Local candle request with `../../etc/passwd` returned 400.

### Integer contract size
- **Cause:** `OrderEntity.quantity` and `PositionEntity.quantity` were integers.
- **Change:** Float columns on the model. SQLite `create_all` will not alter an existing file; new Python writes no longer coerce through `Integer`.

## Left open

- Control routes (`/api/kill-switch`, `/api/daemon/start`, `/api/daemon/cycle`, skill execute) do not require a password while `AUTH_REQUIRED=false`.
- Public trade tape still reads Binance, while marks and candles read Delta. Prices can disagree.
- `decision_id` on orders is not a foreign key.
- Historical database decisions can still appear in `/api/office/agent-actions`. They are stored rows, not the timer script.
- Render has not been updated.

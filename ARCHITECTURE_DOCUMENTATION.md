# Architecture

## Request path

Browser `apps/dashboard/app.js` polls same-origin JSON (`/api/performance`, `/api/positions`, `/api/orders`, `/api/market/quotes`, `/api/market/candles`, `/api/evaluation/status`, `/api/office/agent-actions`, `/api/events`). A WebSocket at `/ws/live-feed` pushes the quote cache, treasury metrics, and an open-position count about once a second.

FastAPI (`apps/api/main.py`) serves the dashboard, those routes, guardian routes, and training routes. The lifespan starts four background jobs:

1. Delta ticker poll into `_live_quotes_cache` (about every 2 seconds).
2. Observed agent log (about every 20 seconds). It does not approve trades.
3. One trading loop (`live_trading_execution_daemon_task`) that calls `AutonomousTradingDaemon.run_single_cycle` about every 45 seconds, behind `_cycle_lock`.
4. A self health ping so the Render free instance is less likely to sleep.

`/api/daemon/start` uses that same loop. It does not create a second one. `/api/daemon/cycle` takes the same lock.

## Trading path

`QuantMarketScanner` proposes candidates. `apps/daemon/state_machine.py` checks broker funds, the kill switch, and the risk engine, then sizes and routes through `OrderRouter`. With `LIVE_TRADING_ENABLED=false` or `TRADING_MODE=PAPER`, `execution/broker_factory.py` returns a paper broker. Delta uses `execution/paper/delta_paper.py`. Other names use `execution/paper/broker.py`.

Live adapters (Angel One, Zerodha, Fyers, Delta) are constructed only when live trading is enabled and mode is not `PAPER`.

## Data

- Runtime paper book: `data/paper_broker_state.json`.
- Daily loss baseline: `data/daily_risk_state.json`.
- Current evaluation clock: `data/live_session_heartbeat.json` (written by the API process, ignored as a historical soak).
- SQL tables: `trade_decisions`, `orders`, `positions`, `trade_journal` in `database/models/tables.py`. SQLite file default `data/trader.db`.
- Older soak artifacts (`data/phase4_heartbeat.json`, `PAPER_7DAY_TRADE_LEDGER.csv`) are historical. Performance and today's order view do not merge those ledgers. Agent actions include a ledger row only when its timestamp is today.

## Agents

The office roster in the dashboard is a status list. Trade permission still sits in the daemon and the risk gate. The background narrator records what it can read: quote cache, kill switch, last cycle dict, and broker equity. It does not invent a 14-point pass.

LLM calls go through `agents/llm_router.py`. A Mac Ollama tunnel is first in line only after `/api/ollama/register` validates a public URL and `OLLAMA_BRIDGE_TOKEN`. Otherwise Groq, Gemini, or the configured provider is used.

## Deploy

`render.yaml` is a single Docker web service in Singapore on the free plan. Health path is `/health`. There is no separate worker service. The trading loop runs inside the web process. The filesystem on Render is ephemeral, so SQLite and JSON state under `data/` do not survive a new instance unless a disk is attached. That is an environment limit, not something this change alters.

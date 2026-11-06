# API Audit

Routes are declared in `apps/api/main.py`, `apps/api/routers/guardian.py`, and `apps/api/routers/training.py`. This inventory is from source. Only the rows in "Exercised" were called.

## Exercised locally

| Method | Path | Result |
| --- | --- | --- |
| GET | `/health` | 200, `trading_mode=PAPER` |
| GET | `/` | 200 dashboard HTML. Watchlist and chart placeholders are "—" before quotes arrive. |
| GET | `/api/market/quotes` | 200. Empty until the Delta poll succeeds, then marks with `source=delta`. No RELIANCE or NIFTY seeds. |
| GET | `/api/market/candles?symbol=BTCUSDT&interval=5m` | 200, 576 candles, last price about 75,800. |
| GET | `/api/market/candles?symbol=../../etc/passwd` | 400 |
| GET | `/api/evaluation/status` | 200. Elapsed from the current session only. System stability is PENDING. |
| POST | `/api/ollama/register` with a link-local URL | 400 |
| POST | `/api/ollama/register` without `OLLAMA_BRIDGE_TOKEN` | 403 |
| GET | `/api/office/agent-actions` | 200. Seed text "Max Drawdown (1.94%" and "Confluence score 82%" absent. |

`/api/performance` and `/api/orders` are covered by `tests/test_dashboard_endpoints.py` when that file is run. It was not re-run in this pass because it calls public candle and trade hosts. The handlers still exclude historical CSV ledgers from today's P&L (`include_historical_ledgers=False` plus a UTC date prefix).

## Auth behavior

`get_current_user` returns an admin principal when `AUTH_REQUIRED` is false, including when no token is sent. `require_admin` then allows the call. `render.yaml` sets `AUTH_REQUIRED=false`. Read endpoints used by the dashboard depend on that. Write endpoints do too, which is the open issue in the security report.

When `AUTH_REQUIRED` is true, missing or bad bearer tokens get 401. That path is covered by `tests/test_security_audit_fixes.py`.

## WebSocket

`/ws/live-feed` checks a token only when `AUTH_REQUIRED` is true. Payload `positions_count` is the paper broker position length, cached about 5 seconds. It is no longer hardcoded to 0.

## Third parties touched by these routes

- Delta India public tickers and chart history for quotes and candles.
- Binance public trades for `/api/market/trades` (different venue).
- Optional Ollama tunnel, only after the bridge token check.
- Broker credentials are not returned by `/health` in paper mode (`broker_client` is `PAPER_LOCAL`).

## Not called in this audit

Factory agent create/delete, skill execute, memory record, premarket prepare, analyze, batch debate, kill-switch POST, daemon start/stop/cycle, guardian emergency exit, and training triggers. They remain in the source. They were not fired, because several of them start work or change control state.

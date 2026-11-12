# Trading Terminal, Framework Benchmark & Implementation Report

Scope: Delta Exchange perpetual futures, daily trend strategy (the only strategy in this repo with a
backtested edge). Date: 2026-11-12. Everything below was built and tested in **paper mode**; no live
orders were sent.

---

## 1. Architecture analysis: the trade lifecycle as it now runs

| Stage | Where | How it works |
|---|---|---|
| Market data | `market/providers/yfinance_provider.py` (engine), `apps/terminal/market.py` (terminal) | Delta public REST: daily candles (`/v2/chart/history`), mark price (`/v2/tickers/{sym}`). Terminal adds full tickers (bid/ask, funding, OI, contract size) every 5s. |
| Analysis & signals | `strategy/daily_trend.py` | Donchian 55/20 on **completed** daily candles only; ATR(20). One copy of the code shared by the live engine and the backtest. |
| Signal record | `apps/daemon/daily_trend_engine.py` → `signals` table | Every coin, every daily close: levels, signal, and what the engine did and why. |
| Risk validation | engine `_update_risk`, `_entries_allowed`; `risk/daily_trend_config.py`; `risk/kill_switch.py`; `risk/edge_gate.py` | Mark-to-market drawdown and daily loss → persisted kill switch; pause flag; per-coin disable; realized-edge gate (live). |
| Position sizing | `size_position()` | Contracts so the stop risks `risk_pct` of equity; **skips** rather than oversizes. |
| Order execution | engine `_enter` / `_exit` → broker | Market orders; paper = `DeltaPaperBroker`, live = `DeltaExchangeBroker` (only if 3 flags are set). |
| Monitoring | engine `_check_stops` (every 15 min + exchange-side stop in live) | Trailing stop raised at each daily close; exchange stop moved with it. |
| Exits | trend exit, stop, take-profit (manual), terminal close/partial | Recorded closed **only after the broker confirms**; a rejected exit stays open and is retried. |
| P&L | `_record_exit` | From fill prices: gross, fees (taker + GST both sides), net, R multiple. Exchange-stop exits use real fills (`/v2/fills`). |
| Persistence | `apps/terminal/store.py` (`data/daily_trend.db`) + existing journal | Orders + raw broker response, trades, signals, events, equity, commands. WAL, transactions, append-only. |
| Dashboard | `apps/terminal/server.py` + `static/` | REST + Server-Sent Events. Live P&L revalued at exchange marks every 2–5s. |
| Actions | terminal → `commands` table → engine `process_commands` (every 2s) | Validated on the server, re-validated by the engine, answered with the broker result. |

## 2. Existing vs required (your spec, sections 1–10)

| Spec section | Before this work | Now |
|---|---|---|
| 1 Trading overview | Read-only page: equity, P&L, open positions | Capital, available/used margin, equity, today realized/unrealized, total P&L, win rate, W/L, avg win/loss, PF, drawdown, exposure, strategy status, bot health |
| 2 Live market monitoring | None for the new strategy | 15 coins: live price, 24h, volume, bid/ask spread, funding, trend, RSI, MACD, ATR%, VWAP, distance to breakout, last signal check; filter + sort |
| 3 Trading chart | Static equity line | Candles 1m–1D, volume, EMA20/50, SMA20, Bollinger, VWAP, RSI and MACD panes, entry/exit markers, entry/stop/initial-stop/TP lines, strategy levels |
| 4 Active trades | Table without actions | Live P&L, %, R, stop, distance to stop, TP, R:R, value, duration, status; **move stop, set/clear TP, partial close, close**, details |
| 5 AI chat | None | Gemini, grounded in a JSON snapshot of real records; cannot place orders |
| 6 AI agents | Hourly bot's agents (strategy has no edge; not running) | Shown honestly as **not applicable**; the System page monitors the real components instead |
| 7 Strategy management | None | Rule, params (read-only by design), coins on/off, risk settings, performance vs backtest, signal table |
| 8 Order management | None | Every order: IDs, type, side, qty, reference vs fill price, slippage, fee, status, mode, reason, raw broker response; command log |
| 9 History & analytics | Closed-trade list | Daily/weekly/monthly/coin/side/exit-reason breakdowns, equity + drawdown curves, win-rate trend, PF, holding time, vs backtest |
| 10 Risk dashboard | None | Exposure, leverage, capital at risk, daily loss vs limit, drawdown vs limit, concentration, remaining risk budget, events; editable limits with server + engine validation; pause; kill switch engage/reset |

## 3. Bugs and gaps found in this round (all fixed)

1. **Paper drawdown was blind to open losses.** The engine's risk checks used cash only in paper mode, so a large open loss could not trip the drawdown kill switch until the trade closed (live mode, using Delta `net_equity`, was fine). Now mark-to-market in both modes. Regression test: `test_open_losses_count_toward_drawdown_in_paper_mode`.
2. **Exchange-stop exits recorded at an assumed price.** A gap through the stop made the journal wrong. Now uses actual fills (NautilusTrader pattern); the estimate is only a labeled fallback.
3. **Chart panes misaligned / feedback loop.** The indicator panes had different time points from the candles. Now padded to identical times; sync only when ranges differ.
4. **Risk form wiped by auto-refresh**, and compared edits against stale settings. Fixed.
5. **Positions view drew only on stream updates**; **actions column off-screen**; **details panel clipped**. Fixed.
6. **Bid/ask missing → fake 0% spread** in the existing API code pattern. The terminal reports missing instead.
7. Old status-file dashboard replaced; `run_trend_dashboard.py` now opens the terminal.

Earlier rounds (already on GitHub): exits capped winners, limit-order stops, oversizing (3.5–6% risk), self-resetting kill switch, synthetic 73%-win benchmark, missing GST, no realized-edge gate.

## 4. Implemented changes (this round)

- `apps/terminal/store.py`: trading record + command queue (atomic claim, idempotent submit, 2-minute expiry, crash-safe).
- `apps/terminal/market.py`: Delta tickers/candles client with caching; indicators.
- `apps/terminal/analytics.py`: summary, breakdowns, curves, live risk view.
- `apps/terminal/chat.py`: grounded, read-only Gemini assistant.
- `apps/terminal/server.py` + `static/`: terminal (10 views), REST, SSE, security guards.
- `apps/daemon/daily_trend_engine.py`: persistence, commands, partial closes, manual TP/stop, MTM risk, fill reconciliation, heartbeat.
- `risk/daily_trend_config.py`: validated, operator-adjustable limits.
- `execution/brokers/delta_exchange.py`: `get_recent_fills()` (`GET /v2/fills`).
- `run_daily_trend.py`: commands every 2s, full cycle every 15 min. `run_terminal.py`: starts the terminal.
- `tools/backtest_trend_daily.py`: Monte Carlo drawdown distribution (Jesse pattern).

## 5. Database

- **New file** `data/daily_trend.db` (SQLite, WAL), created automatically. Tables: `orders`, `trades`, `signals`, `events`, `equity`, `commands` (schema in `apps/terminal/store.py`).
- **No migration of existing data.** The existing journal in `data/trader.db` is unchanged and still written (tagged `market_regime='DAILY_TREND'`). Nothing is deleted. Rows are only inserted; the only update is a command's status/result.

## 6. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | Account, positions at live marks, risk, health, recent commands |
| GET | `/api/stream` | SSE push of `/api/state` on change, 15s heartbeats, `retry: 3000` |
| GET | `/api/markets`, `/api/candles`, `/api/signals` | Market monitor, chart data, strategy signal check |
| GET | `/api/orders`, `/api/trades`, `/api/events`, `/api/analytics` | Records & analytics |
| GET | `/api/risk`, `/api/strategy`, `/api/system` | Risk view, strategy page, component health |
| GET | `/api/commands/<id>` | Command status and engine/broker result |
| POST | `/api/commands` | Queue `CLOSE_POSITION`, `MOVE_STOP`, `SET_TAKE_PROFIT`, `PAUSE_ENTRIES`, `UPDATE_RISK_CONFIG`, `ENGAGE_KILL_SWITCH`, `RESET_KILL_SWITCH` |
| POST | `/api/chat` | Grounded assistant |

Security: binds to 127.0.0.1; Host header must be localhost (DNS-rebinding guard); every POST needs the per-session token **and** same-origin `Origin` (CSRF guard); 503 if the engine is down (nothing would execute); bodies are size-limited.

## 7. Trading execution validation (paper)

- **Parity:** the live engine, driven through a year of days with the real paper broker, trades the exact days, exit reasons and entry prices of the backtest.
- **Commands** (automated + clicked in a real browser):
  - Move stop: valid → done; wrong side of price → rejected; wider than initial stop → rejected.
  - Take-profit: set, triggers an exit (`TAKE_PROFIT`), clear.
  - Partial close: 20 of 59 → +$9.52. Arithmetic checked by hand: (172.661 − 124.881) × 20 × 0.01 − fees.
  - Full close: the row disappeared only after confirmation. Rejected exit: the position stays open.
  - Risk settings: valid saved; invalid rejected by the browser, the server (400) and the engine.
  - Pause/resume; kill switch engage, and reset requiring typed confirmation.
- **Records:** every order stored with its raw broker response; trades satisfy net = gross − fees from fill prices; signals, events and equity recorded.
- **Crash safety:** commands mid-execution at shutdown → FAILED (never silently re-run); stale commands expire unexecuted.

## 8. Frontend tests

Driven through Chrome DevTools in a headless browser against a running server, paper engine and replayed data:
- all 10 views rendered with no console errors (other than a missing favicon)
- every action button above clicked through to an engine result
- filters, sorting, timeframe switching, overlay toggles, coin enable/disable and the chat error path all exercised
- desktop and phone-width layouts checked by screenshot

## 9. Real-time validation

- SSE delivers state within 2s of a change; heartbeats every 15s; the browser reconnects automatically (3s).
- Indicators show engine heartbeat age, price-feed age and link status; banners appear for engine down, kill switch, paused entries, price-feed errors and LIVE mode.
- SSE was chosen over WebSocket because it needs only the standard library and the browser reconnects it automatically. All updates are server → browser; actions use POST. Swapping in WebSocket later is self-contained (`_stream` + `connect()`).

## 10. Paper trading validation

- Paper-first is enforced in code: live requires `TRADING_MODE=live`, `LIVE_TRADING_ENABLED=true` **and** `DAILY_TREND_ALLOW_LIVE=true`.
- The paper account is isolated (`data/daily_trend_paper_broker.json`). Test counts: 68 tests in the new and related suites pass; the rest of the repo's suite is unchanged by this work.

## 11. Framework benchmark (from their source code, cloned 2026-11-12)

| Capability | Strongest reference (source) | This system | Status |
|---|---|---|---|
| Protections / circuit breakers | Freqtrade `plugins/protections/` (StoplossGuard, MaxDrawdown, Cooldown, LowProfitPairs) | Drawdown + daily-loss kill switch, realized-edge gate, re-entry block, pause, per-coin disable | Fully implemented and verified. StoplossGuard deliberately **not** adopted: pausing after N stops was never backtested and would change the tested rule. |
| Stop on exchange + trailing updates | Freqtrade `handle_trailing_stoploss_on_exchange` | Exchange stop placed from fill, moved when the trailing stop rises | Implemented. Verified in paper; the live path is unverified (no Delta access from this environment). |
| Order lifecycle & risk states | NautilusTrader `crates/risk/src/engine` (TradingState ACTIVE/REDUCING/HALTED, max notional, submit throttling) | Kill switch = REDUCING (exits allowed, entries denied); notional cap; commands serialized through one engine | Partially implemented: no per-second order throttle in the engine path (it sends a few orders per day). |
| Reconciliation | NautilusTrader `docs/concepts/execution/reconciliation.md` | Position reconciliation + **fill-based exit prices (adopted)** | Partially implemented: positions and exit fills; no full order-report reconciliation. |
| Executor per position | Hummingbot `strategy_v2/executors/position_executor` (triple barrier: SL, TP, time limit, trailing) | Per-position stop, trailing, optional TP | Implemented, except time limit (not part of the tested rule). |
| Backtest robustness | Jesse `modes/monte_carlo_mode`, `significance_test_mode` | 95% CI, out-of-sample sweep, **Monte Carlo drawdown distribution (adopted)** | Fully implemented and verified. |
| Strategy optimization | Freqtrade hyperopt, Jesse optimize mode | Grid sweep with train/test split | Partially implemented, deliberately small to limit overfitting. |
| WebUI + live push | Freqtrade `rpc/api_server/ws`, OctoBot web interface | Terminal + SSE | Fully implemented and verified (SSE, not WebSocket). |
| Multi-exchange connectors | Hummingbot connectors | Delta only (AngelOne for the old bot) | Not applicable to your futures-on-Delta scope. |
| AI agent orchestration | Hummingbot Condor | Not used by this strategy | Not applicable: the agent pipeline had no measurable edge. |

## 12. Remaining limitations (not hidden)

1. **Not validated against live Delta here.** This environment cannot reach Delta, so tickers, candles, `/v2/fills` and exchange-stop calls were tested with recorded or simulated data. The first runs on your Mac are the real validation (checklist below).
2. **Gemini chat** was tested with a stub; the real API call needs `GEMINI_API_KEY` and is unverified until you run it.
3. **Prices update every 5s (REST)**, not tick-by-tick WebSocket. That's adequate for a daily strategy.
4. **Single local user;** no login (localhost-only by design). Don't expose the port to a network.
5. **Strategy rule is not editable** from the UI, by design.
6. The old FastAPI dashboard (`apps/api`) for the hourly bot is untouched and separate.
7. The full repo test suite needs dependencies that weren't installable here; please run `pytest` on your Mac.

**Checklist for your first runs on your Mac:**
- the Markets page shows 15 coins with prices and spreads
- the Chart page loads for BTCUSD
- the System page is all green, except the daily scan before 05:30 IST
- the Assistant answers a question
- once a paper trade exists: move its stop, then partially close it

## 13. Production readiness assessment

- **Paper trading: ready.** The engine, risk controls, persistence and terminal are tested end to end.
- **Live trading: not yet.**
  1. Complete the Mac checklist above.
  2. Run paper for 2–3 months, until about 3–5 trades include stop, trail and trend-exit paths.
  3. Fund the account to roughly $300+, so trades size correctly at 1% risk.
  4. Then enable live deliberately with the three flags, starting small.
- The strategy's long-run edge is real but modest, and weak since 2024. No software change makes profit certain.

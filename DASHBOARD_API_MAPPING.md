# Dashboard API & Module Mapping (Phase 1)

This document establishes the verified contract between every redesigned frontend module and its backend data source.

---

## Module Mapping Matrix

| UI Module / Section | Target Data Displayed | Backend API Endpoint | HTTP Method | WebSocket / Polling | Response Data Path |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **A. Top Navigation & Safety** | Simulation status, Live disabled tag, Server time | `/health`, `/api/daemon/status` | `GET` | WebSocket `/ws/live-feed` | `status`, `trading_mode`, `live_enabled`, `timestamp` |
| **A. Portfolio Overview** | Equity, Starting Capital, Available Margin, Realized/Unrealized PnL, Win Rate, Profit Factor, Max Drawdown | `/api/performance`, `/api/treasury` | `GET` | 2s polling & WebSocket | `total_capital`, `available_cash`, `realized_pnl`, `unrealized_pnl`, `win_rate`, `profit_factor`, `max_drawdown` |
| **B. Live Market Watchlist** | BTC, ETH, SOL, XRP, DOGE prices, 24h change, spread, volume | `/ws/live-feed`, `/api/scan` | `GET` / `WS` | Real-time Stream | `quotes[]` (`symbol`, `ltp`, `change`, `volume`) |
| **B. Candlestick Terminal** | OHLCV bars, EMA 20, EMA 50, ATR 14, Volume bars | `/api/market/candles`, `/api/forecast/kronos` | `GET` | On symbol/timeframe switch | Array of `{ time, open, high, low, close, volume, ema20, ema50, atr14 }` |
| **B. Market Regime** | Regime name, Confidence, ATR, Volatility, Trend, Liquidity | `/api/data/risk-portfolio`, `/api/data/macro-context` | `GET` | 5s polling | `market_regime`, `confidence`, `volatility_atr14`, `trend`, `condition` |
| **C. Active Positions Table** | Symbol, Side, Size, Entry, Mark, SL, TP, PnL, Fees, Risk Status | `/api/positions`, `/api/guardian/status` | `GET` | 1s polling | `positions[]` (`symbol`, `direction`, `quantity`, `entry_price`, `mark_price`, `stop_loss`, `take_profit`, `unrealized_pnl`) |
| **C. Trade Detail Modal** | Order fills, strategy rationale, entry indicators, exit reason, PnL | `/api/orders`, `/api/office/decisions` | `GET` | On click trade | `trade_details` (`strategy`, `indicators`, `order_history`, `reconciled_pnl`) |
| **D. AI Agent Command Center** | 9 Core Agents: status, task, decision, timestamp, warnings | `/api/office/agents/live-work`, `/api/office/state` | `GET` | 3s polling | `agents[]` (`agent_id`, `name`, `status`, `current_task`, `latest_thought`, `last_active`) |
| **D. Live Activity Stream** | Real-time system events, scan results, filter rejections | `/api/events`, `/api/factory/messages` | `GET` | 2s polling | `events[]` (`timestamp`, `severity`, `component`, `message`) |
| **E. Trading Chat & Threads** | AI agent debates, trade reasoning, risk warnings, filters | `/api/office/agent/{id}/chat`, `/api/factory/messages` | `GET` / `POST` | On demand & 3s polling | `messages[]` (`sender`, `receiver`, `trade_id`, `content`, `timestamp`) |
| **F. Order History & Audit** | Order ID, Trade ID, Symbol, Type, Side, Qty, Fill Price, Status | `/api/orders` | `GET` | 3s polling | `db_orders[]`, `broker_order_book[]`, `broker_trade_book[]` |
| **G. Analytics & Equity Curve** | Equity curve history, PnL distributions, daily returns | `/api/treasury/balance-sheet`, `/api/performance` | `GET` | 5s polling | `history[]`, `daily_summaries[]`, `metrics` |
| **H. Risk Management Center** | 1% daily loss, 6% max DD, Kill Switch, Order Sentinel | `/api/kill-switch`, `/api/guardian/status` | `GET` | 2s polling | `is_engaged`, `circuit_breaker_active`, `daily_loss_pct`, `current_drawdown_pct` |
| **I. Paper Evaluation Monitor** | 168h / 14d Run ID, elapsed time, cycle count, criteria gates | `/api/daemon/status`, `/data/phase4_heartbeat.json` | `GET` | 2s polling | `phase`, `elapsed_seconds`, `target_duration_hours`, `acceptance_criteria[]` |
| **J. Logs & Audit Center** | Structured logs, scanner rejections, execution intents | `/api/events`, `/api/guardian/reports` | `GET` | 2s polling | `log_records[]` (`timestamp`, `level`, `module`, `details`) |
| **K. Settings & System Health** | Read-only config: universe, risk caps, broker connection | `/health`, `/api/system/network-info`, `/api/funds` | `GET` | Initial load | `trading_mode`, `broker_connected`, `db_status`, `redis_status` |

---

## Missing Backend Capabilities & Explicit Gap Document

To strictly honor Phase 4 ("*If a requested feature has no existing backend support, document the gap instead of silently inventing data*"):
1. **Historical Candlestick REST Endpoint:**
   - The backend contains `YFinanceMarketDataProvider.get_historical_ohlcv()`, but had no dedicated lightweight REST route `/api/market/candles` returning formatted OHLCV JSON. Added lightweight adapter endpoint in `apps/api/main.py`.
2. **Dedicated Evaluation Heartbeat Route:**
   - The evaluation runner writes directly to disk (`data/phase4_heartbeat.json` and `data_phase4e/phase4e_heartbeat.json`). A dedicated read-only endpoint `/api/evaluation/status` exposes these verified filesystem metrics directly to the dashboard without reading arbitrary disk paths on the client.

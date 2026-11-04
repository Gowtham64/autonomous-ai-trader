# Master Implementation Plan: Premium AI Trading Dashboard Redesign

**Visual Style:** Bloomberg Terminal / Dark Fintech  
**Target Resolution:** Responsive Desktop (1440px+), Tablet (768px - 1024px), Mobile (<768px)  
**Safety Status:** `TRADING_MODE=PAPER`, `LIVE_TRADING_ENABLED=false`  

---

## 1. Visual Design Architecture (Phase 2)

### Color Palette (Fintech Dark Palette)
- **Background Root:** `#080c14` (Deep obsidian navy)
- **Surface Cards:** `#0e1422` (Subtle dark slate)
- **Card Borders:** `rgba(255, 255, 255, 0.07)` with crisp 1px borders
- **Primary Accent / Brand:** `#06b6d4` (Cyan neon)
- **Positive / Profits:** `#10b981` (Emerald green)
- **Negative / Risk / Drawdown:** `#ef4444` (Vibrant crimson)
- **Warning / Pending:** `#f59e0b` (Amber gold)
- **Muted Text / Secondary:** `#94a3b8` / `#64748b`
- **Headings & Primary Text:** `#f8fafc` (Pure crisp off-white)

### Typography & Spacing
- Monospaced numeric displays (`JetBrains Mono`, `Roboto Mono`, or system monospace).
- Clean geometric sans-serif for UI labels (`Outfit`, `Inter`).
- Strict 8pt grid with 12px, 16px, 20px, and 24px container padding.
- Compact information density — zero oversized decorative banners, zero cartoonish icons.

---

## 2. Module Implementation Breakdown (Phase 3)

### Module A: Top Navbar & Overview Metrics Bar
- Header with green candlestick icon, Title: `AI Trading Dashboard`, Subtitle: `Autonomous Multi-Agent Crypto Trading System`.
- Navigation tabs: `Overview`, `Markets`, `Trading`, `AI Agents`, `Analytics`, `Logs`, `Settings`.
- Safety badges: `PAPER TRADING (SIMULATION)` in green outline pill, `LIVE TRADING: DISABLED` in red lock badge.
- Live clock in UTC: `MMM DD, YYYY HH:mm:ss UTC`.
- 8 KPI cards:
  1. Portfolio Equity ($) + 24h %
  2. Net P&L (Total) ($) + %
  3. Realized P&L ($)
  4. Unrealized P&L ($)
  5. Win Rate (%) + (W / L count)
  6. Profit Factor
  7. Max Drawdown (%) + Limit (≤ 6.00%)
  8. Daily Loss (%) + Limit (≤ 1.00%)

### Module B: Live Market Terminal & Watchlist
- Horizontal Crypto Ticker Pills: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, `DOGEUSDT`.
- Interactive Candlestick Chart:
  - Powered by TradingView's open-source **Lightweight Charts** library.
  - High performance Canvas rendering with EMA 20 (Cyan) and EMA 50 (Purple) overlay curves.
  - Volume histogram below candles.
  - Timeframe toggles: `1m`, `5m`, `15m`, `1h`, `4h`, `1D`.
  - Floating live crosshair with OHLCV values and price scale tag.
- Market Watchlist Table: Symbol, Price, 24h %, Bid/Ask Spread.
- Market Regime Card: Regime Tag (`BULLISH_TREND`), Confidence score, ATR (14), Volatility, Trend Direction, Liquidity state.

### Module C: Active Trading & Positions Table
- Tabs: `Active Positions (n)`, `Open Orders (n)`, `Recent Trades (n)`.
- Columns: Symbol, Direction (BUY/SELL badge), Strategy, Entry Price, Mark Price, Qty, Size ($), Stop Loss, Take Profit, Unrealized P&L ($ / %), Fees, Funding, Age, Risk Status.
- Detail View Modal: Clicking any trade opens comprehensive forensic audit breakdown (Entry thesis, indicators at fill, order audit trail, reconciled exit P&L).

### Module D: AI Agent Command Center
- 9 Dedicated Agent Panels with live pulse indicators:
  1. Market Scanner Agent
  2. Strategy Agent
  3. Market Regime Agent
  4. Expectancy Agent
  5. Risk Management Agent
  6. Position Sizing Agent
  7. Execution Agent
  8. Portfolio Monitoring Agent
  9. Recovery & Reconciliation Agent
- Real-Time Live Activity Stream showing timestamped logs, scanner filters, and risk rejections (`[INFO]`, `[REJECT]`).

### Module E: Trading Chat & Conversation Hub
- Real-time conversation threads filtered by Agent, Symbol, and Trade ID.
- Message timeline preserving strategy explanations, risk warnings, and entry/exit thesis.

### Module F: Order History & Execution Book
- Searchable, filterable order table: Order ID, Client Order ID, Symbol, Type, Side, Qty, Filled Price, Status, Fees, Slippage, Timestamp.
- CSV Export button.

### Module G: Analytics & Performance
- Interactive Equity Curve canvas chart.
- Drawdown & Risk breakdown (Current DD, Max DD, Daily Realized Loss vs 1% limit, Intraday MTM Loss vs 1% limit, Aggregate Committed Risk).
- Performance summary: Total trades, Win/Loss count, Profit Factor, Average Win, Average Loss.

### Module H: Risk Management Center
- Circuit breaker gauges.
- Kill switch manual trigger / reset controls with safety confirmations.
- Order Sentinel & Mark Price valuation reliability status.

### Module I: Paper Evaluation Monitoring
- Active evaluation card: Run ID (`Phase 4H.4 – 14-Day Paper Evaluation`), Start time, Target End time, Elapsed duration, Remaining duration, Progress bar.
- Evaluation targets checklist:
  - ◯ ≥ 0 completed round trips
  - ◯ Profit factor ≥ 1.20
  - ◯ Max drawdown ≤ 6.00%
  - ◯ ≤ 2 daily-loss breaches
  - ◯ Zero crashes / clean recovery

### Module J: Logs & Audit Center
- Searchable console with severity filter (`ALL`, `INFO`, `WARN`, `ERROR`, `REJECT`), component dropdown, and keyword search.

### Module K: Settings & System Health
- Read-only environment inspection: Trading Mode (`PAPER`), Live Enabled (`false`), Max Daily Loss (`1.00%`), Broker (`Delta Exchange`), Database connectivity, Redis connectivity.

---

## 3. Implementation Steps & Milestones

1. **Backend Integration (Read-Only Endpoints):**
   - Add `/api/market/candles` in `apps/api/main.py` using `YFinanceMarketDataProvider.get_historical_ohlcv()`.
   - Add `/api/evaluation/status` in `apps/api/main.py` to stream heartbeat and criteria from verified `data/` artifacts.
2. **Frontend Component Engineering (`apps/dashboard/index.html`):**
   - Restructure HTML into high-density 3-column / grid Bloomberg layout matching mockup.
   - Include lightweight-charts script.
3. **Styling & Design System (`apps/dashboard/style.css`):**
   - Write comprehensive dark fintech terminal styles, custom scrollbars, badges, glowing status dots, and responsive breakpoints.
4. **Interactive Logic & Controller (`apps/dashboard/app.js`):**
   - Implement TradingView Lightweight Charts initialization and candle streaming.
   - Wire up real-time tab navigation, REST pollers (1-3s), WebSocket reconnection, detail modals, filters, and CSV export.
5. **Testing & Verification:**
   - Execute regression test suite.
   - Verify zero modification to trading engine, position guardian, or paper soak runner.


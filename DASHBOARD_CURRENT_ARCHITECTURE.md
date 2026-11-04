# Current Dashboard Architecture Audit (Phase 1)

**System:** Autonomous AI Trading System (Indian Markets & Crypto Perpetuals)  
**Date:** 2026-11-05  
**Evaluation Mode:** `PAPER` (Simulation Enforced)  
**Live Trading:** `DISABLED` (`LIVE_TRADING_ENABLED=false`)  

---

## 1. Frontend Technology Stack & Routing

| Layer | Implementation | Details |
| :--- | :--- | :--- |
| **Architecture** | Modern Vanilla HTML5 / CSS3 / ES6 Modular JS | Zero build-step overhead; instant load; no heavy Node/Vite bundling required. |
| **Serving Mechanism**| FastAPI `StaticFiles` Mount | Mounted at `/static` via `apps/api/main.py:134`; Root endpoint `/` serves `apps/dashboard/index.html`. |
| **Typography** | Google Fonts | Inter / Outfit / JetBrains Mono (monospaced numerical readouts). |
| **3D Rendering** | Three.js (r128) + OrbitControls | Dedicated 3D AI agent trading office rendered at `/office` via WebGL. |
| **Primary Script** | `apps/dashboard/app.js` (1,700 lines) | REST polling (1-5s intervals), DOM manipulation, toast notifications, auth token caching. |
| **Style Sheet** | `apps/dashboard/style.css` (1,060 lines) | Custom CSS custom properties (variables), glassmorphic card overlays, responsive flex/grid layouts. |

### Existing Dashboard Routes
- `GET /` ➔ `apps/dashboard/index.html` (Primary Trading Operations Room)
- `GET /office`, `GET /agent-office` ➔ `apps/dashboard/office.html` (3D Agent Virtual Office)
- `GET /report`, `GET /daily-report` ➔ `apps/dashboard/report.html` (Daily EOD Trading & Forensic Audit Report)

---

## 2. Backend API Architecture & Service Contracts

The backend is built on **FastAPI** (`apps/api/main.py`, 1,211 lines) with asynchronous SQLAlchemy and Uvicorn.

### Key Service Components
1. **Office Service (`apps/api/office_service.py`)**:
   - Manages live state, tasks, agent thought-logs, mission objectives, and live agent chat.
2. **Trade Guardian Router (`apps/api/routers/guardian.py`)**:
   - Real-time protection status, stop-loss / target distance, bracket integrity, and broker reconciliation.
3. **Training Academy Router (`apps/api/routers/training.py`)**:
   - Curriculum progress, reinforcement learning episodes, and skills inventory.
4. **WebSocket Streaming (`/ws/live-feed`)**:
   - Sub-second live quotes (`_live_quotes_cache`), real-time treasury equity, open position counts, and daily loss metrics.

---

## 3. Database Schema & Persistence Layer

- **Engine:** SQLAlchemy 2.0 Async (`create_async_engine`) with `asyncpg` (PostgreSQL) and fallback `aiosqlite` (`database/session.py`).
- **Core Entities (`database/models/tables.py`):**
  - `OrderEntity`: `order_id`, `client_order_id`, `symbol`, `action`, `status`, `quantity`, `average_price`, `commission`, `executed_at`.
  - `PositionEntity`: `symbol`, `direction`, `quantity`, `entry_price`, `mark_price`, `stop_loss`, `take_profit`, `unrealized_pnl`.
  - `TradeDecisionEntity`: `decision_id`, `symbol`, `strategy`, `rationale`, `risk_score`, `timestamp`.
  - `TradeJournalEntity`: 4-quadrant outcome classification (`GOOD_DECISION_GOOD_OUTCOME`, etc.).
- **Telemetry Entities (`database/models/data_metrics_tables.py`):**
  - `TradeMetricEntity`, `RiskMetricEntity`, `MarketRegimeEntity`, `AgentPerformanceEntity`.

---

## 4. AI Multi-Agent Office & Communication System

The system operates a hierarchical 16-agent institutional roster (`agents/roster/sixteen_agents.py`):
1. **Chief Trading Officer (CTO Agent)**: Central decision synthesis and execution approvals.
2. **Quant Market Scanner**: Multi-symbol volatility, liquidity, and momentum screening.
3. **Strategy Agent**: Multi-timeframe trend, mean-reversion, and breakout engines.
4. **Market Regime Agent**: ATR, ADX, CPR, and trend categorization (`BULLISH_TREND`, `RANGE_BOUND`, etc.).
5. **Expectancy Agent**: Mathematical edge and payoff ratio modeling.
6. **Risk Management Agent**: Hard veto power, 14-point audit gate enforcement.
7. **Position Sizing Agent**: Volatility-adjusted Kelly / ATR risk budgeting.
8. **Execution Agent**: Order slicing, limit pegging, and broker routing.
9. **Portfolio Monitoring Agent**: Hard SL, trailing stops, and mark price supervision.
10. **Recovery & Reconciliation Agent**: Crash recovery, state hydration, and orphaned order cancellation.

### Inter-Agent Communication:
- **Message Bus (`agents/factory/message_bus.py`)**: Pub-sub channel message queue recording sender, recipient, message type, and payload. Exposed via `/api/factory/messages`.

---

## 5. Paper Evaluation State & Active Telemetry

- **Active Mode:** Delta Exchange Crypto Perpetuals Paper Soak Test.
- **State Directories:**
  - `data/`: `phase4_heartbeat.json`, `phase4_telemetry.json`, `daily_risk_state.json`, `order_audit_records.json`, `paper_7day_telemetry.json`.
  - `data_phase4e/`: `PHASE4E_EQUITY_AND_DRAWDOWN.csv`, `PHASE4E_ORDER_AND_FILL_AUDIT.csv`, `PHASE4E_TRADE_LEDGER.csv`.
- **Key Safety Invariants Active:**
  - `TRADING_MODE=PAPER`
  - `LIVE_TRADING_ENABLED=false`
  - `MAX_DAILY_LOSS_PCT=0.01` (1.00% daily loss hard circuit breaker)
  - `MAX_PORTFOLIO_DRAWDOWN_PCT=0.06` (6.00% maximum portfolio drawdown limit)

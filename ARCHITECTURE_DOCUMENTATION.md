# Autonomous AI Trader — Architecture Documentation

## 1. High-Level System Architecture

```
+-----------------------------------------------------------------------------------+
|                                 FRONTEND CLIENT                                   |
|   Vanilla JS (ES6+) • Lightweight Charts • Real-Time WebSockets • Dark UI         |
+-----------------------------------------------------------------------------------+
                                        |  REST / WS
                                        v
+-----------------------------------------------------------------------------------+
|                             FASTAPI APPLICATION SERVER                            |
|  - Routers: /api/performance, /api/positions, /api/orders, /api/evaluation/status  |
|  - Event Bus: Pub/Sub realtime telemetry, agent chatter, market tape               |
|  - Auth: JWT Bearer Tokens, Admin Role Verification, Path Sanitization             |
+-----------------------------------------------------------------------------------+
           |                                  |                         |
           v                                  v                         v
+-----------------------+          +--------------------+    +----------------------+
|   AI AGENT OFFICE     |          |   TRADING ENGINE   |    |  DATABASE & STORAGE  |
|  9 Autonomous Agents  |          |  - Quant Scanner   |    |  - SQLite (Async)    |
|  - CIO & Strategy     |          |  - Risk Gate (14p) |    |  - Event Journal     |
|  - Risk Governance    | <======> |  - Paper Broker    | -> |  - Audit Ledgers     |
|  - Order Sentinel     |          |  - Trade Guardian  |    |  - State Cache       |
|  - LLM Failover LPUs  |          |  - Delta Exchange  |    +----------------------+
+-----------------------+          +--------------------+
```

## 2. Component Specifications

### 2.1 Frontend (`apps/dashboard/`)
- **Core Files**:
  - `index.html`: Layout container with 8 top-level KPI cards, live chart, 9-agent status, active position blotter, and 8 modular views.
  - `app.js`: Client orchestration, state caching, API polling intervals, and chart rendering.
  - `style.css`: Responsive CSS grid, dark theme color variables, status indicators.

### 2.2 API Layer (`apps/api/`)
- **FastAPI Core**: `apps/api/main.py`
  - Lifespan tasks initialize database, launch market data quote poller, and run agent loop.
  - Security headers, CORS middleware restricted to allowed origins, and static file hosting for dashboard assets.

### 2.3 Quantitative Scanner (`scanner/quant_scanner.py`)
- **Asset Universe**:
  - Delta Exchange perpetual contracts (USDT & USD settled).
  - Dynamic compounding allocation: dynamically adjusts asset selection thresholds as equity scales beyond $6.00, unlocking BTC, ETH, and SOL at designated capital milestones.
- **Filters**:
  - EMA 20 / EMA 50 trend alignment.
  - 14-period Average True Range (ATR) volatility expansion.
  - Minimum 24h turnover and liquidity verification.

### 2.4 Risk Governance (`risk/engine.py`)
- **14-Point Pre-Trade Gate**:
  1. Market regime verification.
  2. Volatility threshold check (ATR).
  3. Liquidity depth test.
  4. Spread tolerance check (≤ 0.15%).
  5. Maximum position size limit.
  6. Maximum portfolio exposure (leverage cap ≤ 10x).
  7. Risk-to-Reward ratio verification (target R:R ≥ 1.50 : 1 with 0.05 tolerance).
  8. Hard stop loss mandatory anchor.
  9. Take profit mandatory anchor.
  10. Maximum open position concurrency limit (≤ 3 active positions).
  11. Daily loss circuit breaker (≤ 1.00% daily loss).
  12. Lifetime maximum drawdown gate (≤ 6.00% from high-water mark).
  13. Adverse slippage tolerance verification (0.05%).
  14. Capital adequacy and margin check.

### 2.5 Execution & Paper Broker (`execution/paper/delta_paper.py`)
- Emulates Delta Exchange REST/WebSocket behavior:
  - Realistic taker fee model (0.05%).
  - Adverse fill slippage (0.05%).
  - Accurate contract multipliers per asset (e.g., BTC = 0.001, ETH = 0.01).
  - Margin reservation upon order placement and release upon fill/cancel/exit.

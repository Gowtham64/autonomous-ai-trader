# DELTA EXCHANGE PHASE 3 — REAL-TIME 7-DAY PAPER-TRADING TEST PLAN

**Objective:** Transition from discrete-event simulation to a real-time, 7-calendar-day (168-hour wall-clock) autonomous paper run using live Delta Exchange market data feeds and simulated order execution.  
**Execution Engine:** [`execution/paper/delta_paper.py`](file:///Users/gowthamp/Trading-AI-Agents-Live/execution/paper/delta_paper.py) with Live WebSocket/REST Price Provider.  
**Safety Enclosure:** Zero outbound live orders. Isolated paper execution.  

---

## 1. Test Architecture & Data Pipelines

```
┌─────────────────────────────────────────────────────────────┐
│             Delta Exchange Public Market Data               │
│    REST /v2/products + WebSocket v2:ticker / v2:orderbook   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Live Tick / Candle Stream)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│      QuantMarketScanner & MultiStockOrchestrator            │
│    Real-time Momentum, ATR-14, 20-Day Baseline Scanner      │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Generated Trade Signals)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│      DeterministicRiskEngine & PositionSizer                │
│    Daily Circuit Breaker, 5x Leverage Cap, Exposure Cap     │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Approved Order Intents)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    DeltaPaperBroker                         │
│   In-Memory Simulated Matching Engine with 0.05% Slippage   │
│           Zero Live Orders Placed (Isolated Sandbox)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Operational Protocol for 168 Wall-Clock Hours

1. **Continuous Daemon Process:** Deploy daemon via `start_auto.sh` supervised by systemd or tmux session.
2. **Heartbeat Monitoring:** Health check endpoint (`/health` on FastAPI daemon) polled every 60 seconds.
3. **Real-Time Market Data Stale Guard:** If no tick is received for a symbol within 45 seconds, trading on that symbol is halted immediately.
4. **Daily Midnight Rollover (00:00 UTC):** Automatic reset of daily realized loss counter while persisting equity.
5. **Real-Time Journal Persistence:** Every trade execution is immediately written to SQLite database and CSV trade journal.

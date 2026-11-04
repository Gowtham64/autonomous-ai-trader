# Autonomous AI Trading Office (NSE/BSE)

A production-grade, self-managed autonomous AI trading organization designed specifically for Indian financial markets (NSE & BSE) operating under a **₹2,000 bootstrap capital** model.

## Core Architectural Pillars (Master Instruction)

1. **Self-Managed AI Trading Office**:
   - **Chief Trading Officer**: Central decision-maker, multi-agent synthesis, and execution approval.
   - **Quant Market Scanner**: Scans large universes (Nifty 50, Nifty 100) concurrently for liquidity, volume, momentum, and regime.
   - **Specialist Analysts**: Technical (Multi-timeframe), Fundamental (Valuation & Earnings), News & Events, Sentiment, Macro (RBI policy & breadth).
   - **Adversarial Debate Arena**: Bull Researcher vs. Bear Researcher mediated by an impartial Facilitator.
   - **Risk Manager**: Independent deterministic veto authority over every proposed trade.
   - **Dynamic Specialist Agents**: Managed lifecycle for Sector Research, Options, Strategy Validation, and Execution Optimization with automatic Survival Mode shutdown.

2. **"Earn to Survive" Economic Model & AI Treasury**:
   - **Initial Bootstrap Capital**: **₹2,000.00** treated as scarce capital.
   - **AI Treasury Accounting**: Tracks capital, realized/unrealized P&L, and operating expenses (LLM API tokens + compute + exchange fees).
   - **Survival Mode**: Automatically triggers if capital drops below 80% (₹1,600) or runway falls below critical threshold. Halves risk per trade, freezes dynamic agents, and halts non-essential activity.

3. **14-Point Mandatory Pre-Trade Audit Gate**:
   - Every candidate trade must pass all 14 soundness checks (clear thesis, strategy match, market regime, stop-loss placement, bounded max loss, minimum 1:1.5 R:R, liquidity, correlation, and consensus) before execution clearance.

4. **4-Quadrant Post-Trade Learning Loop**:
   - Classifies every completed trade into:
     - `Good Decision → Good Outcome`: Edge verified.
     - `Good Decision → Bad Outcome`: Normal statistical variance; stop loss protected capital.
     - `Bad Decision → Good Outcome`: Lucky win; penalized to prevent bad habits.
     - `Bad Decision → Bad Outcome`: Flawed process; invalidation logic audited.

5. **Independent Emergency Kill Switch**:
   - Absolute circuit breaker triggered by daily loss limits (2% = ₹40 on ₹2k), max drawdown (5% = ₹100 on ₹2k), broker disconnection, or corrupt market data.

6. **Statistical Capital Scaling**:
   - No blind scaling. Scaling beyond ₹2,000 bootstrap requires empirical proof (20+ completed trades, ≥55% win rate, Profit Factor ≥ 1.6, Max Drawdown < 4.5%).

---

## Directory Structure
```
autonomous-ai-trader/
├── apps/                # CLI, FastAPI, and Daemon runners & Web Dashboard
├── core/                # Config, Domain models, Schemas, AI Treasury
├── agents/              # Core Analysts, Bull/Bear Debate, Facilitator, Fund Manager, Lifecycle
├── orchestration/       # LangGraph multi-agent & batch execution workflows
├── market/              # NSE/BSE Market calendar, Data providers, Normalization
├── scanner/             # Quant pre-filtering (Nifty 50 / Nifty 100 universes)
├── strategy/            # Multi-Strategy Engine (Momentum, Trend, Mean Reversion)
├── risk/                # Deterministic Risk Engine, 14-Point Audit Gate, Kill Switch
├── portfolio/           # ATR Position Sizer & Capital Scaling Policy
├── execution/           # Broker interfaces, PaperBroker, Indian broker adapters
├── monitoring/          # Position Monitor, Hard SL, Trailing Stop, Thesis Invalidation
├── memory/              # 4-Quadrant Learning Loop & Reflection Journal
├── backtesting/         # Event-driven backtester with transaction costs & slippage
└── database/            # SQLAlchemy async models & persistence repositories
```

---

## Quick Start & CLI Reference

```bash
# 1. Activate Environment
source .venv/bin/activate

# 2. View AI Office Roster & Treasury
python apps/cli/main.py status
python apps/cli/main.py treasury-cmd
python apps/cli/main.py office

# 3. Parallel Scanning across N Stocks
python apps/cli/main.py scan --universe nifty50 --top 10

# 4. Multi-Stock Research, Bull/Bear Debate & 14-Point Audit
python apps/cli/main.py analyze --symbols "RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS"
python apps/cli/main.py batch-debate --universe nifty50 --top 5

# 5. Autonomous Paper Trading Cycle on Bootstrap ₹2,000 Capital
python apps/cli/main.py paper --universe nifty50 --top 5

# 6. Post-Trade Learning & Capital Scaling Verification
python apps/cli/main.py learning
python apps/cli/main.py scale

# 7. Emergency Kill Switch Controls
python apps/cli/main.py kill
python apps/cli/main.py kill --engage --reason "Manual circuit breaker test"
python apps/cli/main.py kill --reset

# 8. Custom AI Agent Factory & Workforce Governance
python apps/cli/main.py agent list
python apps/cli/main.py agent create --name "Nifty Scalper" --prompt "Monitor NIFTY volume breakouts and momentum. Analyze top candidates every 15 min and send briefs to Chief Trading Agent."
python apps/cli/main.py agent test agent_momentum_hunter --symbol TATAMOTORS.NS
python apps/cli/main.py agent clone agent_momentum_hunter "Momentum Hunter - Mid Cap"

# 9. Unified 3-Layer AI Memory & Knowledge Graph
python apps/cli/main.py memory search -q "breakout"
python apps/cli/main.py memory summary
python apps/cli/main.py graph

# 10. AI Self-Sustaining Economy, CFO, CTO & Balance Sheet
python apps/cli/main.py balance-sheet
python apps/cli/main.py cfo
python apps/cli/main.py cto

# 11. Launch Live Autonomous System (AngelOne + Google Gemini on Laptop)
python run_live.py
# or via CLI:
python apps/cli/main.py live --broker angelone --universe nifty50
```

---

## Custom AI Agent Factory (Sections 19–40)

- **Natural Language Agent Generation**: Convert natural language prompt instructions into fully configured agents with assigned tools, data sources, and system prompts.
- **Strict "Deny-by-Default" Security**: Intelligence permissions (`read_market_data`, `run_technical_analysis`, `generate_signals`) are strictly separated from Financial/Action permissions (`place_live_orders`, `modify_risk_limits`, `withdraw_money`).
- **Anti-Replication Hard Limits**: Prevents uncontrolled agent proliferation (Max 50 total agents, max 10 creations/day).
- **Multi-Stage Sandbox Lifecycle**: `CREATED` ➔ `SANDBOX` ➔ `PAPER_TRADING` ➔ `APPROVED` ➔ `ACTIVE` ➔ `MONITORED` ➔ `PAUSED` / `RETIRED`.
- **Inter-Agent Message Bus & Voting Hub**: Hierarchical messaging bus with priority channels and multi-agent voting tallies with independent Risk Agent veto powers.
- **Cost Center & Resource Limits**: Per-agent compute and API usage accounting (`losses_prevented_inr`, `value_generated_inr`).

---

## Unified AI Memory & Interconnection (Sections 41–62)

- **3-Layer Memory Architecture**:
  - **Level 1 (Private Agent Memory)**: Isolated observations, pattern discoveries, and private experiences.
  - **Level 2 (Shared Organizational Memory)**: Collective knowledge, regime shifts, and cross-firm trade observations.
  - **Level 3 (Permanent Knowledge Memory)**: Institutional principles surviving agent resets, restarts, and model upgrades.
- **Strict Memory Access Control & Quality Categorization**: Distinguishes `FACT`, `OBSERVATION`, `PREDICTION`, `OPINION`, `HYPOTHESIS`, and `LESSON`. Prevents credentials or secrets from ever entering AI memory.
- **Memory Manager Agent**: End-of-session consolidation, deduplication, contradiction resolution, lesson extraction, and daily memory briefs.
- **Interconnected Knowledge Graph**: Entity and relationship network mapping `Company` $\leftrightarrow$ `Sector` $\leftrightarrow$ `Market` $\leftrightarrow$ `Strategy` $\leftrightarrow$ `Signal` $\leftrightarrow$ `Trade` $\leftrightarrow$ `Outcome` $\leftrightarrow$ `Agent` $\leftrightarrow$ `Decision` $\leftrightarrow$ `Risk Event`.
- **Event-Driven Pub-Sub Bus & Task Handoff Engine**: Real-time event routing (`ORDER_FILLED`, `PRICE_MOVEMENT`, `TREASURY_WARNING`) activating only relevant specialist agents.

---

## AI Self-Sustaining Economy, CFO, CTO & Balance Sheet (Sections 63–84)

- **₹2,000 Bootstrap Multi-Bucket Treasury**: Separates Trading Capital, Operating Reserve, AI Upgrade Fund, Infrastructure Reserve, Emergency Reserve, and Reinvestment Surplus.
- **Profit Allocation Engine**: Configurable net profit distribution (25% Operating Reserve, 25% Emergency Reserve, 20% AI Upgrade Fund, 10% Infrastructure, 20% Trading Reinvestment).
- **AI CFO Agent**: Model routing tiers (`LOW_COST`, `STANDARD`, `ADVANCED`, `MULTI_MODEL`), agent ROI accounting (including risk loss-prevention credit), and runway forecasting.
- **AI CTO Agent & System Upgrade Engine**: Gated validation pipeline (`PROPOSE` ➔ `SANDBOX` ➔ `UNIT_TEST` ➔ `BACKTEST` ➔ `PAPER_TRADING` ➔ `CANARY` ➔ `DEPLOY`) with automated rollbacks upon performance degradation.
- **Official AI Organization Balance Sheet**: Real-time balance sheet reporting Capital Structure, Income & Expenses, Profitability, System Health, and Survival Runway.

---

## Production Deployment: Docker, PostgreSQL & GCP

### 1. Local / Server Docker Compose Stack
Orchestrates PostgreSQL 16, Redis 7, FastAPI/Dashboard, and the Autonomous Trading Daemon:
```bash
# Build and launch stack
docker compose up -d --build

# View logs
docker compose logs -f daemon
docker compose logs -f api

# Shutdown stack
docker compose down
```

### 2. PostgreSQL Configuration
The database uses `asyncpg` for high-throughput asynchronous execution:
- Connection URL in `.env`:
  ```bash
  DATABASE_URL=postgresql+asyncpg://trader:traderpassword@postgres:5432/trading_db
  ```
- Tables are automatically synchronized on startup via `await init_db()`.

### 3. Deploying to Google Cloud Platform (GCP)
Deploy to a dedicated GCP Compute Engine instance (recommended for persistent WebSockets and daemons):
```bash
# Configure gcloud
gcloud auth login
gcloud config set project <YOUR_GCP_PROJECT_ID>

# Run deployment script (creates VM, installs Docker, syncs code, launches stack)
./scripts/deploy_gcp.sh
```
The Trading Dashboard will be accessible at `http://<GCP_EXTERNAL_IP>:8000`.



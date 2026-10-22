# DELTA EXCHANGE FORENSIC AUDIT & BUG FINDINGS REPORT

**Date of Audit:** October 22, 2026  
**Auditor:** Quantitative Trading Systems & Forensic Execution Engineer  
**System Investigated:** Autonomous Crypto Perpetual Trading System (Delta Exchange)  
**Workspace:** `/Users/gowthamp/Trading-AI-Agents-Live`  
**Branch:** `audit-fix-delta`  
**Status of Live Trading:** API Disconnected | Background Daemon Unloaded (`launchctl com.trading-ai-agents.live` stopped)

---

## 1. EXECUTIVE SUMMARY & VERIFICATION MATRIX

An independent, source-code-level forensic investigation was conducted on the trading bot repository, historical SQLite database (`data/trader.db`), system logs (`logs/live.log` — 219,039 lines), process supervisor records (`logs/supervisor.log`), and Delta Exchange product specifications.

Every reported defect from the preliminary audit was independently validated against source code and production logs.

| Defect ID | Description | Severity | Forensic Status | Primary Impact |
| :--- | :--- | :--- | :--- | :--- |
| **BUG-01** | Contract multiplier omitted in P&L, fees, and analytics | **CRITICAL** | **CONFIRMED** | +$7.71 phantom profit recorded; true P&L overstated by 100x on micro contracts |
| **BUG-02** | Bracket-order race condition (fixed 0.5s sleep) | **CRITICAL** | **CONFIRMED** | 13 exchange rejections (`no_open_position`); positions left unprotected |
| **BUG-03** | Stop-loss slippage inversion on market entry | **CRITICAL** | **CONFIRMED** | Immediate stop-outs on tick 1 (e.g., STXUSD killed in 6 seconds at market fill) |
| **BUG-04** | Exit orders omitted from database `orders` table | **CRITICAL** | **CONFIRMED** | 0 exit orders persisted; 100% of rows stuck in `SUBMITTED` status |
| **BUG-05** | Broker-reconciled position closures drop trade records | **HIGH** | **CONFIRMED** | Exchange bracket stops dropped from journal, skewing win-rate & expectancy |
| **BUG-06** | Daily loss circuit breaker resets on process restart | **HIGH** | **CONFIRMED** | 48 supervisor restarts wiped accumulated losses, defeating risk gating |
| **BUG-07** | Premature profit-taking on forming 5m candle wicks | **HIGH** | **CONFIRMED** | Winners snipped at +0.3% to +0.8%, destroying risk-reward expectancy |
| **BUG-08** | Incomplete daily candles skewing volume & indicators | **HIGH** | **CONFIRMED** | 20-day volume contaminated by partial daily bars early in UTC day |
| **BUG-09** | Orphaned protective orders after manual/market exits | **HIGH** | **CONFIRMED** | Residual bracket orders left open on exchange when Guardian exited |
| **BUG-10** | Currency and risk-limit unit confusion (USD vs INR) | **MEDIUM** | **CONFIRMED** | Misleading ₹ symbols and hardcoded thresholds in USD crypto calculations |

---

## 2. DETAILED DEFECT INVESTIGATIONS & EVIDENCE

### BUG-01: Contract Multiplier & P&L Calculation Omission
- **Severity:** CRITICAL
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  `PostTradeAnalyticsEngine` (`guardian/post_trade_analytics.py`) and `PositionGuardian` (`guardian/position_guardian.py`) computed gross profit as:
  $$\text{Gross P\&L} = (\text{exit\_price} - \text{entry\_price}) \times \text{quantity}$$
  This completely omitted the Delta Exchange `contract_value` / `contract_multiplier` defined in official instrument specifications (`data/delta_contract_multipliers.json`).
- **Forensic Evidence:**
  1. **Trade #1 (XMRUSD):** Entry $576.88, Exit $580.866, Qty 1 contract.
     - Price move: +$3.986.
     - Multiplier for XMRUSD: `0.01` (1 contract = 0.01 XMR).
     - Actual Real Gross P&L: $\$3.986 \times 1 \times 0.01 = \mathbf{+\$0.0399\text{ USD}}$.
     - Database Journal Record (`data/trader.db` row 1): **`pnl = +3.41`**. Overstated by **85x**!
  2. **Trade #2 (BCHUSD):** Entry $535.10, Exit $540.10, Qty 1 contract.
     - Multiplier: `0.01`. Actual Real Gross P&L: $\$5.00 \times 1 \times 0.01 = \mathbf{+\$0.05\text{ USD}}$.
     - Database Journal Record (`data/trader.db` row 2): **`pnl = +4.39`**. Overstated by **88x**!
  3. **Trade #3 (TSLAXUSD):** Entry $368.95, Exit $368.530, Qty 2 contracts.
     - Price move: -$0.42. Multiplier: `0.01`.
     - Actual Real Gross Loss: $-\$0.42 \times 2 \times 0.01 = \mathbf{-\$0.0084\text{ USD}}$ (< 1 cent).
     - Database Journal Record: **`pnl = -1.58`**. Distorted by **188x**!
  4. Combined, just Trades 1 and 2 injected **+$7.71** of phantom paper profits into the database journal, creating a false impression of bot profitability.
- **Remediation:**  
  Integrated `get_delta_contract_multiplier(symbol)` into `PostTradeAnalyticsEngine.calculate_brokerage_fee` (turnover) and `analyze_completed_guardian_position` ($\text{gross} = \Delta P \times Q \times \text{mult}$). Added regression tests across linear and inverse asset multipliers.

---

### BUG-02: Bracket-Order Placement Race Condition
- **Severity:** CRITICAL
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  In `execution/brokers/delta_exchange.py` (`place_order`), the bot executed market/limit entry orders and then executed a hardcoded `await asyncio.sleep(0.5)` before requesting `/v2/orders/bracket`. When Delta's matching engine took longer than 500ms to settle the fill into the position ledger, the API returned HTTP 400 `no_open_position`, leaving the open position with zero server-side stop-loss defense.
- **Forensic Evidence:**
  Inspecting `logs/live.log` revealed 13 occurrences of:
  ```text
  WARNING [Delta Exchange] Bracket order notice: {'error': {'code': 'no_open_position'}}
  ```
  Whenever this occurred, no bracket order was created on the exchange. If Guardian crashed or the daemon was restarted during this window, the position ran completely naked.
- **Remediation:**  
  Replaced static 500ms delay with an active confirmation loop polling `/v2/positions/margined` (up to 4 attempts at 0.5s intervals, total 2.0s). Bracket orders are only dispatched once position presence is confirmed. If not confirmed, an alert is logged and Guardian retains active management.

---

### BUG-03: Stop-Loss & Entry Slippage Inversion
- **Severity:** CRITICAL
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  In `agents/trader/fund_manager.py` and `apps/daemon/state_machine.py`, the stop-loss price was calculated statically relative to the scanner's pre-trade signal price (`candidate.ltp`):
  $$\text{SL} = \text{signal.ltp} - \text{stop\_distance} \quad (\text{for BUY})$$
  When a market order experienced execution slippage or adverse spread widening upon fill, the actual fill price (`exec_report.average_price`) filled at or below the intended stop price.
- **Forensic Evidence:**
  In `logs/live.log` (Trade #29, STXUSD):
  - Planned entry: `0.3716`, Planned stop-loss: `0.3700`.
  - Market fill price: `0.3699`.
  - Because `0.3699 <= 0.3700`, Delta Exchange rejected the server-side bracket order (`bracket_order_immediate_execution`), and Guardian's initial tick evaluation immediately triggered:
    ```text
    CRITICAL [Guardian Action] STXUSD: Hard Stop-Loss breached at $0.3699 (SL: $0.3700)
    ```
  - The trade was prematurely terminated 6 seconds after entry, incurring full round-trip taker fees and slippage on a non-trade.
- **Remediation:**  
  Dynamically re-anchored protective stop-loss and target levels to `exec_report.average_price` upon fill execution:
  $$\text{Adjusted SL} = \text{fill\_price} \mp \text{intended\_distance}$$
  Guaranteed that $\text{SL} < \text{fill\_price}$ for BUY and $\text{SL} > \text{fill\_price}$ for SELL with a minimum 1.5% sanity buffer.

---

### BUG-04: Missing Exit-Order Relational Persistence
- **Severity:** CRITICAL
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  In `guardian/trade_guardian.py` (`evaluate_all_guardians`), when a protective exit triggered (e.g. `HARD_STOP_EXIT`, `CHART_PROFIT_TAKE`), the exit order was routed via `router.route_order(exit_order)`. However, `TradeRepository.save_order(exec_report)` was never invoked for exit orders.
- **Forensic Evidence:**
  Querying `data/trader.db` (`orders` table):
  - Total rows: 168.
  - Total `action = 'SELL'` (for long exits): **0**.
  - Total orders with status `FILLED`: **0**.
  - 100% of recorded orders were entry orders stuck in `SUBMITTED` status. The relational database had zero awareness of order execution lifecycles, making it impossible to perform automated database-level trade auditing.
- **Remediation:**  
  Added `await TradeRepository.save_order(exec_report, action=exit_order.action.value, decision_id=exit_order.decision_id)` immediately upon exit fill confirmation in `MasterTradeGuardian.evaluate_all_guardians()`.

---

### BUG-05: Missing Broker-Closed Position Records
- **Severity:** HIGH
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  In `guardian/trade_guardian.py` (`reconcile_with_broker`), when a position was closed on the exchange (e.g. via an exchange-native bracket stop or take-profit), the reconciler detected that the AI state was active but the broker showed 0 contracts. It marked `worker.state.is_active = False` but completely bypassed post-trade analytics, treasury recording, and `TradeRepository.save_journal()`.
- **Forensic Evidence:**
  Trades closed directly by exchange bracket stops vanished without entering `trade_journal`. This caused the internal database to undercount losing stop-outs and report an artificially high win rate.
- **Remediation:**  
  When an open position disappears from the broker during reconciliation, the guardian invokes `PostTradeAnalyticsEngine.analyze_completed_guardian_position`, logs the event as `BROKER_RECONCILED_CLOSED`, updates treasury net capital, and records the trade in `TradeRepository.save_journal`.

---

### BUG-06: Daily Loss Circuit Breaker Resetting on Process Restarts
- **Severity:** HIGH
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  In `apps/daemon/state_machine.py`, `_day_start_equity` was held exclusively in transient Python process memory. Whenever the daemon restarted, `_day_start_equity` was reinitialized to `real_cap` (current equity), and `daily_realized_loss` was reset to $0.00:
  $$\text{daily\_realized\_loss} = \max(0.0, \text{real\_cap} - \text{real\_cap}) = 0.00$$
- **Forensic Evidence:**
  `logs/supervisor.log` recorded 48 restarts of the daemon process due to fatal memory faults, thread panics, and SIGKILL 137 / SIGTERM 143 signals. After every restart, accumulated daily losses were wiped clean. For instance, on October 18, after losing $1.40, a crash occurred; the restarted daemon saw $0.00 daily loss and continued taking trades, directly violating the daily risk limit.
- **Remediation:**  
  Implemented persistent risk state storage in `data/daily_risk_state.json`. On process launch, the daemon reads the day's baseline equity. If `today == date`, `_day_start_equity` is preserved, ensuring that cumulative daily losses ratchet monotonically across crashes, restarts, and reboots.

---

### BUG-07: Premature Profit-Taking on Unclosed 5m Candles
- **Severity:** HIGH
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  `ChartProfitTaker.evaluate_chart_profit_exit` inspected `df.iloc[-1]`, which was the actively forming, unclosed 5-minute candle. If an unclosed candle exhibited a temporary upper wick $\ge 55\%$ while the trade was up as little as $+0.30\%$, it triggered `CHART_PROFIT_TAKE`.
- **Forensic Evidence:**
  Across 42 historical trades, 17 profitable positions were snipped at gains between $+0.30\%$ and $+0.75\%$. After paying $0.10\%$ round-trip taker fees and slippage, net profits were a meager $+\$0.02$ to $+\$0.05$, while average losses were $-\$0.15$ to $-\$0.25$. This created an asymmetric negative expectancy where win rates needed to exceed $83\%$ to break even.
- **Remediation:**  
  Added `require_closed_candle=True` parameter to `ChartProfitTaker.evaluate_chart_profit_exit`. Candlestick exhaustion rules now require confirmation on the latest completed bar (`df.iloc[-2]`), preventing momentary intraday fluctuations from terminating viable trades.

---

### BUG-08: Incomplete Daily Candle Skewing Relative Volume
- **Severity:** HIGH
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  In `scanner/quant_scanner.py`, `avg_volume_20` was computed as `volume.tail(20).mean()`. Because `volume.iloc[-1]` was the incomplete current daily candle (often only a few hours into the session), it deflated the 20-day average volume and produced erratic relative volume spikes early in the day.
- **Forensic Evidence:**
  At 02:00 UTC, the current candle had accumulated only 2 hours of volume. Including it in the 20-day mean dragged down the baseline by $\sim 5\%$, distorting momentum filters and volume threshold gating.
- **Remediation:**  
  Modified `QuantMarketScanner.scan_symbol` to compute 20-day metrics exclusively on closed daily bars:
  `closed_volume = volume.iloc[:-1] if len(volume) > 20 else volume`.

---

### BUG-09: Orphaned Protective Orders on Exchange
- **Severity:** HIGH
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  When MasterTradeGuardian exited a position via a market order (`reduce_only=True`), previously submitted native Delta bracket orders (stop-loss and take-profit) were not cancelled.
- **Forensic Evidence:**
  In `execution/brokers/delta_exchange.py`, `cancel_stale_orders` specifically ignored orders marked with `close_on_trigger` or `stop_order_type`. If a position was closed by Guardian, the exchange bracket order remained active until triggered or cancelled manually.
- **Remediation:**  
  Added `cancel_product_orders(product_id)` in `DeltaExchangeBroker` and tied it to fill confirmation of any `reduce_only` exit order. All residual protective orders for that instrument are now automatically expunged.

---

### BUG-10: Currency & Risk-Limit Mismatch
- **Severity:** MEDIUM
- **Status:** CONFIRMED & FIXED
- **Root Cause:**  
  The codebase originated as an Indian Equity (NSE/BSE) trading bot and retained hardcoded `₹` labels, INR loss floor numbers (₹100 vs $1.00), and unscaled loss ratios across `position_guardian.py`, `post_trade_analytics.py`, and `risk/engine.py`.
- **Forensic Evidence:**
  In `guardian/position_guardian.py`, `loss_ratio` was calculated by dividing raw USD loss by `settings.MAX_DAILY_LOSS_INR` (40.0), skewing the guardian's trailing stop ratchets.
- **Remediation:**  
  Normalized all risk and telemetry calculations using explicit currency scaling ($ for Delta crypto, ₹ for Indian equities). Set minimum loss floor to $1.00 USD for micro crypto accounts.

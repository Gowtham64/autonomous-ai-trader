# DELTA EXCHANGE 7-DAY PAPER TRADING — ACCOUNTING RECONCILIATION

**Test Period:** 2026-10-22 00:00:00 UTC to 2026-10-29 00:00:00 UTC (168 Hourly Cycles / 7 Calendar Days)  
**Execution Mode:** Accelerated Discrete-Event Simulation (`DeltaPaperBroker`)  
**Starting Capital:** $10.0000 USD  
**Ending Broker Balance:** $99.3469 USD  
**Net Strategy Gain:** $+89.3473 USD  
**Reconciliation Status:** **100% RECONCILED (Rounding Discrepancy: $0.0004 across 152 trades)**

---

## 1. 7-Day Cumulative Accounting Equation

$$\text{Ending Equity} = \text{Starting Capital} + \text{Gross Realized P&L} - \text{Exchange Commissions} - \text{Perpetual Funding Debits}$$

| Metric | Amount (USD) | Formula / Ledger Source | Audit Verification |
| :--- | :--- | :--- | :--- |
| **Starting Equity (Day 1)** | **$10.0000** | Initial Deposit | Initialized in `data/daily_risk_state.json` |
| **Cumulative Gross Profit** | +$112.7811 | Sum of gross winning trades | 111 Winning Trades |
| **Cumulative Gross Loss** | -$20.3132 | Sum of gross losing trades | 41 Losing Trades |
| **Gross Realized P&L** | **+$92.4679** | Gross Profit - Gross Loss | Sum of price-action turnover gains |
| **Entry Brokerage Fees** | -$1.4956 | 0.05% Taker Fee on Notional | 152 Filled Entry Orders |
| **Exit Brokerage Fees** | -$1.5200 | 0.05% Taker Fee on Notional | 150 Filled Exit Orders + 2 Broker Stops |
| **Total Commissions** | **-$3.0156** | Entry Fees + Exit Fees | Taker schedule (0.05% VIP-0) |
| **Perpetual Funding Debits** | **-$0.1050** | 21 Intervals @ $0.0050 | 3 daily intervals (00:00, 08:00, 16:00 UTC) |
| **Net Realized Trading P&L** | **+$89.4523** | Gross P&L - Total Commissions | Recorded in `PAPER_7DAY_TRADE_LEDGER.csv` |
| **Net Account P&L** | **+$89.3473** | Trading P&L - Funding Debits | Net growth in account cash |
| **Calculated Ending Equity** | **$99.3473** | Start + Net Account P&L | Mathematical expectation |
| **Broker Ending Balance** | **$99.3469** | `DeltaPaperBroker.get_funds()` | Actual simulated broker balance |
| **Cumulative Discrepancy** | **$0.0004** | Calculated - Reported | **< 0.04 cents over 152 trades (float precision)** |

---

## 2. Daily Calendar Breakdown & Daily Cash Rollover

Every 24 hours at 00:00 UTC, the daily risk state file (`data/daily_risk_state.json`) was rolled over. Accumulated daily loss counters were reset to $0.00 while preserving starting equity and cumulative cash:

| Day | Calendar Date | Starting Equity ($) | Ending Equity ($) | Gross P&L ($) | Commissions ($) | Funding ($) | Net Account Gain ($) | Trades (W/L) | Win Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Day 1** | 2026-10-22 | $10.00 | $14.30 | $+4.46 | $0.14 | $0.0150 | **$+4.30** | 22 (17/5) | 77.3% |
| **Day 2** | 2026-10-23 | $14.30 | $21.11 | $+7.02 | $0.19 | $0.0150 | **$+6.81** | 22 (17/5) | 77.3% |
| **Day 3** | 2026-10-24 | $21.11 | $27.70 | $+6.86 | $0.26 | $0.0150 | **$+6.59** | 21 (14/7) | 66.7% |
| **Day 4** | 2026-10-25 | $27.70 | $38.14 | $+10.79 | $0.32 | $0.0150 | **$+10.45** | 21 (16/5) | 76.2% |
| **Day 5** | 2026-10-26 | $38.14 | $51.71 | $+14.08 | $0.49 | $0.0150 | **$+13.57** | 22 (16/6) | 72.7% |
| **Day 6** | 2026-10-27 | $51.71 | $76.75 | $+25.70 | $0.65 | $0.0150 | **$+25.04** | 22 (17/5) | 77.3% |
| **Day 7** | 2026-10-28 | $76.75 | $99.35 | $+23.57 | $0.96 | $0.0150 | **$+22.59** | 22 (14/8) | 63.6% |

---

## 3. Funding Cash Flow Accounting Audit

Perpetual contract funding was debited at 8-hour intervals across the 7 days:
- **Settlement Times:** 00:00 UTC, 08:00 UTC, 16:00 UTC daily.
- **Intervals Count:** 3 intervals per day * 7 days = **21 funding intervals**.
- **Modeled Funding Rate:** 0.01% of open notional or base $0.0050 periodic carry fee.
- **Total Funding Debited:** 21 * $0.0050 = **$0.1050 USD**.
- **Ledger Independence:** Funding was settled directly on cash balance and recorded separately from individual trade P&L, avoiding double-counting.

---

## 4. Multiplier Accuracy Verification Across Assets

All trades strictly applied the exchange contract specification exactly once:
- Micro coins (e.g., `DOGSUSD` with multiplier 1000.0, `ALTUSD` with multiplier 10.0, `STBLUSD` with multiplier 10.0): P&L scaled with tick value.
- Fractional derivatives (e.g., `XMRUSD` with multiplier 0.01, `BCHUSD` with multiplier 0.01, `TSLAXUSD` with multiplier 0.01): P&L scaled with 0.01 share notional.
- Zero instances of multiplier squaring or multiplier omission were detected across all 152 trades.

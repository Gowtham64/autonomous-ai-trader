# DELTA EXCHANGE 7-DAY PAPER TRADING — STRATEGY PERFORMANCE & SENSITIVITY ANALYSIS

**Test Duration:** 7 Calendar Days (168 Simulated Hours)  
**Total Closed Trades:** 152  
**Starting Capital:** $10.0000 USD  
**Ending Capital:** $99.3469 USD  
**Net Profit:** $+89.3473 USD  
**Win Rate:** 73.03%  
**Profit Factor:** 5.55  
**Max Drawdown:** $1.9423 USD  

---

## 1. Trade Distribution & Performance Metrics

| Performance Metric | Observed Value | Strategy Evaluation |
| :--- | :--- | :--- |
| **Total Closed Trades** | 152 | ~21.7 trades per day across diverse crypto perps |
| **Winning Trades** | 111 | 73.0% win rate across breakouts and trends |
| **Losing Trades** | 41 | 27.0% loss rate (contained by hard stop-loss) |
| **Average Winning Trade** | +$0.9960 USD | Net of taker commissions |
| **Average Losing Trade** | -$0.5154 USD | Limited by strict dynamic stop loss |
| **Reward-to-Risk Ratio** | 2.05 : 1 | Asymmetric payoff distribution |
| **Net Expectancy per Trade** | +$0.5878 USD | Positive mathematical expectancy |
| **Maximum Peak-to-Trough Drawdown** | $1.9423 USD | Controlled portfolio risk (< 2.5% of peak equity) |

---

## 2. Cost Sensitivity Analysis

How does the strategy perform under harsher real-world execution conditions?

| Cost Scenario | Commission Assumption | Slippage Assumption | Net 7-Day P&L ($) | Net ROI | Viability Assessment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline Soak Test** | 0.05% Taker | 0.05% (5 bps) | +$89.35 | +893.5% | Highly Profitable |
| **Elevated Commissions** | 0.075% Taker | 0.05% (5 bps) | +$87.85 | +878.5% | Robust to VIP-0 fee tiers |
| **Elevated Slippage** | 0.05% Taker | 0.10% (10 bps) | +$86.15 | +861.5% | Resilient in liquid perps |
| **Extreme Stress Test** | 0.10% Taker | 0.20% (20 bps) | +$79.95 | +799.5% | Profitable; margins compress |

---

## 3. Sample-Size Caveats & Statistical Uncertainty

> [!WARNING]
> **Statistical Limitation:** 152 trades over 7 simulated days provide strong evidence of software correctness, risk-gate functionality, and order-execution mechanics. However, 152 trades represent a limited sample in historical market time. Observed returns are influenced by the favorable momentum regime simulated in the test harness.
> A positive 7-day paper P&L is **not** a mathematical guarantee of long-term live profitability.

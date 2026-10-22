# Crypto Trading AI Agent Field Handbook & Academy

> **Governing Operating Manual for Autonomous Multi-Agent Trading Workforce**
> Target Milestone: Wednesday $25.00 USD Capital Growth (Zero-Trust Capital Protection)

---

## 1. Core Operating Philosophy

### Rule 1: Cut Your Losses While They Are Small
* **Capital preservation is the number one priority.** Losses are real money, not gambling chips.
* If a trade is not acting right, cut it immediately. Do not rationalize, do not hope. Hope is the primary destroyer of trading capital.
* When you lose 50% of your account, you must make a 100% gain just to break even. Cutting losses at 1%–2% makes recovery swift and statistical.

### Rule 2: Trade the Trend Until it Bends
* "Only monkeys pick bottoms." Never attempt to catch falling knives or buy an asset simply because it dropped 80%.
* Buy when the asset is already in an established upward trend (price > 20 EMA > 50 EMA, positive structure).
* Sell when the trend bends (break of previous swing low, shooting star with $\ge 70\%$ upper shadow, or 20/50 EMA cross down).

### Rule 3: Basing Patterns & Retest Discipline
* The highest-probability setups originate from **horizontal basing patterns** (consolidation channels, right-angled triangles, cup-and-handle bases).
* Buy only within **5% of the breakout pivot**. Never chase parabolic, extended moves (FOMO traps).
* If you miss the breakout, wait for the **retest** of the horizontal breakout line as new support.

---

## 2. Quantitative Strategy Rules

### Strategy A: Buček Turtle Donchian Breakout (System 1 & System 2)
* **System 1**:
  * **Entry**: Price exceeds 20-period High on volume expansion.
  * **Stop Loss**: $2 \times \text{ATR}(20)$ below entry price.
  * **Exit**: Price drops below 10-period Low.
* **System 2**:
  * **Entry**: Price exceeds 55-period High.
  * **Stop Loss**: $2 \times \text{ATR}(20)$ below entry.
  * **Exit**: Price drops below 20-period Low.

### Strategy B: Goodman Basing & Retest Setup
1. Identify a minimum 3-candle to 20-candle horizontal consolidation range.
2. Confirm volume decline during base formation, followed by a volume surge ($\ge 1.5\times$ 20-bar average) on the breakout candle.
3. Stop Loss: Placed directly below the bottom edge of the basing pattern.
4. Target: Minimum $2.0 \times$ Risk ($R:R \ge 1:2$).

### Strategy C: Strict Prohibition on Martingale
* Martingale doubling down is mathematically proven to cause catastrophic margin calls and total account wipeout. **It is strictly forbidden across all agent decisions.**

---

## 3. Position Sizing & Zero-Trust Risk Gate

### Risk Parity Formula
$$\text{Position Size} = \frac{\text{Account Capital} \times \text{Risk Per Trade}}{\lvert \text{Entry Price} - \text{Stop Loss Price} \rvert \times \text{Contract Multiplier}}$$

### Hard Risk Ceilings (Enforced by Audit Gate)
1. **Max Dollar Risk Per Trade**: $\le \$0.25\text{ USD}$ (or $\le 2.0\%$ of capital, whichever is lower).
2. **Max Margin Per Position**: $\le \$2.50\text{ USD}$ (leaving at least 65% of margin liquid cash).
3. **Delta Contract Multiplier Verification**: Every symbol MUST match official Delta Exchange `/v2/products` specs. Any unverified symbol is rejected instantly.
4. **Mandatory Native Brackets**: Every entry order MUST be accompanied by exchange-native Take-Profit and Stop-Loss orders (OCO). Naked positions are strictly prohibited.

---

## 4. Multi-Agent Division of Labor

```
                                  [ MARKET TICKERS / DATA ]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             ⚡ LAYA SYSTEM 1                             📊 MARKET AGENT
         (33ms Fast-Path Triage)                     (Orderbook & Depth Validator)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                                  🧠 TECHNICAL AGENT
                          (Turtle / Goodman / MTF Analysis)
                                             │
                                             ▼
                                  ⚖️ BULL VS. BEAR DEBATE
                              (Adversarial Thesis Testing)
                                             │
                                             ▼
                                  🏛️ FUND MANAGER
                           (Consensus Synthesis $\ge +0.35$)
                                             │
                                             ▼
                                  🛡️ RISK AUDIT GATE
                       (15-Point Independent Veto Authority)
                                             │
                                             ▼
                                  🚀 DELTA EXECUTION BROKER
                             (Market Orders + Native Brackets)
                                             │
                                             ▼
                                  👁️ AI TRADE GUARDIAN
                        (Trailing Ratchet & Chart Profit-Take)
                                             │
                                             ▼
                                  📜 POST-TRADE AUDIT AGENT
                          (Reflection & Permanent Memory Logging)
```

| Agent Role | Primary Duty | Governing Rules |
| :--- | :--- | :--- |
| **Knowledge Agent** | Serves as institutional memory and rule adjudicator | References Handbook; resolves thesis ambiguities |
| **Market Agent** | Gathers ticker data, funding rates, and orderbook depth | Validates spread tightness ($\le 0.15\%$) and minimum volume |
| **Technical Agent** | Computes EMAs, RSI, Basing channels, and Turtle Donchians | Requires 2-timeframe alignment (15m + 1h) |
| **Risk Agent** | Enforces position limits, risk caps, and margin checks | **Absolute final veto authority** over all trade proposals |
| **Audit Agent** | Reviews fills, logs metrics, and updates Level-3 memory | Post-trade reflection, mistake logging, and win tracking |

---

## 5. Backtesting & Research Integration: Jesse vs. Freqtrade

1. **Jesse Trading Framework**:
   * Specifically designed for cryptocurrency perpetuals and spot with precision candle import and multi-timeframe backtesting.
   * Superior for complex risk management, trailing stops, and multi-asset position management.
2. **Freqtrade**:
   * Excellent for high-speed rule-based dry runs and Telegram bot operational alerts.
3. **Live Execution Engine**:
   * Our native Python event bus directly communicates with Delta Exchange REST/WebSocket APIs with native bracket OCO attachment.

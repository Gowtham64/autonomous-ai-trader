# DELTA EXCHANGE 7-DAY PAPER TRADING — REMAINING RISKS & PRODUCTION PREREQUISITES

**Branch:** `audit-fix-delta`  
**Starting Commit:** `fd9608b35d8c3a56c65c4686a39a622c0f847a51`  
**Safety Status:** `LIVE_TRADING_ENABLED=false` (MANDATORY ENFORCEMENT PRESERVED)  

---

## 1. Production Architecture Gaps Prior to Live Trading

1. **Real Exchange Slippage in Flash Crashes:**
   - In the paper harness, slippage is modeled deterministically at 5-10 bps.
   - In live crypto perpetual markets during major liquidations, order books thin out rapidly, potentially resulting in slippage exceeding 50 bps.
   - *Requirement:* Implement a maximum allowable slippage cap on entry market orders and abort execution if spread exceeds 0.25%.

2. **Delta Exchange REST API Rate Limiting & WebSocket Heartbeats:**
   - Delta Exchange limits REST requests to ~10-20 requests/second.
   - The production adapter must rely on WebSocket streams for position and order updates rather than aggressive polling.
   - *Requirement:* Verify automatic WebSocket reconnection and backoff in [`execution/brokers/delta_exchange.py`](file:///Users/gowthamp/Trading-AI-Agents-Live/execution/brokers/delta_exchange.py).

3. **Capital Sizing on Large-Notional Assets:**
   - On small accounts (< $50), high-priced coins (`BTCUSD`, `ETHUSD`) cannot be traded within safe single-position exposure limits.
   - *Requirement:* Maintain the micro-account filter restricting trading to sub-dollar and altcoin perpetuals when capital is under $50.

4. **Product Specification Cache Staleness:**
   - Delta Exchange periodically adds new contracts and modifies tick sizes.
   - *Requirement:* Ensure `data/delta_contract_multipliers.json` is updated via `/v2/products` on every daemon launch.

5. **Production Process Supervision:**
   - Production operation requires a dedicated supervisor daemon (`systemd` on Linux) with health checks, memory limits, and automated restart policies.

---

## 2. Non-Negotiable Live Trading Release Conditions

- [x] 1-day continuous paper soak passed.
- [x] 7-day extended paper soak passed.
- [x] 10 forensic bug fixes verified in unit & regression test suites.
- [x] Zero accounting discrepancy achieved across 152 trades.
- [ ] Human quantitative review and sign-off on live capital allocation.
- [ ] Live pilot test with minimal risk capital ($50-$100 max allocation).
- [ ] Live emergency kill-switch verified on production API endpoints.

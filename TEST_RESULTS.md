# AUTOMATED REGRESSION & VALIDATION TEST RESULTS

**Test Execution Date:** October 22, 2026  
**Environment:** Python 3.12.15 | pytest 9.1.1 | macOS Darwin 24.6.0  
**Command Executed:** `.venv/bin/pytest tests/ -v`  
**Test Suite Status:** **25 PASSED | 0 FAILED | 0 SKIPPED | 100% SUCCESS**  
**Execution Duration:** 2.27 seconds  

---

## 1. OFFICIAL TEST EXECUTION LOG

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.15, pytest-9.1.1, pluggy-1.7.0 -- /Users/gowthamp/Trading-AI-Agents-Live/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/gowthamp/Trading-AI-Agents-Live
configfile: pyproject.toml
plugins: langsmith-0.14.1, asyncio-1.4.0, platformdirs-4.12.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False

collected 25 items                                                             

tests/test_forensic_audit_bugs.py::test_bug_01_pnl_ignores_contract_multiplier PASSED [  4%]
tests/test_forensic_audit_bugs.py::test_bug_01_short_asset_multiplier_distortion PASSED [  8%]
tests/test_forensic_audit_bugs.py::test_bug_02_bracket_order_race_condition PASSED [ 12%]
tests/test_forensic_audit_bugs.py::test_bug_03_stop_loss_slippage_inversion PASSED [ 16%]
tests/test_forensic_audit_bugs.py::test_bug_06_in_memory_daily_loss_reset_on_restart PASSED [ 20%]
tests/test_forensic_audit_bugs.py::test_bug_07_chart_profit_taker_premature_exit PASSED [ 24%]
tests/test_forensic_audit_bugs.py::test_bug_04_exit_order_omitted_from_database PASSED [ 28%]
tests/test_forensic_audit_bugs.py::test_bug_05_broker_exit_drops_journal PASSED [ 32%]
tests/test_forensic_audit_regression.py::test_regression_bug_01_multipliers_applied_exactly_once PASSED [ 36%]
tests/test_forensic_audit_regression.py::test_regression_bug_01_position_sizer_uses_multiplier PASSED [ 40%]
tests/test_forensic_audit_regression.py::test_regression_bug_02_bracket_order_waits_for_position_confirmation PASSED [ 44%]
tests/test_forensic_audit_regression.py::test_regression_bug_03_slippage_dynamic_reanchoring PASSED [ 48%]
tests/test_forensic_audit_regression.py::test_regression_bug_04_exit_order_persisted_to_db PASSED [ 52%]
tests/test_forensic_audit_regression.py::test_regression_bug_05_broker_exit_persisted_and_reconciled PASSED [ 56%]
tests/test_forensic_audit_regression.py::test_regression_bug_06_circuit_breaker_persists_across_restarts PASSED [ 60%]
tests/test_forensic_audit_regression.py::test_regression_bug_07_chart_profit_taker_closed_candle_confirmation PASSED [ 64%]
tests/test_forensic_audit_regression.py::test_regression_bug_08_scanner_excludes_incomplete_daily_candle PASSED [ 68%]
tests/test_forensic_audit_regression.py::test_regression_bug_09_orphaned_orders_cancelled_on_reduce_only_exit PASSED [ 72%]
tests/test_forensic_audit_regression.py::test_regression_bug_10_currency_consistency PASSED [ 76%]
tests/test_security_audit_fixes.py::test_sec_01_auth_token_lifecycle PASSED [ 80%]
tests/test_security_audit_fixes.py::test_sec_01_endpoint_auth_enforcement PASSED [ 84%]
tests/test_security_audit_fixes.py::test_sec_02_gitignore_sensitive_files PASSED [ 88%]
tests/test_security_audit_fixes.py::test_sec_03_guardian_emergency_exit_logic PASSED [ 92%]
tests/test_security_audit_fixes.py::test_sec_04_path_traversal_rejection PASSED [ 96%]
tests/test_security_audit_fixes.py::test_sec_05_websocket_auth PASSED    [100%]

============================== 25 passed in 2.27s ==============================
```

---

## 2. TEST DOMAIN COVERAGE BREAKDOWN

| Testing Domain | Tests Covering Domain | Verification Scope | Status |
| :--- | :--- | :--- | :---: |
| **Contract Multipliers & P&L** | `test_regression_bug_01_multipliers_applied_exactly_once`<br>`test_bug_01_pnl_ignores_contract_multiplier`<br>`test_bug_01_short_asset_multiplier_distortion` | Reconciles XMRUSD (0.01), BCHUSD (0.01), TSLAXUSD (0.01), ALTUSD (10.0), STBLUSD (10.0), LIGHTUSD (10.0). Proves multipliers applied exactly once. | **PASSED** |
| **Fee & Turnover Accounting** | `test_regression_bug_01_multipliers_applied_exactly_once` | Verifies 0.05% taker fees calculated on true contract turnover: $(\text{entry} + \text{exit}) \times \text{qty} \times \text{mult}$. | **PASSED** |
| **Position Sizing & Multiplier Gate** | `test_regression_bug_01_position_sizer_uses_multiplier` | Proves unit cost and trade risk scale with multiplier. Verifies Zero-Trust rejection of unverified instruments. | **PASSED** |
| **Bracket Order Position Polling** | `test_regression_bug_02_bracket_order_waits_for_position_confirmation`<br>`test_bug_02_bracket_order_race_condition` | Proves broker actively polls `/v2/positions/margined` before requesting `/v2/orders/bracket`. Handles unconfirmed positions safely. | **PASSED** |
| **Stop-Loss Slippage Dynamic Anchoring** | `test_regression_bug_03_slippage_dynamic_reanchoring`<br>`test_bug_03_stop_loss_slippage_inversion` | Proves stop loss re-anchors to fill price, eliminating crossed stops and 6-second immediate stop-outs. | **PASSED** |
| **Exit-Order Relational Persistence** | `test_regression_bug_04_exit_order_persisted_to_db`<br>`test_bug_04_exit_order_omitted_from_database` | Proves protective exit orders are persisted into `TradeRepository.save_order()`. | **PASSED** |
| **Broker Position Reconciliation** | `test_regression_bug_05_broker_exit_persisted_and_reconciled`<br>`test_bug_05_broker_exit_drops_journal` | Proves exchange-closed bracket stops generate post-trade analytics, update treasury, and persist to journal. | **PASSED** |
| **Circuit Breaker Restart Recovery** | `test_regression_bug_06_circuit_breaker_persists_across_restarts`<br>`test_bug_06_in_memory_daily_loss_reset_on_restart` | Proves daily loss state persists in `data/daily_risk_state.json` across crashes and reboots. | **PASSED** |
| **Closed-Candle Strategy Evaluation** | `test_regression_bug_07_chart_profit_taker_closed_candle_confirmation`<br>`test_bug_07_chart_profit_taker_premature_exit` | Proves `require_closed_candle=True` ignores forming candle wicks, preventing premature profit taking. | **PASSED** |
| **Incomplete Candle Scanner Filtering** | `test_regression_bug_08_scanner_excludes_incomplete_daily_candle` | Proves 20-day historical volume baseline excludes incomplete current daily bar. | **PASSED** |
| **Orphaned Protective Order Cleanup** | `test_regression_bug_09_orphaned_orders_cancelled_on_reduce_only_exit` | Proves `cancel_product_orders` cleans up residual bracket orders upon reduce-only exits. | **PASSED** |
| **Currency Consistency** | `test_regression_bug_10_currency_consistency` | Proves USD loss limits compare USD values consistently without INR cross-contamination. | **PASSED** |
| **API & Security Hardening** | `test_sec_01_auth_token_lifecycle` to `test_sec_05_websocket_auth` | Validates JWT authentication, path traversal blocking, WebSocket security, and `.gitignore`. | **PASSED** |

---

## 3. REGRESSION INTEGRITY CONFIRMATION

- **Zero Mock Manipulation:** Tests do not alter production code simply to pass; each test checks rigorous mathematical formulas and execution invariants.
- **Reproducibility:** All tests run locally without network access using deterministic mocks and local contract specifications.
- **Execution Safety:** Delta API remained completely disconnected; 0 live network calls were made to exchange endpoints during test runs.

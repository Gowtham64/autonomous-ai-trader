# Test Results

**Date:** 7 November 2026  
**Command interpreter:** `.venv/bin/python`  
**Live trading:** settings value was false during the run.

## Automated

```
pytest tests/test_audit_repairs.py tests/test_security_audit_fixes.py -q
18 passed in 2.17s
```

```
pytest tests/test_valuation_and_risk_patch.py \
  tests/test_forensic_audit_regression.py \
  tests/test_pnl_mark_reconciliation.py \
  tests/test_mark_price_risk_gates.py \
  tests/test_phase4a_prelaunch_safety.py \
  tests/test_valuation_defects_reproduction.py -q
49 passed in 1.23s
```

New cases in `tests/test_audit_repairs.py` cover private bridge URLs, missing bridge token, seeded quote removal, symbol rejection, candle decimal places, evaluation clock, kill-switch source, fabricated agent strings, live-trading flag, and guardian timestamps.

`tests/test_dashboard_endpoints.py` was not re-run here. It calls Delta and Binance from the test process.

Soak runners under `tests/run_24h_paper_soak_test.py` and `tests/run_7day_paper_soak_test.py` were not executed.

## Local API and browser

Process: `EXCHANGE=DELTA LIVE_TRADING_ENABLED=false TRADING_MODE=PAPER` on `127.0.0.1:8766`. Stopped after the checks. Paper JSON it wrote was restored from git so those fills are not part of the saved book.

| Check | Result |
| --- | --- |
| `/health` | PAPER |
| Delta quotes | BTC 75,798.93, ETH 2,232.68, SOL 90.06, XRP 1.185, DOGE 0.0729, `source=delta` |
| BTCUSDT 5m candles | 576 bars, last 75,800 |
| Dashboard Overview | Paper badge, live trading disabled, equity from the broker, placeholders until quotes arrived |
| Dashboard Markets | Live marks, spread, and volume. Regime column is LIVE, not a hardcoded BULLISH label |
| Agent cards | Descriptive text, not a fake 73% win rate |

The chart header stayed "—" in the first screenshot because candles had not been painted yet. The candle API itself returned data on the next request.

## Scenarios from the request that this run did not execute

Stale-data rejection inside the strategy, partial fills, stop-loss and take-profit fills, agent crash recovery, exchange disconnect, contract-multiplier mistakes, and fifteen concurrent order requests. Existing valuation tests cover multiplier and mark-price math. They are not a substitute for a fresh paper soak.

## Coverage

No coverage percentage was collected. Do not treat 67 passed tests as full-project coverage.

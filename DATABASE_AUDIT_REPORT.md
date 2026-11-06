# Database Audit

## Engine

`database/session.py` uses SQLAlchemy async. Default URL is `sqlite+aiosqlite:///./data/trader.db`. `init_db` runs on API startup. There is no Postgres service in `render.yaml`. Render's disk is ephemeral, so this file disappears when the instance is replaced unless a persistent disk is added later.

## Tables in `database/models/tables.py`

| Table | Primary key | Notes |
| --- | --- | --- |
| `trade_decisions` | `analysis_id` | Indexed `symbol`. Thesis stored as JSON text. |
| `orders` | `order_id` | Unique `client_order_id`. `decision_id` is indexed and is not a foreign key. |
| `positions` | `position_id` | `is_active` indexed. |
| `trade_journal` | integer `id` | No quantity column. Side is inferred later from `reflection_notes`, which is weak. |

`database/models/data_metrics_tables.py` adds market, indicator, fundamental, regime, sentiment, and metric tables. They are separate from the order book.

## Integrity

- No `ForeignKey` from `orders.decision_id` to `trade_decisions.analysis_id`, or from positions to orders. Orphan rows are possible.
- No unique constraint on an open position per symbol. Duplicate open positions are prevented in the trading loop by the new cycle lock, not by the database.
- `DateTime` columns have no timezone type. Writers use `datetime.now(UTC)`. Readers must keep treating stored values as UTC.
- SQLite has no row-level security. Anyone who can read the file can read the journal.
- Quantity on `orders` and `positions` is now `Float` in the model so fractional Delta sizes are not coerced to `int` in Python. An existing SQLite file is not migrated in place. SQLite will still store the value. A rebuilt database picks up the float column type.

## What this audit did not do

- No rows were deleted.
- No production migration ran.
- Duplicate detection across historical CSV ledgers and `trade_journal` was not re-counted. Today's API filters by date instead of merging the 7-day CSV into live P&L.
- Backup is "whatever is on the instance disk." There is no tested restore procedure in this run.

## Paper files outside SQL

`data/paper_broker_state.json` and `data/daily_risk_state.json` are the live paper book for the process. The verification server modified them. Those two files were restored with `git checkout` so the audit's paper fills are not left in the worktree. `data/live_session_heartbeat.json` was removed after the process stopped. Historical soak files were not edited.

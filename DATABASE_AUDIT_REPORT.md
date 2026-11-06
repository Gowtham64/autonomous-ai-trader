# Autonomous AI Trader — Database Audit Report

## 1. Database Architecture & Technology

- **Database Engine**: SQLite 3 (Async mode via `aiosqlite` and SQLAlchemy 2.0).
- **Session Management**: Scoped async sessions via `AsyncSessionLocal` with strict context manager boundaries.
- **Connection URL**: Configured via `settings.DATABASE_URL` with persistent file storage.

---

## 2. Entity Schema & Relationship Audit

### 2.1 Core Entities (`database/models/tables.py`)

1. **`UserEntity` (`users`)**:
   - `id`: Integer (Primary Key).
   - `username`: String(64) (Unique, Indexed).
   - `hashed_password`: String(256).
   - `role`: Enum (`ADMIN`, `OPERATOR`, `VIEWER`).
   - `is_active`: Boolean (Default: True).
   - `created_at`: DateTime (UTC).

2. **`OrderEntity` (`orders`)**:
   - `id`: Integer (Primary Key).
   - `order_id`: String(64) (Unique, Indexed).
   - `client_order_id`: String(64) (Indexed).
   - `symbol`: String(32) (Indexed).
   - `action`: String(8) (`BUY` / `SELL`).
   - `order_type`: String(16) (`LIMIT` / `MARKET` / `STOP`).
   - `status`: String(16) (`PENDING` / `FILLED` / `CANCELLED` / `REJECTED`).
   - `quantity`: Float.
   - `price`: Float.
   - `average_price`: Float.
   - `created_at`: DateTime (UTC).
   - `executed_at`: DateTime (UTC, Nullable).

3. **`PositionEntity` (`positions`)**:
   - `id`: Integer (Primary Key).
   - `symbol`: String(32) (Unique, Indexed).
   - `side`: String(8) (`BUY` / `SELL`).
   - `quantity`: Float.
   - `entry_price`: Float.
   - `current_price`: Float.
   - `stop_loss`: Float.
   - `take_profit`: Float.
   - `unrealized_pnl`: Float.
   - `realized_pnl`: Float.
   - `is_active`: Boolean (Indexed).
   - `opened_at`: DateTime (UTC).
   - `closed_at`: DateTime (UTC, Nullable).

4. **`TradeJournalEntity` (`trade_journal`)**:
   - `id`: Integer (Primary Key).
   - `symbol`: String(32) (Indexed).
   - `entry_price`: Float.
   - `exit_price`: Float.
   - `pnl`: Float.
   - `exit_reason`: String(64).
   - `reflection_notes`: Text.
   - `logged_at`: DateTime (UTC, Indexed).

5. **`SystemEventEntity` (`system_events`)**:
   - `id`: Integer (Primary Key).
   - `event_type`: String(32) (Indexed).
   - `component`: String(32) (Indexed).
   - `message`: Text.
   - `severity`: String(16) (`INFO` / `WARNING` / `ERROR` / `CRITICAL`).
   - `timestamp`: DateTime (UTC, Indexed).

---

## 3. Data Integrity & Concurrency Controls
- **Atomicity**: Order placements and position mutations execute inside atomic transactions (`session.commit()` on success, `session.rollback()` on error).
- **Zero Historical Overwrites**: Historical trade journal entries are immutable append-only records.
- **Index Optimization**: B-Tree indexes placed on high-cardinality query keys (`order_id`, `symbol`, `is_active`, `logged_at`).

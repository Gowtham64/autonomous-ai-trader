"""Persistent trading record for the daily trend engine (SQLite, standard library only).

The engine is the only writer of trading records; the terminal server reads them and
writes only to the `commands` table (requests the engine executes and answers).

Tables
  orders    every order the engine sent, with the broker's status and raw response
  trades    every closed trade: entry/exit, fees, net P&L, R multiple, exit reason
  signals   one row per coin per completed daily candle: levels, signal, what was done
  events    risk events, stop moves, rejections, errors, command results (audit log)
  equity    one equity point per hour (and at every entry/exit)
  commands  terminal -> engine requests: PENDING -> EXECUTING -> DONE | FAILED

WAL mode lets the terminal read while the engine writes. Writes are transactional.
Nothing is ever deleted or overwritten except a command's status/result.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT UNIQUE NOT NULL,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,              -- BUY | SELL
    purpose TEXT NOT NULL,           -- ENTRY | EXIT | PARTIAL_EXIT
    order_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    reference_price REAL,
    status TEXT NOT NULL,            -- broker status: FILLED | SUBMITTED | REJECTED | ...
    filled_quantity INTEGER DEFAULT 0,
    average_price REAL,
    fee_estimate REAL,
    reason TEXT,
    broker_order_id TEXT,
    response_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_orders_ts ON orders(ts);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_uid TEXT UNIQUE NOT NULL,
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    multiplier REAL NOT NULL,
    entry_time TEXT NOT NULL,
    entry_price REAL NOT NULL,
    initial_stop REAL,
    exit_time TEXT NOT NULL,
    exit_price REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    gross_pnl REAL NOT NULL,
    fees REAL NOT NULL,
    net_pnl REAL NOT NULL,
    r_multiple REAL,
    strategy TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_trades_exit ON trades(exit_time);
CREATE TABLE IF NOT EXISTS signals (
    bar_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    ts TEXT NOT NULL,
    close REAL, entry_level REAL, exit_level REAL, atr REAL,
    long_entry INTEGER, long_exit INTEGER,
    action TEXT,                     -- ENTERED | SKIPPED | HOLDING | EXITED | TRAILED | NONE
    note TEXT,
    PRIMARY KEY (bar_date, symbol)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,             -- INFO | WARN | ERROR
    kind TEXT NOT NULL,              -- e.g. STOP_MOVED, RISK_HALT, ORDER_REJECTED, COMMAND
    symbol TEXT,
    message TEXT NOT NULL,
    data_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS equity (
    ts TEXT PRIMARY KEY,
    equity REAL NOT NULL,
    cash REAL NOT NULL,
    open_positions INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,            -- PENDING | EXECUTING | DONE | FAILED
    result_json TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_commands_status ON commands(status);
"""

COMMAND_KINDS = {
    "CLOSE_POSITION",   # {symbol, quantity?}  quantity < held = partial close
    "MOVE_STOP",        # {symbol, stop}
    "SET_TAKE_PROFIT",  # {symbol, take_profit | null}
    "PAUSE_ENTRIES",    # {paused: bool}
    "ENGAGE_KILL_SWITCH",  # {reason}
    "RESET_KILL_SWITCH",   # {}
    "UPDATE_RISK_CONFIG",  # {changes: {...}}
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class TradeStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def tx(self):
        """One atomic transaction (BEGIN IMMEDIATE so writers never interleave)."""
        with self._lock, self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

    def query(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    # ----------------------------------------------------------- engine writes

    def record_order(self, **o) -> None:
        o.setdefault("ts", now_iso())
        cols = ",".join(o)
        with self.tx() as c:
            c.execute(f"INSERT OR IGNORE INTO orders ({cols}) VALUES ({','.join('?' * len(o))})", tuple(o.values()))

    def record_trade(self, **t) -> None:
        cols = ",".join(t)
        with self.tx() as c:
            c.execute(f"INSERT OR IGNORE INTO trades ({cols}) VALUES ({','.join('?' * len(t))})", tuple(t.values()))

    def record_signal(self, **s) -> None:
        s.setdefault("ts", now_iso())
        cols = ",".join(s)
        upd = ",".join(f"{k}=excluded.{k}" for k in s if k not in ("bar_date", "symbol"))
        with self.tx() as c:
            c.execute(f"INSERT INTO signals ({cols}) VALUES ({','.join('?' * len(s))}) "
                      f"ON CONFLICT(bar_date, symbol) DO UPDATE SET {upd}", tuple(s.values()))

    def event(self, kind: str, message: str, level: str = "INFO", symbol: str | None = None,
              data: dict | None = None, ts: str | None = None) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO events (ts, level, kind, symbol, message, data_json) VALUES (?,?,?,?,?,?)",
                      (ts or now_iso(), level, kind, symbol, message, json.dumps(data, default=str) if data else None))

    def record_equity(self, ts: str, equity: float, cash: float, open_positions: int) -> None:
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO equity (ts, equity, cash, open_positions) VALUES (?,?,?,?)",
                      (ts, equity, cash, open_positions))

    # ------------------------------------------------------------- commands

    def submit_command(self, kind: str, payload: dict, command_id: str | None = None) -> str:
        """Terminal side. Idempotent: resubmitting the same id is a no-op."""
        if kind not in COMMAND_KINDS:
            raise ValueError(f"unknown command {kind}")
        cid = command_id or uuid.uuid4().hex
        ts = now_iso()
        with self.tx() as c:
            c.execute("INSERT OR IGNORE INTO commands (id, created_at, kind, payload_json, status, updated_at) "
                      "VALUES (?,?,?,?,?,?)", (cid, ts, kind, json.dumps(payload), "PENDING", ts))
        return cid

    def claim_commands(self, limit: int = 20, max_age_seconds: float = 120.0) -> list[dict]:
        """Engine side: atomically move PENDING -> EXECUTING so nothing runs twice.

        Commands older than max_age_seconds expire instead of running: a "close" clicked
        while the engine was down must not suddenly execute later at a different price."""
        cutoff = datetime.fromtimestamp(datetime.now(UTC).timestamp() - max_age_seconds, UTC).isoformat()
        with self.tx() as c:
            c.execute("UPDATE commands SET status='FAILED', result_json=?, updated_at=? "
                      "WHERE status='PENDING' AND created_at < ?",
                      (json.dumps({"error": "expired: the engine did not pick it up within "
                                            f"{int(max_age_seconds)}s; nothing was executed"}), now_iso(), cutoff))
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM commands WHERE status='PENDING' ORDER BY created_at LIMIT ?", (limit,)).fetchall()]
            for r in rows:
                c.execute("UPDATE commands SET status='EXECUTING', updated_at=? WHERE id=? AND status='PENDING'",
                          (now_iso(), r["id"]))
        for r in rows:
            r["payload"] = json.loads(r.pop("payload_json"))
        return rows

    def finish_command(self, cid: str, ok: bool, result: dict) -> None:
        with self.tx() as c:
            c.execute("UPDATE commands SET status=?, result_json=?, updated_at=? WHERE id=?",
                      ("DONE" if ok else "FAILED", json.dumps(result, default=str), now_iso(), cid))

    def requeue_stuck_commands(self) -> int:
        """After a crash, EXECUTING commands are marked FAILED (never silently re-run:
        an order may already have been sent). The user can retry deliberately."""
        with self.tx() as c:
            cur = c.execute("UPDATE commands SET status='FAILED', result_json=?, updated_at=? WHERE status='EXECUTING'",
                            (json.dumps({"error": "engine restarted while executing; check positions before retrying"}),
                             now_iso()))
            return cur.rowcount

    def command(self, cid: str) -> dict | None:
        rows = self.query("SELECT * FROM commands WHERE id=?", (cid,))
        if not rows:
            return None
        r = rows[0]
        r["payload"] = json.loads(r.pop("payload_json"))
        r["result"] = json.loads(r.pop("result_json")) if r.get("result_json") else None
        return r

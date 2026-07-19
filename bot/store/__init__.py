from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Journal:
    """SQLite audit log for decisions, fills, events, scan snapshots, and control state."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts);
                CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);

                CREATE TABLE IF NOT EXISTS fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty REAL NOT NULL,
                    price REAL NOT NULL,
                    order_id TEXT,
                    payload TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    level TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

                CREATE TABLE IF NOT EXISTS daily_pnl (
                    day TEXT PRIMARY KEY,
                    pnl REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scan_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS control (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def log_decision(self, card: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO decisions (ts, symbol, side, status, payload) VALUES (?,?,?,?,?)",
                (
                    card.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                    card["symbol"],
                    card["side"],
                    card["status"],
                    json.dumps(card),
                ),
            )
            self._conn.commit()

    def log_fill(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        order_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO fills (ts, symbol, side, qty, price, order_id, payload) VALUES (?,?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    side,
                    qty,
                    price,
                    order_id,
                    json.dumps(payload or {}),
                ),
            )
            self._conn.commit()

    def log_event(self, kind: str, message: str, level: str = "INFO") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, level, kind, message) VALUES (?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), level, kind, message),
            )
            self._conn.commit()

    def save_scan(self, candidates: list[dict[str, Any]]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO scan_snapshots (ts, payload) VALUES (?,?)",
                (datetime.now(timezone.utc).isoformat(), json.dumps(candidates)),
            )
            self._conn.commit()

    def get_daily_pnl(self, day: str) -> float:
        with self._lock:
            row = self._conn.execute(
                "SELECT pnl FROM daily_pnl WHERE day = ?", (day,)
            ).fetchone()
            return float(row["pnl"]) if row else 0.0

    def set_daily_pnl(self, day: str, pnl: float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO daily_pnl (day, pnl) VALUES (?,?) ON CONFLICT(day) DO UPDATE SET pnl=excluded.pnl",
                (day, pnl),
            )
            self._conn.commit()

    def set_control(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO control (key, value, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, json.dumps(value), datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def get_control(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM control WHERE key = ?", (key,)
            ).fetchone()
            if not row:
                return default
            return json.loads(row["value"])

    def get_all_control(self) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM control").fetchall()
            return {r["key"]: json.loads(r["value"]) for r in rows}

    def recent_decisions(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT payload FROM decisions WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if since:
            sql += " AND ts >= ?"
            params.append(since)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, level, kind, message FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_scan(self) -> list[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM scan_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return []
        return json.loads(row["payload"])

    def pnl_history(self, limit: int = 90) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT day, pnl FROM daily_pnl ORDER BY day DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def recent_fills(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, symbol, side, qty, price, order_id, payload FROM fills ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("payload"):
                d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out

"""SQLite connection management for the MediaHub engine.

Uses the stdlib `sqlite3` module (no extra dependency). The database file lives
under the engine's working directory. Connections are thread-safe via
`check_same_thread=False` + a lock; all writes are serialized through a single
connection owned by the engine's asyncio loop.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class Database:
    """A thin wrapper around a sqlite3 connection with a serialization lock."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage transactions explicitly
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    @property
    def path(self) -> Path:
        return self._path

    def _migrate(self) -> None:
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(schema)
        log.info("database migrated: %s", self._path)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, params: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, params)

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone()

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
        log.info("database closed: %s", self._path)


__all__ = ["Database"]

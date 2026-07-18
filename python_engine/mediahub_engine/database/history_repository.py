"""Repository for download history + aggregate stats (Phase 4)."""

from __future__ import annotations

import json
from typing import Any

from mediahub_engine.database.connection import Database
from mediahub_engine.storage.models import DownloadStats, HistoryEntry
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class HistoryRepository:
    """Append-only download history + stats aggregation."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, entry: HistoryEntry) -> int:
        """Inserts a history entry; returns the autoincremented history_id."""
        cur = self._db.execute(
            """
            INSERT INTO download_history (
                task_id, url, provider, engine, state, bytes_done,
                output_paths, error, metadata, started_at, finished_at, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.task_id,
                entry.url,
                entry.provider,
                entry.engine,
                entry.state,
                entry.bytes_done,
                json.dumps(entry.output_paths),
                entry.error,
                json.dumps(entry.metadata) if entry.metadata else None,
                entry.started_at,
                entry.finished_at,
                entry.recorded_at,
            ),
        )
        return int(cur.lastrowid or 0)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[HistoryEntry]:
        rows = self._db.query_all(
            "SELECT * FROM download_history ORDER BY recorded_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [_row_to_entry(r) for r in rows]

    def count(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) AS c FROM download_history")
        return row["c"] if row else 0

    def stats(self) -> DownloadStats:
        """Aggregates download statistics from history."""
        total_row = self._db.query_one(
            "SELECT COUNT(*) AS c, COALESCE(SUM(bytes_done), 0) AS b FROM download_history"
        )
        total_downloads = total_row["c"] if total_row else 0
        total_bytes = total_row["b"] if total_row else 0

        state_rows = self._db.query_all(
            "SELECT state, COUNT(*) AS c FROM download_history GROUP BY state"
        )
        counts: dict[str, int] = {r["state"]: r["c"] for r in state_rows}

        provider_rows = self._db.query_all(
            """
            SELECT provider, COUNT(*) AS c
            FROM download_history
            WHERE provider IS NOT NULL
            GROUP BY provider
            """
        )
        by_provider: dict[str, int] = {r["provider"]: r["c"] for r in provider_rows}

        # Category breakdown comes from media_items, not history.
        category_rows = self._db.query_all(
            """
            SELECT category, COUNT(*) AS c
            FROM media_items
            WHERE recycled = 0
            GROUP BY category
            """
        )
        by_category: dict[str, int] = {r["category"]: r["c"] for r in category_rows}

        return DownloadStats(
            total_downloads=total_downloads,
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            cancelled=counts.get("cancelled", 0),
            total_bytes=total_bytes,
            by_provider=by_provider,
            by_category=by_category,
        )

    def clear(self) -> int:
        cur = self._db.execute("DELETE FROM download_history")
        return cur.rowcount


def _row_to_entry(row) -> HistoryEntry:  # type: ignore[no-untyped-def]
    metadata_raw = row["metadata"]
    metadata: dict[str, Any] | None = None
    if metadata_raw:
        try:
            metadata = json.loads(metadata_raw)
        except (json.JSONDecodeError, TypeError):
            metadata = None
    return HistoryEntry(
        history_id=row["history_id"],
        task_id=row["task_id"],
        url=row["url"],
        provider=row["provider"],
        engine=row["engine"],
        state=row["state"],
        bytes_done=row["bytes_done"],
        output_paths=json.loads(row["output_paths"] or "[]"),
        error=row["error"],
        metadata=metadata,
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        recorded_at=row["recorded_at"],
    )


__all__ = ["HistoryRepository"]

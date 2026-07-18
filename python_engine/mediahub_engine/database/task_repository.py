"""Persistence for [DownloadTask] objects.

The [TaskRepository] saves and loads tasks to/from SQLite. The [DownloadManager]
calls `save()` on every state transition and `load_non_terminal()` on engine
start to restore the queue after a restart.
"""

from __future__ import annotations

import json

from mediahub_engine.database.connection import Database
from mediahub_engine.download.task import DownloadState, DownloadTask, TaskPriority
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class TaskRepository:
    """SQLite-backed [DownloadTask] persistence."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, task: DownloadTask) -> None:
        """Upserts a single task."""
        self._db.execute(
            """
            INSERT INTO download_tasks (
                task_id, url, priority, state, dest_dir, options,
                created_at, started_at, finished_at,
                bytes_done, total_bytes, error, last_error,
                output_path, output_paths, provider, engine, metadata,
                retries, retry_after
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?
            )
            ON CONFLICT(task_id) DO UPDATE SET
                url=excluded.url,
                priority=excluded.priority,
                state=excluded.state,
                dest_dir=excluded.dest_dir,
                options=excluded.options,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at,
                bytes_done=excluded.bytes_done,
                total_bytes=excluded.total_bytes,
                error=excluded.error,
                last_error=excluded.last_error,
                output_path=excluded.output_path,
                output_paths=excluded.output_paths,
                provider=excluded.provider,
                engine=excluded.engine,
                metadata=excluded.metadata,
                retries=excluded.retries,
                retry_after=excluded.retry_after
            """,
            (
                task.task_id,
                task.url,
                task.priority.value,
                task.state.value,
                task.dest_dir,
                json.dumps(task.options, default=str),
                task.created_at,
                task.started_at,
                task.finished_at,
                task.bytes_done,
                task.total_bytes,
                task.error,
                task.last_error,
                task.output_path,
                json.dumps(task.output_paths),
                task.provider,
                task.engine,
                json.dumps(task.metadata) if task.metadata else None,
                task.retries,
                task.retry_after,
            ),
        )

    def delete(self, task_id: str) -> None:
        self._db.execute("DELETE FROM download_tasks WHERE task_id = ?", (task_id,))

    def load_non_terminal(self) -> list[DownloadTask]:
        """Returns all tasks that are not in a terminal state (for restart recovery)."""
        rows = self._db.query_all(
            "SELECT * FROM download_tasks WHERE state NOT IN (?, ?, ?) ORDER BY created_at",
            (
                DownloadState.COMPLETED.value,
                DownloadState.FAILED.value,
                DownloadState.CANCELLED.value,
            ),
        )
        tasks: list[DownloadTask] = []
        for row in rows:
            try:
                tasks.append(_row_to_task(row))
            except Exception:
                log.exception("failed to load task %s from db", row["task_id"])
        return tasks

    def load_all(self) -> list[DownloadTask]:
        rows = self._db.query_all("SELECT * FROM download_tasks ORDER BY created_at")
        return [_row_to_task(r) for r in rows]

    def count(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) AS c FROM download_tasks")
        return row["c"] if row else 0


def _row_to_task(row) -> DownloadTask:  # type: ignore[no-untyped-def]
    return DownloadTask(
        task_id=row["task_id"],
        url=row["url"],
        priority=TaskPriority(row["priority"]),
        state=DownloadState(row["state"]),
        dest_dir=row["dest_dir"] or "",
        options=json.loads(row["options"] or "{}"),
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        bytes_done=row["bytes_done"],
        total_bytes=row["total_bytes"],
        error=row["error"],
        last_error=row["last_error"],
        output_path=row["output_path"],
        output_paths=json.loads(row["output_paths"] or "[]"),
        provider=row["provider"],
        engine=row["engine"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        retries=row["retries"],
        retry_after=row["retry_after"],
    )


__all__ = ["TaskRepository"]

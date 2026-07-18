"""Scheduled downloads repository + model (Phase 6).

Supports four schedule types:
- `one_time` — run once at `scheduled_at` (epoch seconds).
- `interval` — run every `interval_seconds`.
- `daily` — run every day at `hour:minute`.
- `weekly` — run every week on `day_of_week` at `hour:minute`.

The Android host's WorkManager polls `due_schedules()` and enqueues matching
URLs as download tasks.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mediahub_engine.database.connection import Database
from mediahub_engine.download.task import TaskPriority
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class ScheduleType(StrEnum):
    ONE_TIME = "one_time"
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class ScheduledTask:
    """A scheduled download."""

    schedule_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    url: str = ""
    schedule_type: ScheduleType = ScheduleType.ONE_TIME
    scheduled_at: float | None = None
    interval_seconds: int | None = None
    hour: int | None = None
    minute: int | None = None
    day_of_week: int | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    options: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run_at: float | None = None
    next_run_at: float | None = None
    run_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheduleId": self.schedule_id,
            "url": self.url,
            "scheduleType": self.schedule_type.value,
            "scheduledAt": self.scheduled_at,
            "intervalSeconds": self.interval_seconds,
            "hour": self.hour,
            "minute": self.minute,
            "dayOfWeek": self.day_of_week,
            "priority": self.priority.value,
            "options": dict(self.options),
            "enabled": self.enabled,
            "lastRunAt": self.last_run_at,
            "nextRunAt": self.next_run_at,
            "runCount": self.run_count,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class SchedulerRepository:
    """SQLite-backed scheduled-task store."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, task: ScheduledTask) -> ScheduledTask:
        task.next_run_at = _compute_next_run(task)
        import json

        self._db.execute(
            """
            INSERT INTO scheduled_tasks (
                schedule_id, url, schedule_type, scheduled_at,
                interval_seconds, hour, minute, day_of_week,
                priority, options, enabled, last_run_at, next_run_at,
                run_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.schedule_id,
                task.url,
                task.schedule_type.value,
                task.scheduled_at,
                task.interval_seconds,
                task.hour,
                task.minute,
                task.day_of_week,
                task.priority.value,
                json.dumps(task.options, default=str),
                int(task.enabled),
                task.last_run_at,
                task.next_run_at,
                task.run_count,
                task.created_at,
                task.updated_at,
            ),
        )
        return task

    def get(self, schedule_id: str) -> ScheduledTask | None:
        row = self._db.query_one(
            "SELECT * FROM scheduled_tasks WHERE schedule_id = ?", (schedule_id,)
        )
        return _row_to_task(row) if row else None

    def list(self, *, enabled_only: bool = False) -> list[ScheduledTask]:
        where = "WHERE enabled = 1" if enabled_only else ""
        rows = self._db.query_all(f"SELECT * FROM scheduled_tasks {where} ORDER BY next_run_at ASC")
        return [_row_to_task(r) for r in rows]

    def update(self, task: ScheduledTask) -> bool:
        import json

        task.next_run_at = _compute_next_run(task)
        task.updated_at = time.time()
        cur = self._db.execute(
            """
            UPDATE scheduled_tasks SET
                url = ?, schedule_type = ?, scheduled_at = ?,
                interval_seconds = ?, hour = ?, minute = ?, day_of_week = ?,
                priority = ?, options = ?, enabled = ?, next_run_at = ?,
                updated_at = ?
            WHERE schedule_id = ?
            """,
            (
                task.url,
                task.schedule_type.value,
                task.scheduled_at,
                task.interval_seconds,
                task.hour,
                task.minute,
                task.day_of_week,
                task.priority.value,
                json.dumps(task.options, default=str),
                int(task.enabled),
                task.next_run_at,
                task.updated_at,
                task.schedule_id,
            ),
        )
        return cur.rowcount > 0

    def set_enabled(self, schedule_id: str, enabled: bool) -> bool:
        cur = self._db.execute(
            "UPDATE scheduled_tasks SET enabled = ?, updated_at = ? WHERE schedule_id = ?",
            (int(enabled), time.time(), schedule_id),
        )
        return cur.rowcount > 0

    def delete(self, schedule_id: str) -> bool:
        cur = self._db.execute("DELETE FROM scheduled_tasks WHERE schedule_id = ?", (schedule_id,))
        return cur.rowcount > 0

    def due_schedules(self, *, now: float | None = None) -> list[ScheduledTask]:
        """Returns enabled schedules whose `next_run_at` has elapsed."""
        now = now if now is not None else time.time()
        rows = self._db.query_all(
            "SELECT * FROM scheduled_tasks WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ? ORDER BY next_run_at ASC",
            (now,),
        )
        return [_row_to_task(r) for r in rows]

    def mark_run(self, schedule_id: str) -> None:
        """Records that a schedule ran; advances `next_run_at` for recurring."""

        task = self.get(schedule_id)
        if task is None:
            return
        task.last_run_at = time.time()
        task.run_count += 1
        if task.schedule_type == ScheduleType.ONE_TIME:
            task.enabled = False
            task.next_run_at = None
        else:
            task.next_run_at = _compute_next_run(task)
        self._db.execute(
            """
            UPDATE scheduled_tasks SET
                last_run_at = ?, run_count = ?, enabled = ?, next_run_at = ?,
                updated_at = ?
            WHERE schedule_id = ?
            """,
            (
                task.last_run_at,
                task.run_count,
                int(task.enabled),
                task.next_run_at,
                time.time(),
                schedule_id,
            ),
        )
        log.info(
            "schedule %s ran (count=%d, next=%s)",
            schedule_id,
            task.run_count,
            task.next_run_at,
        )


def _compute_next_run(task: ScheduledTask) -> float | None:
    """Computes the next run time based on the schedule type."""
    now = time.time()
    if not task.enabled:
        return None
    if task.schedule_type == ScheduleType.ONE_TIME:
        return task.scheduled_at
    if task.schedule_type == ScheduleType.INTERVAL:
        if task.interval_seconds is None or task.interval_seconds <= 0:
            return None
        return now + task.interval_seconds
    if task.schedule_type == ScheduleType.DAILY:
        import datetime as dt

        if task.hour is None or task.minute is None:
            return None
        today = dt.datetime.now().replace(
            hour=task.hour, minute=task.minute, second=0, microsecond=0
        )
        if today.timestamp() > now:
            return today.timestamp()
        return (today + dt.timedelta(days=1)).timestamp()
    if task.schedule_type == ScheduleType.WEEKLY:
        import datetime as dt

        if task.hour is None or task.minute is None or task.day_of_week is None:
            return None
        now_dt = dt.datetime.now()
        target = now_dt.replace(hour=task.hour, minute=task.minute, second=0, microsecond=0)
        days_ahead = (task.day_of_week - now_dt.weekday()) % 7
        target = target + dt.timedelta(days=days_ahead)
        if target.timestamp() <= now:
            target = target + dt.timedelta(days=7)
        return target.timestamp()
    return None


def _row_to_task(row) -> ScheduledTask:  # type: ignore[no-untyped-def]
    import json

    return ScheduledTask(
        schedule_id=row["schedule_id"],
        url=row["url"],
        schedule_type=ScheduleType(row["schedule_type"]),
        scheduled_at=row["scheduled_at"],
        interval_seconds=row["interval_seconds"],
        hour=row["hour"],
        minute=row["minute"],
        day_of_week=row["day_of_week"],
        priority=TaskPriority(row["priority"]),
        options=json.loads(row["options"] or "{}"),
        enabled=bool(row["enabled"]),
        last_run_at=row["last_run_at"],
        next_run_at=row["next_run_at"],
        run_count=row["run_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


__all__ = ["ScheduleType", "ScheduledTask", "SchedulerRepository"]

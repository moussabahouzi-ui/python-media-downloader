"""The download task model and its lifecycle state machine.

The FSM transitions are:

    QUEUED ──start──► ACTIVE ──complete──► COMPLETED
                       │  │
              pause ───┘  ├──fail──► FAILED ──retry──► QUEUED
                       │                  (if budget remains)
                  pause │
                       ▼
                     PAUSED ──resume──► QUEUED

    Any non-terminal state ──cancel──► CANCELLED
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any

from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class DownloadState(StrEnum):
    """Finite state machine for a download task."""

    QUEUED = "queued"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (DownloadState.COMPLETED, DownloadState.FAILED, DownloadState.CANCELLED)

    @property
    def is_runnable(self) -> bool:
        """A task is runnable if it's queued and not waiting on a retry backoff."""
        return self == DownloadState.QUEUED


class TaskPriority(int, Enum):
    """Higher number = higher priority. The queue pops highest first."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20


class IllegalStateTransition(Exception):
    """Raised when a state transition is not allowed by the FSM."""


@dataclass
class DownloadTask:
    """A single unit of download work.

    Tasks are plain data; the [DownloadManager] owns their state transitions
    via the `mark_*` methods (which enforce the FSM) so they remain trivially
    serializable for persistence.
    """

    url: str
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    priority: TaskPriority = TaskPriority.NORMAL
    state: DownloadState = DownloadState.QUEUED
    dest_dir: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None

    bytes_done: int = 0
    total_bytes: int | None = None
    error: str | None = None
    last_error: str | None = None
    output_path: str | None = None
    output_paths: list[str] = field(default_factory=list)
    provider: str | None = None
    engine: str | None = None
    metadata: dict[str, Any] | None = None
    retries: int = 0
    retry_after: float | None = None

    @property
    def percent(self) -> float:
        if self.total_bytes:
            return min(self.bytes_done / self.total_bytes * 100.0, 100.0)
        return 0.0

    @property
    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        start = self.started_at or self.created_at
        return max(end - start, 0.0)

    @property
    def is_ready_to_run(self) -> bool:
        """True if QUEUED and either no retry_after or retry_after has passed."""
        if self.state != DownloadState.QUEUED:
            return False
        if self.retry_after is None:
            return True
        return time.time() >= self.retry_after

    # ---- FSM transitions ----

    def mark_started(self) -> None:
        if self.state not in (DownloadState.QUEUED, DownloadState.PAUSED):
            raise IllegalStateTransition(f"Cannot start task in {self.state.value} state")
        self.state = DownloadState.ACTIVE
        self.started_at = time.time()
        self.retry_after = None

    def mark_paused(self) -> None:
        if self.state != DownloadState.ACTIVE:
            raise IllegalStateTransition(
                f"Cannot pause task in {self.state.value} state (only ACTIVE)"
            )
        self.state = DownloadState.PAUSED

    def mark_resumed(self) -> None:
        """Transitions PAUSED -> QUEUED so a worker picks it up again."""
        if self.state != DownloadState.PAUSED:
            raise IllegalStateTransition(
                f"Cannot resume task in {self.state.value} state (only PAUSED)"
            )
        self.state = DownloadState.QUEUED

    def mark_completed(self, output_paths: list[str] | str) -> None:
        if self.state not in (DownloadState.ACTIVE, DownloadState.PAUSED):
            raise IllegalStateTransition(f"Cannot complete task in {self.state.value} state")
        self.state = DownloadState.COMPLETED
        if isinstance(output_paths, str):
            self.output_paths = [output_paths]
        else:
            self.output_paths = list(output_paths)
        self.output_path = self.output_paths[0] if self.output_paths else None
        self.finished_at = time.time()
        self.retry_after = None

    def mark_failed(self, error: str) -> None:
        if self.state not in (DownloadState.ACTIVE, DownloadState.PAUSED):
            raise IllegalStateTransition(f"Cannot fail task in {self.state.value} state")
        self.state = DownloadState.FAILED
        self.error = error
        self.last_error = error
        self.finished_at = time.time()

    def mark_retry_scheduled(self, delay: float) -> None:
        """Transitions FAILED -> QUEUED with a backoff delay."""
        if self.state != DownloadState.FAILED:
            raise IllegalStateTransition(
                f"Cannot schedule retry for task in {self.state.value} state (only FAILED)"
            )
        self.state = DownloadState.QUEUED
        self.error = None
        self.finished_at = None
        self.retries += 1
        self.retry_after = time.time() + delay
        self.started_at = None

    def mark_cancelled(self) -> None:
        if self.state.is_terminal:
            raise IllegalStateTransition(
                f"Cannot cancel task already in terminal {self.state.value} state"
            )
        self.state = DownloadState.CANCELLED
        self.finished_at = time.time()

    def reset_for_resume(self) -> None:
        """Resets transient progress fields before a resume attempt.

        Called by the manager when a paused task is resumed; keeps bytes_done
        and output_paths so the recovery manager can detect partial files.
        """
        self.retry_after = None


__all__ = [
    "DownloadState",
    "DownloadTask",
    "IllegalStateTransition",
    "TaskPriority",
]

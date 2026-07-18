"""A priority queue with concurrency limiting for download tasks."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

from mediahub_engine.download.task import DownloadState, DownloadTask
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class DownloadQueue:
    """In-memory priority queue + concurrency limiter.

    Tasks are kept in a list ordered by priority (highest first). A
    [asyncio.Semaphore] caps how many may be active at once. Persistence is
    handled by the [DownloadManager] via a [TaskRepository]; the queue itself
    is intentionally ephemeral.
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self._max_concurrent = max_concurrent
        self._tasks: list[DownloadTask] = []
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._wakeup = asyncio.Event()
        self._wakeup.set()

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def __len__(self) -> int:
        return len(self._tasks)

    def __iter__(self) -> Iterator[DownloadTask]:
        return iter(list(self._tasks))

    def add(self, task: DownloadTask) -> None:
        if any(t.task_id == task.task_id for t in self._tasks):
            raise ValueError(f"Task already in queue: {task.task_id}")
        self._tasks.append(task)
        self._sort()
        self._wakeup.set()
        log.info("queue: added task %s (%s)", task.task_id, task.url)

    def get(self, task_id: str) -> DownloadTask | None:
        for task in self._tasks:
            if task.task_id == task_id:
                return task
        return None

    def remove(self, task_id: str) -> DownloadTask | None:
        task = self.get(task_id)
        if task is None:
            return None
        self._tasks.remove(task)
        return task

    def all(self) -> tuple[DownloadTask, ...]:
        return tuple(self._tasks)

    def pending(self) -> tuple[DownloadTask, ...]:
        return tuple(t for t in self._tasks if t.state == DownloadState.QUEUED)

    def active(self) -> tuple[DownloadTask, ...]:
        return tuple(
            t for t in self._tasks if t.state in (DownloadState.ACTIVE, DownloadState.PAUSED)
        )

    def terminal(self) -> tuple[DownloadTask, ...]:
        return tuple(t for t in self._tasks if t.state.is_terminal)

    def next_runnable(self) -> DownloadTask | None:
        """Returns the highest-priority runnable task, or ``None``.

        A task is runnable if it is QUEUED and either has no ``retry_after``
        or the backoff delay has elapsed.
        """
        for task in self._tasks:
            if task.is_ready_to_run:
                return task
        return None

    async def acquire_slot(self) -> None:
        await self._semaphore.acquire()

    def release_slot(self) -> None:
        self._semaphore.release()

    def clear_terminal(self) -> int:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if not t.state.is_terminal]
        return before - len(self._tasks)

    def _sort(self) -> None:
        # Highest priority first; ties broken by creation time (FIFO).
        self._tasks.sort(key=lambda t: (-t.priority.value, t.created_at))


__all__ = ["DownloadQueue"]

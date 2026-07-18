"""The download manager orchestrates the queue + providers + workers.

Phase 3 production controls:

- **Concurrency**: a semaphore caps simultaneous active downloads; a pool of
  worker coroutines drains the queue.
- **Pause / Resume**: each running download owns a [CancellationTokenSource].
  Pause sets the token; the running [asyncio.Task] is cancelled, partial files
  are preserved, and the task transitions to PAUSED. Resume moves it back to
  QUEUED; a worker picks it up and the [RecoveryManager] passes resume hints.
- **Cancel**: like pause but transitions to CANCELLED and cleans up partials.
- **Retry**: on failure, the [RetryPolicy] decides whether to schedule a retry
  (FAILED -> QUEUED with a ``retry_after`` backoff) or leave the task FAILED.
- **Persistence**: a [TaskRepository] snapshots every state transition to
  SQLite; on engine start, non-terminal tasks are restored.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from mediahub_engine.config import EngineConfig
from mediahub_engine.download.cancellation import (
    CancellationTokenSource,
    DownloadCancelled,
)
from mediahub_engine.download.queue import DownloadQueue
from mediahub_engine.download.recovery import RecoveryManager
from mediahub_engine.download.retry import DEFAULT_RETRY_POLICY, RetryPolicy
from mediahub_engine.download.strategy import pick_engine
from mediahub_engine.download.task import (
    DownloadState,
    DownloadTask,
    IllegalStateTransition,
)
from mediahub_engine.ipc.jsonrpc import RpcDispatcher, RpcError
from mediahub_engine.providers.base import DownloadSink, ProviderError, ProviderResult
from mediahub_engine.providers.registry import get_registry
from mediahub_engine.utils.logging import get_logger

if TYPE_CHECKING:
    from mediahub_engine.database import (
        HistoryRepository,
        MediaRepository,
        TaskRepository,
    )

log = get_logger(__name__)


class _ProgressSink(DownloadSink):
    """Forwards provider progress to JSON-RPC notifications (throttled).

    Also checks the cancellation token between progress callbacks so a paused
    or cancelled download aborts promptly.
    """

    def __init__(
        self,
        dispatcher: RpcDispatcher,
        task_id: str,
        min_interval: float,
        cancel_source: CancellationTokenSource,
    ) -> None:
        self._dispatcher = dispatcher
        self._task_id = task_id
        self._min_interval = min_interval
        self._last_emit: float = 0.0
        self._loop = asyncio.get_event_loop()
        self._cancel_source = cancel_source

    def on_progress(
        self, *, task_id: str, percent: float, bytes_done: int, total_bytes: int | None
    ) -> None:
        # Cooperative cancellation: if the token is set, raise to abort the
        # download coroutine. The manager catches DownloadCancelled.
        if self._cancel_source.token.is_cancelled():
            reason = self._cancel_source.reason or "cancel"
            raise DownloadCancelled(reason)

        now = self._loop.time()
        if now - self._last_emit < self._min_interval and percent < 100.0:
            return
        self._last_emit = now
        self._dispatcher.emit_notification(
            "download.progress",
            {
                "taskId": task_id,
                "percent": round(percent, 2),
                "bytes": bytes_done,
                "total": total_bytes,
            },
        )

    def on_log(self, message: str) -> None:
        log.info("[task %s] %s", self._task_id, message)


class DownloadManager:
    """Owns the queue, the worker pool, and the persistence layer."""

    def __init__(
        self,
        config: EngineConfig,
        dispatcher: RpcDispatcher,
        *,
        retry_policy: RetryPolicy | None = None,
        repository: TaskRepository | None = None,
        recovery: RecoveryManager | None = None,
        history_repository: HistoryRepository | None = None,
        media_repository: MediaRepository | None = None,
    ) -> None:
        self._config = config
        self._dispatcher = dispatcher
        self._retry_policy = retry_policy or DEFAULT_RETRY_POLICY
        self._repository = repository
        self._recovery = recovery or RecoveryManager()
        self._history_repo = history_repository
        self._media_repo = media_repository
        self._queue = DownloadQueue(max_concurrent=config.max_concurrent_downloads)
        self._workers: list[asyncio.Task[None]] = []
        self._stop = asyncio.Event()

        #: Maps task_id -> the running asyncio.Task wrapping provider.download().
        self._running: dict[str, asyncio.Task[ProviderResult]] = {}
        #: Maps task_id -> the cancellation token source for the current run.
        self._cancel_sources: dict[str, CancellationTokenSource] = {}

    @property
    def queue(self) -> DownloadQueue:
        return self._queue

    @property
    def repository(self) -> TaskRepository | None:
        return self._repository

    # ---- Lifecycle ----

    async def start(self) -> None:
        self._stop.clear()
        await self._restore_from_db()
        for i in range(self._config.max_concurrent_downloads):
            self._workers.append(asyncio.create_task(self._worker(i), name=f"dl-worker-{i}"))
        log.info("download manager started with %d workers", len(self._workers))

    async def stop(self) -> None:
        self._stop.set()
        # Cancel all running downloads so workers exit promptly.
        for source in list(self._cancel_sources.values()):
            source.cancel()
        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        self._workers.clear()
        log.info("download manager stopped")

    async def _restore_from_db(self) -> None:
        """Loads non-terminal tasks from SQLite and re-queues them."""
        if self._repository is None:
            return
        tasks = self._repository.load_non_terminal()
        for task in tasks:
            # Active tasks were interrupted by the restart; move them back to
            # QUEUED so a worker picks them up. The recovery manager handles
            # partial-file resume.
            if task.state == DownloadState.ACTIVE:
                task.state = DownloadState.QUEUED
                task.started_at = None
            if self._queue.get(task.task_id) is None:
                self._queue.add(task)
                log.info("restored task %s from db (state=%s)", task.task_id, task.state.value)
        if tasks:
            log.info("restored %d task(s) from persistence", len(tasks))

    # ---- Public API (called by engine method handlers) ----

    async def enqueue(self, task: DownloadTask) -> DownloadTask:
        self._queue.add(task)
        self._persist(task)
        self._dispatcher.emit_notification(
            "download.enqueued", {"taskId": task.task_id, "url": task.url}
        )
        return task

    async def pause(self, task_id: str) -> bool:
        task = self._require_task(task_id)
        if task.state == DownloadState.QUEUED:
            # Not yet running — just mark paused directly.
            task.state = DownloadState.PAUSED
            self._persist(task)
            self._dispatcher.emit_notification("download.paused", {"taskId": task_id})
            return True
        if task.state != DownloadState.ACTIVE:
            return False
        source = self._cancel_sources.get(task_id)
        if source is None:
            return False
        source.pause()
        # The worker loop's CancelledError handler will call mark_paused.
        running = self._running.get(task_id)
        if running is not None:
            running.cancel()
        return True

    async def resume(self, task_id: str) -> bool:
        task = self._require_task(task_id)
        if task.state != DownloadState.PAUSED:
            return False
        task.reset_for_resume()
        task.mark_resumed()
        self._persist(task)
        self._dispatcher.emit_notification("download.resumed", {"taskId": task_id})
        return True

    async def retry(self, task_id: str) -> bool:
        task = self._require_task(task_id)
        if task.state != DownloadState.FAILED:
            return False
        task.retries = 0  # manual retry resets the budget
        task.mark_retry_scheduled(delay=0.0)
        self._persist(task)
        self._dispatcher.emit_notification("download.retry_scheduled", {"taskId": task_id})
        return True

    async def cancel(self, task_id: str) -> bool:
        task = self._require_task(task_id)
        if task.state.is_terminal:
            return False
        if task.state == DownloadState.ACTIVE:
            source = self._cancel_sources.get(task_id)
            if source is not None:
                source.cancel()
                running = self._running.get(task_id)
                if running is not None:
                    running.cancel()
                # The worker's CancelledError handler calls mark_cancelled.
                return True
        # Not running — mark cancelled directly.
        task.mark_cancelled()
        self._recovery.cleanup_partials(task)
        self._persist(task)
        self._dispatcher.emit_notification("download.cancelled", {"taskId": task_id})
        return True

    def clear_terminal(self) -> int:
        """Removes all terminal tasks from the queue and the database."""
        terminal = [t for t in self._queue.all() if t.state.is_terminal]
        for task in terminal:
            if self._repository is not None:
                self._repository.delete(task.task_id)
        removed = self._queue.clear_terminal()
        if removed:
            log.info("cleared %d terminal task(s)", removed)
        return removed

    def status(self, task_id: str) -> dict[str, Any]:
        task = self._require_task(task_id)
        return _task_to_dict(task)

    def list_tasks(self) -> list[dict[str, Any]]:
        return [_task_to_dict(t) for t in self._queue.all()]

    # ---- Worker loop ----

    async def _worker(self, index: int) -> None:
        log.info("worker %d ready", index)
        while not self._stop.is_set():
            task = self._queue.next_runnable()
            if task is None:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=0.5)
                except TimeoutError:
                    continue
                continue

            await self._queue.acquire_slot()
            try:
                await self._run_task(task)
            except Exception:
                log.exception("worker %d: unhandled error for task %s", index, task.task_id)
            finally:
                self._queue.release_slot()

    async def _run_task(self, task: DownloadTask) -> None:
        try:
            task.mark_started()
        except IllegalStateTransition:
            return  # Task was cancelled/paused before a worker grabbed it.

        registry = get_registry()
        try:
            provider = registry.require(task.url)
        except (RpcError, ProviderError):
            # Provider-not-found is a permanent error — never retry.
            task.mark_failed("No provider supports this URL")
            self._persist(task)
            self._dispatcher.emit_notification(
                "download.failed", {"taskId": task.task_id, "error": task.error}
            )
            return

        decision = pick_engine(provider.capability)
        task.provider = provider.capability.name
        task.engine = decision.engine_label
        self._persist(task)
        log.info(
            "task %s -> provider=%s engine=%s",
            task.task_id,
            provider.capability.name,
            decision.engine_label,
        )
        self._dispatcher.emit_notification(
            "download.started",
            {"taskId": task.task_id, "provider": task.provider, "engine": task.engine},
        )

        # Prepare resume options if this is a resumed task.
        resume_opts = self._recovery.prepare_resume(task)
        download_options = {**task.options, **resume_opts, "engine": decision.engine_label}

        cancel_source = CancellationTokenSource()
        self._cancel_sources[task.task_id] = cancel_source
        sink = _ProgressSink(
            self._dispatcher, task.task_id, self._config.progress_emit_interval, cancel_source
        )

        download_coro = provider.download(
            task.url,
            dest_dir=task.dest_dir or str(self._config.work_dir / "downloads"),
            task_id=task.task_id,
            sink=sink,
            options=download_options,
        )
        running = asyncio.create_task(download_coro, name=f"dl-{task.task_id}")
        self._running[task.task_id] = running

        try:
            result: ProviderResult = await running
        except asyncio.CancelledError:
            await self._handle_cancellation(task, cancel_source)
            return
        except DownloadCancelled:
            await self._handle_cancellation(task, cancel_source)
            return
        except Exception as exc:
            await self._handle_failure(task, str(exc))
            return
        finally:
            self._running.pop(task.task_id, None)
            self._cancel_sources.pop(task.task_id, None)

        task.bytes_done = result.bytes_written
        task.total_bytes = result.bytes_written
        if result.metadata is not None:
            task.metadata = _metadata_to_dict(result.metadata)
        task.mark_completed(result.output_paths)
        self._persist(task)
        self._index_completed_task(task, result)
        self._record_history(task, state="completed")
        self._dispatcher.emit_notification(
            "download.completed",
            {
                "taskId": task.task_id,
                "paths": result.output_paths,
                "path": result.output_path,
                "bytes": result.bytes_written,
            },
        )

    async def _handle_cancellation(
        self, task: DownloadTask, source: CancellationTokenSource
    ) -> None:
        """Handles a CancelledError / DownloadCancelled from a running download."""
        reason = source.reason or "cancel"
        if reason == "pause":
            with contextlib.suppress(IllegalStateTransition):
                task.mark_paused()
            self._persist(task)
            self._dispatcher.emit_notification("download.paused", {"taskId": task.task_id})
            log.info("task %s paused", task.task_id)
        else:
            with contextlib.suppress(IllegalStateTransition):
                task.mark_cancelled()
            self._recovery.cleanup_partials(task)
            self._persist(task)
            self._dispatcher.emit_notification("download.cancelled", {"taskId": task.task_id})
            log.info("task %s cancelled", task.task_id)

    async def _handle_failure(self, task: DownloadTask, error: str) -> None:
        """Handles a download failure, applying the retry policy."""
        try:
            task.mark_failed(error)
        except IllegalStateTransition:
            return

        if self._retry_policy.should_retry(task.retries):
            delay = self._retry_policy.delay_for(task.retries)
            task.mark_retry_scheduled(delay)
            self._persist(task)
            self._dispatcher.emit_notification(
                "download.retry_scheduled",
                {
                    "taskId": task.task_id,
                    "attempt": task.retries,
                    "delaySeconds": delay,
                },
            )
            log.info(
                "task %s failed, retry %d scheduled in %.1fs",
                task.task_id,
                task.retries,
                delay,
            )
        else:
            self._persist(task)
            self._record_history(task, state="failed", error=error)
            self._dispatcher.emit_notification(
                "download.failed", {"taskId": task.task_id, "error": task.error}
            )
            log.warning("task %s failed permanently: %s", task.task_id, error)

    # ---- Phase 4: history + media indexing ----

    def _record_history(self, task: DownloadTask, *, state: str, error: str | None = None) -> None:
        """Records an append-only history entry for terminal task states."""
        if self._history_repo is None:
            return
        import time

        from mediahub_engine.storage.models import HistoryEntry

        entry = HistoryEntry(
            task_id=task.task_id,
            url=task.url,
            provider=task.provider,
            engine=task.engine,
            state=state,
            bytes_done=task.bytes_done,
            output_paths=list(task.output_paths),
            error=error or task.error,
            metadata=task.metadata,
            started_at=task.started_at,
            finished_at=task.finished_at or time.time(),
        )
        try:
            self._history_repo.record(entry)
        except Exception:
            log.exception("failed to record history for task %s", task.task_id)

    def _index_completed_task(self, task: DownloadTask, result: ProviderResult) -> None:
        """Indexes completed download output files into the media library."""
        if self._media_repo is None:
            return
        import os
        import time

        from mediahub_engine.storage.models import MediaCategory, MediaItem

        for path in result.output_paths:
            if not os.path.exists(path):
                continue
            # Skip if already indexed (resume / re-run).
            if self._media_repo.get_by_path(path) is not None:
                continue
            name = os.path.basename(path)
            category = MediaCategory.from_path(path)
            size = os.path.getsize(path)
            item = MediaItem(
                path=path,
                name=name,
                category=category,
                size_bytes=size,
                provider=task.provider,
                url=task.url,
                task_id=task.task_id,
                title=result.metadata.title if result.metadata else None,
                uploader=result.metadata.uploader if result.metadata else None,
                tags=list(result.metadata.tags) if result.metadata else [],
                created_at=time.time(),
                added_at=time.time(),
            )
            try:
                self._media_repo.upsert(item)
            except Exception:
                log.exception("failed to index media item %s", path)

    # ---- Helpers ----

    def _require_task(self, task_id: str) -> DownloadTask:
        task = self._queue.get(task_id)
        if task is None:
            raise RpcError(-2, "Unknown task", data={"taskId": task_id})
        return task

    def _persist(self, task: DownloadTask) -> None:
        if self._repository is not None:
            try:
                self._repository.save(task)
            except Exception:
                log.exception("failed to persist task %s", task.task_id)


def _metadata_to_dict(metadata) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "title": metadata.title,
        "uploader": metadata.uploader,
        "durationSeconds": metadata.duration_seconds,
        "thumbnailUrl": metadata.thumbnail_url,
        "categories": list(metadata.categories),
        "tags": list(metadata.tags),
    }


def _task_to_dict(task: DownloadTask) -> dict[str, Any]:
    return {
        "taskId": task.task_id,
        "url": task.url,
        "state": task.state.value,
        "priority": task.priority.value,
        "percent": round(task.percent, 2),
        "bytes": task.bytes_done,
        "total": task.total_bytes,
        "outputPath": task.output_path,
        "outputPaths": list(task.output_paths),
        "provider": task.provider,
        "engine": task.engine,
        "metadata": task.metadata,
        "error": task.error,
        "lastError": task.last_error,
        "retries": task.retries,
        "retryAfter": task.retry_after,
        "elapsed": round(task.elapsed, 3),
    }


__all__ = ["DownloadManager"]

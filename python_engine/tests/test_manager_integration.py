"""Integration tests for the Phase 3 DownloadManager: pause/resume/cancel/retry.

Uses a controllable fake provider that can be made to sleep, fail, or succeed
on demand so we can exercise the cancellation and retry paths without real
network I/O.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from mediahub_engine.config import EngineConfig
from mediahub_engine.download.manager import DownloadManager
from mediahub_engine.download.retry import RetryPolicy
from mediahub_engine.download.task import DownloadState, DownloadTask
from mediahub_engine.ipc.jsonrpc import RpcDispatcher
from mediahub_engine.providers.base import (
    Capability,
    DownloadSink,
    MediaMetadata,
    Provider,
    ProviderError,
    ProviderFeature,
    ProviderResult,
)
from mediahub_engine.providers.registry import get_registry

# ---------------------------------------------------------------------------
# Controllable provider for integration tests
# ---------------------------------------------------------------------------


class _ControllableProvider(Provider):
    """A provider whose download() blocks on an event, enabling pause/cancel tests."""

    capability = Capability(
        name="_test",
        engine="http",
        url_patterns=("_test://",),
        features=ProviderFeature.SINGLE,
    )

    def __init__(self, *, fail_times: int = 0, delay: float = 0.0) -> None:
        self._fail_times = fail_times
        self._delay = delay
        self._attempts = 0
        self._gate = asyncio.Event()
        self._gate.set()

    def matches(self, url: str) -> bool:
        return url.startswith("_test://")

    async def extract_metadata(self, url: str) -> MediaMetadata:
        return MediaMetadata(title="test")

    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict | None = None,
    ) -> ProviderResult:
        self._attempts += 1
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._attempts <= self._fail_times:
            raise ProviderError(f"simulated failure #{self._attempts}", code="TEST_FAIL")
        # Write a real file so the manager can report bytes.
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, "out.bin")
        with open(path, "wb") as fh:
            fh.write(b"hello")
        if sink is not None:
            sink.on_progress(task_id=task_id, percent=100.0, bytes_done=5, total_bytes=5)
        return ProviderResult(output_paths=[path], bytes_written=5)


def _register_test_provider(provider: Provider) -> None:
    """Injects a test provider into the global registry."""
    registry = get_registry()
    # The registry may already have providers from a previous test; just add ours.
    if registry.by_name(provider.capability.name) is None:
        registry.register(provider)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_completes_successful_download(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    manager = DownloadManager(config, RpcDispatcher())
    provider = _ControllableProvider()
    _register_test_provider(provider)

    task = DownloadTask(url="_test://ok", dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    await manager._run_task(task)

    assert task.state is DownloadState.COMPLETED
    assert task.output_paths == [os.path.join(str(tmp_path / "out"), "out.bin")]
    assert task.bytes_done == 5


@pytest.mark.asyncio
async def test_manager_retries_on_failure_then_succeeds(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    policy = RetryPolicy(max_retries=3, base_delay=0.001, max_delay=0.01, jitter=0.0)
    manager = DownloadManager(config, RpcDispatcher(), retry_policy=policy)
    provider = _ControllableProvider(fail_times=2)
    _register_test_provider(provider)

    task = DownloadTask(url="_test://flaky", dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    # First run fails and schedules retry 1.
    await manager._run_task(task)
    assert task.state is DownloadState.QUEUED  # retry scheduled
    assert task.retries == 1

    # Second run (retry 1) fails and schedules retry 2.
    await manager._run_task(task)
    assert task.retries == 2

    # Third run (retry 2) succeeds.
    await manager._run_task(task)
    assert task.state is DownloadState.COMPLETED
    assert provider._attempts == 3


@pytest.mark.asyncio
async def test_manager_exhausts_retries_and_fails(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    policy = RetryPolicy(max_retries=2, base_delay=0.001, max_delay=0.01, jitter=0.0)
    manager = DownloadManager(config, RpcDispatcher(), retry_policy=policy)
    provider = _ControllableProvider(fail_times=99)
    _register_test_provider(provider)

    task = DownloadTask(url="_test://always-fails", dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    # Run all retries.
    await manager._run_task(task)  # attempt 1 -> retry 1
    await manager._run_task(task)  # retry 1 -> retry 2
    await manager._run_task(task)  # retry 2 -> exhausted (FAILED)

    assert task.state is DownloadState.FAILED
    assert task.retries == 2
    assert task.error is not None


@pytest.mark.asyncio
async def test_manager_cancel_queued_task(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    manager = DownloadManager(config, RpcDispatcher())

    task = DownloadTask(url="_test://x", dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    cancelled = await manager.cancel(task.task_id)
    assert cancelled is True
    assert task.state is DownloadState.CANCELLED


@pytest.mark.asyncio
async def test_manager_pause_queued_task(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    manager = DownloadManager(config, RpcDispatcher())

    task = DownloadTask(url="_test://x", dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    paused = await manager.pause(task.task_id)
    assert paused is True
    assert task.state is DownloadState.PAUSED

    # Resume moves it back to QUEUED.
    resumed = await manager.resume(task.task_id)
    assert resumed is True
    assert task.state is DownloadState.QUEUED


@pytest.mark.asyncio
async def test_manager_retry_failed_task(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    policy = RetryPolicy(max_retries=0)  # no auto-retry
    manager = DownloadManager(config, RpcDispatcher(), retry_policy=policy)
    provider = _ControllableProvider(fail_times=1)
    _register_test_provider(provider)

    task = DownloadTask(url="_test://manual-retry", dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    await manager._run_task(task)
    assert task.state is DownloadState.FAILED

    retried = await manager.retry(task.task_id)
    assert retried is True
    assert task.state is DownloadState.QUEUED

    # Now it succeeds.
    await manager._run_task(task)
    assert task.state is DownloadState.COMPLETED


@pytest.mark.asyncio
async def test_manager_clear_terminal_removes_finished_tasks(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    manager = DownloadManager(config, RpcDispatcher())

    t1 = DownloadTask(url="_test://1")
    t2 = DownloadTask(url="_test://2")
    t2.mark_started()
    t2.mark_completed("/out")
    manager.queue.add(t1)
    manager.queue.add(t2)

    removed = manager.clear_terminal()
    assert removed == 1
    assert all(not t.state.is_terminal for t in manager.queue.all())


@pytest.mark.asyncio
async def test_manager_persists_to_repository(tmp_path) -> None:
    """Verify that the manager snapshots state transitions to SQLite."""
    from mediahub_engine.database import Database, TaskRepository

    config = EngineConfig(work_dir=tmp_path / "work", persist_downloads=False)
    db = Database(tmp_path / "test.db")
    repo = TaskRepository(db)
    manager = DownloadManager(config, RpcDispatcher(), repository=repo)

    task = DownloadTask(url="_test://persist", dest_dir=str(tmp_path / "out"))
    await manager.enqueue(task)  # enqueue() persists; queue.add() does not.
    assert repo.count() == 1

    loaded = repo.load_all()
    assert loaded[0].url == "_test://persist"
    assert loaded[0].state is DownloadState.QUEUED

    db.close()


@pytest.mark.asyncio
async def test_manager_restores_non_terminal_on_start(tmp_path) -> None:
    """Verify that start() reloads non-terminal tasks from SQLite."""
    from mediahub_engine.database import Database, TaskRepository

    config = EngineConfig(
        work_dir=tmp_path / "work",
        persist_downloads=False,
        max_concurrent_downloads=1,
    )
    db = Database(tmp_path / "test.db")
    repo = TaskRepository(db)

    # Pre-populate with a QUEUED task (simulating a restart).
    task = DownloadTask(url="_test://restored", dest_dir=str(tmp_path / "out"))
    repo.save(task)

    manager = DownloadManager(config, RpcDispatcher(), repository=repo)
    await manager.start()

    # The task should have been loaded into the queue.
    restored = manager.queue.get(task.task_id)
    assert restored is not None
    assert restored.url == "_test://restored"

    await manager.stop()
    db.close()


@pytest.mark.asyncio
async def test_manager_restores_active_as_queued_on_start(tmp_path) -> None:
    """Active tasks are moved back to QUEUED on restart (recovery via worker)."""
    from mediahub_engine.database import Database, TaskRepository

    config = EngineConfig(
        work_dir=tmp_path / "work",
        persist_downloads=False,
        max_concurrent_downloads=1,
    )
    db = Database(tmp_path / "test.db")
    repo = TaskRepository(db)

    # Simulate a task that was ACTIVE when the engine died.
    task = DownloadTask(url="_test://interrupted", dest_dir=str(tmp_path / "out"))
    task.mark_started()
    repo.save(task)

    manager = DownloadManager(config, RpcDispatcher(), repository=repo)
    await manager.start()

    restored = manager.queue.get(task.task_id)
    assert restored is not None
    assert restored.state is DownloadState.QUEUED  # moved back

    await manager.stop()
    db.close()

"""Tests for the download manager + engine-selection strategy."""

from __future__ import annotations

import os

import pytest

from mediahub_engine.config import EngineConfig
from mediahub_engine.download.manager import DownloadManager
from mediahub_engine.download.queue import DownloadQueue
from mediahub_engine.download.strategy import EngineStrategy, pick_engine
from mediahub_engine.download.task import DownloadState, DownloadTask, TaskPriority
from mediahub_engine.ipc.jsonrpc import RpcDispatcher
from mediahub_engine.providers.base import Capability

# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


def test_queue_orders_by_priority() -> None:
    q = DownloadQueue()
    low = DownloadTask(url="https://e.com/a.mp4", priority=TaskPriority.LOW)
    urgent = DownloadTask(url="https://e.com/b.mp4", priority=TaskPriority.URGENT)
    normal = DownloadTask(url="https://e.com/c.mp4", priority=TaskPriority.NORMAL)
    q.add(low)
    q.add(urgent)
    q.add(normal)
    assert q.next_runnable() is urgent
    q.remove(urgent.task_id)
    assert q.next_runnable() is normal


def test_queue_rejects_duplicate_task_ids() -> None:
    q = DownloadQueue()
    task = DownloadTask(url="https://e.com/a.mp4")
    q.add(task)
    with pytest.raises(ValueError, match="already in queue"):
        q.add(task)


def test_queue_clear_terminal_only_removes_finished() -> None:
    q = DownloadQueue()
    queued = DownloadTask(url="https://e.com/a.mp4")
    done = DownloadTask(url="https://e.com/b.mp4")
    done.mark_started()
    done.mark_completed("/tmp/out")
    q.add(queued)
    q.add(done)
    removed = q.clear_terminal()
    assert removed == 1
    assert all(not t.state.is_terminal for t in q.all())


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


def test_pick_engine_maps_known_engines() -> None:
    cap = Capability(name="yt", engine="yt-dlp", url_patterns=())
    assert pick_engine(cap).strategy is EngineStrategy.YTDLP

    cap = Capability(name="ig", engine="gallery-dl", url_patterns=())
    assert pick_engine(cap).strategy is EngineStrategy.GALLERY_DL


def test_pick_engine_falls_back_to_http_for_unknown() -> None:
    cap = Capability(name="x", engine="voodoo-magic", url_patterns=())
    decision = pick_engine(cap)
    assert decision.strategy is EngineStrategy.HTTP


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_runs_task_to_completion(tmp_path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"hello-mediahub")

    config = EngineConfig(work_dir=tmp_path / "work")
    dispatcher = RpcDispatcher()
    manager = DownloadManager(config, dispatcher)

    task = DownloadTask(url=src.as_uri(), dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    await manager._run_task(task)

    assert task.state is DownloadState.COMPLETED
    assert os.path.exists(task.output_path)  # type: ignore[arg-type]
    assert task.bytes_done == len(b"hello-mediahub")


@pytest.mark.asyncio
async def test_manager_marks_failed_when_no_provider(tmp_path) -> None:
    config = EngineConfig(work_dir=tmp_path / "work")
    dispatcher = RpcDispatcher()
    manager = DownloadManager(config, dispatcher)

    # A URL no provider claims (no platform match, no media extension).
    task = DownloadTask(url="https://example.com/blog/post", dest_dir=str(tmp_path / "out"))
    manager.queue.add(task)

    await manager._run_task(task)

    assert task.state is DownloadState.FAILED
    assert task.error is not None

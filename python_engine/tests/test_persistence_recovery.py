"""Tests for the SQLite persistence layer and the recovery manager."""

from __future__ import annotations

import pytest

from mediahub_engine.database import Database, TaskRepository
from mediahub_engine.download.recovery import RecoveryManager
from mediahub_engine.download.task import DownloadState, DownloadTask, TaskPriority

# ---------------------------------------------------------------------------
# TaskRepository
# ---------------------------------------------------------------------------


@pytest.fixture
def repository(tmp_path: pytest.TempPathFactory) -> TaskRepository:
    db = Database(tmp_path / "test.db")
    yield TaskRepository(db)
    db.close()


def test_save_and_load_round_trip(repository: TaskRepository) -> None:
    task = DownloadTask(
        url="https://example.com/video.mp4",
        priority=TaskPriority.HIGH,
        dest_dir="/tmp/out",
        options={"format": "best"},
    )
    task.mark_started()
    task.mark_completed(["/tmp/out/video.mp4"])
    task.provider = "generic"
    task.engine = "http"
    task.metadata = {"title": "My Video"}
    task.bytes_done = 1024
    task.total_bytes = 1024

    repository.save(task)
    loaded = repository.load_all()
    assert len(loaded) == 1
    t = loaded[0]
    assert t.task_id == task.task_id
    assert t.url == task.url
    assert t.priority is TaskPriority.HIGH
    assert t.state is DownloadState.COMPLETED
    assert t.dest_dir == "/tmp/out"
    assert t.options == {"format": "best"}
    assert t.output_paths == ["/tmp/out/video.mp4"]
    assert t.provider == "generic"
    assert t.engine == "http"
    assert t.metadata == {"title": "My Video"}
    assert t.bytes_done == 1024
    assert t.total_bytes == 1024


def test_save_upserts_existing_task(repository: TaskRepository) -> None:
    task = DownloadTask(url="https://example.com/a.mp4")
    repository.save(task)

    task.mark_started()
    repository.save(task)

    loaded = repository.load_all()
    assert len(loaded) == 1
    assert loaded[0].state is DownloadState.ACTIVE


def test_delete_removes_task(repository: TaskRepository) -> None:
    task = DownloadTask(url="https://example.com/a.mp4")
    repository.save(task)
    assert repository.count() == 1

    repository.delete(task.task_id)
    assert repository.count() == 0


def test_load_non_terminal_excludes_completed(repository: TaskRepository) -> None:
    queued = DownloadTask(url="https://example.com/a.mp4")
    active = DownloadTask(url="https://example.com/b.mp4")
    active.mark_started()

    done = DownloadTask(url="https://example.com/c.mp4")
    done.mark_started()
    done.mark_completed("/out.mp4")

    failed = DownloadTask(url="https://example.com/d.mp4")
    failed.mark_started()
    failed.mark_failed("err")

    for t in (queued, active, done, failed):
        repository.save(t)

    non_terminal = repository.load_non_terminal()
    assert len(non_terminal) == 2
    states = {t.state for t in non_terminal}
    assert DownloadState.COMPLETED not in states
    assert DownloadState.FAILED not in states


def test_load_non_terminal_includes_paused_and_retry(repository: TaskRepository) -> None:
    paused = DownloadTask(url="https://example.com/a.mp4")
    paused.mark_started()
    paused.mark_paused()
    repository.save(paused)

    retrying = DownloadTask(url="https://example.com/b.mp4")
    retrying.mark_started()
    retrying.mark_failed("timeout")
    retrying.mark_retry_scheduled(1.0)
    repository.save(retrying)

    non_terminal = repository.load_non_terminal()
    assert len(non_terminal) == 2
    assert any(t.state is DownloadState.PAUSED for t in non_terminal)
    assert any(t.state is DownloadState.QUEUED and t.retry_after is not None for t in non_terminal)


def test_count_returns_total(repository: TaskRepository) -> None:
    for i in range(5):
        repository.save(DownloadTask(url=f"https://example.com/{i}.mp4"))
    assert repository.count() == 5


def test_round_trip_preserves_retry_fields(repository: TaskRepository) -> None:
    task = DownloadTask(url="https://example.com/a.mp4")
    task.mark_started()
    task.mark_failed("network")
    task.mark_retry_scheduled(delay=5.0)
    repository.save(task)

    loaded = repository.load_all()[0]
    assert loaded.retries == 1
    assert loaded.retry_after is not None
    assert loaded.last_error == "network"
    assert loaded.state is DownloadState.QUEUED


# ---------------------------------------------------------------------------
# RecoveryManager
# ---------------------------------------------------------------------------


def test_recovery_no_partial_files_returns_empty(tmp_path) -> None:
    task = DownloadTask(url="https://example.com/a.mp4", dest_dir=str(tmp_path))
    task.mark_started()
    task.mark_paused()
    task.mark_resumed()
    result = RecoveryManager().prepare_resume(task)
    assert result["resume"] is False


def test_recovery_detects_part_files(tmp_path) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "video.mp4.part").write_bytes(b"partial")
    task = DownloadTask(url="https://example.com/a.mp4", dest_dir=str(dest))
    task.mark_started()
    task.mark_paused()
    task.mark_resumed()
    task.bytes_done = 7

    result = RecoveryManager().prepare_resume(task)
    assert result["resume"] is True
    assert len(result["partial_files"]) == 1
    assert result["resume_from"] == 7


def test_recovery_detects_known_output_paths(tmp_path) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    existing = dest / "clip.mp4"
    existing.write_bytes(b"data")

    task = DownloadTask(url="https://example.com/a.mp4", dest_dir=str(dest))
    task.output_paths = [str(existing)]
    task.mark_started()
    task.mark_paused()
    task.mark_resumed()

    result = RecoveryManager().prepare_resume(task)
    assert result["resume"] is True
    assert str(existing) in result["partial_files"]


def test_recovery_no_dest_dir_returns_empty(tmp_path) -> None:
    task = DownloadTask(url="https://example.com/a.mp4", dest_dir="")
    result = RecoveryManager().prepare_resume(task)
    assert result["resume"] is False


def test_cleanup_partials_removes_part_files(tmp_path) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "a.mp4.part").write_bytes(b"x")
    (dest / "b.mp4.part").write_bytes(b"y")
    (dest / "c.mp4").write_bytes(b"keep")

    task = DownloadTask(url="https://example.com/a.mp4", dest_dir=str(dest))
    removed = RecoveryManager().cleanup_partials(task)
    assert removed == 2
    assert not (dest / "a.mp4.part").exists()
    assert not (dest / "b.mp4.part").exists()
    assert (dest / "c.mp4").exists()  # non-part files untouched


def test_cleanup_partials_no_dest_dir_returns_zero(tmp_path) -> None:
    task = DownloadTask(url="https://example.com/a.mp4", dest_dir="")
    assert RecoveryManager().cleanup_partials(task) == 0

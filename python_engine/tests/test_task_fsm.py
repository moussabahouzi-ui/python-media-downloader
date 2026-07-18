"""Tests for the download task FSM and state transitions."""

from __future__ import annotations

import pytest

from mediahub_engine.download.task import (
    DownloadState,
    DownloadTask,
    IllegalStateTransition,
    TaskPriority,
)


def test_new_task_starts_queued() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    assert task.state is DownloadState.QUEUED
    assert task.state.is_terminal is False
    assert task.state.is_runnable is True
    assert task.is_ready_to_run is True


def test_start_from_queued() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    assert task.state is DownloadState.ACTIVE
    assert task.started_at is not None


def test_start_from_paused() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_paused()
    task.mark_started()
    assert task.state is DownloadState.ACTIVE


def test_start_from_terminal_rejected() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_completed("/out.mp4")
    with pytest.raises(IllegalStateTransition):
        task.mark_started()


def test_pause_only_from_active() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    with pytest.raises(IllegalStateTransition):
        task.mark_paused()

    task.mark_started()
    task.mark_paused()
    assert task.state is DownloadState.PAUSED


def test_resume_only_from_paused() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    with pytest.raises(IllegalStateTransition):
        task.mark_resumed()

    task.mark_started()
    task.mark_paused()
    task.mark_resumed()
    assert task.state is DownloadState.QUEUED
    assert task.is_ready_to_run is True


def test_complete_from_active() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_completed(["/out.mp4", "/out.srt"])
    assert task.state is DownloadState.COMPLETED
    assert task.output_paths == ["/out.mp4", "/out.srt"]
    assert task.output_path == "/out.mp4"
    assert task.finished_at is not None


def test_complete_from_paused() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_paused()
    task.mark_completed("/out.mp4")
    assert task.state is DownloadState.COMPLETED


def test_complete_from_queued_rejected() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    with pytest.raises(IllegalStateTransition):
        task.mark_completed("/out.mp4")


def test_fail_from_active() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_failed("network error")
    assert task.state is DownloadState.FAILED
    assert task.error == "network error"
    assert task.last_error == "network error"
    assert task.finished_at is not None


def test_retry_schedules_from_failed() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_failed("timeout")
    task.mark_retry_scheduled(delay=2.0)
    assert task.state is DownloadState.QUEUED
    assert task.retries == 1
    assert task.retry_after is not None
    assert task.error is None
    assert task.finished_at is None
    assert task.is_ready_to_run is False  # retry_after is in the future


def test_retry_becomes_runnable_after_delay() -> None:

    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_failed("timeout")
    task.mark_retry_scheduled(delay=0.0)  # no delay
    assert task.is_ready_to_run is True


def test_retry_from_non_failed_rejected() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    with pytest.raises(IllegalStateTransition):
        task.mark_retry_scheduled(delay=1.0)


def test_cancel_from_queued() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_cancelled()
    assert task.state is DownloadState.CANCELLED


def test_cancel_from_active() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_cancelled()
    assert task.state is DownloadState.CANCELLED


def test_cancel_from_paused() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_paused()
    task.mark_cancelled()
    assert task.state is DownloadState.CANCELLED


def test_cancel_from_terminal_rejected() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.mark_started()
    task.mark_completed("/out.mp4")
    with pytest.raises(IllegalStateTransition):
        task.mark_cancelled()


def test_completed_is_terminal() -> None:
    assert DownloadState.COMPLETED.is_terminal
    assert DownloadState.FAILED.is_terminal
    assert DownloadState.CANCELLED.is_terminal
    assert not DownloadState.QUEUED.is_terminal
    assert not DownloadState.ACTIVE.is_terminal
    assert not DownloadState.PAUSED.is_terminal


def test_task_priority_ordering() -> None:
    assert TaskPriority.URGENT > TaskPriority.HIGH
    assert TaskPriority.HIGH > TaskPriority.NORMAL
    assert TaskPriority.NORMAL > TaskPriority.LOW


def test_percent_calculation() -> None:
    task = DownloadTask(url="https://example.com/x.mp4")
    task.total_bytes = 1000
    task.bytes_done = 500
    assert task.percent == 50.0

    task.bytes_done = 1500
    assert task.percent == 100.0  # capped

    task.total_bytes = None
    assert task.percent == 0.0

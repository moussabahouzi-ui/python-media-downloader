"""Tests for the Phase 2 engine method surface (provider.*, download.*)."""

from __future__ import annotations

import pytest

from mediahub_engine.config import EngineConfig
from mediahub_engine.contracts import EngineError, JsonRpcRequest
from mediahub_engine.engine import Engine
from mediahub_engine.ipc.jsonrpc import RpcDispatcher, RpcError


def _make_engine(tmp_path) -> Engine:
    return Engine(config=EngineConfig(work_dir=tmp_path / "work"))


# ---------------------------------------------------------------------------
# provider.detect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_detect_returns_youtube_for_youtube_url(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    result = await engine._provider_detect({"url": "https://youtube.com/watch?v=abc"})
    assert result["provider"] == "youtube"
    assert result["engine"] == "yt-dlp"
    assert result["displayName"] == "YouTube"
    assert result["authRequired"] is False


@pytest.mark.asyncio
async def test_provider_detect_returns_instagram_for_instagram_url(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    result = await engine._provider_detect({"url": "https://www.instagram.com/p/Cabc/"})
    assert result["provider"] == "instagram"
    assert result["engine"] == "gallery-dl"


@pytest.mark.asyncio
async def test_provider_detect_raises_for_unsupported_url(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with pytest.raises(RpcError) as exc_info:
        await engine._provider_detect({"url": "https://example.com/blog"})
    assert exc_info.value.code == EngineError.PROVIDER_NOT_FOUND


@pytest.mark.asyncio
async def test_provider_detect_rejects_missing_url(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with pytest.raises(RpcError) as exc_info:
        await engine._provider_detect({})
    assert exc_info.value.code == EngineError.INVALID_PARAMS


# ---------------------------------------------------------------------------
# provider.list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_list_returns_all_platforms(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    result = await engine._provider_list({})
    names = {p["name"] for p in result["providers"]}
    expected = {
        "youtube",
        "instagram",
        "facebook",
        "tiktok",
        "twitter_x",
        "reddit",
        "vimeo",
        "dailymotion",
        "pinterest",
        "twitch",
        "soundcloud",
        "threads",
        "snapchat",
        "generic",
    }
    assert names == expected
    # Each descriptor has the required fields.
    sample = result["providers"][0]
    assert {"name", "displayName", "engine", "authRequired", "features", "urlPatterns"} <= set(
        sample
    )


# ---------------------------------------------------------------------------
# provider.metadata (delegates to provider.extract_metadata -> backend)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_metadata_raises_not_found_for_unknown_url(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with pytest.raises(RpcError) as exc_info:
        await engine._provider_metadata({"url": "https://example.com/blog"})
    assert exc_info.value.code == EngineError.PROVIDER_NOT_FOUND


@pytest.mark.asyncio
async def test_provider_metadata_works_for_generic_direct_url(tmp_path) -> None:
    """The generic provider handles direct media URLs without a backend lib."""
    engine = _make_engine(tmp_path)
    result = await engine._provider_metadata({"url": "https://cdn.example.com/clip.mp4"})
    assert result["provider"] == "generic"
    assert result["title"] == "clip.mp4"


# ---------------------------------------------------------------------------
# download.enqueue / list / status / cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_enqueue_returns_task_id(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    result = await engine._download_enqueue({"url": "https://example.com/x"})
    assert "taskId" in result
    assert result["state"] == "queued"
    assert isinstance(result["taskId"], str) and len(result["taskId"]) > 0


@pytest.mark.asyncio
async def test_download_enqueue_rejects_missing_url(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with pytest.raises(RpcError):
        await engine._download_enqueue({})


@pytest.mark.asyncio
async def test_download_list_returns_enqueued_tasks(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    await engine._download_enqueue({"url": "https://example.com/a"})
    await engine._download_enqueue({"url": "https://example.com/b"})
    result = await engine._download_list({})
    assert len(result["tasks"]) == 2
    assert all("taskId" in t and "state" in t for t in result["tasks"])


@pytest.mark.asyncio
async def test_download_status_returns_task_dict(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    status = await engine._download_status({"taskId": enq["taskId"]})
    assert status["taskId"] == enq["taskId"]
    assert status["url"] == "https://example.com/a"
    assert status["state"] == "queued"


@pytest.mark.asyncio
async def test_download_status_raises_for_unknown_task(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with pytest.raises(RpcError):
        await engine._download_status({"taskId": "nope"})


@pytest.mark.asyncio
async def test_download_cancel_marks_task_cancelled(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    result = await engine._download_cancel({"taskId": enq["taskId"]})
    assert result["cancelled"] is True


@pytest.mark.asyncio
async def test_download_cancel_returns_false_for_terminal_task(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    await engine._download_cancel({"taskId": enq["taskId"]})
    result = await engine._download_cancel({"taskId": enq["taskId"]})
    assert result["cancelled"] is False


# ---- download.pause / resume / retry / clear (Phase 3) ----


@pytest.mark.asyncio
async def test_download_pause_queued_task(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    result = await engine._download_pause({"taskId": enq["taskId"]})
    assert result["paused"] is True


@pytest.mark.asyncio
async def test_download_resume_paused_task(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    await engine._download_pause({"taskId": enq["taskId"]})
    result = await engine._download_resume({"taskId": enq["taskId"]})
    assert result["resumed"] is True
    status = await engine._download_status({"taskId": enq["taskId"]})
    assert status["state"] == "queued"


@pytest.mark.asyncio
async def test_download_resume_non_paused_returns_false(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    result = await engine._download_resume({"taskId": enq["taskId"]})
    assert result["resumed"] is False


@pytest.mark.asyncio
async def test_download_retry_failed_task(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    # Manually fail the task so retry is testable.
    task = engine.manager.queue.get(enq["taskId"])
    task.mark_started()
    task.mark_failed("test error")
    result = await engine._download_retry({"taskId": enq["taskId"]})
    assert result["retried"] is True


@pytest.mark.asyncio
async def test_download_retry_non_failed_returns_false(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    result = await engine._download_retry({"taskId": enq["taskId"]})
    assert result["retried"] is False


@pytest.mark.asyncio
async def test_download_clear_removes_terminal_tasks(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    await engine._download_cancel({"taskId": enq["taskId"]})
    result = await engine._download_clear({})
    assert result["cleared"] == 1
    tasks = await engine._download_list({})
    assert len(tasks["tasks"]) == 0


@pytest.mark.asyncio
async def test_download_status_includes_retry_fields(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    enq = await engine._download_enqueue({"url": "https://example.com/a"})
    task = engine.manager.queue.get(enq["taskId"])
    task.mark_started()
    task.mark_failed("err")
    task.mark_retry_scheduled(2.0)
    status = await engine._download_status({"taskId": enq["taskId"]})
    assert status["retries"] == 1
    assert status["retryAfter"] is not None
    assert status["lastError"] == "err"


# ---------------------------------------------------------------------------
# Dispatcher integration: the new methods are reachable via JSON-RPC.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_routes_provider_detect(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    dispatcher: RpcDispatcher = engine.dispatcher
    request = JsonRpcRequest(
        jsonrpc="2.0",
        id=1,
        method="provider.detect",
        params={"url": "https://youtu.be/abc"},
    )
    response = await dispatcher.dispatch(request)
    assert response is not None
    assert response.error is None
    assert response.result["provider"] == "youtube"


@pytest.mark.asyncio
async def test_dispatcher_routes_download_enqueue(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    dispatcher = engine.dispatcher
    request = JsonRpcRequest(
        jsonrpc="2.0",
        id=2,
        method="download.enqueue",
        params={"url": "https://example.com/a"},
    )
    response = await dispatcher.dispatch(request)
    assert response is not None
    assert response.error is None
    assert "taskId" in response.result

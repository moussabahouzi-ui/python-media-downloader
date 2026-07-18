"""Tests for the Phase 4 engine method surface (library/favorites/collections/
history/file/storage)."""

from __future__ import annotations

import os

import pytest

from mediahub_engine.config import EngineConfig
from mediahub_engine.contracts import JsonRpcRequest
from mediahub_engine.engine import Engine


def _make_engine(tmp_path) -> Engine:
    return Engine(config=EngineConfig(work_dir=tmp_path / "work", persist_downloads=True))


def _add_media_item(engine: Engine, path: str, name: str = "item", category: str = "video") -> str:
    """Directly inserts a media item via the repository for test setup."""
    from mediahub_engine.storage.models import MediaCategory, MediaItem

    assert engine._media_repo is not None
    item = MediaItem(
        path=path,
        name=name,
        category=MediaCategory(category),
        size_bytes=100,
    )
    engine._media_repo.upsert(item)
    return item.item_id


# ---------------------------------------------------------------------------
# library.*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_library_list_returns_items(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    _add_media_item(engine, "/a.mp4", "a")
    _add_media_item(engine, "/b.mp3", "b", category="audio")
    result = await engine._library_list({})
    assert len(result["items"]) == 2


@pytest.mark.asyncio
async def test_library_list_filters_by_category(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    _add_media_item(engine, "/a.mp4", "a", category="video")
    _add_media_item(engine, "/b.mp3", "b", category="audio")
    result = await engine._library_list({"category": "video"})
    assert len(result["items"]) == 1
    assert result["items"][0]["category"] == "video"


@pytest.mark.asyncio
async def test_library_search(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    _add_media_item(engine, "/concert.mp4", "concert")
    _add_media_item(engine, "/podcast.mp3", "podcast", category="audio")
    result = await engine._library_search({"query": "concert"})
    assert len(result["items"]) == 1
    assert result["items"][0]["name"] == "concert"


@pytest.mark.asyncio
async def test_library_item(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    item_id = _add_media_item(engine, "/a.mp4", "a")
    result = await engine._library_item({"itemId": item_id})
    assert result["itemId"] == item_id


@pytest.mark.asyncio
async def test_library_item_not_found_raises(tmp_path) -> None:
    from mediahub_engine.ipc.jsonrpc import RpcError

    engine = _make_engine(tmp_path)
    with pytest.raises(RpcError):
        await engine._library_item({"itemId": "nope"})


@pytest.mark.asyncio
async def test_library_count(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    _add_media_item(engine, "/a.mp4", "a")
    _add_media_item(engine, "/b.mp4", "b")
    result = await engine._library_count({})
    assert result["count"] == 2


# ---------------------------------------------------------------------------
# favorites.*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_favorites_add_and_list(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    item_id = _add_media_item(engine, "/a.mp4", "a")
    _add_media_item(engine, "/b.mp4", "b")

    await engine._favorites_add({"itemId": item_id})
    result = await engine._favorites_list({})
    assert len(result["items"]) == 1
    assert result["items"][0]["itemId"] == item_id


@pytest.mark.asyncio
async def test_favorites_remove(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    item_id = _add_media_item(engine, "/a.mp4", "a")
    await engine._favorites_add({"itemId": item_id})
    await engine._favorites_remove({"itemId": item_id})
    result = await engine._favorites_list({})
    assert len(result["items"]) == 0


# ---------------------------------------------------------------------------
# collections.*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collections_create_and_list(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    created = await engine._collections_create({"name": "My Collection"})
    assert created["name"] == "My Collection"

    listed = await engine._collections_list({})
    assert len(listed["collections"]) == 1


@pytest.mark.asyncio
async def test_collections_rename_and_delete(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    created = await engine._collections_create({"name": "Old"})

    renamed = await engine._collections_rename(
        {"collectionId": created["collectionId"], "name": "New"}
    )
    assert renamed["renamed"] is True

    deleted = await engine._collections_delete({"collectionId": created["collectionId"]})
    assert deleted["deleted"] is True


@pytest.mark.asyncio
async def test_collections_add_remove_items(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    created = await engine._collections_create({"name": "C"})
    item_id = _add_media_item(engine, "/a.mp4", "a")

    added = await engine._collections_add_item(
        {"collectionId": created["collectionId"], "itemId": item_id}
    )
    assert added["added"] is True

    items = await engine._collections_items({"collectionId": created["collectionId"]})
    assert len(items["items"]) == 1

    removed = await engine._collections_remove_item(
        {"collectionId": created["collectionId"], "itemId": item_id}
    )
    assert removed["removed"] is True


# ---------------------------------------------------------------------------
# history.*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_stats_empty(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    stats = await engine._history_stats({})
    assert stats["totalDownloads"] == 0


@pytest.mark.asyncio
async def test_history_list_and_clear(tmp_path) -> None:
    from mediahub_engine.storage.models import HistoryEntry

    engine = _make_engine(tmp_path)
    assert engine._history_repo is not None
    engine._history_repo.record(
        HistoryEntry(task_id="t1", url="u", state="completed", bytes_done=100)
    )

    listed = await engine._history_list({})
    assert len(listed["entries"]) == 1

    cleared = await engine._history_clear({})
    assert cleared["cleared"] == 1


# ---------------------------------------------------------------------------
# file.*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_rename(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    src = str(tmp_path / "old.mp4")
    with open(src, "wb") as f:
        f.write(b"data")
    item_id = _add_media_item(engine, src, "old.mp4")

    result = await engine._file_rename({"itemId": item_id, "name": "new.mp4"})
    assert result["name"] == "new.mp4"
    assert os.path.exists(str(tmp_path / "new.mp4"))


@pytest.mark.asyncio
async def test_file_recycle_and_restore(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    src = str(tmp_path / "media" / "a.mp4")
    os.makedirs(os.path.dirname(src), exist_ok=True)
    with open(src, "wb") as f:
        f.write(b"data")
    item_id = _add_media_item(engine, src, "a.mp4")

    recycled = await engine._file_recycle({"itemId": item_id})
    assert recycled["recycled"] is True
    assert not os.path.exists(src)

    restored = await engine._file_restore({"itemId": item_id, "destDir": str(tmp_path / "back")})
    assert restored["restored"] is True
    assert os.path.exists(str(tmp_path / "back" / "a.mp4"))


@pytest.mark.asyncio
async def test_file_delete_permanent(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    src = str(tmp_path / "a.mp4")
    with open(src, "wb") as f:
        f.write(b"data")
    item_id = _add_media_item(engine, src, "a.mp4")

    result = await engine._file_delete({"itemId": item_id})
    assert result["deleted"] is True
    assert not os.path.exists(src)


# ---------------------------------------------------------------------------
# storage.*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_storage_analyze(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    _add_media_item(engine, "/a.mp4", "a", category="video")
    _add_media_item(engine, "/b.mp3", "b", category="audio")
    result = await engine._storage_analyze({})
    assert result["fileCount"] == 2
    assert "video" in result["byCategory"]
    assert "audio" in result["byCategory"]


@pytest.mark.asyncio
async def test_storage_duplicates(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    # Two identical files
    content = b"same"
    p1 = str(tmp_path / "a.mp4")
    p2 = str(tmp_path / "b.mp4")
    with open(p1, "wb") as f:
        f.write(content)
    with open(p2, "wb") as f:
        f.write(content)
    _add_media_item(engine, p1, "a")
    _add_media_item(engine, p2, "b")

    result = await engine._storage_duplicates({})
    assert len(result["groups"]) == 1
    assert len(result["groups"][0]["paths"]) == 2


# ---------------------------------------------------------------------------
# Persistence-disabled guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_library_methods_require_persistence(tmp_path) -> None:
    from mediahub_engine.ipc.jsonrpc import RpcError

    engine = Engine(config=EngineConfig(work_dir=tmp_path / "work", persist_downloads=False))
    with pytest.raises(RpcError):
        await engine._library_list({})


# ---------------------------------------------------------------------------
# Dispatcher integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_routes_library_list(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    _add_media_item(engine, "/a.mp4", "a")
    request = JsonRpcRequest(jsonrpc="2.0", id=1, method="library.list", params={})
    response = await engine.dispatcher.dispatch(request)
    assert response is not None
    assert response.error is None
    assert len(response.result["items"]) == 1

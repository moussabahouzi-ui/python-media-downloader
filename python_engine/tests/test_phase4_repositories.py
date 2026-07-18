"""Tests for the Phase 4 repositories: media, history, collections."""

from __future__ import annotations

import pytest

from mediahub_engine.database import (
    CollectionsRepository,
    Database,
    HistoryRepository,
    MediaRepository,
)
from mediahub_engine.storage.models import (
    Collection,
    HistoryEntry,
    MediaCategory,
    MediaItem,
)


@pytest.fixture
def repos(tmp_path: pytest.TempPathFactory):
    db = Database(tmp_path / "test.db")
    yield (
        MediaRepository(db),
        HistoryRepository(db),
        CollectionsRepository(db),
        db,
    )
    db.close()


# ---------------------------------------------------------------------------
# MediaRepository
# ---------------------------------------------------------------------------


def test_media_upsert_and_get(repos) -> None:
    media, _, _, _ = repos
    item = MediaItem(
        path="/media/video.mp4",
        name="video.mp4",
        category=MediaCategory.VIDEO,
        size_bytes=1024,
        provider="youtube",
        title="My Video",
        tags=["music", "live"],
    )
    media.upsert(item)

    fetched = media.get(item.item_id)
    assert fetched is not None
    assert fetched.path == "/media/video.mp4"
    assert fetched.category is MediaCategory.VIDEO
    assert fetched.title == "My Video"
    assert fetched.tags == ["music", "live"]
    assert fetched.favorite is False


def test_media_get_by_path(repos) -> None:
    media, _, _, _ = repos
    item = MediaItem(path="/media/a.mp3", name="a.mp3", category=MediaCategory.AUDIO)
    media.upsert(item)

    fetched = media.get_by_path("/media/a.mp3")
    assert fetched is not None
    assert fetched.item_id == item.item_id


def test_media_list_filters_by_category(repos) -> None:
    media, _, _, _ = repos
    media.upsert(MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO))
    media.upsert(MediaItem(path="/b.mp3", name="b.mp3", category=MediaCategory.AUDIO))
    media.upsert(MediaItem(path="/c.jpg", name="c.jpg", category=MediaCategory.IMAGE))

    videos = media.list(category="video")
    assert len(videos) == 1
    assert videos[0].category is MediaCategory.VIDEO


def test_media_list_excludes_recycled_by_default(repos) -> None:
    media, _, _, _ = repos
    item = MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO, recycled=True)
    media.upsert(item)

    assert len(media.list()) == 0
    assert len(media.list(include_recycled=True)) == 1


def test_media_search(repos) -> None:
    media, _, _, _ = repos
    media.upsert(
        MediaItem(
            path="/a.mp4", name="concert.mp4", category=MediaCategory.VIDEO, title="Live Concert"
        )
    )
    media.upsert(
        MediaItem(
            path="/b.mp3", name="podcast.mp3", category=MediaCategory.AUDIO, title="Tech Talk"
        )
    )
    media.upsert(MediaItem(path="/c.jpg", name="photo.jpg", category=MediaCategory.IMAGE))

    results = media.search("concert")
    assert len(results) == 1
    assert results[0].title == "Live Concert"

    results = media.search("podcast")
    assert len(results) == 1
    assert results[0].name == "podcast.mp3"


def test_media_set_favorite(repos) -> None:
    media, _, _, _ = repos
    item = MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO)
    media.upsert(item)

    assert media.set_favorite(item.item_id, True) is True
    assert media.get(item.item_id).favorite is True  # type: ignore[union-attr]

    assert media.set_favorite(item.item_id, False) is True
    assert media.get(item.item_id).favorite is False  # type: ignore[union-attr]


def test_media_set_recycled(repos) -> None:
    media, _, _, _ = repos
    item = MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO)
    media.upsert(item)

    assert media.set_recycled(item.item_id, True) is True
    assert media.get(item.item_id).recycled is True  # type: ignore[union-attr]


def test_media_update_path(repos) -> None:
    media, _, _, _ = repos
    item = MediaItem(path="/old/a.mp4", name="a.mp4", category=MediaCategory.VIDEO)
    media.upsert(item)

    assert media.update_path(item.item_id, "/new/renamed.mp4") is True
    fetched = media.get(item.item_id)
    assert fetched.path == "/new/renamed.mp4"  # type: ignore[union-attr]
    assert fetched.name == "renamed.mp4"  # type: ignore[union-attr]


def test_media_count(repos) -> None:
    media, _, _, _ = repos
    for i in range(5):
        media.upsert(MediaItem(path=f"/{i}.mp4", name=f"{i}.mp4", category=MediaCategory.VIDEO))
    media.upsert(
        MediaItem(path="/recycled.mp4", name="r.mp4", category=MediaCategory.VIDEO, recycled=True)
    )

    assert media.count() == 5  # excludes recycled
    assert media.count(include_recycled=True) == 6


def test_media_list_sorting(repos) -> None:
    media, _, _, _ = repos
    import time

    media.upsert(
        MediaItem(
            path="/c.mp4",
            name="c.mp4",
            category=MediaCategory.VIDEO,
            size_bytes=300,
            added_at=time.time() - 10,
        )
    )
    media.upsert(
        MediaItem(
            path="/a.mp4",
            name="a.mp4",
            category=MediaCategory.VIDEO,
            size_bytes=100,
            added_at=time.time() - 5,
        )
    )
    media.upsert(
        MediaItem(
            path="/b.mp4",
            name="b.mp4",
            category=MediaCategory.VIDEO,
            size_bytes=200,
            added_at=time.time(),
        )
    )

    by_size = media.list(sort_by="size_bytes", sort_desc=False)
    assert [i.size_bytes for i in by_size] == [100, 200, 300]

    by_name = media.list(sort_by="name", sort_desc=False)
    assert [i.name for i in by_name] == ["a.mp4", "b.mp4", "c.mp4"]


# ---------------------------------------------------------------------------
# HistoryRepository
# ---------------------------------------------------------------------------


def test_history_record_and_list(repos) -> None:
    _, history, _, _ = repos
    entry = HistoryEntry(
        task_id="t1",
        url="https://example.com/a",
        provider="youtube",
        engine="yt-dlp",
        state="completed",
        bytes_done=1024,
        output_paths=["/out/a.mp4"],
    )
    hid = history.record(entry)
    assert hid > 0

    entries = history.list()
    assert len(entries) == 1
    assert entries[0].task_id == "t1"
    assert entries[0].state == "completed"
    assert entries[0].bytes_done == 1024


def test_history_stats(repos) -> None:
    _, history, _, _ = repos
    for i in range(3):
        history.record(
            HistoryEntry(
                task_id=f"t{i}",
                url=f"https://e.com/{i}",
                provider="youtube",
                state="completed",
                bytes_done=1000,
            )
        )
    history.record(
        HistoryEntry(
            task_id="tf",
            url="https://e.com/f",
            provider="instagram",
            state="failed",
            bytes_done=0,
        )
    )

    stats = history.stats()
    assert stats.total_downloads == 4
    assert stats.completed == 3
    assert stats.failed == 1
    assert stats.total_bytes == 3000
    assert stats.by_provider["youtube"] == 3
    assert stats.by_provider["instagram"] == 1


def test_history_clear(repos) -> None:
    _, history, _, _ = repos
    history.record(HistoryEntry(task_id="t1", url="u", state="completed"))
    assert history.count() == 1

    removed = history.clear()
    assert removed == 1
    assert history.count() == 0


# ---------------------------------------------------------------------------
# CollectionsRepository
# ---------------------------------------------------------------------------


def test_collections_create_and_list(repos) -> None:
    _, _, collections, _ = repos
    c = Collection(name="My Favorites", description="Best videos")
    collections.create(c)

    listed = collections.list()
    assert len(listed) == 1
    assert listed[0].name == "My Favorites"
    assert listed[0].description == "Best videos"


def test_collections_rename(repos) -> None:
    _, _, collections, _ = repos
    c = Collection(name="Old")
    collections.create(c)

    assert collections.rename(c.collection_id, "New") is True
    fetched = collections.get(c.collection_id)
    assert fetched.name == "New"  # type: ignore[union-attr]


def test_collections_delete(repos) -> None:
    _, _, collections, _ = repos
    c = Collection(name="ToDelete")
    collections.create(c)

    assert collections.delete(c.collection_id) is True
    assert collections.get(c.collection_id) is None


def test_collections_add_and_remove_items(repos) -> None:
    media, _, collections, _ = repos
    c = Collection(name="Playlist")
    collections.create(c)

    item = MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO)
    media.upsert(item)

    assert collections.add_item(c.collection_id, item.item_id) is True
    fetched = collections.get(c.collection_id)
    assert fetched.item_count == 1  # type: ignore[union-attr]

    items = collections.items(c.collection_id)
    assert len(items) == 1
    assert items[0].item_id == item.item_id

    assert collections.remove_item(c.collection_id, item.item_id) is True
    fetched = collections.get(c.collection_id)
    assert fetched.item_count == 0  # type: ignore[union-attr]


def test_collections_add_duplicate_item_returns_false(repos) -> None:
    media, _, collections, _ = repos
    c = Collection(name="Dup")
    collections.create(c)
    item = MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO)
    media.upsert(item)

    assert collections.add_item(c.collection_id, item.item_id) is True
    assert collections.add_item(c.collection_id, item.item_id) is False  # PK conflict


# ---------------------------------------------------------------------------
# MediaCategory helper
# ---------------------------------------------------------------------------


def test_media_category_from_path() -> None:
    assert MediaCategory.from_path("/a/video.mp4") is MediaCategory.VIDEO
    assert MediaCategory.from_path("/b/song.flac") is MediaCategory.AUDIO
    assert MediaCategory.from_path("/c/pic.jpg") is MediaCategory.IMAGE
    assert MediaCategory.from_path("/d/file.xyz") is MediaCategory.OTHER

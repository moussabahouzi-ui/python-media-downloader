"""Tests for the Phase 5 PlaylistsRepository + engine methods."""

from __future__ import annotations

import pytest

from mediahub_engine.database import Database, MediaRepository, PlaylistsRepository
from mediahub_engine.storage.models import MediaCategory, MediaItem, Playlist, RepeatMode


@pytest.fixture
def repos(tmp_path: pytest.TempPathFactory):
    db = Database(tmp_path / "test.db")
    media = MediaRepository(db)
    playlists = PlaylistsRepository(db)
    yield media, playlists, db
    db.close()


def _add_media(media: MediaRepository, name: str, path: str | None = None) -> str:
    p = path or f"/media/{name}"
    item = MediaItem(path=p, name=name, category=MediaCategory.VIDEO)
    media.upsert(item)
    return item.item_id


# ---------------------------------------------------------------------------
# PlaylistsRepository
# ---------------------------------------------------------------------------


def test_create_and_get(repos) -> None:
    _, playlists, _ = repos
    pl = Playlist(name="My Playlist", description="Cool mixes")
    playlists.create(pl)

    fetched = playlists.get(pl.playlist_id)
    assert fetched is not None
    assert fetched.name == "My Playlist"
    assert fetched.description == "Cool mixes"
    assert fetched.repeat_mode is RepeatMode.OFF
    assert fetched.shuffle is False


def test_list_returns_all(repos) -> None:
    _, playlists, _ = repos
    playlists.create(Playlist(name="A"))
    playlists.create(Playlist(name="B"))

    listed = playlists.list()
    assert len(listed) == 2


def test_rename(repos) -> None:
    _, playlists, _ = repos
    pl = Playlist(name="Old")
    playlists.create(pl)
    assert playlists.rename(pl.playlist_id, "New") is True
    assert playlists.get(pl.playlist_id).name == "New"  # type: ignore[union-attr]


def test_delete(repos) -> None:
    _, playlists, _ = repos
    pl = Playlist(name="Del")
    playlists.create(pl)
    assert playlists.delete(pl.playlist_id) is True
    assert playlists.get(pl.playlist_id) is None


def test_set_shuffle(repos) -> None:
    _, playlists, _ = repos
    pl = Playlist(name="Shuffle")
    playlists.create(pl)
    assert playlists.set_shuffle(pl.playlist_id, True) is True
    assert playlists.get(pl.playlist_id).shuffle is True  # type: ignore[union-attr]


def test_set_repeat_mode(repos) -> None:
    _, playlists, _ = repos
    pl = Playlist(name="Repeat")
    playlists.create(pl)
    assert playlists.set_repeat_mode(pl.playlist_id, RepeatMode.ALL) is True
    assert playlists.get(pl.playlist_id).repeat_mode is RepeatMode.ALL  # type: ignore[union-attr]


# ---- item membership (ordered) ----


def test_add_item_appends(repos) -> None:
    media, playlists, _ = repos
    pl = Playlist(name="PL")
    playlists.create(pl)
    i1 = _add_media(media, "a.mp4")
    i2 = _add_media(media, "b.mp4")

    assert playlists.add_item(pl.playlist_id, i1) is True
    assert playlists.add_item(pl.playlist_id, i2) is True

    items = playlists.items(pl.playlist_id)
    assert [i.name for i in items] == ["a.mp4", "b.mp4"]
    fetched = playlists.get(pl.playlist_id)
    assert fetched.item_count == 2  # type: ignore[union-attr]


def test_add_item_at_position(repos) -> None:
    media, playlists, _ = repos
    pl = Playlist(name="PL")
    playlists.create(pl)
    i1 = _add_media(media, "a.mp4")
    i2 = _add_media(media, "b.mp4")
    i3 = _add_media(media, "c.mp4")

    playlists.add_item(pl.playlist_id, i1)  # pos 0
    playlists.add_item(pl.playlist_id, i2)  # pos 1
    playlists.add_item(pl.playlist_id, i3, position=1)  # insert at pos 1

    items = playlists.items(pl.playlist_id)
    assert [i.name for i in items] == ["a.mp4", "c.mp4", "b.mp4"]


def test_remove_item_reindexes(repos) -> None:
    media, playlists, _ = repos
    pl = Playlist(name="PL")
    playlists.create(pl)
    i1 = _add_media(media, "a.mp4")
    i2 = _add_media(media, "b.mp4")
    i3 = _add_media(media, "c.mp4")
    playlists.add_item(pl.playlist_id, i1)
    playlists.add_item(pl.playlist_id, i2)
    playlists.add_item(pl.playlist_id, i3)

    assert playlists.remove_item(pl.playlist_id, i2) is True

    items = playlists.items(pl.playlist_id)
    assert [i.name for i in items] == ["a.mp4", "c.mp4"]
    fetched = playlists.get(pl.playlist_id)
    assert fetched.item_count == 2  # type: ignore[union-attr]


def test_reorder_item(repos) -> None:
    media, playlists, _ = repos
    pl = Playlist(name="PL")
    playlists.create(pl)
    i1 = _add_media(media, "a.mp4")
    i2 = _add_media(media, "b.mp4")
    i3 = _add_media(media, "c.mp4")
    playlists.add_item(pl.playlist_id, i1)
    playlists.add_item(pl.playlist_id, i2)
    playlists.add_item(pl.playlist_id, i3)

    # Move c (pos 2) to pos 0
    assert playlists.reorder_item(pl.playlist_id, i3, 0) is True

    items = playlists.items(pl.playlist_id)
    assert [i.name for i in items] == ["c.mp4", "a.mp4", "b.mp4"]


def test_add_duplicate_item_returns_false(repos) -> None:
    media, playlists, _ = repos
    pl = Playlist(name="PL")
    playlists.create(pl)
    i1 = _add_media(media, "a.mp4")

    assert playlists.add_item(pl.playlist_id, i1) is True
    assert playlists.add_item(pl.playlist_id, i1) is False  # PK conflict


def test_items_excludes_recycled(repos) -> None:
    media, playlists, _ = repos
    pl = Playlist(name="PL")
    playlists.create(pl)
    i1 = _add_media(media, "a.mp4")
    playlists.add_item(pl.playlist_id, i1)

    # Recycle the item
    media.set_recycled(i1, True)
    items = playlists.items(pl.playlist_id)
    assert len(items) == 0  # recycled items hidden


# ---------------------------------------------------------------------------
# Engine methods (integration)
# ---------------------------------------------------------------------------


def _make_engine(tmp_path):
    from mediahub_engine.config import EngineConfig
    from mediahub_engine.engine import Engine

    return Engine(config=EngineConfig(work_dir=tmp_path / "work", persist_downloads=True))


@pytest.mark.asyncio
async def test_engine_playlists_create_and_list(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    created = await engine._playlists_create({"name": "My PL"})
    assert created["name"] == "My PL"

    listed = await engine._playlists_list({})
    assert len(listed["playlists"]) == 1


@pytest.mark.asyncio
async def test_engine_playlists_full_lifecycle(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    # Create a playlist
    pl = await engine._playlists_create({"name": "Mix"})
    pid = pl["playlistId"]

    # Add a media item directly via repo
    assert engine._media_repo is not None
    item = MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO)
    engine._media_repo.upsert(item)

    # Add to playlist
    added = await engine._playlists_add_item({"playlistId": pid, "itemId": item.item_id})
    assert added["added"] is True

    # List items
    result = await engine._playlists_items({"playlistId": pid})
    assert len(result["items"]) == 1

    # Remove item
    removed = await engine._playlists_remove_item({"playlistId": pid, "itemId": item.item_id})
    assert removed["removed"] is True

    # Delete playlist
    deleted = await engine._playlists_delete({"playlistId": pid})
    assert deleted["deleted"] is True


@pytest.mark.asyncio
async def test_engine_playlists_set_shuffle_and_repeat(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    pl = await engine._playlists_create({"name": "Settings"})
    pid = pl["playlistId"]

    shuffle_result = await engine._playlists_set_shuffle({"playlistId": pid, "shuffle": True})
    assert shuffle_result["shuffle"] is True

    repeat_result = await engine._playlists_set_repeat({"playlistId": pid, "repeatMode": "all"})
    assert repeat_result["repeatMode"] == "all"


@pytest.mark.asyncio
async def test_engine_playlists_set_repeat_invalid_mode_raises(tmp_path) -> None:
    from mediahub_engine.ipc.jsonrpc import RpcError

    engine = _make_engine(tmp_path)
    pl = await engine._playlists_create({"name": "Bad"})
    with pytest.raises(RpcError):
        await engine._playlists_set_repeat(
            {"playlistId": pl["playlistId"], "repeatMode": "nonsense"}
        )

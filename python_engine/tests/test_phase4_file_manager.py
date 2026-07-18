"""Tests for the Phase 4 file manager, storage analyzer, and duplicate finder."""

from __future__ import annotations

import os

import pytest

from mediahub_engine.database import Database, MediaRepository
from mediahub_engine.storage.analyzer import DuplicateFinder, StorageAnalyzer
from mediahub_engine.storage.file_manager import FileManager, FileManagerError
from mediahub_engine.storage.models import MediaCategory, MediaItem


@pytest.fixture
def file_manager(tmp_path: pytest.TempPathFactory):
    db = Database(tmp_path / "test.db")
    repo = MediaRepository(db)
    fm = FileManager(repo, recycle_dir=tmp_path / "recycle")
    yield repo, fm, tmp_path
    db.close()


def _make_file(path, content=b"hello") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# FileManager: rename / move / copy
# ---------------------------------------------------------------------------


def test_rename_updates_filesystem_and_index(file_manager) -> None:
    repo, fm, tmp = file_manager
    src = str(tmp / "media" / "old.mp4")
    _make_file(src)
    item = MediaItem(path=src, name="old.mp4", category=MediaCategory.VIDEO, size_bytes=5)
    repo.upsert(item)

    updated = fm.rename(item.item_id, "new.mp4")
    assert updated.name == "new.mp4"
    assert os.path.exists(str(tmp / "media" / "new.mp4"))
    assert not os.path.exists(src)
    assert repo.get(item.item_id).name == "new.mp4"  # type: ignore[union-attr]


def test_rename_rejects_invalid_name(file_manager) -> None:
    repo, fm, tmp = file_manager
    src = str(tmp / "a.mp4")
    _make_file(src)
    item = MediaItem(path=src, name="a.mp4", category=MediaCategory.VIDEO)
    repo.upsert(item)

    with pytest.raises(FileManagerError, match="Invalid name"):
        fm.rename(item.item_id, "with/slash.mp4")


def test_rename_conflict_raises(file_manager) -> None:
    repo, fm, tmp = file_manager
    _make_file(str(tmp / "a.mp4"))
    _make_file(str(tmp / "b.mp4"))
    item = MediaItem(path=str(tmp / "a.mp4"), name="a.mp4", category=MediaCategory.VIDEO)
    repo.upsert(item)

    with pytest.raises(FileManagerError, match="already exists"):
        fm.rename(item.item_id, "b.mp4")


def test_move_updates_filesystem_and_index(file_manager) -> None:
    repo, fm, tmp = file_manager
    src = str(tmp / "src" / "a.mp4")
    _make_file(src)
    item = MediaItem(path=src, name="a.mp4", category=MediaCategory.VIDEO)
    repo.upsert(item)

    dest_dir = str(tmp / "dest")
    updated = fm.move(item.item_id, dest_dir)
    assert os.path.exists(os.path.join(dest_dir, "a.mp4"))
    assert not os.path.exists(src)
    assert updated.path == os.path.join(dest_dir, "a.mp4")


def test_copy_creates_new_indexed_item(file_manager) -> None:
    repo, fm, tmp = file_manager
    src = str(tmp / "src" / "a.mp4")
    _make_file(src, b"content")
    item = MediaItem(path=src, name="a.mp4", category=MediaCategory.VIDEO, size_bytes=7)
    repo.upsert(item)

    dest_dir = str(tmp / "dest")
    copy = fm.copy(item.item_id, dest_dir)
    assert copy.item_id != item.item_id
    assert os.path.exists(os.path.join(dest_dir, "a.mp4"))
    assert os.path.exists(src)  # original untouched
    assert repo.get_by_path(os.path.join(dest_dir, "a.mp4")) is not None


# ---------------------------------------------------------------------------
# FileManager: recycle / restore / delete
# ---------------------------------------------------------------------------


def test_recycle_moves_to_recycle_bin_and_marks_recycled(file_manager) -> None:
    repo, fm, tmp = file_manager
    src = str(tmp / "media" / "a.mp4")
    _make_file(src)
    item = MediaItem(path=src, name="a.mp4", category=MediaCategory.VIDEO)
    repo.upsert(item)

    assert fm.recycle(item.item_id) is True
    assert not os.path.exists(src)
    fetched = repo.get(item.item_id)
    assert fetched.recycled is True  # type: ignore[union-attr]
    assert os.path.exists(fetched.path)  # type: ignore[union-attr]  # in recycle bin


def test_recycle_unknown_item_raises(file_manager) -> None:
    _, fm, _ = file_manager
    with pytest.raises(FileManagerError, match="Unknown item"):
        fm.recycle("nonexistent")


def test_restore_moves_back_and_clears_recycled_flag(file_manager) -> None:
    repo, fm, tmp = file_manager
    src = str(tmp / "media" / "a.mp4")
    _make_file(src)
    item = MediaItem(path=src, name="a.mp4", category=MediaCategory.VIDEO)
    repo.upsert(item)
    fm.recycle(item.item_id)

    dest_dir = str(tmp / "restored")
    assert fm.restore(item.item_id, dest_dir) is True
    fetched = repo.get(item.item_id)
    assert fetched.recycled is False  # type: ignore[union-attr]
    assert os.path.exists(fetched.path)  # type: ignore[union-attr]


def test_delete_permanent_removes_file_and_index(file_manager) -> None:
    repo, fm, tmp = file_manager
    src = str(tmp / "a.mp4")
    _make_file(src)
    item = MediaItem(path=src, name="a.mp4", category=MediaCategory.VIDEO)
    repo.upsert(item)

    assert fm.delete_permanent(item.item_id) is True
    assert not os.path.exists(src)
    assert repo.get(item.item_id) is None


def test_empty_recycle_bin_removes_all_recycled(file_manager) -> None:
    repo, fm, tmp = file_manager
    for i in range(3):
        src = str(tmp / f"media{i}.mp4")
        _make_file(src)
        item = MediaItem(path=src, name=f"{i}.mp4", category=MediaCategory.VIDEO)
        repo.upsert(item)
        fm.recycle(item.item_id)

    count = fm.empty_recycle_bin()
    assert count == 3
    assert repo.count(include_recycled=True) == 0


# ---------------------------------------------------------------------------
# StorageAnalyzer
# ---------------------------------------------------------------------------


def test_storage_analyzer_breaks_down_by_category(file_manager) -> None:
    repo, _, _ = file_manager
    repo.upsert(
        MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO, size_bytes=1000)
    )
    repo.upsert(
        MediaItem(path="/b.mp3", name="b.mp3", category=MediaCategory.AUDIO, size_bytes=500)
    )
    repo.upsert(
        MediaItem(path="/c.jpg", name="c.jpg", category=MediaCategory.IMAGE, size_bytes=200)
    )
    repo.upsert(MediaItem(path="/d.txt", name="d.txt", category=MediaCategory.OTHER, size_bytes=50))

    breakdown = StorageAnalyzer(repo).analyze()
    assert breakdown.total_bytes == 1750
    assert breakdown.by_category["video"] == 1000
    assert breakdown.by_category["audio"] == 500
    assert breakdown.by_category["image"] == 200
    assert breakdown.file_count == 4
    assert breakdown.file_count_by_category["video"] == 1


def test_storage_analyzer_excludes_recycled_by_default(file_manager) -> None:
    repo, _, _ = file_manager
    repo.upsert(
        MediaItem(path="/a.mp4", name="a.mp4", category=MediaCategory.VIDEO, size_bytes=1000)
    )
    repo.upsert(
        MediaItem(
            path="/b.mp4", name="b.mp4", category=MediaCategory.VIDEO, size_bytes=500, recycled=True
        )
    )

    breakdown = StorageAnalyzer(repo).analyze()
    assert breakdown.total_bytes == 1000
    assert breakdown.file_count == 1


# ---------------------------------------------------------------------------
# DuplicateFinder
# ---------------------------------------------------------------------------


def test_duplicate_finder_finds_identical_files(file_manager) -> None:
    repo, _, tmp = file_manager
    # Two identical files
    content = b"identical-content"
    p1 = str(tmp / "a.mp4")
    p2 = str(tmp / "b.mp4")
    _make_file(p1, content)
    _make_file(p2, content)
    repo.upsert(
        MediaItem(path=p1, name="a.mp4", category=MediaCategory.VIDEO, size_bytes=len(content))
    )
    repo.upsert(
        MediaItem(path=p2, name="b.mp4", category=MediaCategory.VIDEO, size_bytes=len(content))
    )

    groups = DuplicateFinder(repo).find()
    assert len(groups) == 1
    assert len(groups[0].paths) == 2
    assert groups[0].size_bytes == len(content)


def test_duplicate_finder_ignores_different_content(file_manager) -> None:
    repo, _, tmp = file_manager
    p1 = str(tmp / "a.mp4")
    p2 = str(tmp / "b.mp4")
    _make_file(p1, b"content-one")
    _make_file(p2, b"content-two")
    repo.upsert(MediaItem(path=p1, name="a.mp4", category=MediaCategory.VIDEO, size_bytes=12))
    repo.upsert(MediaItem(path=p2, name="b.mp4", category=MediaCategory.VIDEO, size_bytes=12))

    groups = DuplicateFinder(repo).find()
    assert len(groups) == 0  # same size, different hash


def test_duplicate_finder_returns_empty_for_single_item(file_manager) -> None:
    repo, _, tmp = file_manager
    p = str(tmp / "a.mp4")
    _make_file(p)
    repo.upsert(MediaItem(path=p, name="a.mp4", category=MediaCategory.VIDEO, size_bytes=5))

    groups = DuplicateFinder(repo).find()
    assert len(groups) == 0

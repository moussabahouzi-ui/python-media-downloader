"""File manager: rename, move, copy, delete, recycle bin.

All operations update both the filesystem and the [MediaRepository] so the
library index stays consistent. Soft-delete moves files to a recycle bin
directory and marks the item `recycled=1`; hard-delete removes the file and
the index row.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from mediahub_engine.storage.models import MediaItem
from mediahub_engine.utils.logging import get_logger

if TYPE_CHECKING:
    from mediahub_engine.database import MediaRepository

log = get_logger(__name__)


class FileManagerError(Exception):
    """Raised for file-manager failures (missing files, conflicts, etc.)."""

    def __init__(self, message: str, *, code: str = "FILE_ERROR") -> None:
        super().__init__(message)
        self.code = code


class FileManager:
    """Filesystem operations that keep the media index in sync."""

    def __init__(self, media_repo: MediaRepository, recycle_dir: Path) -> None:
        self._repo = media_repo
        self._recycle_dir = recycle_dir
        self._recycle_dir.mkdir(parents=True, exist_ok=True)

    @property
    def recycle_dir(self) -> Path:
        return self._recycle_dir

    # ---- rename / move / copy ----

    def rename(self, item_id: str, new_name: str) -> MediaItem:
        """Renames the file on disk and updates the index."""
        item = self._require_item(item_id)
        if not new_name or "/" in new_name or "\\" in new_name:
            raise FileManagerError("Invalid name", code="INVALID_NAME")

        old_path = Path(item.path)
        if not old_path.exists():
            raise FileManagerError(f"File not found: {old_path}", code="NOT_FOUND")

        new_path = old_path.parent / new_name
        if new_path.exists():
            raise FileManagerError(f"Name already exists: {new_path}", code="CONFLICT")

        old_path.rename(new_path)
        self._repo.update_path(item_id, str(new_path), new_name)
        log.info("renamed %s -> %s", old_path, new_path)
        return self._require_item(item_id)

    def move(self, item_id: str, dest_dir: str) -> MediaItem:
        """Moves the file to `dest_dir` (created if needed) and updates the index."""
        item = self._require_item(item_id)
        old_path = Path(item.path)
        if not old_path.exists():
            raise FileManagerError(f"File not found: {old_path}", code="NOT_FOUND")

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        new_path = dest / old_path.name
        if new_path.exists():
            raise FileManagerError(f"Destination exists: {new_path}", code="CONFLICT")

        shutil.move(str(old_path), str(new_path))
        self._repo.update_path(item_id, str(new_path))
        log.info("moved %s -> %s", old_path, new_path)
        return self._require_item(item_id)

    def copy(self, item_id: str, dest_dir: str) -> MediaItem:
        """Copies the file to `dest_dir` and indexes the copy as a new item."""
        import time
        import uuid

        item = self._require_item(item_id)
        src = Path(item.path)
        if not src.exists():
            raise FileManagerError(f"File not found: {src}", code="NOT_FOUND")

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        dest_path = dest / src.name
        if dest_path.exists():
            raise FileManagerError(f"Destination exists: {dest_path}", code="CONFLICT")

        shutil.copy2(str(src), str(dest_path))

        new_item = MediaItem(
            item_id=uuid.uuid4().hex,
            path=str(dest_path),
            name=dest_path.name,
            category=item.category,
            size_bytes=item.size_bytes,
            mime_type=item.mime_type,
            duration_ms=item.duration_ms,
            width=item.width,
            height=item.height,
            provider=item.provider,
            url=item.url,
            title=item.title,
            uploader=item.uploader,
            tags=list(item.tags),
            created_at=item.created_at,
            added_at=time.time(),
        )
        self._repo.upsert(new_item)
        log.info("copied %s -> %s", src, dest_path)
        return new_item

    # ---- delete / recycle ----

    def recycle(self, item_id: str) -> bool:
        """Soft-delete: moves the file to the recycle bin and marks recycled=1."""
        item = self._require_item(item_id)
        if item.recycled:
            return True

        src = Path(item.path)
        if not src.exists():
            raise FileManagerError(f"File not found: {src}", code="NOT_FOUND")

        # Avoid name collisions in the recycle bin.
        dest = self._recycle_dir / src.name
        if dest.exists():
            dest = self._recycle_dir / f"{src.stem}_{item.item_id[:8]}{src.suffix}"

        shutil.move(str(src), str(dest))
        self._repo.update_path(item_id, str(dest))
        self._repo.set_recycled(item_id, True)
        log.info("recycled %s -> %s", src, dest)
        return True

    def restore(self, item_id: str, dest_dir: str | None = None) -> bool:
        """Restores a recycled item, optionally to a specific directory."""
        item = self._require_item(item_id)
        if not item.recycled:
            return False

        src = Path(item.path)
        if not src.exists():
            raise FileManagerError(f"Recycled file missing: {src}", code="NOT_FOUND")

        if dest_dir:
            dest = Path(dest_dir)
            dest.mkdir(parents=True, exist_ok=True)
            dest_path = dest / src.name
        else:
            # Best-effort: restore to the parent of the recycle bin.
            dest_path = src.parent.parent / src.name

        if dest_path.exists():
            dest_path = dest_path.parent / f"{src.stem}_restored{src.suffix}"

        shutil.move(str(src), str(dest_path))
        self._repo.update_path(item_id, str(dest_path))
        self._repo.set_recycled(item_id, False)
        log.info("restored %s -> %s", src, dest_path)
        return True

    def delete_permanent(self, item_id: str) -> bool:
        """Hard-delete: removes the file from disk and the index row."""
        item = self._require_item(item_id)
        src = Path(item.path)
        if src.exists():
            src.unlink()
        self._repo.delete(item_id)
        log.info("permanently deleted %s", item_id)
        return True

    def empty_recycle_bin(self) -> int:
        """Permanently deletes all recycled items. Returns the count removed."""
        items = self._repo.list(include_recycled=True)
        count = 0
        for item in items:
            if item.recycled:
                src = Path(item.path)
                if src.exists():
                    src.unlink()
                self._repo.delete(item.item_id)
                count += 1
        log.info("emptied recycle bin: %d item(s)", count)
        return count

    # ---- helpers ----

    def _require_item(self, item_id: str) -> MediaItem:
        item = self._repo.get(item_id)
        if item is None:
            raise FileManagerError(f"Unknown item: {item_id}", code="NOT_FOUND")
        return item


__all__ = ["FileManager", "FileManagerError"]

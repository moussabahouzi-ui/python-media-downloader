"""Storage analyzer + duplicate finder (Phase 4)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from mediahub_engine.storage.models import DuplicateGroup, StorageBreakdown
from mediahub_engine.utils.logging import get_logger

if TYPE_CHECKING:
    from mediahub_engine.database import MediaRepository

log = get_logger(__name__)

_HASH_CHUNK_SIZE = 64 * 1024


class StorageAnalyzer:
    """Computes storage usage broken down by category."""

    def __init__(self, media_repo: MediaRepository) -> None:
        self._repo = media_repo

    def analyze(self, *, include_recycled: bool = False) -> StorageBreakdown:
        items = self._repo.list(include_recycled=include_recycled, limit=100_000)
        by_category: dict[str, int] = defaultdict(int)
        count_by_category: dict[str, int] = defaultdict(int)
        total = 0
        for item in items:
            cat = item.category.value
            by_category[cat] += item.size_bytes
            count_by_category[cat] += 1
            total += item.size_bytes
        return StorageBreakdown(
            total_bytes=total,
            by_category=dict(by_category),
            file_count=len(items),
            file_count_by_category=dict(count_by_category),
        )


class DuplicateFinder:
    """Finds probable duplicate files by size, then by content hash.

    Strategy:
      1. Group all (non-recycled) items by (size, name-stem) as a fast first pass.
      2. For each group with >1 file, compute the SHA-256 of each file.
      3. Sub-group by hash; groups with >1 file are true duplicates.
    """

    def __init__(self, media_repo: MediaRepository) -> None:
        self._repo = media_repo

    def find(self, *, max_files: int = 10_000) -> list[DuplicateGroup]:
        items = self._repo.list(include_recycled=False, limit=max_files)
        if len(items) < 2:
            return []

        # Pass 1: group by size. Same-size files are duplicate candidates.
        by_size: dict[int, list[Path]] = defaultdict(list)
        for item in items:
            if item.size_bytes > 0 and Path(item.path).exists():
                by_size[item.size_bytes].append(Path(item.path))

        groups: list[DuplicateGroup] = []
        for size, paths in by_size.items():
            if len(paths) < 2:
                continue
            # Pass 2: sub-group by content hash.
            by_hash: dict[str, list[Path]] = defaultdict(list)
            for p in paths:
                h = _hash_file(p)
                if h is not None:
                    by_hash[h].append(p)
            for h, dup_paths in by_hash.items():
                if len(dup_paths) > 1:
                    groups.append(
                        DuplicateGroup(
                            key=h[:16],
                            size_bytes=size,
                            paths=[str(p) for p in dup_paths],
                        )
                    )
        log.info("duplicate scan: found %d group(s)", len(groups))
        return groups


def _hash_file(path: Path) -> str | None:
    """Returns the SHA-256 hex digest of a file, or None on error."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(_HASH_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


__all__ = ["DuplicateFinder", "StorageAnalyzer"]

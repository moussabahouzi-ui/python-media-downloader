# Media Library & File Manager

This document describes the Phase 4 media library, file manager, history,
favorites, collections, storage analyzer, and duplicate finder.

> Authoritative for Phase 4. Mirrored in code at
> `python_engine/mediahub_engine/storage/` and `mediahub_engine/database/`.

## 1. Overview

Completed downloads are automatically indexed into a `media_items` table so the
library can be browsed, searched, filtered, favorited, organized into
collections, and managed (rename/move/copy/delete/recycle). An append-only
`download_history` table powers the History screen and statistics. A
`StorageAnalyzer` breaks down usage by category; a `DuplicateFinder` detects
duplicate files by content hash.

## 2. Data model

### media_items

| Column | Purpose |
|--------|---------|
| `item_id` (PK) | UUID |
| `path` (UNIQUE) | Filesystem path |
| `name` | Display name |
| `category` | `video` \| `audio` \| `image` \| `other` (inferred from extension) |
| `size_bytes` | File size |
| `duration_ms`, `width`, `height` | Media-specific (video/audio/image) |
| `provider`, `url`, `task_id` | Provenance from the originating download |
| `title`, `uploader`, `thumbnail_path`, `tags` | Metadata |
| `favorite` | 0/1 boolean |
| `recycled` | 0/1 — in recycle bin (hidden from default views) |
| `created_at`, `added_at` | Timestamps |

### download_history (append-only)

Records every terminal download state (completed/failed/cancelled) with bytes,
output paths, error, provider, and timestamps. Powers the History screen and
`history.stats`.

### collections + collection_items

User-defined groups of media items. `collection_items` is a join table with
composite PK `(collection_id, item_id)` and `ON DELETE CASCADE` FKs.

## 3. Auto-indexing on completion

When a download completes, the `DownloadManager._index_completed_task()` method:

1. Iterates `result.output_paths`.
2. Skips files that don't exist or are already indexed (resume / re-run).
3. Infers `MediaCategory` from the extension.
4. Creates a `MediaItem` with provenance (`provider`, `url`, `task_id`) and
   metadata (`title`, `uploader`, `tags` from the provider result).
5. Upserts into `media_items`.

This means the library is always populated automatically — no manual scan
needed.

## 4. File manager

`FileManager` (`storage/file_manager.py`) performs filesystem operations that
keep the media index in sync:

| Operation | Behavior |
|-----------|----------|
| `rename(itemId, name)` | Renames on disk + updates `path`/`name` in index |
| `move(itemId, destDir)` | `shutil.move` + updates index path |
| `copy(itemId, destDir)` | `shutil.copy2` + indexes the copy as a new item |
| `recycle(itemId)` | Moves to recycle bin dir + sets `recycled=1` |
| `restore(itemId, destDir?)` | Moves back from recycle bin + sets `recycled=0` |
| `delete_permanent(itemId)` | Unlinks file + deletes index row |
| `empty_recycle_bin()` | Permanently deletes all recycled items |

All operations raise `FileManagerError` on missing files, name conflicts, or
unknown items.

## 5. Favorites & collections

- **Favorites**: `set_favorite(itemId, bool)` toggles the `favorite` flag.
  `library.list(favorite_only=True)` returns only favorites.
- **Collections**: create/rename/delete collections; add/remove items. The
  `item_count` on each collection is maintained incrementally. `items(collection_id)`
  returns all non-recycled items in a collection via a JOIN.

## 6. Storage analyzer

`StorageAnalyzer.analyze()` aggregates `total_bytes`, `by_category`, `file_count`,
and `file_count_by_category` from the media index. Recycled items are excluded
by default.

## 7. Duplicate finder

`DuplicateFinder.find()` uses a two-pass strategy:

1. **Pass 1**: group all non-recycled items by `size_bytes`. Same-size files
   are duplicate candidates. (Fast — no I/O.)
2. **Pass 2**: for each candidate group, compute the SHA-256 of each file.
   Sub-group by hash; groups with >1 file are true duplicates.

Returns a list of `DuplicateGroup(key, size_bytes, paths)`.

## 8. Engine method surface (Phase 4)

### library.*

| Method | Params | Returns |
|--------|--------|---------|
| `library.list` | `category?, favoriteOnly?, includeRecycled?, limit, offset, sortBy, sortDesc` | `{items: [MediaItem]}` |
| `library.search` | `query, limit` | `{items: [MediaItem]}` |
| `library.item` | `itemId` | `MediaItem` |
| `library.count` | `includeRecycled?` | `{count: int}` |

### favorites.*

| Method | Params | Returns |
|--------|--------|---------|
| `favorites.add` | `itemId` | `{itemId, favorited}` |
| `favorites.remove` | `itemId` | `{itemId, unfavorited}` |
| `favorites.list` | `limit` | `{items: [MediaItem]}` |

### collections.*

| Method | Params | Returns |
|--------|--------|---------|
| `collections.create` | `name, description?, color?, icon?` | `Collection` |
| `collections.list` | `{}` | `{collections: [Collection]}` |
| `collections.rename` | `collectionId, name, description?` | `{renamed}` |
| `collections.delete` | `collectionId` | `{deleted}` |
| `collections.add_item` | `collectionId, itemId` | `{added}` |
| `collections.remove_item` | `collectionId, itemId` | `{removed}` |
| `collections.items` | `collectionId` | `{items: [MediaItem]}` |

### history.*

| Method | Params | Returns |
|--------|--------|---------|
| `history.list` | `limit, offset` | `{entries: [HistoryEntry]}` |
| `history.stats` | `{}` | `DownloadStats` |
| `history.clear` | `{}` | `{cleared: int}` |

### file.*

| Method | Params | Returns |
|--------|--------|---------|
| `file.rename` | `itemId, name` | `MediaItem` |
| `file.move` | `itemId, destDir` | `MediaItem` |
| `file.copy` | `itemId, destDir` | `MediaItem` (new) |
| `file.recycle` | `itemId` | `{recycled}` |
| `file.restore` | `itemId, destDir?` | `{restored}` |
| `file.delete` | `itemId` | `{deleted}` |
| `file.empty_recycle` | `{}` | `{emptied: int}` |

### storage.*

| Method | Params | Returns |
|--------|--------|---------|
| `storage.analyze` | `includeRecycled?` | `StorageBreakdown` |
| `storage.duplicates` | `maxFiles?` | `{groups: [DuplicateGroup]}` |

All Phase 4 methods require persistence to be enabled; they return an
`INTERNAL` error if `persist_downloads=False`.

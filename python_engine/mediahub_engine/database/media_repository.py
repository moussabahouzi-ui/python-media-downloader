"""Repository for [MediaItem] — the indexed media library.

Completed downloads are indexed into `media_items` so the library can be
browsed, searched, filtered, favorited, and organized into collections.
"""

from __future__ import annotations

from typing import Any

from mediahub_engine.database.connection import Database
from mediahub_engine.storage.models import (
    MediaCategory,
    MediaItem,
    dump_tags,
    parse_tags,
)
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class MediaRepository:
    """SQLite-backed [MediaItem] CRUD + queries."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert(self, item: MediaItem) -> None:
        self._db.execute(
            """
            INSERT INTO media_items (
                item_id, path, name, category, size_bytes, mime_type,
                duration_ms, width, height, provider, url, task_id,
                title, uploader, thumbnail_path, tags,
                favorite, recycled, created_at, added_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            ON CONFLICT(item_id) DO UPDATE SET
                path=excluded.path,
                name=excluded.name,
                category=excluded.category,
                size_bytes=excluded.size_bytes,
                mime_type=excluded.mime_type,
                duration_ms=excluded.duration_ms,
                width=excluded.width,
                height=excluded.height,
                provider=excluded.provider,
                url=excluded.url,
                task_id=excluded.task_id,
                title=excluded.title,
                uploader=excluded.uploader,
                thumbnail_path=excluded.thumbnail_path,
                tags=excluded.tags,
                favorite=excluded.favorite,
                recycled=excluded.recycled
            """,
            (
                item.item_id,
                item.path,
                item.name,
                item.category.value,
                item.size_bytes,
                item.mime_type,
                item.duration_ms,
                item.width,
                item.height,
                item.provider,
                item.url,
                item.task_id,
                item.title,
                item.uploader,
                item.thumbnail_path,
                dump_tags(item.tags),
                int(item.favorite),
                int(item.recycled),
                item.created_at,
                item.added_at,
            ),
        )

    def get(self, item_id: str) -> MediaItem | None:
        row = self._db.query_one("SELECT * FROM media_items WHERE item_id = ?", (item_id,))
        return _row_to_item(row) if row else None

    def get_by_path(self, path: str) -> MediaItem | None:
        row = self._db.query_one("SELECT * FROM media_items WHERE path = ?", (path,))
        return _row_to_item(row) if row else None

    def delete(self, item_id: str) -> None:
        self._db.execute("DELETE FROM media_items WHERE item_id = ?", (item_id,))

    def list(
        self,
        *,
        category: str | None = None,
        favorite_only: bool = False,
        include_recycled: bool = False,
        limit: int = 500,
        offset: int = 0,
        sort_by: str = "added_at",
        sort_desc: bool = True,
    ) -> list[MediaItem]:
        """Lists media items with optional filtering and sorting."""
        clauses: list[str] = []
        params: list[Any] = []

        if category is not None and category != "all":
            clauses.append("category = ?")
            params.append(category)
        if favorite_only:
            clauses.append("favorite = 1")
        if not include_recycled:
            clauses.append("recycled = 0")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        # Validate sort column to prevent SQL injection.
        valid_sorts = {"added_at", "name", "size_bytes", "created_at", "title"}
        sort_col = sort_by if sort_by in valid_sorts else "added_at"
        order = "DESC" if sort_desc else "ASC"

        sql = f"SELECT * FROM media_items {where} ORDER BY {sort_col} {order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._db.query_all(sql, tuple(params))
        return [_row_to_item(r) for r in rows]

    def search(self, query: str, *, limit: int = 100) -> list[MediaItem]:
        """Full-text search across name, title, uploader, and tags."""
        like = f"%{query}%"
        rows = self._db.query_all(
            """
            SELECT * FROM media_items
            WHERE recycled = 0 AND (
                name LIKE ? OR title LIKE ? OR uploader LIKE ? OR tags LIKE ?
            )
            ORDER BY added_at DESC LIMIT ?
            """,
            (like, like, like, like, limit),
        )
        return [_row_to_item(r) for r in rows]

    def set_favorite(self, item_id: str, favorite: bool) -> bool:
        cur = self._db.execute(
            "UPDATE media_items SET favorite = ? WHERE item_id = ?",
            (int(favorite), item_id),
        )
        return cur.rowcount > 0

    def set_recycled(self, item_id: str, recycled: bool) -> bool:
        cur = self._db.execute(
            "UPDATE media_items SET recycled = ? WHERE item_id = ?",
            (int(recycled), item_id),
        )
        return cur.rowcount > 0

    def update_path(self, item_id: str, new_path: str, new_name: str | None = None) -> bool:
        if new_name is None:
            new_name = new_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        cur = self._db.execute(
            "UPDATE media_items SET path = ?, name = ? WHERE item_id = ?",
            (new_path, new_name, item_id),
        )
        return cur.rowcount > 0

    def count(self, *, include_recycled: bool = False) -> int:
        where = "" if include_recycled else "WHERE recycled = 0"
        row = self._db.query_one(f"SELECT COUNT(*) AS c FROM media_items {where}")
        return row["c"] if row else 0


def _row_to_item(row) -> MediaItem:  # type: ignore[no-untyped-def]
    return MediaItem(
        item_id=row["item_id"],
        path=row["path"],
        name=row["name"],
        category=MediaCategory(row["category"]),
        size_bytes=row["size_bytes"],
        mime_type=row["mime_type"],
        duration_ms=row["duration_ms"],
        width=row["width"],
        height=row["height"],
        provider=row["provider"],
        url=row["url"],
        task_id=row["task_id"],
        title=row["title"],
        uploader=row["uploader"],
        thumbnail_path=row["thumbnail_path"],
        tags=parse_tags(row["tags"]),
        favorite=bool(row["favorite"]),
        recycled=bool(row["recycled"]),
        created_at=row["created_at"],
        added_at=row["added_at"],
    )


__all__ = ["MediaRepository"]

"""Repository for collections + collection-item membership (Phase 4)."""

from __future__ import annotations

import time

from mediahub_engine.database.connection import Database
from mediahub_engine.storage.models import Collection, MediaItem
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class CollectionsRepository:
    """User-defined collections of media items."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, collection: Collection) -> Collection:
        self._db.execute(
            """
            INSERT INTO collections (
                collection_id, name, description, color, icon,
                item_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collection.collection_id,
                collection.name,
                collection.description,
                collection.color,
                collection.icon,
                collection.item_count,
                collection.created_at,
                collection.updated_at,
            ),
        )
        return collection

    def get(self, collection_id: str) -> Collection | None:
        row = self._db.query_one(
            "SELECT * FROM collections WHERE collection_id = ?", (collection_id,)
        )
        return _row_to_collection(row) if row else None

    def list(self) -> list[Collection]:
        rows = self._db.query_all("SELECT * FROM collections ORDER BY updated_at DESC")
        return [_row_to_collection(r) for r in rows]

    def rename(self, collection_id: str, name: str, description: str | None = None) -> bool:
        if description is not None:
            cur = self._db.execute(
                "UPDATE collections SET name = ?, description = ?, updated_at = ? WHERE collection_id = ?",
                (name, description, time.time(), collection_id),
            )
        else:
            cur = self._db.execute(
                "UPDATE collections SET name = ?, updated_at = ? WHERE collection_id = ?",
                (name, time.time(), collection_id),
            )
        return cur.rowcount > 0

    def delete(self, collection_id: str) -> bool:
        cur = self._db.execute("DELETE FROM collections WHERE collection_id = ?", (collection_id,))
        return cur.rowcount > 0

    def add_item(self, collection_id: str, item_id: str) -> bool:
        try:
            self._db.execute(
                "INSERT INTO collection_items (collection_id, item_id, added_at) VALUES (?, ?, ?)",
                (collection_id, item_id, time.time()),
            )
        except Exception:
            return False
        self._db.execute(
            "UPDATE collections SET item_count = item_count + 1, updated_at = ? WHERE collection_id = ?",
            (time.time(), collection_id),
        )
        return True

    def remove_item(self, collection_id: str, item_id: str) -> bool:
        cur = self._db.execute(
            "DELETE FROM collection_items WHERE collection_id = ? AND item_id = ?",
            (collection_id, item_id),
        )
        if cur.rowcount > 0:
            self._db.execute(
                "UPDATE collections SET item_count = MAX(item_count - 1, 0), updated_at = ? WHERE collection_id = ?",
                (time.time(), collection_id),
            )
            return True
        return False

    def items(self, collection_id: str) -> list[MediaItem]:
        from mediahub_engine.database.media_repository import _row_to_item

        rows = self._db.query_all(
            """
            SELECT m.* FROM media_items m
            JOIN collection_items ci ON ci.item_id = m.item_id
            WHERE ci.collection_id = ? AND m.recycled = 0
            ORDER BY ci.added_at DESC
            """,
            (collection_id,),
        )
        return [_row_to_item(r) for r in rows]


def _row_to_collection(row) -> Collection:  # type: ignore[no-untyped-def]
    return Collection(
        collection_id=row["collection_id"],
        name=row["name"],
        description=row["description"],
        color=row["color"],
        icon=row["icon"],
        item_count=row["item_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


__all__ = ["CollectionsRepository"]

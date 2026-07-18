"""Repository for playlists + ordered playlist items (Phase 5).

Playlists are ordered playback queues. Unlike collections (unordered groups),
playlist items have a `position` column that defines playback order. The
repository maintains position gaps on insert/remove/reorder.
"""

from __future__ import annotations

import time

from mediahub_engine.database.connection import Database
from mediahub_engine.storage.models import MediaItem, Playlist, RepeatMode
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class PlaylistsRepository:
    """Ordered playlists of media items."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, playlist: Playlist) -> Playlist:
        self._db.execute(
            """
            INSERT INTO playlists (
                playlist_id, name, description, item_count,
                shuffle, repeat_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                playlist.playlist_id,
                playlist.name,
                playlist.description,
                playlist.item_count,
                int(playlist.shuffle),
                playlist.repeat_mode.value,
                playlist.created_at,
                playlist.updated_at,
            ),
        )
        return playlist

    def get(self, playlist_id: str) -> Playlist | None:
        row = self._db.query_one("SELECT * FROM playlists WHERE playlist_id = ?", (playlist_id,))
        return _row_to_playlist(row) if row else None

    def list(self) -> list[Playlist]:
        rows = self._db.query_all("SELECT * FROM playlists ORDER BY updated_at DESC")
        return [_row_to_playlist(r) for r in rows]

    def rename(self, playlist_id: str, name: str, description: str | None = None) -> bool:
        if description is not None:
            cur = self._db.execute(
                "UPDATE playlists SET name = ?, description = ?, updated_at = ? WHERE playlist_id = ?",
                (name, description, time.time(), playlist_id),
            )
        else:
            cur = self._db.execute(
                "UPDATE playlists SET name = ?, updated_at = ? WHERE playlist_id = ?",
                (name, time.time(), playlist_id),
            )
        return cur.rowcount > 0

    def set_shuffle(self, playlist_id: str, shuffle: bool) -> bool:
        cur = self._db.execute(
            "UPDATE playlists SET shuffle = ?, updated_at = ? WHERE playlist_id = ?",
            (int(shuffle), time.time(), playlist_id),
        )
        return cur.rowcount > 0

    def set_repeat_mode(self, playlist_id: str, mode: RepeatMode) -> bool:
        cur = self._db.execute(
            "UPDATE playlists SET repeat_mode = ?, updated_at = ? WHERE playlist_id = ?",
            (mode.value, time.time(), playlist_id),
        )
        return cur.rowcount > 0

    def delete(self, playlist_id: str) -> bool:
        cur = self._db.execute("DELETE FROM playlists WHERE playlist_id = ?", (playlist_id,))
        return cur.rowcount > 0

    # ---- item membership (ordered) ----

    def add_item(self, playlist_id: str, item_id: str, position: int | None = None) -> bool:
        """Adds an item at `position` (or appends to the end if None)."""
        try:
            if position is None:
                pos = self._next_position(playlist_id)
            else:
                self._shift_positions(playlist_id, position, delta=1)
                pos = position
            self._db.execute(
                "INSERT INTO playlist_items (playlist_id, item_id, position, added_at) VALUES (?, ?, ?, ?)",
                (playlist_id, item_id, pos, time.time()),
            )
        except Exception:
            return False
        self._db.execute(
            "UPDATE playlists SET item_count = item_count + 1, updated_at = ? WHERE playlist_id = ?",
            (time.time(), playlist_id),
        )
        return True

    def remove_item(self, playlist_id: str, item_id: str) -> bool:
        cur = self._db.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ? AND item_id = ?",
            (playlist_id, item_id),
        )
        if cur.rowcount > 0:
            self._reindex_positions(playlist_id)
            self._db.execute(
                "UPDATE playlists SET item_count = MAX(item_count - 1, 0), updated_at = ? WHERE playlist_id = ?",
                (time.time(), playlist_id),
            )
            return True
        return False

    def reorder_item(self, playlist_id: str, item_id: str, new_position: int) -> bool:
        """Moves an item to `new_position`, shifting others as needed."""
        existing = self._db.query_one(
            "SELECT position FROM playlist_items WHERE playlist_id = ? AND item_id = ?",
            (playlist_id, item_id),
        )
        if existing is None:
            return False
        old_position = existing["position"]

        # Remove the item, shift, then re-insert at the new position.
        self._db.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ? AND item_id = ?",
            (playlist_id, item_id),
        )
        if new_position > old_position:
            self._shift_range(playlist_id, old_position + 1, new_position, delta=-1)
        else:
            self._shift_range(playlist_id, new_position, old_position - 1, delta=1)
        self._db.execute(
            "INSERT INTO playlist_items (playlist_id, item_id, position, added_at) VALUES (?, ?, ?, ?)",
            (playlist_id, item_id, new_position, time.time()),
        )
        self._reindex_positions(playlist_id)
        return True

    def items(self, playlist_id: str) -> list[MediaItem]:
        """Returns the playlist's media items in playback order."""
        from mediahub_engine.database.media_repository import _row_to_item

        rows = self._db.query_all(
            """
            SELECT m.* FROM media_items m
            JOIN playlist_items pi ON pi.item_id = m.item_id
            WHERE pi.playlist_id = ? AND m.recycled = 0
            ORDER BY pi.position ASC
            """,
            (playlist_id,),
        )
        return [_row_to_item(r) for r in rows]

    # ---- position helpers ----

    def _next_position(self, playlist_id: str) -> int:
        row = self._db.query_one(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,),
        )
        return row["next_pos"] if row else 0

    def _shift_positions(self, playlist_id: str, from_pos: int, *, delta: int) -> None:
        self._db.execute(
            "UPDATE playlist_items SET position = position + ? WHERE playlist_id = ? AND position >= ?",
            (delta, playlist_id, from_pos),
        )

    def _shift_range(self, playlist_id: str, lo: int, hi: int, *, delta: int) -> None:
        self._db.execute(
            "UPDATE playlist_items SET position = position + ? WHERE playlist_id = ? AND position >= ? AND position <= ?",
            (delta, playlist_id, lo, hi),
        )

    def _reindex_positions(self, playlist_id: str) -> None:
        """Re-sequenced positions to 0, 1, 2, ... after a remove/reorder."""
        rows = self._db.query_all(
            "SELECT item_id FROM playlist_items WHERE playlist_id = ? ORDER BY position ASC",
            (playlist_id,),
        )
        for new_pos, row in enumerate(rows):
            self._db.execute(
                "UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND item_id = ?",
                (new_pos, playlist_id, row["item_id"]),
            )


def _row_to_playlist(row) -> Playlist:  # type: ignore[no-untyped-def]
    return Playlist(
        playlist_id=row["playlist_id"],
        name=row["name"],
        description=row["description"],
        item_count=row["item_count"],
        shuffle=bool(row["shuffle"]),
        repeat_mode=RepeatMode(row["repeat_mode"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


__all__ = ["PlaylistsRepository"]

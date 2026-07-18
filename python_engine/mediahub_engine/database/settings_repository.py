"""Key-value app settings store (Phase 6).

A simple `app_settings` table with `key`/`value`/`updated_at` columns. Values
are stored as JSON-encoded strings so any type can be persisted. The
[SettingsRepository] provides typed getters/setters for the known keys.
"""

from __future__ import annotations

import json
import time
from typing import Any

from mediahub_engine.database.connection import Database
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


#: Known setting keys with defaults.
DEFAULT_SETTINGS: dict[str, Any] = {
    "download.defaultDestDir": "",
    "download.maxConcurrent": 4,
    "download.maxRetries": 3,
    "download.retryBaseDelay": 1.0,
    "download.retryMaxDelay": 60.0,
    "download.progressInterval": 0.25,
    "appearance.themeMode": "system",  # system | light | dark | amoled
    "appearance.useDynamicColor": True,
    "appearance.language": "en",
    "security.encryptStorage": True,
    "security.autoLock": False,
    "playback.defaultSpeed": 1.0,
    "playback.skipSilence": False,
    "notifications.downloadProgress": True,
    "notifications.downloadComplete": True,
    "scheduler.checkInterval": 300,  # seconds
}


class SettingsRepository:
    """SQLite-backed key-value settings store."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str, default: Any = None) -> Any:
        row = self._db.query_one("SELECT value FROM app_settings WHERE key = ?", (key,))
        if row is None:
            return DEFAULT_SETTINGS.get(key, default)
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return default

    def get_all(self) -> dict[str, Any]:
        """Returns all settings, merged with defaults."""
        rows = self._db.query_all("SELECT key, value FROM app_settings")
        stored: dict[str, Any] = {}
        for row in rows:
            try:
                stored[row["key"]] = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                continue
        # Merge: defaults first, stored overrides.
        merged = dict(DEFAULT_SETTINGS)
        merged.update(stored)
        return merged

    def set(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, default=str)
        self._db.execute(
            """
            INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, encoded, time.time()),
        )

    def set_many(self, items: dict[str, Any]) -> None:
        for key, value in items.items():
            self.set(key, value)

    def delete(self, key: str) -> bool:
        cur = self._db.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        return cur.rowcount > 0

    def reset(self) -> None:
        """Removes all stored settings (revert to defaults)."""
        self._db.execute("DELETE FROM app_settings")


__all__ = ["DEFAULT_SETTINGS", "SettingsRepository"]

"""SQLite persistence for the MediaHub engine.

Phase 3: download task persistence.
Phase 4: media items, history, favorites, collections.
Phase 5: playlists.
Phase 6: settings, scheduler, credentials.
"""

from mediahub_engine.database.collections_repository import CollectionsRepository
from mediahub_engine.database.connection import Database
from mediahub_engine.database.credentials_repository import CredentialsRepository
from mediahub_engine.database.history_repository import HistoryRepository
from mediahub_engine.database.media_repository import MediaRepository
from mediahub_engine.database.playlists_repository import PlaylistsRepository
from mediahub_engine.database.scheduler_repository import SchedulerRepository
from mediahub_engine.database.settings_repository import SettingsRepository
from mediahub_engine.database.task_repository import TaskRepository

__all__ = [
    "CollectionsRepository",
    "CredentialsRepository",
    "Database",
    "HistoryRepository",
    "MediaRepository",
    "PlaylistsRepository",
    "SchedulerRepository",
    "SettingsRepository",
    "TaskRepository",
]

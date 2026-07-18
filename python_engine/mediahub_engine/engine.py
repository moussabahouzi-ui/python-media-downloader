"""The MediaHub engine: owns the asyncio loop, IPC dispatch, and providers.

The engine is the single entry point invoked by the Android host as
``python -m mediahub_engine``. It:

1. configures structured logging (stderr),
2. builds an [EngineConfig] from the environment,
3. constructs a [DownloadManager] and a [RpcDispatcher],
4. registers method handlers (engine.*, provider.*, download.*),
5. runs the read/dispatch loop on stdin/stdout.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from mediahub_engine import __version__
from mediahub_engine.config import EngineConfig
from mediahub_engine.contracts import EngineError
from mediahub_engine.database import (
    CollectionsRepository,
    CredentialsRepository,
    Database,
    HistoryRepository,
    MediaRepository,
    PlaylistsRepository,
    SchedulerRepository,
    SettingsRepository,
    TaskRepository,
)
from mediahub_engine.download.manager import DownloadManager
from mediahub_engine.download.retry import RetryPolicy
from mediahub_engine.download.task import DownloadTask, TaskPriority
from mediahub_engine.ipc.jsonrpc import RpcDispatcher, RpcError, read_messages, write_message
from mediahub_engine.providers.base import Credential, ProviderError
from mediahub_engine.providers.registry import get_registry
from mediahub_engine.storage import (
    Collection,
    FileManager,
    Playlist,
    RepeatMode,
)
from mediahub_engine.storage.analyzer import DuplicateFinder, StorageAnalyzer
from mediahub_engine.utils.logging import configure_logging, get_logger

log = get_logger(__name__)

#: Bridge version — mirrors the Dart and Kotlin constants.
BRIDGE_VERSION = 1


class Engine:
    """Top-level orchestrator."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        configure_logging()
        self.config = config or EngineConfig.from_env()
        self.dispatcher = RpcDispatcher()

        # Persistence (optional; disabled in tests via config).
        self._db: Database | None = None
        self._repo: TaskRepository | None = None
        self._media_repo: MediaRepository | None = None
        self._history_repo: HistoryRepository | None = None
        self._collections_repo: CollectionsRepository | None = None
        self._playlists_repo: PlaylistsRepository | None = None
        self._settings_repo: SettingsRepository | None = None
        self._scheduler_repo: SchedulerRepository | None = None
        self._credentials_repo: CredentialsRepository | None = None
        self._file_manager: FileManager | None = None
        self._storage_analyzer: StorageAnalyzer | None = None
        self._duplicate_finder: DuplicateFinder | None = None
        if self.config.persist_downloads:
            self._db = Database(self.config.db_path)
            self._repo = TaskRepository(self._db)
            self._media_repo = MediaRepository(self._db)
            self._history_repo = HistoryRepository(self._db)
            self._collections_repo = CollectionsRepository(self._db)
            self._playlists_repo = PlaylistsRepository(self._db)
            self._settings_repo = SettingsRepository(self._db)
            self._scheduler_repo = SchedulerRepository(self._db)
            self._credentials_repo = CredentialsRepository(self._db)
            self._file_manager = FileManager(
                self._media_repo,
                recycle_dir=self.config.work_dir / "recycle",
            )
            self._storage_analyzer = StorageAnalyzer(self._media_repo)
            self._duplicate_finder = DuplicateFinder(self._media_repo)

        retry_policy = RetryPolicy(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_base_delay,
            max_delay=self.config.retry_max_delay,
        )
        self.manager = DownloadManager(
            self.config,
            self.dispatcher,
            retry_policy=retry_policy,
            repository=self._repo,
            history_repository=self._history_repo,
            media_repository=self._media_repo,
        )
        self._stop = asyncio.Event()
        self._register_handlers()

    def _register_handlers(self) -> None:
        d = self.dispatcher
        # engine.*
        d.register("engine.ping", self._ping)
        d.register("engine.version", self._version)
        d.register("engine.shutdown", self._shutdown)
        # provider.*
        d.register("provider.detect", self._provider_detect)
        d.register("provider.metadata", self._provider_metadata)
        d.register("provider.list", self._provider_list)
        # download.*
        d.register("download.enqueue", self._download_enqueue)
        d.register("download.pause", self._download_pause)
        d.register("download.resume", self._download_resume)
        d.register("download.retry", self._download_retry)
        d.register("download.cancel", self._download_cancel)
        d.register("download.list", self._download_list)
        d.register("download.status", self._download_status)
        d.register("download.clear", self._download_clear)
        # library.* (Phase 4)
        d.register("library.list", self._library_list)
        d.register("library.search", self._library_search)
        d.register("library.item", self._library_item)
        d.register("library.count", self._library_count)
        # favorites.* (Phase 4)
        d.register("favorites.add", self._favorites_add)
        d.register("favorites.remove", self._favorites_remove)
        d.register("favorites.list", self._favorites_list)
        # collections.* (Phase 4)
        d.register("collections.create", self._collections_create)
        d.register("collections.list", self._collections_list)
        d.register("collections.rename", self._collections_rename)
        d.register("collections.delete", self._collections_delete)
        d.register("collections.add_item", self._collections_add_item)
        d.register("collections.remove_item", self._collections_remove_item)
        d.register("collections.items", self._collections_items)
        # history.* (Phase 4)
        d.register("history.list", self._history_list)
        d.register("history.stats", self._history_stats)
        d.register("history.clear", self._history_clear)
        # file.* (Phase 4)
        d.register("file.rename", self._file_rename)
        d.register("file.move", self._file_move)
        d.register("file.copy", self._file_copy)
        d.register("file.recycle", self._file_recycle)
        d.register("file.restore", self._file_restore)
        d.register("file.delete", self._file_delete)
        d.register("file.empty_recycle", self._file_empty_recycle)
        # storage.* (Phase 4)
        d.register("storage.analyze", self._storage_analyze)
        d.register("storage.duplicates", self._storage_duplicates)
        # playlists.* (Phase 5)
        d.register("playlists.create", self._playlists_create)
        d.register("playlists.list", self._playlists_list)
        d.register("playlists.rename", self._playlists_rename)
        d.register("playlists.delete", self._playlists_delete)
        d.register("playlists.add_item", self._playlists_add_item)
        d.register("playlists.remove_item", self._playlists_remove_item)
        d.register("playlists.reorder", self._playlists_reorder)
        d.register("playlists.items", self._playlists_items)
        d.register("playlists.set_shuffle", self._playlists_set_shuffle)
        d.register("playlists.set_repeat", self._playlists_set_repeat)
        # settings.* (Phase 6)
        d.register("settings.get", self._settings_get)
        d.register("settings.get_all", self._settings_get_all)
        d.register("settings.set", self._settings_set)
        d.register("settings.set_many", self._settings_set_many)
        d.register("settings.delete", self._settings_delete)
        d.register("settings.reset", self._settings_reset)
        # scheduler.* (Phase 6)
        d.register("scheduler.create", self._scheduler_create)
        d.register("scheduler.list", self._scheduler_list)
        d.register("scheduler.get", self._scheduler_get)
        d.register("scheduler.update", self._scheduler_update)
        d.register("scheduler.set_enabled", self._scheduler_set_enabled)
        d.register("scheduler.delete", self._scheduler_delete)
        d.register("scheduler.due", self._scheduler_due)
        d.register("scheduler.mark_run", self._scheduler_mark_run)
        # credentials.* (Phase 6)
        d.register("credentials.set", self._credentials_set)
        d.register("credentials.get", self._credentials_get)
        d.register("credentials.list", self._credentials_list)
        d.register("credentials.delete", self._credentials_delete)
        d.register("credentials.has", self._credentials_has)

    # ---- engine.* ----

    async def _ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"pong": True, "version": __version__}

    async def _version(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "app": __version__,
            "engine": __version__,
            "bridgeVersion": BRIDGE_VERSION,
        }

    async def _shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        log.info("shutdown requested")
        self._stop.set()
        return {"stopped": True}

    # ---- provider.* ----

    async def _provider_detect(self, params: dict[str, Any]) -> dict[str, Any]:
        url = _require_str(params, "url")
        registry = get_registry()
        provider = registry.find(url)
        if provider is None:
            raise RpcError(
                EngineError.PROVIDER_NOT_FOUND,
                "No provider supports this URL",
                {"url": url},
            )
        c = provider.capability
        return {
            "provider": c.name,
            "displayName": c.display_name or c.name.title(),
            "engine": c.engine,
            "authRequired": c.auth_required,
            "maxBatch": c.max_batch,
        }

    async def _provider_metadata(self, params: dict[str, Any]) -> dict[str, Any]:
        url = _require_str(params, "url")
        registry = get_registry()
        try:
            provider = registry.require(url)
        except ProviderError as exc:
            raise RpcError(EngineError.PROVIDER_NOT_FOUND, str(exc), exc.details) from exc
        metadata = await provider.extract_metadata(url)
        return {
            "title": metadata.title,
            "uploader": metadata.uploader,
            "durationSeconds": metadata.duration_seconds,
            "thumbnailUrl": metadata.thumbnail_url,
            "categories": list(metadata.categories),
            "tags": list(metadata.tags),
            "extra": metadata.extra,
            "provider": provider.capability.name,
            "engine": provider.capability.engine,
        }

    async def _provider_list(self, params: dict[str, Any]) -> dict[str, Any]:
        registry = get_registry()
        return {"providers": registry.describe()}

    # ---- download.* ----

    async def _download_enqueue(self, params: dict[str, Any]) -> dict[str, Any]:
        url = _require_str(params, "url")
        options: dict[str, Any] = params.get("options") or {}
        priority_raw = params.get("priority")
        try:
            priority = (
                TaskPriority(int(priority_raw)) if priority_raw is not None else TaskPriority.NORMAL
            )
        except (ValueError, TypeError) as exc:
            raise RpcError(EngineError.INVALID_PARAMS, "Invalid priority") from exc
        task = DownloadTask(
            url=url,
            priority=priority,
            dest_dir=params.get("destDir") or "",
            options=options,
        )
        await self.manager.enqueue(task)
        return {"taskId": task.task_id, "state": task.state.value}

    async def _download_pause(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = _require_str(params, "taskId")
        paused = await self.manager.pause(task_id)
        return {"taskId": task_id, "paused": paused}

    async def _download_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = _require_str(params, "taskId")
        resumed = await self.manager.resume(task_id)
        return {"taskId": task_id, "resumed": resumed}

    async def _download_retry(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = _require_str(params, "taskId")
        retried = await self.manager.retry(task_id)
        return {"taskId": task_id, "retried": retried}

    async def _download_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = _require_str(params, "taskId")
        try:
            cancelled = await self.manager.cancel(task_id)
        except RpcError:
            raise
        return {"taskId": task_id, "cancelled": cancelled}

    async def _download_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tasks": self.manager.list_tasks()}

    async def _download_status(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = _require_str(params, "taskId")
        try:
            return self.manager.status(task_id)
        except RpcError:
            raise

    async def _download_clear(self, params: dict[str, Any]) -> dict[str, Any]:
        removed = self.manager.clear_terminal()
        return {"cleared": removed}

    # ---- library.* (Phase 4) ----

    async def _library_list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._media_repo is not None
        items = self._media_repo.list(
            category=params.get("category"),
            favorite_only=bool(params.get("favoriteOnly", False)),
            include_recycled=bool(params.get("includeRecycled", False)),
            limit=int(params.get("limit", 500)),
            offset=int(params.get("offset", 0)),
            sort_by=str(params.get("sortBy", "added_at")),
            sort_desc=bool(params.get("sortDesc", True)),
        )
        return {"items": [i.to_dict() for i in items]}

    async def _library_search(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._media_repo is not None
        query = _require_str(params, "query")
        items = self._media_repo.search(query, limit=int(params.get("limit", 100)))
        return {"items": [i.to_dict() for i in items]}

    async def _library_item(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._media_repo is not None
        item_id = _require_str(params, "itemId")
        item = self._media_repo.get(item_id)
        if item is None:
            raise RpcError(-2, "Item not found", {"itemId": item_id})
        return item.to_dict()

    async def _library_count(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._media_repo is not None
        return {
            "count": self._media_repo.count(
                include_recycled=bool(params.get("includeRecycled", False))
            )
        }

    # ---- favorites.* (Phase 4) ----

    async def _favorites_add(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._media_repo is not None
        item_id = _require_str(params, "itemId")
        ok = self._media_repo.set_favorite(item_id, True)
        return {"itemId": item_id, "favorited": ok}

    async def _favorites_remove(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._media_repo is not None
        item_id = _require_str(params, "itemId")
        ok = self._media_repo.set_favorite(item_id, False)
        return {"itemId": item_id, "unfavorited": ok}

    async def _favorites_list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._media_repo is not None
        items = self._media_repo.list(favorite_only=True, limit=int(params.get("limit", 500)))
        return {"items": [i.to_dict() for i in items]}

    # ---- collections.* (Phase 4) ----

    async def _collections_create(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._collections_repo is not None
        name = _require_str(params, "name")
        collection = Collection(
            name=name,
            description=str(params.get("description", "")),
            color=params.get("color"),
            icon=params.get("icon"),
        )
        self._collections_repo.create(collection)
        return collection.to_dict()

    async def _collections_list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._collections_repo is not None
        collections = self._collections_repo.list()
        return {"collections": [c.to_dict() for c in collections]}

    async def _collections_rename(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._collections_repo is not None
        collection_id = _require_str(params, "collectionId")
        name = _require_str(params, "name")
        ok = self._collections_repo.rename(collection_id, name, params.get("description"))
        return {"collectionId": collection_id, "renamed": ok}

    async def _collections_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._collections_repo is not None
        collection_id = _require_str(params, "collectionId")
        ok = self._collections_repo.delete(collection_id)
        return {"collectionId": collection_id, "deleted": ok}

    async def _collections_add_item(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._collections_repo is not None
        collection_id = _require_str(params, "collectionId")
        item_id = _require_str(params, "itemId")
        ok = self._collections_repo.add_item(collection_id, item_id)
        return {"collectionId": collection_id, "itemId": item_id, "added": ok}

    async def _collections_remove_item(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._collections_repo is not None
        collection_id = _require_str(params, "collectionId")
        item_id = _require_str(params, "itemId")
        ok = self._collections_repo.remove_item(collection_id, item_id)
        return {"collectionId": collection_id, "itemId": item_id, "removed": ok}

    async def _collections_items(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._collections_repo is not None
        collection_id = _require_str(params, "collectionId")
        items = self._collections_repo.items(collection_id)
        return {"items": [i.to_dict() for i in items]}

    # ---- history.* (Phase 4) ----

    async def _history_list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._history_repo is not None
        entries = self._history_repo.list(
            limit=int(params.get("limit", 100)),
            offset=int(params.get("offset", 0)),
        )
        return {"entries": [e.to_dict() for e in entries]}

    async def _history_stats(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._history_repo is not None
        return self._history_repo.stats().to_dict()

    async def _history_clear(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._history_repo is not None
        removed = self._history_repo.clear()
        return {"cleared": removed}

    # ---- file.* (Phase 4) ----

    async def _file_rename(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._file_manager is not None
        item = self._file_manager.rename(
            _require_str(params, "itemId"), _require_str(params, "name")
        )
        return item.to_dict()

    async def _file_move(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._file_manager is not None
        item = self._file_manager.move(
            _require_str(params, "itemId"), _require_str(params, "destDir")
        )
        return item.to_dict()

    async def _file_copy(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._file_manager is not None
        item = self._file_manager.copy(
            _require_str(params, "itemId"), _require_str(params, "destDir")
        )
        return item.to_dict()

    async def _file_recycle(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._file_manager is not None
        ok = self._file_manager.recycle(_require_str(params, "itemId"))
        return {"itemId": params["itemId"], "recycled": ok}

    async def _file_restore(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._file_manager is not None
        ok = self._file_manager.restore(_require_str(params, "itemId"), params.get("destDir"))
        return {"itemId": params["itemId"], "restored": ok}

    async def _file_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._file_manager is not None
        ok = self._file_manager.delete_permanent(_require_str(params, "itemId"))
        return {"itemId": params["itemId"], "deleted": ok}

    async def _file_empty_recycle(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._file_manager is not None
        count = self._file_manager.empty_recycle_bin()
        return {"emptied": count}

    # ---- storage.* (Phase 4) ----

    async def _storage_analyze(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._storage_analyzer is not None
        return self._storage_analyzer.analyze(
            include_recycled=bool(params.get("includeRecycled", False))
        ).to_dict()

    async def _storage_duplicates(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._duplicate_finder is not None
        groups = self._duplicate_finder.find(max_files=int(params.get("maxFiles", 10_000)))
        return {"groups": [g.to_dict() for g in groups]}

    # ---- playlists.* (Phase 5) ----

    async def _playlists_create(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        name = _require_str(params, "name")
        playlist = Playlist(
            name=name,
            description=str(params.get("description", "")),
        )
        self._playlists_repo.create(playlist)
        return playlist.to_dict()

    async def _playlists_list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlists = self._playlists_repo.list()
        return {"playlists": [p.to_dict() for p in playlists]}

    async def _playlists_rename(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        name = _require_str(params, "name")
        ok = self._playlists_repo.rename(playlist_id, name, params.get("description"))
        return {"playlistId": playlist_id, "renamed": ok}

    async def _playlists_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        ok = self._playlists_repo.delete(playlist_id)
        return {"playlistId": playlist_id, "deleted": ok}

    async def _playlists_add_item(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        item_id = _require_str(params, "itemId")
        position = params.get("position")
        ok = self._playlists_repo.add_item(
            playlist_id, item_id, int(position) if position is not None else None
        )
        return {"playlistId": playlist_id, "itemId": item_id, "added": ok}

    async def _playlists_remove_item(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        item_id = _require_str(params, "itemId")
        ok = self._playlists_repo.remove_item(playlist_id, item_id)
        return {"playlistId": playlist_id, "itemId": item_id, "removed": ok}

    async def _playlists_reorder(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        item_id = _require_str(params, "itemId")
        new_position = int(_require_str(params, "position"))
        ok = self._playlists_repo.reorder_item(playlist_id, item_id, new_position)
        return {"playlistId": playlist_id, "itemId": item_id, "reordered": ok}

    async def _playlists_items(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        items = self._playlists_repo.items(playlist_id)
        return {"items": [i.to_dict() for i in items]}

    async def _playlists_set_shuffle(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        shuffle = bool(params.get("shuffle", False))
        ok = self._playlists_repo.set_shuffle(playlist_id, shuffle)
        return {"playlistId": playlist_id, "shuffle": shuffle, "updated": ok}

    async def _playlists_set_repeat(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._playlists_repo is not None
        playlist_id = _require_str(params, "playlistId")
        mode_raw = _require_str(params, "repeatMode")
        try:
            mode = RepeatMode(mode_raw)
        except ValueError as exc:
            raise RpcError(EngineError.INVALID_PARAMS, "Invalid repeatMode") from exc
        ok = self._playlists_repo.set_repeat_mode(playlist_id, mode)
        return {"playlistId": playlist_id, "repeatMode": mode.value, "updated": ok}

    # ---- settings.* (Phase 6) ----

    async def _settings_get(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._settings_repo is not None
        key = _require_str(params, "key")
        value = self._settings_repo.get(key)
        return {"key": key, "value": value}

    async def _settings_get_all(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._settings_repo is not None
        return {"settings": self._settings_repo.get_all()}

    async def _settings_set(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._settings_repo is not None
        key = _require_str(params, "key")
        if "value" not in params:
            raise RpcError(EngineError.INVALID_PARAMS, "Missing 'value'")
        self._settings_repo.set(key, params["value"])
        return {"key": key, "updated": True}

    async def _settings_set_many(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._settings_repo is not None
        items = params.get("settings")
        if not isinstance(items, dict):
            raise RpcError(EngineError.INVALID_PARAMS, "Missing 'settings' map")
        self._settings_repo.set_many(dict(items))
        return {"updated": len(items)}

    async def _settings_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._settings_repo is not None
        key = _require_str(params, "key")
        ok = self._settings_repo.delete(key)
        return {"key": key, "deleted": ok}

    async def _settings_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._settings_repo is not None
        self._settings_repo.reset()
        return {"reset": True}

    # ---- scheduler.* (Phase 6) ----

    async def _scheduler_create(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        from mediahub_engine.database.scheduler_repository import (
            ScheduledTask,
            ScheduleType,
        )

        url = _require_str(params, "url")
        type_raw = _require_str(params, "scheduleType")
        try:
            stype = ScheduleType(type_raw)
        except ValueError as exc:
            raise RpcError(EngineError.INVALID_PARAMS, "Invalid scheduleType") from exc

        task = ScheduledTask(
            url=url,
            schedule_type=stype,
            scheduled_at=params.get("scheduledAt"),
            interval_seconds=params.get("intervalSeconds"),
            hour=params.get("hour"),
            minute=params.get("minute"),
            day_of_week=params.get("dayOfWeek"),
            priority=TaskPriority(int(params.get("priority", 5))),
            options=dict(params.get("options") or {}),
            enabled=bool(params.get("enabled", True)),
        )
        self._scheduler_repo.create(task)
        return task.to_dict()

    async def _scheduler_list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        enabled_only = bool(params.get("enabledOnly", False))
        tasks = self._scheduler_repo.list(enabled_only=enabled_only)
        return {"schedules": [t.to_dict() for t in tasks]}

    async def _scheduler_get(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        sid = _require_str(params, "scheduleId")
        task = self._scheduler_repo.get(sid)
        if task is None:
            raise RpcError(-2, "Schedule not found", {"scheduleId": sid})
        return task.to_dict()

    async def _scheduler_update(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        sid = _require_str(params, "scheduleId")
        task = self._scheduler_repo.get(sid)
        if task is None:
            raise RpcError(-2, "Schedule not found", {"scheduleId": sid})
        if "url" in params:
            task.url = params["url"]
        if "enabled" in params:
            task.enabled = bool(params["enabled"])
        if "priority" in params:
            task.priority = TaskPriority(int(params["priority"]))
        if "options" in params:
            task.options = dict(params["options"])
        self._scheduler_repo.update(task)
        return task.to_dict()

    async def _scheduler_set_enabled(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        sid = _require_str(params, "scheduleId")
        enabled = bool(params.get("enabled", False))
        ok = self._scheduler_repo.set_enabled(sid, enabled)
        return {"scheduleId": sid, "enabled": enabled, "updated": ok}

    async def _scheduler_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        sid = _require_str(params, "scheduleId")
        ok = self._scheduler_repo.delete(sid)
        return {"scheduleId": sid, "deleted": ok}

    async def _scheduler_due(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        tasks = self._scheduler_repo.due_schedules()
        return {"schedules": [t.to_dict() for t in tasks]}

    async def _scheduler_mark_run(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._scheduler_repo is not None
        sid = _require_str(params, "scheduleId")
        self._scheduler_repo.mark_run(sid)
        task = self._scheduler_repo.get(sid)
        return task.to_dict() if task else {"scheduleId": sid, "marked": True}

    # ---- credentials.* (Phase 6) ----

    async def _credentials_set(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._credentials_repo is not None
        provider = _require_str(params, "provider")
        cred = Credential(
            username=params.get("username"),
            password=params.get("password"),
            cookies_path=params.get("cookiesPath"),
            session_path=params.get("sessionPath"),
            token=params.get("token"),
            extra=dict(params.get("extra") or {}),
        )
        self._credentials_repo.set(provider, cred)
        return {"provider": provider, "updated": True}

    async def _credentials_get(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._credentials_repo is not None
        provider = _require_str(params, "provider")
        cred = self._credentials_repo.get(provider)
        if cred is None:
            return {"provider": provider, "credential": None}
        # Never return the password/token in plaintext over the bridge.
        return {
            "provider": provider,
            "credential": {
                "username": cred.username,
                "cookiesPath": cred.cookies_path,
                "sessionPath": cred.session_path,
                "hasPassword": cred.password is not None,
                "hasToken": cred.token is not None,
            },
        }

    async def _credentials_list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._credentials_repo is not None
        return {"providers": self._credentials_repo.list_providers()}

    async def _credentials_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._credentials_repo is not None
        provider = _require_str(params, "provider")
        ok = self._credentials_repo.delete(provider)
        return {"provider": provider, "deleted": ok}

    async def _credentials_has(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_persistence()
        assert self._credentials_repo is not None
        provider = _require_str(params, "provider")
        return {"provider": provider, "has": self._credentials_repo.has(provider)}

    # ---- Helpers ----

    def _require_persistence(self) -> None:
        if self._db is None:
            raise RpcError(
                EngineError.INTERNAL,
                "Persistence is disabled (persist_downloads=False)",
            )

    # ---- Lifecycle ----

    async def run(self) -> int:
        """Reads requests from stdin and writes responses to stdout until EOF."""
        await self.manager.start()
        log.info("MediaHub engine %s ready (bridge v%d)", __version__, BRIDGE_VERSION)

        try:
            async for request in _aiter_messages(sys.stdin):
                try:
                    response = await self.dispatcher.dispatch(request)
                except RpcError as exc:
                    if request.id is not None:
                        write_message(
                            sys.stdout,
                            {
                                "jsonrpc": "2.0",
                                "id": request.id,
                                "error": {
                                    "code": exc.code,
                                    "message": exc.message,
                                    "data": exc.data,
                                },
                            },
                        )
                    continue

                if response is not None:
                    write_message(sys.stdout, response)
                if self._stop.is_set():
                    break
        finally:
            await self.manager.stop()
            if self._db is not None:
                self._db.close()
            log.info("MediaHub engine stopped")
        return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_str(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(
            EngineError.INVALID_PARAMS,
            f"Missing or invalid parameter: {key}",
            {"field": key},
        )
    return value


async def _aiter_messages(stream: Any):
    """Wraps the synchronous [read_messages] generator in an async iterator.

    Line reads are delegated to a thread so the event loop stays responsive.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    async def _producer() -> None:
        def _read_all() -> None:
            for request in read_messages(stream):
                loop.call_soon_threadsafe(queue.put_nowait, request)

        await loop.run_in_executor(None, _read_all)
        loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    producer = asyncio.create_task(_producer())
    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            yield item
    finally:
        producer.cancel()


def main() -> int:
    """Synchronous entry point used by the ``mediahub-engine`` console script."""
    return asyncio.run(Engine().run())


__all__ = ["BRIDGE_VERSION", "Engine", "main"]

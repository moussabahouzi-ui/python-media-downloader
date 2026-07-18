"""Models for the media library (Phase 4).

These are plain dataclasses mirrored on the Flutter side. They are
serializable for JSON-RPC and persistable to SQLite via the repositories.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class MediaCategory(StrEnum):
    """High-level media categories used for browsing and filtering."""

    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    OTHER = "other"

    @classmethod
    def from_path(cls, path: str) -> MediaCategory:
        """Infers the category from a file extension."""
        ext = Path(path).suffix.lower()
        if ext in _VIDEO_EXTS:
            return cls.VIDEO
        if ext in _AUDIO_EXTS:
            return cls.AUDIO
        if ext in _IMAGE_EXTS:
            return cls.IMAGE
        return cls.OTHER


_VIDEO_EXTS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mkv",
        ".webm",
        ".mov",
        ".avi",
        ".flv",
        ".wmv",
        ".m4v",
        ".ts",
        ".mpg",
    }
)
_AUDIO_EXTS: frozenset[str] = frozenset(
    {
        ".mp3",
        ".aac",
        ".m4a",
        ".flac",
        ".ogg",
        ".wav",
        ".opus",
        ".wma",
    }
)
_IMAGE_EXTS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".heic",
    }
)


@dataclass
class MediaItem:
    """A single indexed media file."""

    item_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    path: str = ""
    name: str = ""
    category: MediaCategory = MediaCategory.OTHER
    size_bytes: int = 0
    mime_type: str | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    provider: str | None = None
    url: str | None = None
    task_id: str | None = None
    title: str | None = None
    uploader: str | None = None
    thumbnail_path: str | None = None
    tags: list[str] = field(default_factory=list)
    favorite: bool = False
    recycled: bool = False
    created_at: float = field(default_factory=time.time)
    added_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "itemId": self.item_id,
            "path": self.path,
            "name": self.name,
            "category": self.category.value,
            "sizeBytes": self.size_bytes,
            "mimeType": self.mime_type,
            "durationMs": self.duration_ms,
            "width": self.width,
            "height": self.height,
            "provider": self.provider,
            "url": self.url,
            "taskId": self.task_id,
            "title": self.title,
            "uploader": self.uploader,
            "thumbnailPath": self.thumbnail_path,
            "tags": list(self.tags),
            "favorite": self.favorite,
            "recycled": self.recycled,
            "createdAt": self.created_at,
            "addedAt": self.added_at,
        }


@dataclass
class Collection:
    """A user-defined group of media items."""

    collection_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    description: str = ""
    color: str | None = None
    icon: str | None = None
    item_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collectionId": self.collection_id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "itemCount": self.item_count,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass
class HistoryEntry:
    """An append-only record of a finished (or failed) download."""

    history_id: int | None = None
    task_id: str = ""
    url: str = ""
    provider: str | None = None
    engine: str | None = None
    state: str = ""  # completed | failed | cancelled
    bytes_done: int = 0
    output_paths: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] | None = None
    started_at: float | None = None
    finished_at: float | None = None
    recorded_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "historyId": self.history_id,
            "taskId": self.task_id,
            "url": self.url,
            "provider": self.provider,
            "engine": self.engine,
            "state": self.state,
            "bytesDone": self.bytes_done,
            "outputPaths": list(self.output_paths),
            "error": self.error,
            "metadata": self.metadata,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "recordedAt": self.recorded_at,
        }


@dataclass
class DownloadStats:
    """Aggregate download statistics."""

    total_downloads: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total_bytes: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalDownloads": self.total_downloads,
            "completed": self.completed,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "totalBytes": self.total_bytes,
            "byProvider": dict(self.by_provider),
            "byCategory": dict(self.by_category),
        }


@dataclass
class StorageBreakdown:
    """Storage usage broken down by category (for the storage analyzer)."""

    total_bytes: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    file_count: int = 0
    file_count_by_category: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalBytes": self.total_bytes,
            "byCategory": dict(self.by_category),
            "fileCount": self.file_count,
            "fileCountByCategory": dict(self.file_count_by_category),
        }


@dataclass
class DuplicateGroup:
    """A set of files that are probable duplicates (same hash or size+name)."""

    key: str
    size_bytes: int
    paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "sizeBytes": self.size_bytes,
            "paths": list(self.paths),
        }


class RepeatMode(StrEnum):
    """Playback repeat modes for playlists."""

    OFF = "off"
    ALL = "all"
    ONE = "one"


@dataclass
class Playlist:
    """An ordered playback queue of media items."""

    playlist_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    description: str = ""
    item_count: int = 0
    shuffle: bool = False
    repeat_mode: RepeatMode = RepeatMode.OFF
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "playlistId": self.playlist_id,
            "name": self.name,
            "description": self.description,
            "itemCount": self.item_count,
            "shuffle": self.shuffle,
            "repeatMode": self.repeat_mode.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def parse_tags(raw: str | None) -> list[str]:
    """Parses a JSON-encoded tags column into a list."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return list(data) if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def dump_tags(tags: list[str]) -> str:
    """Serializes a tags list for the JSON-encoded column."""
    return json.dumps(tags)


__all__ = [
    "Collection",
    "DownloadStats",
    "DuplicateGroup",
    "HistoryEntry",
    "MediaCategory",
    "MediaItem",
    "Playlist",
    "RepeatMode",
    "StorageBreakdown",
    "dump_tags",
    "parse_tags",
]

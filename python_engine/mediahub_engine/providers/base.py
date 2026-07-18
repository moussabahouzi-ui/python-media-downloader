"""The provider abstraction.

A [Provider] knows how to:

1. detect whether it handles a given URL ([matches]),
2. extract metadata for the URL ([extract_metadata]),
3. download the media it represents ([download]).

Adding a new platform means implementing this class (or, more commonly,
[BackendDelegateProvider]) and registering it in
[mediahub_engine.providers.registry]. No core download logic changes.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Any, Protocol

from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class ProviderFeature(Flag):
    """Capability bits a provider may advertise."""

    NONE = 0
    SINGLE = auto()
    BATCH = auto()
    SUBTITLES = auto()
    AUDIO_EXTRACTION = auto()
    THUMBNAIL = auto()
    METADATA = auto()
    AUTH = auto()
    RESUMABLE = auto()
    LOGIN = auto()


@dataclass(frozen=True)
class Capability:
    """Static descriptor of what a provider can do."""

    #: Human-readable platform name (e.g. ``"youtube"``).
    name: str
    #: Preferred extraction engine (``"yt-dlp"``, ``"gallery-dl"``, ...).
    engine: str
    #: URL-fragment patterns this provider claims (used for fast detection).
    url_patterns: tuple[str, ...]
    #: Capability bits.
    features: ProviderFeature = ProviderFeature.NONE
    #: Whether authentication is *required* (vs. optional).
    auth_required: bool = False
    #: Maximum items in a single batch (0 = unlimited).
    max_batch: int = 1
    #: Human-readable display name shown in the UI.
    display_name: str | None = None


class ProviderError(Exception):
    """Raised by providers for expected, user-presentable failures."""

    def __init__(
        self, message: str, *, code: str = "PROVIDER_ERROR", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass
class MediaMetadata:
    """Normalized metadata extracted for a URL."""

    title: str
    uploader: str | None = None
    duration_seconds: float | None = None
    thumbnail_url: str | None = None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FormatOption:
    """A selectable output format offered by a provider."""

    format_id: str
    label: str
    ext: str
    resolution: str | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    filesize: int | None = None
    is_audio_only: bool = False


@dataclass
class ProviderResult:
    """The outcome of a download operation."""

    bytes_written: int
    #: All files produced by the download (single-item downloads have one).
    output_paths: list[str] = field(default_factory=list)
    metadata: MediaMetadata | None = None
    formats: list[FormatOption] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def output_path(self) -> str:
        """The primary output path (first file, or empty string)."""
        return self.output_paths[0] if self.output_paths else ""


@dataclass
class Credential:
    """Credentials a provider may consume for authenticated access."""

    username: str | None = None
    password: str | None = None
    cookies_path: str | None = None
    session_path: str | None = None
    token: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (
            self.username or self.password or self.cookies_path or self.session_path or self.token
        )


class CredentialStore(Protocol):
    """Read-only credential store providers may consult."""

    def get(self, provider_name: str) -> Credential | None: ...


class InMemoryCredentialStore:
    """Simple in-memory credential store, used by tests and Phase 6 persistence."""

    def __init__(self) -> None:
        self._creds: dict[str, Credential] = {}

    def set(self, provider_name: str, credential: Credential) -> None:
        self._creds[provider_name] = credential

    def get(self, provider_name: str) -> Credential | None:
        return self._creds.get(provider_name)

    def clear(self) -> None:
        self._creds.clear()


class DownloadSink(Protocol):
    """Sink the engine passes to providers so they can report progress.

    Implementations forward these to JSON-RPC notifications (throttled).
    """

    def on_progress(
        self, *, task_id: str, percent: float, bytes_done: int, total_bytes: int | None
    ) -> None: ...

    def on_log(self, message: str) -> None: ...


class Provider(abc.ABC):
    """Base class every provider implements."""

    #: Subclasses override this with a [Capability] instance.
    capability: Capability

    def __init__(self) -> None:
        if not hasattr(type(self), "capability") or getattr(type(self), "capability", None) is None:
            raise TypeError(f"{type(self).__name__} must set a class-level `capability`")

    @property
    def name(self) -> str:
        return self.capability.name

    def matches(self, url: str) -> bool:
        """Default detection by URL-fragment match. Override for custom logic."""
        return any(pattern in url for pattern in self.capability.url_patterns)

    @abc.abstractmethod
    async def extract_metadata(self, url: str) -> MediaMetadata:
        """Fetches metadata without downloading the media."""

    @abc.abstractmethod
    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """Downloads the media for ``url`` into ``dest_dir``."""

    def __repr__(self) -> str:
        return f"<Provider {self.capability.name} ({self.capability.engine})>"


__all__ = [
    "Capability",
    "Credential",
    "CredentialStore",
    "DownloadSink",
    "FormatOption",
    "InMemoryCredentialStore",
    "MediaMetadata",
    "Provider",
    "ProviderError",
    "ProviderFeature",
    "ProviderResult",
]

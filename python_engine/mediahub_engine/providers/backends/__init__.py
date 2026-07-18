"""Extraction backend wrappers.

A backend wraps a concrete extraction engine (yt-dlp, gallery-dl, Instaloader)
and exposes a uniform async surface to providers. Backends lazy-import their
underlying library so the engine boots even when a library is absent, and so
unit tests can inject a [FakeBackend] without the heavy dependencies.
"""

from mediahub_engine.providers.backends.base import (
    BackendNotAvailableError,
    ExtractionBackend,
    ExtractionResult,
)
from mediahub_engine.providers.backends.gallerydl import GalleryDlBackend
from mediahub_engine.providers.backends.instaloader import InstaloaderBackend
from mediahub_engine.providers.backends.registry import (
    BackendRegistry,
    get_backend_registry,
    reset_backend_registry,
)
from mediahub_engine.providers.backends.ytdlp import YtDlpBackend

__all__ = [
    "BackendNotAvailableError",
    "BackendRegistry",
    "ExtractionBackend",
    "ExtractionResult",
    "GalleryDlBackend",
    "InstaloaderBackend",
    "YtDlpBackend",
    "get_backend_registry",
    "reset_backend_registry",
]

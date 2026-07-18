"""Threads provider (gallery-dl)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class ThreadsProvider(BackendDelegateProvider):
    """Threads posts (text + image/video) via gallery-dl."""

    capability = Capability(
        name="threads",
        engine="gallery-dl",
        display_name="Threads",
        url_patterns=(
            "threads.net/",
            "threads.com/",
            "www.threads.net/post/",
            "www.threads.com/post/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.BATCH
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
        ),
        auth_required=False,
        max_batch=20,
    )

    backend_strategy = EngineStrategy.GALLERY_DL


__all__ = ["ThreadsProvider"]

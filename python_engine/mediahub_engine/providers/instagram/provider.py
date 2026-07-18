"""Instagram provider (gallery-dl primary, instaloader for stories/reels)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    MediaMetadata,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class InstagramProvider(BackendDelegateProvider):
    """Instagram posts, reels, and galleries via gallery-dl.

    Auth is optional for public posts but required for private/reels/stories.
    Credential injection is handled by [BackendDelegateProvider].
    """

    capability = Capability(
        name="instagram",
        engine="gallery-dl",
        display_name="Instagram",
        url_patterns=(
            "instagram.com/p/",
            "instagram.com/reel/",
            "instagram.com/reels/",
            "instagram.com/tv/",
            "instagram.com/stories/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.BATCH
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
            | ProviderFeature.AUTH
        ),
        auth_required=False,
        max_batch=20,
    )

    backend_strategy = EngineStrategy.GALLERY_DL

    def _normalize_metadata(self, metadata: MediaMetadata, result) -> MediaMetadata:  # type: ignore[no-untyped-def]
        metadata.extra.setdefault("item_count", result.raw.get("item_count"))
        return metadata


__all__ = ["InstagramProvider"]

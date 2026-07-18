"""Snapchat provider (gallery-dl, falls back to generic)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class SnapchatProvider(BackendDelegateProvider):
    """Snapchat Spotlights and public stories via gallery-dl.

    Snapchat support in gallery-dl is partial; the generic provider acts as
    the final fallback for direct media URLs.
    """

    capability = Capability(
        name="snapchat",
        engine="gallery-dl",
        display_name="Snapchat",
        url_patterns=(
            "snapchat.com/spotlight/",
            "snapchat.com/add/",
            "snapchat.com/p/",
            "story.snapchat.com/",
        ),
        features=(ProviderFeature.SINGLE | ProviderFeature.THUMBNAIL | ProviderFeature.METADATA),
        auth_required=False,
        max_batch=1,
    )

    backend_strategy = EngineStrategy.GALLERY_DL


__all__ = ["SnapchatProvider"]

"""Pinterest provider (gallery-dl)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class PinterestProvider(BackendDelegateProvider):
    """Pinterest pins and boards via gallery-dl."""

    capability = Capability(
        name="pinterest",
        engine="gallery-dl",
        display_name="Pinterest",
        url_patterns=(
            "pinterest.com/pin/",
            "pinterest.co.uk/pin/",
            "pin.it/",
            "pinterest.com/board/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.BATCH
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
        ),
        auth_required=False,
        max_batch=50,
    )

    backend_strategy = EngineStrategy.GALLERY_DL


__all__ = ["PinterestProvider"]

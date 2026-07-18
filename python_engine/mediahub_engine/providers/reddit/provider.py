"""Reddit provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class RedditProvider(BackendDelegateProvider):
    """Reddit videos and GIFs via yt-dlp."""

    capability = Capability(
        name="reddit",
        engine="yt-dlp",
        display_name="Reddit",
        url_patterns=(
            "reddit.com/r/",
            "redd.it/",
            "reddit.com/gallery/",
            "redditmedia.com/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.AUDIO_EXTRACTION
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
        ),
        auth_required=False,
        max_batch=1,
    )

    backend_strategy = EngineStrategy.YTDLP


__all__ = ["RedditProvider"]

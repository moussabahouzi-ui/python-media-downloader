"""Twitter / X provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class TwitterXProvider(BackendDelegateProvider):
    """Twitter/X videos and GIFs via yt-dlp. Auth is typically required."""

    capability = Capability(
        name="twitter_x",
        engine="yt-dlp",
        display_name="Twitter / X",
        url_patterns=(
            "twitter.com/",
            "x.com/",
            "t.co/",
            "twitter.com/i/status/",
            "x.com/i/status/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.BATCH
            | ProviderFeature.AUDIO_EXTRACTION
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
            | ProviderFeature.AUTH
        ),
        auth_required=True,
        max_batch=20,
    )

    backend_strategy = EngineStrategy.YTDLP


__all__ = ["TwitterXProvider"]

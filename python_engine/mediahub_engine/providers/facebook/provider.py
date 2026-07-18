"""Facebook provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class FacebookProvider(BackendDelegateProvider):
    """Facebook videos and reels via yt-dlp."""

    capability = Capability(
        name="facebook",
        engine="yt-dlp",
        display_name="Facebook",
        url_patterns=(
            "facebook.com/watch",
            "facebook.com/reel/",
            "facebook.com/",
            "fb.watch/",
            "fb.com/watch",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.SUBTITLES
            | ProviderFeature.AUDIO_EXTRACTION
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
            | ProviderFeature.AUTH
        ),
        auth_required=False,
        max_batch=1,
    )

    backend_strategy = EngineStrategy.YTDLP


__all__ = ["FacebookProvider"]

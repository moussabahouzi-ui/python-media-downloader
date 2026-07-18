"""Dailymotion provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class DailymotionProvider(BackendDelegateProvider):
    """Dailymotion videos via yt-dlp."""

    capability = Capability(
        name="dailymotion",
        engine="yt-dlp",
        display_name="Dailymotion",
        url_patterns=(
            "dailymotion.com/video/",
            "dailymotion.com/embed/",
            "dai.ly/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.SUBTITLES
            | ProviderFeature.AUDIO_EXTRACTION
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
        ),
        auth_required=False,
        max_batch=1,
    )

    backend_strategy = EngineStrategy.YTDLP


__all__ = ["DailymotionProvider"]

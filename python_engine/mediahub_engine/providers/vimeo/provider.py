"""Vimeo provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class VimeoProvider(BackendDelegateProvider):
    """Vimeo videos via yt-dlp."""

    capability = Capability(
        name="vimeo",
        engine="yt-dlp",
        display_name="Vimeo",
        url_patterns=(
            "vimeo.com/",
            "player.vimeo.com/video/",
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


__all__ = ["VimeoProvider"]

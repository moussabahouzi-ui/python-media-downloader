"""Twitch provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class TwitchProvider(BackendDelegateProvider):
    """Twitch clips and VODs via yt-dlp. Live streams are not supported in
    Phase 2 (requires stream recording; deferred to Phase 3)."""

    capability = Capability(
        name="twitch",
        engine="yt-dlp",
        display_name="Twitch",
        url_patterns=(
            "twitch.tv/clips/",
            "clips.twitch.tv/",
            "twitch.tv/videos/",
            "twitch.tv/collections/",
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


__all__ = ["TwitchProvider"]

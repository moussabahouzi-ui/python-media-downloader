"""SoundCloud provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class SoundcloudProvider(BackendDelegateProvider):
    """SoundCloud tracks and playlists via yt-dlp."""

    capability = Capability(
        name="soundcloud",
        engine="yt-dlp",
        display_name="SoundCloud",
        url_patterns=(
            "soundcloud.com/",
            "on.soundcloud.com/",
            "api.soundcloud.com/tracks/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.BATCH
            | ProviderFeature.AUDIO_EXTRACTION
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
        ),
        auth_required=False,
        max_batch=50,
    )

    backend_strategy = EngineStrategy.YTDLP


__all__ = ["SoundcloudProvider"]

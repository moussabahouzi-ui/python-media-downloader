"""YouTube provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    MediaMetadata,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class YouTubeProvider(BackendDelegateProvider):
    """YouTube videos, shorts, and playlists via yt-dlp."""

    capability = Capability(
        name="youtube",
        engine="yt-dlp",
        display_name="YouTube",
        url_patterns=(
            "youtube.com/watch",
            "youtu.be/",
            "youtube.com/shorts/",
            "youtube.com/embed/",
            "m.youtube.com/watch",
            "music.youtube.com/watch",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.BATCH
            | ProviderFeature.SUBTITLES
            | ProviderFeature.AUDIO_EXTRACTION
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
            | ProviderFeature.RESUMABLE
        ),
        auth_required=False,
        max_batch=50,
    )

    backend_strategy = EngineStrategy.YTDLP

    def _normalize_metadata(self, metadata: MediaMetadata, result) -> MediaMetadata:  # type: ignore[no-untyped-def]
        # Enrich with format count for the UI.
        metadata.extra["format_count"] = len(result.formats)
        return metadata


__all__ = ["YouTubeProvider"]

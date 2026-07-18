"""TikTok provider (yt-dlp)."""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.base import (
    Capability,
    ProviderFeature,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider


class TikTokProvider(BackendDelegateProvider):
    """TikTok videos via yt-dlp (no watermark when available)."""

    capability = Capability(
        name="tiktok",
        engine="yt-dlp",
        display_name="TikTok",
        url_patterns=(
            "tiktok.com/",
            "vm.tiktok.com/",
            "vt.tiktok.com/",
        ),
        features=(
            ProviderFeature.SINGLE
            | ProviderFeature.BATCH
            | ProviderFeature.AUDIO_EXTRACTION
            | ProviderFeature.THUMBNAIL
            | ProviderFeature.METADATA
        ),
        auth_required=False,
        max_batch=30,
    )

    backend_strategy = EngineStrategy.YTDLP


__all__ = ["TikTokProvider"]

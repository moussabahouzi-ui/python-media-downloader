"""Tests for the extraction backends.

The real backends lazy-import yt-dlp / gallery-dl / instaloader, which are not
installed in this environment (they are device-runtime deps). These tests
verify the availability guard, the not-available error path, and the option
merging / metadata normalization helpers (which are pure functions and thus
unit-testable without the libs).
"""

from __future__ import annotations

import pytest

from mediahub_engine.engine_kinds import EngineStrategy
from mediahub_engine.providers.backends.base import (
    BackendNotAvailableError,
    ExtractionResult,
)
from mediahub_engine.providers.backends.gallerydl import GalleryDlBackend
from mediahub_engine.providers.backends.instaloader import InstaloaderBackend
from mediahub_engine.providers.backends.ytdlp import (
    YtDlpBackend,
    _format_label,
    _info_to_result,
    _merge_options,
    _resolution_from_dims,
)
from mediahub_engine.providers.base import MediaMetadata


def test_ytdlp_backend_reports_unavailable_without_lib() -> None:
    backend = YtDlpBackend()
    # yt-dlp is not installed in this environment.
    assert backend.is_available() is False


def test_gallerydl_backend_reports_unavailable_without_lib() -> None:
    assert GalleryDlBackend().is_available() is False


def test_instaloader_backend_reports_unavailable_without_lib() -> None:
    assert InstaloaderBackend().is_available() is False


@pytest.mark.asyncio
async def test_ytdlp_raises_when_unavailable() -> None:
    backend = YtDlpBackend()
    with pytest.raises(BackendNotAvailableError) as exc_info:
        await backend.extract_metadata("https://youtube.com/watch?v=abc")
    assert exc_info.value.engine is EngineStrategy.YTDLP


@pytest.mark.asyncio
async def test_gallerydl_raises_when_unavailable() -> None:
    backend = GalleryDlBackend()
    with pytest.raises(BackendNotAvailableError):
        await backend.download("https://instagram.com/p/abc", dest_dir="/tmp", task_id="t1")


@pytest.mark.asyncio
async def test_instaloader_raises_when_unavailable() -> None:
    backend = InstaloaderBackend()
    with pytest.raises(BackendNotAvailableError):
        await backend.extract_metadata("https://instagram.com/reel/abc")


# ---- pure helper tests (yt-dlp option merging + metadata normalization) ----


def test_merge_options_defaults_skip_download_for_metadata() -> None:
    opts = _merge_options(None, download=False)
    assert opts["skip_download"] is True
    assert opts["noplaylist"] is True
    assert "outtmpl" not in opts


def test_merge_options_sets_outtmpl_for_download() -> None:
    opts = _merge_options(None, download=True, dest_dir="/out")
    assert opts["outtmpl"] == "/out/%(title).200B.%(ext)s"
    assert "skip_download" not in opts


def test_merge_options_passes_caller_overrides() -> None:
    opts = _merge_options(
        {"format": "bestvideo+bestaudio/best", "writesubtitles": True},
        download=True,
        dest_dir="/out",
    )
    assert opts["format"] == "bestvideo+bestaudio/best"
    assert opts["writesubtitles"] is True


def test_merge_options_ignores_unknown_caller_keys() -> None:
    opts = _merge_options({"evil_key": "no"}, download=False)
    assert "evil_key" not in opts


def test_info_to_result_normalizes_metadata() -> None:
    info = {
        "title": "My Video",
        "uploader": "Creator",
        "duration": 120,
        "thumbnail": "https://img/thumb.jpg",
        "categories": ["music"],
        "tags": ["a", "b"],
        "formats": [
            {"format_id": "137", "ext": "mp4", "height": 720, "vcodec": "h264", "acodec": "none"},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp3"},
        ],
    }
    result = _info_to_result(info)
    assert result.metadata.title == "My Video"
    assert result.metadata.uploader == "Creator"
    assert result.metadata.duration_seconds == 120
    assert len(result.formats) == 2
    assert result.formats[0].is_audio_only is False
    assert result.formats[1].is_audio_only is True


def test_resolution_from_dims() -> None:
    assert _resolution_from_dims({"width": 1920, "height": 1080}) == "1920x1080"
    assert _resolution_from_dims({"height": 720}) == "720p"
    assert _resolution_from_dims({}) is None


def test_format_label_audio_only() -> None:
    assert _format_label({"ext": "m4a", "vcodec": "none"}) == "audio m4a"


def test_format_label_video() -> None:
    assert _format_label({"ext": "mp4", "resolution": "720p", "vcodec": "h264"}) == "720p mp4"


def test_extraction_result_defaults() -> None:
    r = ExtractionResult(metadata=MediaMetadata(title="x"))
    assert r.output_paths == []
    assert r.bytes_written == 0
    assert r.formats == []
    assert r.warnings == []


def test_instaloader_shortcode_extraction_success() -> None:
    from mediahub_engine.providers.backends.instaloader import _extract_shortcode

    assert _extract_shortcode("https://www.instagram.com/p/Cabc123/") == "Cabc123"
    assert _extract_shortcode("https://www.instagram.com/reel/Dxyz456/?igsh=1") == "Dxyz456"


def test_instaloader_shortcode_extraction_failure() -> None:
    from mediahub_engine.providers.backends.instaloader import _extract_shortcode
    from mediahub_engine.providers.base import ProviderError

    with pytest.raises(ProviderError):
        _extract_shortcode("https://www.instagram.com/explore/")

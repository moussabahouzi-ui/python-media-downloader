"""Tests for the platform providers: detection, metadata, and download delegation.

Each platform is exercised against an injected [FakeBackend] so the tests are
deterministic and do not require yt-dlp / gallery-dl / instaloader to be
installed. The detection matrix also guards against two providers claiming the
same URL (which would make routing ambiguous).
"""

from __future__ import annotations

from typing import Any

import pytest

from mediahub_engine.engine_kinds import EngineStrategy
from mediahub_engine.providers.backends.registry import BackendRegistry
from mediahub_engine.providers.base import (
    Credential,
    InMemoryCredentialStore,
    MediaMetadata,
    ProviderFeature,
    ProviderResult,
)
from mediahub_engine.providers.dailymotion import DailymotionProvider
from mediahub_engine.providers.facebook import FacebookProvider
from mediahub_engine.providers.generic import GenericProvider
from mediahub_engine.providers.instagram import InstagramProvider
from mediahub_engine.providers.pinterest import PinterestProvider
from mediahub_engine.providers.reddit import RedditProvider
from mediahub_engine.providers.snapchat import SnapchatProvider
from mediahub_engine.providers.soundcloud import SoundcloudProvider
from mediahub_engine.providers.threads import ThreadsProvider
from mediahub_engine.providers.tiktok import TikTokProvider
from mediahub_engine.providers.twitch import TwitchProvider
from mediahub_engine.providers.twitter_x import TwitterXProvider
from mediahub_engine.providers.vimeo import VimeoProvider
from mediahub_engine.providers.youtube import YouTubeProvider
from tests.conftest_providers import FakeBackend, NullSink, build_registry_with

# ---------------------------------------------------------------------------
# Provider class + capability table
# ---------------------------------------------------------------------------

#: (provider_class, engine_strategy, sample_url, non_matching_url)
PROVIDER_CASES: list[tuple[type, EngineStrategy, str, str]] = [
    (
        YouTubeProvider,
        EngineStrategy.YTDLP,
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://example.com/page",
    ),
    (YouTubeProvider, EngineStrategy.YTDLP, "https://youtu.be/abc123", "https://example.com/page"),
    (
        YouTubeProvider,
        EngineStrategy.YTDLP,
        "https://youtube.com/shorts/abc",
        "https://vimeo.com/x",
    ),
    (
        InstagramProvider,
        EngineStrategy.GALLERY_DL,
        "https://www.instagram.com/p/Cabc/",
        "https://youtube.com/watch?v=x",
    ),
    (
        InstagramProvider,
        EngineStrategy.GALLERY_DL,
        "https://instagram.com/reel/Dxyz/",
        "https://example.com",
    ),
    (
        FacebookProvider,
        EngineStrategy.YTDLP,
        "https://www.facebook.com/watch?v=123",
        "https://youtube.com/watch?v=x",
    ),
    (FacebookProvider, EngineStrategy.YTDLP, "https://fb.watch/abc/", "https://example.com"),
    (
        TikTokProvider,
        EngineStrategy.YTDLP,
        "https://www.tiktok.com/@user/video/123",
        "https://example.com",
    ),
    (TikTokProvider, EngineStrategy.YTDLP, "https://vm.tiktok.com/abc/", "https://youtube.com"),
    (
        TwitterXProvider,
        EngineStrategy.YTDLP,
        "https://twitter.com/user/status/123",
        "https://example.com",
    ),
    (
        TwitterXProvider,
        EngineStrategy.YTDLP,
        "https://x.com/user/status/456",
        "https://youtube.com",
    ),
    (
        RedditProvider,
        EngineStrategy.YTDLP,
        "https://www.reddit.com/r/sub/comments/abc/title/",
        "https://example.com",
    ),
    (RedditProvider, EngineStrategy.YTDLP, "https://redd.it/abc", "https://youtube.com"),
    (VimeoProvider, EngineStrategy.YTDLP, "https://vimeo.com/123456", "https://example.com"),
    (
        VimeoProvider,
        EngineStrategy.YTDLP,
        "https://player.vimeo.com/video/123",
        "https://youtube.com",
    ),
    (
        DailymotionProvider,
        EngineStrategy.YTDLP,
        "https://www.dailymotion.com/video/abc",
        "https://example.com",
    ),
    (DailymotionProvider, EngineStrategy.YTDLP, "https://dai.ly/abc", "https://youtube.com"),
    (
        PinterestProvider,
        EngineStrategy.GALLERY_DL,
        "https://www.pinterest.com/pin/123/",
        "https://example.com",
    ),
    (PinterestProvider, EngineStrategy.GALLERY_DL, "https://pin.it/abc", "https://youtube.com"),
    (
        TwitchProvider,
        EngineStrategy.YTDLP,
        "https://www.twitch.tv/clips/abc",
        "https://example.com",
    ),
    (TwitchProvider, EngineStrategy.YTDLP, "https://clips.twitch.tv/abc", "https://youtube.com"),
    (
        TwitchProvider,
        EngineStrategy.YTDLP,
        "https://www.twitch.tv/videos/123",
        "https://example.com",
    ),
    (
        SoundcloudProvider,
        EngineStrategy.YTDLP,
        "https://soundcloud.com/artist/track",
        "https://example.com",
    ),
    (
        SoundcloudProvider,
        EngineStrategy.YTDLP,
        "https://on.soundcloud.com/abc",
        "https://youtube.com",
    ),
    (
        ThreadsProvider,
        EngineStrategy.GALLERY_DL,
        "https://www.threads.net/post/abc",
        "https://example.com",
    ),
    (
        ThreadsProvider,
        EngineStrategy.GALLERY_DL,
        "https://www.threads.com/post/abc",
        "https://youtube.com",
    ),
    (
        SnapchatProvider,
        EngineStrategy.GALLERY_DL,
        "https://www.snapchat.com/spotlight/abc",
        "https://example.com",
    ),
    (
        SnapchatProvider,
        EngineStrategy.GALLERY_DL,
        "https://story.snapchat.com/abc",
        "https://youtube.com",
    ),
]


@pytest.mark.parametrize(("provider_cls", "engine", "url", "_non"), PROVIDER_CASES)
def test_provider_matches_expected_urls(provider_cls, engine, url, _non) -> None:
    provider = _make_provider(provider_cls, engine)
    assert provider.matches(url) is True


@pytest.mark.parametrize(("provider_cls", "engine", "_url", "non_url"), PROVIDER_CASES)
def test_provider_rejects_non_matching_urls(provider_cls, engine, _url, non_url) -> None:
    provider = _make_provider(provider_cls, engine)
    assert provider.matches(non_url) is False


@pytest.mark.parametrize(("provider_cls", "engine", "_a", "_b"), PROVIDER_CASES)
def test_provider_capability_is_consistent(provider_cls, engine, _a, _b) -> None:
    provider = _make_provider(provider_cls, engine)
    cap = provider.capability
    assert cap.engine == engine.value
    assert cap.url_patterns  # at least one
    assert cap.name
    assert cap.display_name
    # Features must include SINGLE or BATCH (every provider handles at least one).
    assert bool(cap.features & (ProviderFeature.SINGLE | ProviderFeature.BATCH))


# ---------------------------------------------------------------------------
# Ambiguity: no two non-generic providers should match the same URL.
# (Generic deliberately matches direct media URLs only.)
# ---------------------------------------------------------------------------


AMBIGUITY_URLS = [url for (_cls, _engine, url, _non) in PROVIDER_CASES]


def test_no_provider_overlap_on_sample_urls() -> None:
    """No sample URL should be matched by more than one provider."""
    providers = [_make_provider(cls, engine) for (cls, engine, _u, _n) in PROVIDER_CASES]
    # Deduplicate providers by class (multiple cases per class).
    seen: dict[str, object] = {}
    unique: list = []
    for p in providers:
        if p.capability.name not in seen:
            seen[p.capability.name] = True
            unique.append(p)

    for url in AMBIGUITY_URLS:
        matches = [p.capability.name for p in unique if p.matches(url)]
        assert len(matches) == 1, f"URL {url!r} matched by {matches}"


# ---------------------------------------------------------------------------
# Delegation: extract_metadata + download route to the backend.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("provider_cls", "engine", "url", "_non"), PROVIDER_CASES)
@pytest.mark.asyncio
async def test_provider_extract_metadata_delegates_to_backend(
    provider_cls, engine, url, _non
) -> None:
    fake = FakeBackend(engine, metadata=MediaMetadata(title="meta-title", uploader="meta-up"))
    provider = _make_provider(provider_cls, engine, backends=build_registry_with(fake))
    metadata = await provider.extract_metadata(url)
    assert metadata.title == "meta-title"
    assert metadata.uploader == "meta-up"
    assert fake.calls and fake.calls[0][0] == "extract_metadata"
    assert fake.calls[0][1] == url


@pytest.mark.parametrize(("provider_cls", "engine", "url", "_non"), PROVIDER_CASES)
@pytest.mark.asyncio
async def test_provider_download_delegates_to_backend(
    provider_cls, engine, url, _non, tmp_path
) -> None:
    fake = FakeBackend(
        engine,
        output_paths=[str(tmp_path / "out.mp4")],
        bytes_written=4096,
    )
    provider = _make_provider(provider_cls, engine, backends=build_registry_with(fake))
    result: ProviderResult = await provider.download(
        url,
        dest_dir=str(tmp_path),
        task_id="task-1",
        sink=NullSink(),
        options={"format": "best"},
    )
    assert result.bytes_written == 4096
    assert result.output_paths == [str(tmp_path / "out.mp4")]
    assert result.output_path == str(tmp_path / "out.mp4")
    assert fake.calls and fake.calls[0][0] == "download"


# ---------------------------------------------------------------------------
# Auth / credential injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_injects_credentials_into_backend_options() -> None:
    fake = FakeBackend(EngineStrategy.YTDLP)
    store = InMemoryCredentialStore()
    store.set("youtube", Credential(username="u", password="p", cookies_path="/c.jar"))
    provider = YouTubeProvider(backends=build_registry_with(fake), credentials=store)
    await provider.extract_metadata("https://youtube.com/watch?v=x")
    _op, _url, opts = fake.calls[0]
    assert opts["username"] == "u"
    assert opts["password"] == "p"
    assert opts["cookiefile"] == "/c.jar"


def test_twitter_x_requires_auth() -> None:
    provider = TwitterXProvider(backends=build_registry_with(FakeBackend(EngineStrategy.YTDLP)))
    assert provider.capability.auth_required is True


def test_youtube_does_not_require_auth() -> None:
    provider = YouTubeProvider(backends=build_registry_with(FakeBackend(EngineStrategy.YTDLP)))
    assert provider.capability.auth_required is False


# ---------------------------------------------------------------------------
# Generic provider (kept for regression — Phase 1 behavior)
# ---------------------------------------------------------------------------


def test_generic_provider_still_matches_direct_media() -> None:
    g = GenericProvider()
    assert g.matches("https://cdn.example.com/clip.mp4")
    assert not g.matches("https://youtube.com/watch?v=x")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    provider_cls: type,
    engine: EngineStrategy,
    *,
    backends: BackendRegistry | None = None,
) -> Any:
    """Constructs a provider with a default fake backend if none provided."""
    if backends is None:
        backends = build_registry_with(FakeBackend(engine))
    # Delegate providers accept backends + credentials kwargs.
    return provider_cls(backends=backends)

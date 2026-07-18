"""Tests for the provider registry and the generic provider."""

from __future__ import annotations

import os

import pytest

from mediahub_engine.providers.base import ProviderError
from mediahub_engine.providers.generic import GenericProvider
from mediahub_engine.providers.registry import ProviderRegistry, get_registry


def test_generic_provider_matches_direct_media_urls() -> None:
    provider = GenericProvider()
    assert provider.matches("https://example.com/video.mp4")
    assert provider.matches("http://example.com/audio.mp3?token=abc")
    assert provider.matches("https://cdn.example.com/image.PNG")


def test_generic_provider_rejects_non_media_urls() -> None:
    provider = GenericProvider()
    assert not provider.matches("https://youtube.com/watch?v=abc")
    assert not provider.matches("https://example.com/page")
    assert not provider.matches("ftp://example.com/file.mp4")


@pytest.mark.asyncio
async def test_generic_provider_extract_metadata_derives_title() -> None:
    provider = GenericProvider()
    meta = await provider.extract_metadata("https://example.com/path/cool_video.mp4?x=1")
    assert meta.title == "cool_video.mp4"


@pytest.mark.asyncio
async def test_generic_provider_downloads_file(tmp_path: pytest.TempPathFactory) -> None:
    # Write a tiny local "remote" file and serve via file:// URL.
    src = tmp_path / "source.mp4"
    src.write_bytes(b"mediahub-test-bytes")

    provider = GenericProvider()
    dest_dir = str(tmp_path / "out")
    result = await provider.download(
        src.as_uri(),
        dest_dir=dest_dir,
        task_id="t1",
        sink=None,
    )
    assert os.path.exists(result.output_path)
    assert result.bytes_written == len(b"mediahub-test-bytes")


def test_registry_finds_matching_provider() -> None:
    registry = ProviderRegistry()
    registry.register(GenericProvider())
    provider = registry.find("https://example.com/clip.mp4")
    assert provider is not None
    assert provider.capability.name == "generic"


def test_registry_returns_none_for_unsupported_url() -> None:
    registry = ProviderRegistry()
    registry.register(GenericProvider())
    assert registry.find("https://youtube.com/watch?v=abc") is None


def test_registry_require_raises_provider_error() -> None:
    registry = ProviderRegistry()
    registry.register(GenericProvider())
    with pytest.raises(ProviderError) as exc_info:
        registry.require("https://youtube.com/watch?v=abc")
    assert exc_info.value.code == "PROVIDER_NOT_FOUND"


def test_registry_rejects_duplicate_names() -> None:
    registry = ProviderRegistry()
    registry.register(GenericProvider())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(GenericProvider())


def test_get_registry_is_singleton_and_bootstrapped() -> None:
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2
    assert "generic" in r1.names()

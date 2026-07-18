"""The provider registry.

Providers register themselves here at import time. The engine queries the
registry to find the best provider for a URL (first match wins, ordered by
registration; the generic provider is always last as the fallback).

Phase 2 adds the platform providers; each lives in its own module under
``providers/<platform>/`` and exposes a ``Provider`` subclass.
"""

from __future__ import annotations

from collections.abc import Iterable

from mediahub_engine.providers.base import Provider, ProviderError
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class ProviderRegistry:
    """Ordered registry of providers."""

    def __init__(self) -> None:
        self._providers: list[Provider] = []

    def register(self, provider: Provider) -> None:
        if any(p.capability.name == provider.capability.name for p in self._providers):
            raise ValueError(f"Provider already registered: {provider.capability.name}")
        self._providers.append(provider)
        log.info("registered provider: %s", provider)

    def providers(self) -> tuple[Provider, ...]:
        return tuple(self._providers)

    def find(self, url: str) -> Provider | None:
        """Returns the first provider whose [Provider.matches] returns True."""
        for provider in self._providers:
            try:
                if provider.matches(url):
                    return provider
            except Exception:
                log.exception("provider %s raised during match", provider)
        return None

    def require(self, url: str) -> Provider:
        """Like [find] but raises a [ProviderError] if none matches."""
        provider = self.find(url)
        if provider is None:
            raise ProviderError(
                "No provider supports this URL",
                code="PROVIDER_NOT_FOUND",
                details={"url": url},
            )
        return provider

    def by_name(self, name: str) -> Provider | None:
        for provider in self._providers:
            if provider.capability.name == name:
                return provider
        return None

    def names(self) -> tuple[str, ...]:
        return tuple(p.capability.name for p in self._providers)

    def describe(self) -> list[dict[str, object]]:
        """Returns capability descriptors for every provider (for the UI)."""
        out: list[dict[str, object]] = []
        for p in self._providers:
            c = p.capability
            out.append(
                {
                    "name": c.name,
                    "displayName": c.display_name or c.name.title(),
                    "engine": c.engine,
                    "authRequired": c.auth_required,
                    "maxBatch": c.max_batch,
                    "features": sorted(f.name for f in ProviderFeatureFlags.iter(c.features)),
                    "urlPatterns": list(c.url_patterns),
                }
            )
        return out


# ---------------------------------------------------------------------------
# ProviderFeature helper (avoid circular import with base.ProviderFeature)
# ---------------------------------------------------------------------------

from enum import Flag  # noqa: E402


class ProviderFeatureFlags:
    """Iterates the set bits of a [ProviderFeature] flag."""

    @staticmethod
    def iter(flag: Flag) -> Iterable[Flag]:
        for member in type(flag):
            if member.name is None or member.value == 0:
                continue
            if member & flag:
                yield member


# ---------------------------------------------------------------------------
# Singleton + bootstrap
# ---------------------------------------------------------------------------

_REGISTRY: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    """Returns the process-wide registry, populating it on first call."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ProviderRegistry()
        _bootstrap(_REGISTRY)
    return _REGISTRY


def reset_registry() -> None:
    """Clears the singleton. Used by tests to inject a fresh registry."""
    global _REGISTRY
    _REGISTRY = None


def _bootstrap(registry: ProviderRegistry) -> None:
    """Registers the built-in providers in priority order.

    Specialized platforms are registered first so they win URL detection over
    the generic fallback, which is always last.
    """
    # Local imports keep the module graph lazy and avoid import cycles.
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

    ordered: list[type[Provider]] = [
        YouTubeProvider,
        InstagramProvider,
        FacebookProvider,
        TikTokProvider,
        TwitterXProvider,
        RedditProvider,
        VimeoProvider,
        DailymotionProvider,
        PinterestProvider,
        TwitchProvider,
        SoundcloudProvider,
        ThreadsProvider,
        SnapchatProvider,
        # Fallback always last.
        GenericProvider,
    ]
    for provider_cls in ordered:
        try:
            registry.register(provider_cls())
        except Exception:
            log.exception("failed to register provider %s", provider_cls.__name__)


__all__ = ["ProviderFeatureFlags", "ProviderRegistry", "get_registry", "reset_registry"]

"""Registry of extraction backends, keyed by [EngineStrategy].

Process-singleton, populated on first access with the built-in backends.
Tests override via [reset_backend_registry] + manual population, or by
constructing a fresh [BackendRegistry] and passing it to providers.
"""

from __future__ import annotations

from mediahub_engine.download.strategy import EngineStrategy
from mediahub_engine.providers.backends.base import ExtractionBackend
from mediahub_engine.providers.backends.gallerydl import GalleryDlBackend
from mediahub_engine.providers.backends.instaloader import InstaloaderBackend
from mediahub_engine.providers.backends.ytdlp import YtDlpBackend
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class BackendRegistry:
    """Maps [EngineStrategy] -> [ExtractionBackend] instance."""

    def __init__(self) -> None:
        self._backends: dict[EngineStrategy, ExtractionBackend] = {}

    def register(self, backend: ExtractionBackend) -> None:
        strategy = backend.strategy
        if strategy in self._backends:
            raise ValueError(f"Backend already registered for {strategy}")
        self._backends[strategy] = backend
        log.info("registered backend: %s (available=%s)", strategy.value, backend.is_available())

    def get(self, strategy: EngineStrategy) -> ExtractionBackend:
        backend = self._backends.get(strategy)
        if backend is None:
            raise KeyError(f"No backend registered for {strategy}")
        return backend

    def get_or_none(self, strategy: EngineStrategy) -> ExtractionBackend | None:
        return self._backends.get(strategy)

    def strategies(self) -> tuple[EngineStrategy, ...]:
        return tuple(self._backends.keys())

    def available_strategies(self) -> tuple[EngineStrategy, ...]:
        return tuple(s for s, b in self._backends.items() if b.is_available())


_REGISTRY: BackendRegistry | None = None


def get_backend_registry() -> BackendRegistry:
    """Returns the process-wide backend registry, bootstrapping on first call."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = BackendRegistry()
        _bootstrap(_REGISTRY)
    return _REGISTRY


def reset_backend_registry() -> None:
    """Clears the singleton. Used by tests to inject a fresh registry."""
    global _REGISTRY
    _REGISTRY = None


def _bootstrap(registry: BackendRegistry) -> None:
    """Registers the built-in backends. Order is irrelevant; lookup is by key."""
    for backend_cls in (YtDlpBackend, GalleryDlBackend, InstaloaderBackend):
        try:
            registry.register(backend_cls())
        except Exception:
            log.exception("failed to register backend %s", backend_cls.__name__)


__all__ = [
    "BackendRegistry",
    "get_backend_registry",
    "reset_backend_registry",
]

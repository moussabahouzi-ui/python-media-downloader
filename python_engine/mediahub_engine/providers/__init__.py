"""Provider registry, base classes, backends, and platform modules."""

from mediahub_engine.providers.backends.base import (
    BackendNotAvailableError,
    ExtractionBackend,
    ExtractionResult,
)
from mediahub_engine.providers.backends.registry import (
    BackendRegistry,
    get_backend_registry,
    reset_backend_registry,
)
from mediahub_engine.providers.base import (
    Capability,
    Credential,
    CredentialStore,
    DownloadSink,
    FormatOption,
    InMemoryCredentialStore,
    MediaMetadata,
    Provider,
    ProviderError,
    ProviderFeature,
    ProviderResult,
)
from mediahub_engine.providers.delegate import BackendDelegateProvider
from mediahub_engine.providers.generic import GenericProvider
from mediahub_engine.providers.registry import ProviderRegistry, get_registry
from mediahub_engine.providers.strategy import EngineStrategy, pick_engine

__all__ = [
    "BackendDelegateProvider",
    "BackendNotAvailableError",
    "BackendRegistry",
    "Capability",
    "Credential",
    "CredentialStore",
    "DownloadSink",
    "EngineStrategy",
    "ExtractionBackend",
    "ExtractionResult",
    "FormatOption",
    "GenericProvider",
    "InMemoryCredentialStore",
    "MediaMetadata",
    "Provider",
    "ProviderError",
    "ProviderFeature",
    "ProviderRegistry",
    "ProviderResult",
    "get_backend_registry",
    "get_registry",
    "pick_engine",
    "reset_backend_registry",
]

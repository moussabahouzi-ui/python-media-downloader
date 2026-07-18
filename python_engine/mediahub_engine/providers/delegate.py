"""[BackendDelegateProvider] — the common base for platform providers.

Most providers do not implement extraction/download themselves; they declare a
[Capability], pick a [EngineStrategy] backend, and delegate. This base factors
out that boilerplate so each platform module is a few dozen lines.

Providers that need bespoke logic (e.g. the generic HTTP provider) continue to
subclass [Provider] directly.
"""

from __future__ import annotations

from typing import Any

from mediahub_engine.engine_kinds import EngineStrategy
from mediahub_engine.providers.backends.base import (
    BackendNotAvailableError,
    ExtractionResult,
)
from mediahub_engine.providers.backends.registry import BackendRegistry, get_backend_registry
from mediahub_engine.providers.base import (
    Credential,
    CredentialStore,
    DownloadSink,
    InMemoryCredentialStore,
    MediaMetadata,
    Provider,
    ProviderResult,
)
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class BackendDelegateProvider(Provider):
    """A [Provider] that delegates to an [ExtractionBackend]."""

    #: Subclasses set this to their preferred backend strategy.
    backend_strategy: EngineStrategy

    def __init__(
        self,
        backends: BackendRegistry | None = None,
        credentials: CredentialStore | None = None,
    ) -> None:
        super().__init__()
        if not hasattr(type(self), "backend_strategy"):
            raise TypeError(
                f"{type(self).__name__} must set a class-level `backend_strategy`",
            )
        self._backends = backends or get_backend_registry()
        self._credentials = credentials or InMemoryCredentialStore()

    # ---- credential access ----

    @property
    def credentials(self) -> CredentialStore:
        return self._credentials

    def credential(self) -> Credential | None:
        return self._credentials.get(self.capability.name)

    # ---- backend access ----

    def _backend(self):
        try:
            return self._backends.get(self.backend_strategy)
        except KeyError as exc:
            raise BackendNotAvailableError(self.backend_strategy) from exc

    # ---- Provider contract ----

    async def extract_metadata(self, url: str) -> MediaMetadata:
        backend = self._backend()
        if not backend.is_available():
            raise BackendNotAvailableError(self.backend_strategy)
        opts = self._metadata_options(url)
        result = await backend.extract_metadata(url, options=opts)
        return self._normalize_metadata(result.metadata, result)

    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ProviderResult:
        backend = self._backend()
        if not backend.is_available():
            raise BackendNotAvailableError(self.backend_strategy)
        opts = self._download_options(url, options)
        result: ExtractionResult = await backend.download(
            url,
            dest_dir=dest_dir,
            task_id=task_id,
            sink=sink,
            options=opts,
        )
        return ProviderResult(
            output_paths=list(result.output_paths),
            bytes_written=result.bytes_written,
            metadata=self._normalize_metadata(result.metadata, result),
            formats=list(result.formats),
            warnings=list(result.warnings),
        )

    # ---- hooks for subclasses ----

    def _metadata_options(self, url: str) -> dict[str, Any]:
        """Options passed to the backend for metadata extraction."""
        opts: dict[str, Any] = {}
        cred = self.credential()
        if cred:
            _inject_credential(opts, cred)
        return opts

    def _download_options(self, url: str, caller_options: dict[str, Any] | None) -> dict[str, Any]:
        """Options passed to the backend for download."""
        opts: dict[str, Any] = {}
        cred = self.credential()
        if cred:
            _inject_credential(opts, cred)
        if caller_options:
            opts.update(caller_options)
        return opts

    def _normalize_metadata(
        self, metadata: MediaMetadata, result: ExtractionResult
    ) -> MediaMetadata:
        """Hook to post-process backend metadata. Default is identity."""
        return metadata


def _inject_credential(opts: dict[str, Any], cred: Credential) -> None:
    if cred.username:
        opts["username"] = cred.username
    if cred.password:
        opts["password"] = cred.password
    if cred.cookies_path:
        opts["cookiefile"] = cred.cookies_path
    if cred.session_path:
        opts["sessionfile"] = cred.session_path
    if cred.token:
        opts.setdefault("extra", {})["token"] = cred.token


__all__ = [
    "BackendDelegateProvider",
    "BackendNotAvailableError",
    "ExtractionResult",
]

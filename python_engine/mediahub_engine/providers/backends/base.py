"""The extraction backend abstraction.

A [ExtractionBackend] wraps a single concrete extraction engine and exposes a
uniform async API. Providers delegate to a backend chosen via their
[Capability.engine] and the [BackendRegistry].

Backends MUST:

- lazy-import their underlying library (so the engine boots without it),
- run all blocking library calls in a [ThreadPoolExecutor] (engines are sync),
- report availability via [is_available],
- raise [BackendNotAvailableError] when invoked while unavailable.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from mediahub_engine.engine_kinds import EngineStrategy
from mediahub_engine.providers.base import DownloadSink, FormatOption, MediaMetadata
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class BackendNotAvailableError(Exception):
    """Raised when a backend's underlying library is not importable."""

    def __init__(self, engine: EngineStrategy) -> None:
        super().__init__(f"Extraction backend not available: {engine.value}")
        self.engine = engine


@dataclass
class ExtractionResult:
    """Normalized output of an extraction/download operation."""

    metadata: MediaMetadata
    output_paths: list[str] = field(default_factory=list)
    bytes_written: int = 0
    formats: list[FormatOption] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class ExtractionBackend(abc.ABC):
    """Base class every backend implements."""

    #: The [EngineStrategy] this backend serves.
    strategy: EngineStrategy

    @abc.abstractmethod
    def is_available(self) -> bool:
        """`True` iff the underlying library can be imported."""

    @abc.abstractmethod
    async def extract_metadata(
        self,
        url: str,
        *,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Fetches metadata for `url` without downloading media."""

    @abc.abstractmethod
    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Downloads media for `url` into `dest_dir`."""


__all__ = [
    "BackendNotAvailableError",
    "ExtractionBackend",
    "ExtractionResult",
    "FormatOption",
]

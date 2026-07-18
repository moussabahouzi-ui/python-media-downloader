"""Shared test fixtures for provider/backend tests."""

from __future__ import annotations

from typing import Any

import pytest

from mediahub_engine.engine_kinds import EngineStrategy
from mediahub_engine.providers.backends.base import (
    BackendNotAvailableError,
    ExtractionBackend,
    ExtractionResult,
)
from mediahub_engine.providers.backends.registry import (
    BackendRegistry,
    reset_backend_registry,
)
from mediahub_engine.providers.base import (
    DownloadSink,
    FormatOption,
    MediaMetadata,
)
from mediahub_engine.providers.registry import reset_registry


class FakeBackend(ExtractionBackend):
    """A controllable in-memory backend for provider tests.

    Records every call and returns canned [ExtractionResult]s. Optional
    `raise_on` lets a test simulate a backend failure.
    """

    def __init__(
        self,
        strategy: EngineStrategy,
        *,
        metadata: MediaMetadata | None = None,
        formats: list[FormatOption] | None = None,
        output_paths: list[str] | None = None,
        bytes_written: int = 0,
        raise_on: str | None = None,
        available: bool = True,
    ) -> None:
        self.strategy = strategy
        self._metadata = metadata or MediaMetadata(title="fake-title", uploader="fake-uploader")
        self._formats = formats or []
        self._output_paths = output_paths or ["/tmp/fake-out.mp4"]
        self._bytes_written = bytes_written or 1024
        self._raise_on = raise_on
        self._available = available
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def is_available(self) -> bool:
        return self._available

    async def extract_metadata(
        self,
        url: str,
        *,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        self.calls.append(("extract_metadata", url, options or {}))
        if self._raise_on == "extract":
            raise BackendNotAvailableError(self.strategy)
        return ExtractionResult(metadata=self._metadata, formats=self._formats, raw={"url": url})

    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        self.calls.append(
            ("download", url, {"dest_dir": dest_dir, "task_id": task_id, **(options or {})})
        )
        if self._raise_on == "download":
            raise BackendNotAvailableError(self.strategy)
        if sink is not None:
            sink.on_progress(
                task_id=task_id,
                percent=100.0,
                bytes_done=self._bytes_written,
                total_bytes=self._bytes_written,
            )
        return ExtractionResult(
            metadata=self._metadata,
            formats=self._formats,
            output_paths=list(self._output_paths),
            bytes_written=self._bytes_written,
            raw={"url": url, "task_id": task_id},
        )


class NullSink:
    """A no-op [DownloadSink] for tests that don't care about progress."""

    def on_progress(
        self, *, task_id: str, percent: float, bytes_done: int, total_bytes: int | None
    ) -> None:
        pass

    def on_log(self, message: str) -> None:
        pass


@pytest.fixture(autouse=True)
def _reset_registries():
    """Ensure every test starts with a clean provider + backend registry."""
    reset_registry()
    reset_backend_registry()
    yield
    reset_registry()
    reset_backend_registry()


def build_registry_with(*backends: ExtractionBackend) -> BackendRegistry:
    """Returns a fresh [BackendRegistry] pre-populated with `backends`."""
    reg = BackendRegistry()
    for b in backends:
        reg.register(b)
    return reg


@pytest.fixture
def null_sink() -> NullSink:
    return NullSink()

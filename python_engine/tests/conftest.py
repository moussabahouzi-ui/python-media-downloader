"""Shared pytest fixtures."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest

from mediahub_engine.ipc.jsonrpc import RpcDispatcher
from mediahub_engine.providers.backends.registry import reset_backend_registry
from mediahub_engine.providers.registry import reset_registry


@pytest.fixture(autouse=True)
def _reset_provider_registries():
    """Ensure every test starts with clean provider + backend singletons.

    The singletons are rebuilt lazily on first access, so tests that need the
    real registry still get it; tests that inject fakes don't see leftover
    state from a previous test.
    """
    reset_registry()
    reset_backend_registry()
    yield
    reset_registry()
    reset_backend_registry()


@pytest.fixture
def dispatcher() -> RpcDispatcher:
    return RpcDispatcher()


@pytest.fixture
def captured_notifications() -> tuple[list[tuple[str, dict]], callable]:
    """Returns a (list, sink) pair recording every emitted notification."""
    events: list[tuple[str, dict]] = []

    def sink(method: str, params: dict) -> None:
        events.append((method, params))

    return events, sink


@pytest.fixture
def stdout_buffer() -> Iterator[io.StringIO]:
    buf = io.StringIO()
    yield buf

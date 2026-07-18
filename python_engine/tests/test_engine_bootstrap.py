"""Tests for engine bootstrap: config resolution + handler registration."""

from __future__ import annotations

import pytest

from mediahub_engine import __version__
from mediahub_engine.config import EngineConfig
from mediahub_engine.engine import BRIDGE_VERSION, Engine


def test_version_is_set() -> None:
    assert __version__ == "0.1.0"


def test_bridge_version_matches_contract() -> None:
    # Mirrors the Dart (kBridgeVersion) and Kotlin (BRIDGE_VERSION) constants.
    assert BRIDGE_VERSION == 1


def test_engine_registers_phase1_methods() -> None:
    engine = Engine(config=EngineConfig(work_dir=_tmp_workdir()))
    methods = set(engine.dispatcher.methods)
    assert {"engine.ping", "engine.version", "engine.shutdown"}.issubset(methods)


@pytest.mark.asyncio
async def test_engine_ping_returns_version() -> None:
    engine = Engine(config=EngineConfig(work_dir=_tmp_workdir()))
    result = await engine._ping({})
    assert result == {"pong": True, "version": __version__}


@pytest.mark.asyncio
async def test_engine_version_returns_cross_layer_info() -> None:
    engine = Engine(config=EngineConfig(work_dir=_tmp_workdir()))
    result = await engine._version({})
    assert result["app"] == __version__
    assert result["engine"] == __version__
    assert result["bridgeVersion"] == BRIDGE_VERSION


@pytest.mark.asyncio
async def test_engine_shutdown_sets_stop_event() -> None:
    engine = Engine(config=EngineConfig(work_dir=_tmp_workdir()))
    result = await engine._shutdown({})
    assert result == {"stopped": True}
    assert engine._stop.is_set()


def test_engine_config_reads_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("MEDIAHUB_WORKDIR", str(tmp_path / "eng"))
    monkeypatch.setenv("MEDIAHUB_MAX_CONCURRENT", "8")
    monkeypatch.setenv("MEDIAHUB_PROGRESS_INTERVAL", "0.5")
    cfg = EngineConfig.from_env()
    assert cfg.work_dir == tmp_path / "eng"
    assert cfg.max_concurrent_downloads == 8
    assert cfg.progress_emit_interval == 0.5


def test_engine_config_rejects_invalid_concurrency(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("MEDIAHUB_WORKDIR", str(tmp_path))
    monkeypatch.setenv("MEDIAHUB_MAX_CONCURRENT", "0")
    cfg = EngineConfig.from_env()
    # 0 is clamped to the minimum (1).
    assert cfg.max_concurrent_downloads == 1


def _tmp_workdir() -> object:
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp(prefix="mediahub-test-"))

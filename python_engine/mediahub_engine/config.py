"""Frozen runtime configuration for the MediaHub engine.

Resolved once at startup from environment variables (set by the Android host)
and never mutated. Keeping it immutable makes the engine trivially testable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EngineConfig:
    """Immutable engine configuration."""

    work_dir: Path
    """Scratch directory for partial files, engine state, etc."""

    max_concurrent_downloads: int = 4
    """Maximum number of concurrently active download tasks."""

    progress_emit_interval: float = 0.25
    """Minimum seconds between progress notifications for a single task (4 Hz)."""

    call_timeout: float = 30.0
    """Default per-call timeout for synchronous engine methods."""

    persist_downloads: bool = True
    """Whether to persist download tasks to SQLite for restart recovery."""

    max_retries: int = 3
    """Maximum retry attempts per download task."""

    retry_base_delay: float = 1.0
    """Base delay (seconds) for exponential backoff."""

    retry_max_delay: float = 60.0
    """Cap (seconds) for backoff delay."""

    @property
    def db_path(self) -> Path:
        """Path to the SQLite database file."""
        return self.work_dir / "mediahub.db"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> EngineConfig:
        """Builds a config from the process environment.

        Recognized variables (all optional):

        - ``MEDIAHUB_WORKDIR`` — working directory (defaults to a temp dir).
        - ``MEDIAHUB_MAX_CONCURRENT`` — max concurrent downloads.
        - ``MEDIAHUB_PROGRESS_INTERVAL`` — progress emit interval (seconds).
        - ``MEDIAHUB_PERSIST_DOWNLOADS`` — "0"/"false" disables SQLite persistence.
        - ``MEDIAHUB_MAX_RETRIES`` — max retry attempts per task.
        """
        env = env if env is not None else dict(os.environ)

        work_dir = Path(env.get("MEDIAHUB_WORKDIR", _default_workdir()))
        work_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            work_dir=work_dir,
            max_concurrent_downloads=_int(
                env.get("MEDIAHUB_MAX_CONCURRENT"),
                default=4,
                minimum=1,
            ),
            progress_emit_interval=_float(
                env.get("MEDIAHUB_PROGRESS_INTERVAL"),
                default=0.25,
                minimum=0.05,
            ),
            persist_downloads=_bool(env.get("MEDIAHUB_PERSIST_DOWNLOADS"), default=True),
            max_retries=_int(env.get("MEDIAHUB_MAX_RETRIES"), default=3, minimum=0),
            retry_base_delay=_float(env.get("MEDIAHUB_RETRY_BASE_DELAY"), default=1.0, minimum=0.1),
            retry_max_delay=_float(env.get("MEDIAHUB_RETRY_MAX_DELAY"), default=60.0, minimum=1.0),
        )


def _default_workdir() -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / "mediahub-engine"


def _int(raw: str | None, *, default: int, minimum: int) -> int:
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _float(raw: str | None, *, default: float, minimum: float) -> float:
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _bool(raw: str | None, *, default: bool) -> bool:
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")

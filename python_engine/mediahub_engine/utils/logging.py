"""Structured logging for the MediaHub engine.

All output goes to **stderr**. stdout is reserved exclusively for JSON-RPC.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class _StderrFormatter(logging.Formatter):
    """Emits one JSON object per log line to stderr."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: int = logging.INFO) -> None:
    """Configures the root logger to write structured JSON to stderr.

    Idempotent: safe to call multiple times.
    """
    root = logging.getLogger()
    if getattr(root, "_mediahub_configured", False):
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_StderrFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    root._mediahub_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]

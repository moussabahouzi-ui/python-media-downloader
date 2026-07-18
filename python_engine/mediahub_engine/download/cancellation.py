"""Cancellation tokens for interrupting running downloads.

A [CancellationToken] is a lightweight [asyncio.Event] wrapper that providers
and the manager cooperatively check. When a user pauses or cancels a task, the
manager sets the token; the running download coroutine sees the cancellation
and aborts cleanly, leaving partial files on disk for resume.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


class CancellationToken:
    """A cooperative cancellation primitive.

    The manager creates one per task run and passes it to the download sink.
    The sink checks [is_cancelled] between progress updates and raises
    [DownloadCancelled] if set. The manager also wraps the provider call in an
    [asyncio.Task] and cancels it for hard interruption.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def reset(self) -> None:
        self._event.clear()


class DownloadCancelled(Exception):
    """Raised when a download is cancelled or paused mid-flight."""

    def __init__(self, reason: str = "cancelled") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class CancellationTokenSource:
    """Owns a [CancellationToken] and tracks whether cancellation was for
    pause or cancel, so the manager can transition state correctly."""

    token: CancellationToken = field(default_factory=CancellationToken)
    reason: str | None = None  # "pause" | "cancel" | None

    def pause(self) -> None:
        self.reason = "pause"
        self.token.cancel()

    def cancel(self) -> None:
        self.reason = "cancel"
        self.token.cancel()

    def reset(self) -> None:
        self.reason = None
        self.token.reset()


__all__ = ["CancellationToken", "CancellationTokenSource", "DownloadCancelled"]

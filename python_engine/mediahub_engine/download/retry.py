"""Retry policy with exponential backoff + jitter.

A [RetryPolicy] decides whether a failed task should be retried and, if so,
after how many seconds. Policies are pure value objects; the [DownloadManager]
applies them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff retry policy.

    Delay for attempt *n* (0-indexed) is::

        min(base_delay * (multiplier ** n), max_delay) + jitter()

    where ``jitter()`` is a uniform random value in ``[0, jitter)``.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    multiplier: float = 2.0
    max_delay: float = 60.0
    jitter: float = 0.5

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be > 0")
        if self.multiplier < 1.0:
            raise ValueError("multiplier must be >= 1.0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if self.jitter < 0:
            raise ValueError("jitter must be >= 0")

    def should_retry(self, retries_so_far: int) -> bool:
        """Returns True if the task has remaining retry budget."""
        return retries_so_far < self.max_retries

    def delay_for(self, attempt: int) -> float:
        """Returns the backoff delay (seconds) for the given attempt index.

        ``attempt`` is 0-indexed: the first retry (attempt 0) uses ``base_delay``.
        """
        if attempt < 0:
            return 0.0
        raw = self.base_delay * (self.multiplier**attempt)
        capped = min(raw, self.max_delay)
        jitter = random.uniform(0, self.jitter) if self.jitter > 0 else 0.0
        return round(capped + jitter, 3)


#: Default policy used by the manager when none is configured.
DEFAULT_RETRY_POLICY = RetryPolicy()


__all__ = ["DEFAULT_RETRY_POLICY", "RetryPolicy"]

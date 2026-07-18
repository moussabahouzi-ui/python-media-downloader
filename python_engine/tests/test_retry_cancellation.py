"""Tests for the retry policy + backoff and cancellation tokens."""

from __future__ import annotations

import pytest

from mediahub_engine.download.cancellation import (
    CancellationToken,
    CancellationTokenSource,
    DownloadCancelled,
)
from mediahub_engine.download.retry import DEFAULT_RETRY_POLICY, RetryPolicy

# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


def test_default_policy_allows_3_retries() -> None:
    policy = DEFAULT_RETRY_POLICY
    assert policy.should_retry(0) is True
    assert policy.should_retry(1) is True
    assert policy.should_retry(2) is True
    assert policy.should_retry(3) is False


def test_custom_policy_zero_retries() -> None:
    policy = RetryPolicy(max_retries=0)
    assert policy.should_retry(0) is False


def test_delay_for_exponential_growth() -> None:
    policy = RetryPolicy(max_retries=5, base_delay=1.0, multiplier=2.0, max_delay=100.0, jitter=0.0)
    assert policy.delay_for(0) == 1.0
    assert policy.delay_for(1) == 2.0
    assert policy.delay_for(2) == 4.0
    assert policy.delay_for(3) == 8.0


def test_delay_capped_at_max() -> None:
    policy = RetryPolicy(
        max_retries=10, base_delay=1.0, multiplier=10.0, max_delay=50.0, jitter=0.0
    )
    assert policy.delay_for(0) == 1.0
    assert policy.delay_for(1) == 10.0
    assert policy.delay_for(2) == 50.0  # capped
    assert policy.delay_for(3) == 50.0  # still capped


def test_delay_includes_jitter() -> None:
    policy = RetryPolicy(max_retries=3, base_delay=10.0, multiplier=1.0, max_delay=10.0, jitter=2.0)
    delay = policy.delay_for(0)
    assert 10.0 <= delay <= 12.0


def test_policy_validation_rejects_bad_values() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=-1)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=-1)
    with pytest.raises(ValueError):
        RetryPolicy(multiplier=0.5)
    with pytest.raises(ValueError):
        RetryPolicy(max_delay=0.5, base_delay=1.0)
    with pytest.raises(ValueError):
        RetryPolicy(jitter=-1)


# ---------------------------------------------------------------------------
# CancellationToken
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_starts_not_cancelled() -> None:
    token = CancellationToken()
    assert token.is_cancelled() is False


@pytest.mark.asyncio
async def test_token_cancel_sets_event() -> None:
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled() is True


@pytest.mark.asyncio
async def test_token_reset_clears_event() -> None:
    token = CancellationToken()
    token.cancel()
    token.reset()
    assert token.is_cancelled() is False


@pytest.mark.asyncio
async def test_token_wait_returns_after_cancel() -> None:
    token = CancellationToken()
    token.cancel()
    await token.wait()  # should return immediately


def test_source_pause_sets_reason() -> None:
    source = CancellationTokenSource()
    source.pause()
    assert source.reason == "pause"
    assert source.token.is_cancelled() is True


def test_source_cancel_sets_reason() -> None:
    source = CancellationTokenSource()
    source.cancel()
    assert source.reason == "cancel"
    assert source.token.is_cancelled() is True


def test_source_reset_clears_reason() -> None:
    source = CancellationTokenSource()
    source.pause()
    source.reset()
    assert source.reason is None
    assert source.token.is_cancelled() is False


def test_download_cancelled_carries_reason() -> None:
    exc = DownloadCancelled("pause")
    assert exc.reason == "pause"

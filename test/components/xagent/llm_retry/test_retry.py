from datetime import datetime, timezone
from random import Random

from xagent.llm_config import RetryConfig
from xagent.llm_retry import backoff_delay, is_retryable_status, parse_retry_after


def test_retryable_status_classifier() -> None:
    assert is_retryable_status(429)
    assert is_retryable_status(409, provider_transient=True)
    assert not is_retryable_status(409)
    assert not is_retryable_status(400)


def test_parse_retry_after_seconds() -> None:
    assert parse_retry_after("3") == 3.0


def test_parse_retry_after_http_date() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert parse_retry_after("Thu, 01 Jan 2026 00:00:05 GMT", now=now) == 5.0


def test_backoff_delay_without_jitter() -> None:
    config = RetryConfig(jitter=False, initial_delay_seconds=1, multiplier=2)

    assert backoff_delay(3, config) == 4


def test_backoff_delay_with_jitter_is_bounded() -> None:
    config = RetryConfig(jitter=True, initial_delay_seconds=10)

    assert 0 <= backoff_delay(1, config, rng=Random(1)) <= 10

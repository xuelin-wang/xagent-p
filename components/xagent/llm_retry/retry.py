import email.utils
import random
from datetime import datetime, timezone

from xagent.llm_config import RetryConfig


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable_status(status_code: int, *, provider_transient: bool = False) -> bool:
    if status_code == 409:
        return provider_transient
    return status_code in RETRYABLE_STATUS_CODES


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    if not value:
        return None
    stripped = value.strip()
    try:
        return max(float(stripped), 0.0)
    except ValueError:
        pass
    parsed = email.utils.parsedate_to_datetime(stripped)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return max((parsed - current).total_seconds(), 0.0)


def backoff_delay(
    attempt: int,
    config: RetryConfig,
    *,
    retry_after: float | None = None,
    rng: random.Random | None = None,
) -> float:
    if config.respect_retry_after and retry_after is not None:
        return min(retry_after, config.max_delay_seconds)

    delay = config.initial_delay_seconds * (config.multiplier ** max(attempt - 1, 0))
    delay = min(delay, config.max_delay_seconds)
    if config.jitter:
        generator = rng or random
        delay = generator.uniform(0, delay)
    return delay

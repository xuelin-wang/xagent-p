import email.utils
import asyncio
import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import TypeVar

from xagent.llm_config import RetryConfig

T = TypeVar("T")


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


async def retry_async(
    call: Callable[[], Awaitable[T]],
    config: RetryConfig,
    *,
    should_retry_result: Callable[[T], bool] | None = None,
    retry_after_from_result: Callable[[T], float | None] | None = None,
    should_retry_exception: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    attempts = max(config.max_attempts, 1)
    for attempt in range(1, attempts + 1):
        try:
            result = await call()
        except Exception as exc:
            if (
                not config.enabled
                or attempt >= attempts
                or should_retry_exception is None
                or not should_retry_exception(exc)
            ):
                raise
            await sleep(backoff_delay(attempt, config))
            continue

        if (
            config.enabled
            and attempt < attempts
            and should_retry_result is not None
            and should_retry_result(result)
        ):
            retry_after = retry_after_from_result(result) if retry_after_from_result else None
            await sleep(backoff_delay(attempt, config, retry_after=retry_after))
            continue
        return result

    raise RuntimeError("retry_async exhausted attempts unexpectedly.")

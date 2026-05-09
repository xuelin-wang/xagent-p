import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from xagent.llm_config import PollingConfig

T = TypeVar("T")


async def poll_until(
    fetch: Callable[[], Awaitable[T]],
    is_done: Callable[[T], bool],
    config: PollingConfig,
) -> T:
    started = time.monotonic()
    interval = config.initial_interval_seconds
    while True:
        value = await fetch()
        if is_done(value):
            return value
        if config.timeout_seconds is not None and time.monotonic() - started >= config.timeout_seconds:
            return value
        await asyncio.sleep(interval)
        interval = min(interval * 2, config.max_interval_seconds)

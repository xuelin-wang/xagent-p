import asyncio

from xagent.llm_batch import poll_until
from xagent.llm_config import PollingConfig


async def _test_poll_until() -> None:
    values = iter([1, 2, 3])

    async def fetch() -> int:
        return next(values)

    result = await poll_until(
        fetch,
        lambda value: value == 3,
        PollingConfig(initial_interval_seconds=0, max_interval_seconds=0),
    )

    assert result == 3


def test_poll_until() -> None:
    asyncio.run(_test_poll_until())

import httpx

from xagent.llm_config import TimeoutConfig
from xagent.llm_retry import to_httpx_timeout


def test_to_httpx_timeout() -> None:
    timeout = to_httpx_timeout(TimeoutConfig(connect=1, read=2, write=3, pool=4))

    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 1
    assert timeout.read == 2

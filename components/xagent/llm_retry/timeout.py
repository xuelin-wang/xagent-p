import httpx

from xagent.llm_config import TimeoutConfig


def to_httpx_timeout(config: TimeoutConfig) -> httpx.Timeout:
    return httpx.Timeout(
        connect=config.connect,
        read=config.read,
        write=config.write,
        pool=config.pool,
    )

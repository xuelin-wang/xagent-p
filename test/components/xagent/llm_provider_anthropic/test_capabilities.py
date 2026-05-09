import asyncio

import pytest

from xagent.llm_batch import EmbeddingRequest
from xagent.llm_config import ProviderConfig
from xagent.llm_contracts import Capability, UnsupportedCapabilityError
from xagent.llm_provider_anthropic import AnthropicProvider


def test_anthropic_capabilities() -> None:
    provider = AnthropicProvider(ProviderConfig(provider="anthropic", default_model="claude-sonnet-4-6"))

    capabilities = provider.capabilities()

    assert Capability.TEXT_GENERATION in capabilities.capabilities
    assert Capability.STRUCTURED_OUTPUT in capabilities.capabilities
    assert Capability.APP_TOOL_CALLS in capabilities.capabilities
    assert Capability.PROVIDER_HOSTED_TOOLS in capabilities.capabilities
    assert Capability.FILE_UPLOAD in capabilities.capabilities
    assert Capability.FILE_INPUT in capabilities.capabilities
    assert Capability.NATIVE_BATCH in capabilities.capabilities
    assert Capability.CONCURRENT_BATCH in capabilities.capabilities
    assert Capability.EMBEDDINGS not in capabilities.capabilities
    assert "web_search" in capabilities.provider_tools


async def _test_anthropic_embed_raises_unsupported() -> None:
    provider = AnthropicProvider(ProviderConfig(provider="anthropic", default_model="claude-sonnet-4-6"))

    with pytest.raises(UnsupportedCapabilityError):
        await provider.embed(EmbeddingRequest(inputs=["hello"]))


def test_anthropic_embed_raises_unsupported() -> None:
    asyncio.run(_test_anthropic_embed_raises_unsupported())

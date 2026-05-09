from xagent.llm_config import ProviderConfig
from xagent.llm_contracts import Capability
from xagent.llm_provider_openai import OpenAIProvider


def test_openai_capabilities() -> None:
    provider = OpenAIProvider(ProviderConfig(provider="openai", default_model="gpt-5.5"))

    capabilities = provider.capabilities()

    assert Capability.TEXT_GENERATION in capabilities.capabilities
    assert Capability.STRUCTURED_OUTPUT in capabilities.capabilities
    assert Capability.APP_TOOL_CALLS in capabilities.capabilities
    assert Capability.PROVIDER_HOSTED_TOOLS in capabilities.capabilities
    assert Capability.MIXED_APP_AND_PROVIDER_TOOLS in capabilities.capabilities
    assert Capability.FILE_UPLOAD in capabilities.capabilities
    assert Capability.FILE_INPUT in capabilities.capabilities
    assert Capability.CONCURRENT_BATCH in capabilities.capabilities
    assert Capability.EMBEDDINGS in capabilities.capabilities
    assert "web_search" in capabilities.provider_tools
    assert "file_search" in capabilities.provider_tools

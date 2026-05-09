from xagent.llm_config import ProviderConfig
from xagent.llm_registry import LLMClientFactory, ProviderRegistry, default_registry


class DummyProvider:
    provider_name = "dummy"

    def __init__(self, config: ProviderConfig):
        self.config = config


def test_factory_uses_injected_registry() -> None:
    registry = ProviderRegistry()
    registry.register("openai", DummyProvider)

    provider = LLMClientFactory(registry).create(ProviderConfig(provider="openai", default_model="m"))

    assert isinstance(provider, DummyProvider)


def test_default_registry_contains_builtin_skeletons() -> None:
    assert default_registry().list_providers() == ["anthropic", "openai"]

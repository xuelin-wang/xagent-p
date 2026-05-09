import pytest

from xagent.llm_config import ProviderConfig
from xagent.llm_registry import ProviderRegistry


class DummyProvider:
    provider_name = "dummy"

    def __init__(self, config: ProviderConfig):
        self.config = config


def test_registry_create() -> None:
    registry = ProviderRegistry()
    registry.register("openai", DummyProvider)

    provider = registry.create("openai", ProviderConfig(provider="openai", default_model="m"))

    assert isinstance(provider, DummyProvider)
    assert registry.list_providers() == ["openai"]


def test_registry_unknown_provider() -> None:
    registry = ProviderRegistry()

    with pytest.raises(ValueError):
        registry.create("openai", ProviderConfig(provider="openai", default_model="m"))

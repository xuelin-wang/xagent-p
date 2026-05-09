import os
from typing import Literal

from xagent.llm_config import ProviderConfig
from xagent.llm_registry.provider_protocol import LLMProvider
from xagent.llm_registry.registry import ProviderRegistry


DEFAULT_MODELS = {
    "openai": "gpt-5.5",
    "anthropic": "claude-sonnet-4-6",
}


def default_registry() -> ProviderRegistry:
    from xagent.llm_provider_anthropic import AnthropicProvider
    from xagent.llm_provider_openai import OpenAIProvider

    registry = ProviderRegistry()
    registry.register("openai", OpenAIProvider)
    registry.register("anthropic", AnthropicProvider)
    return registry


class LLMClientFactory:
    def __init__(self, registry: ProviderRegistry | None = None):
        self.registry = registry or default_registry()

    def create(self, config: ProviderConfig) -> LLMProvider:
        return self.registry.create(config.provider, config)

    def from_env(
        self,
        provider: Literal["openai", "anthropic"],
        model: str | None = None,
    ) -> LLMProvider:
        return self.create(
            ProviderConfig(
                provider=provider,
                default_model=model or DEFAULT_MODELS[provider],
                api_key_env=os.environ.get(f"{provider.upper()}_API_KEY_ENV"),
            )
        )

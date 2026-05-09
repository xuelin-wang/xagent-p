from xagent.llm_config import ProviderConfig
from xagent.llm_registry.provider_protocol import LLMProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, type[LLMProvider]] = {}

    def register(self, name: str, provider_cls: type[LLMProvider]) -> None:
        self._providers[name] = provider_cls

    def create(self, name: str, config: ProviderConfig) -> LLMProvider:
        try:
            provider_cls = self._providers[name]
        except KeyError as exc:
            raise ValueError(f"Unknown LLM provider: {name}") from exc
        return provider_cls(config)

    def list_providers(self) -> list[str]:
        return sorted(self._providers)

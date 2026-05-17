from pydantic import SecretStr

from xagent.llm_config.settings import DEFAULT_API_KEY_ENV, ProviderConfig


def resolve_api_key(config: ProviderConfig) -> SecretStr | None:
    return config.api_key


def require_api_key(config: ProviderConfig) -> SecretStr:
    api_key = config.api_key
    if api_key is None:
        env_name = DEFAULT_API_KEY_ENV.get(config.provider)
        raise ValueError(
            f"Missing API key for provider '{config.provider}' via {env_name}."
        )
    return api_key

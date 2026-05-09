import os

from pydantic import SecretStr

from xagent.llm_config.settings import ProviderConfig


DEFAULT_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def resolve_api_key(config: ProviderConfig) -> SecretStr | None:
    if config.api_key is not None:
        return config.api_key
    env_name = config.api_key_env or DEFAULT_API_KEY_ENV.get(config.provider)
    if env_name is None:
        return None
    value = os.environ.get(env_name)
    return SecretStr(value) if value else None


def require_api_key(config: ProviderConfig) -> SecretStr:
    api_key = resolve_api_key(config)
    if api_key is None:
        env_name = config.api_key_env or DEFAULT_API_KEY_ENV.get(config.provider)
        raise ValueError(f"Missing API key for provider '{config.provider}' via {env_name}.")
    return api_key

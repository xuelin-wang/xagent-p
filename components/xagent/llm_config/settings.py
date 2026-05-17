from __future__ import annotations

import os
from typing import Literal

from pydantic import Field, SecretStr, model_validator

from xagent.config import StrictConfigModel

DEFAULT_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class TimeoutConfig(StrictConfigModel):
    connect: float = 10.0
    read: float = 120.0
    write: float = 30.0
    pool: float = 10.0


class RetryConfig(StrictConfigModel):
    enabled: bool = True
    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 20.0
    multiplier: float = 2.0
    jitter: bool = True
    respect_retry_after: bool = True


class PollingConfig(StrictConfigModel):
    initial_interval_seconds: float = 2.0
    max_interval_seconds: float = 60.0
    timeout_seconds: float | None = None


def provider_api_key_env(provider: str) -> str | None:
    return DEFAULT_API_KEY_ENV.get(provider)


def validate_provider_api_key_env_var(
    config_type: type[ProviderConfig],
) -> None:
    provider_field = config_type.model_fields.get("provider")
    api_key_field = config_type.model_fields.get("api_key")
    provider = provider_field.default if provider_field is not None else None
    if not isinstance(provider, str):
        return

    expected = DEFAULT_API_KEY_ENV.get(provider)
    if expected is None:
        return

    extra = api_key_field.json_schema_extra if api_key_field is not None else None
    if not isinstance(extra, dict):
        raise ValueError(
            "Invalid provider config: api_key metadata must be a mapping."
        )
    env_var = extra.get("env_var")
    if env_var != expected:
        raise ValueError(
            "Invalid provider config: api_key env_var must match the default "
            f"provider env var for '{provider}'. Expected '{expected}', got "
            f"'{env_var}'."
        )


class ProviderConfig(StrictConfigModel):
    provider: Literal["openai", "anthropic"]
    default_model: str
    api_key: SecretStr | None = Field(
        default=None,
        json_schema_extra={"secret": True},
    )
    base_url: str | None = None
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)

    @model_validator(mode="after")
    def _populate_api_key_from_env(self) -> ProviderConfig:
        if self.api_key is not None:
            return self

        env_name = provider_api_key_env(self.provider)
        if env_name is None:
            return self

        validate_provider_api_key_env_var(type(self))
        value = os.environ.get(env_name)
        if value:
            self.api_key = SecretStr(value)
        return self


class OpenAIProviderConfig(ProviderConfig):
    provider: Literal["openai"] = "openai"
    api_key: SecretStr | None = Field(
        default=None,
        json_schema_extra={"secret": True, "env_var": "OPENAI_API_KEY"},
    )


class AnthropicProviderConfig(ProviderConfig):
    provider: Literal["anthropic"] = "anthropic"
    api_key: SecretStr | None = Field(
        default=None,
        json_schema_extra={"secret": True, "env_var": "ANTHROPIC_API_KEY"},
    )


PROVIDER_CONFIG_TYPES: dict[str, type[ProviderConfig]] = {
    "openai": OpenAIProviderConfig,
    "anthropic": AnthropicProviderConfig,
}


def build_provider_config(
    provider: Literal["openai", "anthropic"],
    default_model: str,
    *,
    api_key: SecretStr | None = None,
    base_url: str | None = None,
    timeout: TimeoutConfig | None = None,
    retry: RetryConfig | None = None,
    polling: PollingConfig | None = None,
) -> ProviderConfig:
    config_type = PROVIDER_CONFIG_TYPES[provider]
    return config_type(
        provider=provider,
        default_model=default_model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout or TimeoutConfig(),
        retry=retry or RetryConfig(),
        polling=polling or PollingConfig(),
    )

from typing import cast

from xagent.llm_config import (
    DEFAULT_API_KEY_ENV,
    AnthropicProviderConfig,
    OpenAIProviderConfig,
    ProviderConfig,
    build_provider_config,
    validate_provider_api_key_env_var,
)


def test_provider_config_defaults() -> None:
    config = ProviderConfig(provider="openai", default_model="gpt-5.5")

    assert config.timeout.read == 120.0
    assert config.retry.max_attempts == 3
    assert config.polling.initial_interval_seconds == 2.0


def test_provider_config_subclasses_have_expected_env_metadata() -> None:
    openai_extra = cast(
        dict[str, object],
        OpenAIProviderConfig.model_fields["api_key"].json_schema_extra,
    )
    anthropic_extra = cast(
        dict[str, object],
        AnthropicProviderConfig.model_fields["api_key"].json_schema_extra,
    )
    assert openai_extra["env_var"] == DEFAULT_API_KEY_ENV["openai"]
    assert anthropic_extra["env_var"] == DEFAULT_API_KEY_ENV["anthropic"]


def test_build_provider_config_uses_provider_specific_subclass() -> None:
    config = build_provider_config("anthropic", "claude-sonnet-4-6")

    assert isinstance(config, AnthropicProviderConfig)
    validate_provider_api_key_env_var(type(config))

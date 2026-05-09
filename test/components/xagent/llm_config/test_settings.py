from xagent.llm_config import ProviderConfig


def test_provider_config_defaults() -> None:
    config = ProviderConfig(provider="openai", default_model="gpt-5.5")

    assert config.timeout.read == 120.0
    assert config.retry.max_attempts == 3
    assert config.polling.initial_interval_seconds == 2.0

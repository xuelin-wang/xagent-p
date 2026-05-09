import pytest
from pydantic import SecretStr

from xagent.llm_config import ProviderConfig, require_api_key, resolve_api_key


def test_resolve_api_key_prefers_explicit_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    config = ProviderConfig(
        provider="openai",
        default_model="gpt-5.5",
        api_key=SecretStr("explicit-key"),
    )

    assert resolve_api_key(config).get_secret_value() == "explicit-key"


def test_resolve_api_key_uses_default_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    config = ProviderConfig(provider="anthropic", default_model="claude-sonnet-4-6")

    assert require_api_key(config).get_secret_value() == "anthropic-key"

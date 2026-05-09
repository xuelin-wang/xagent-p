import pytest

from xagent.llm_contracts import (
    Capability,
    ModelCapabilities,
    UnsupportedCapabilityError,
    assert_capability,
)


def test_assert_capability_passes_when_supported() -> None:
    capabilities = ModelCapabilities(
        provider="openai",
        model="gpt-5.5",
        capabilities={Capability.TEXT_GENERATION},
    )

    assert_capability(capabilities, Capability.TEXT_GENERATION)


def test_assert_capability_raises_when_missing() -> None:
    capabilities = ModelCapabilities(provider="anthropic", model="claude", capabilities=set())

    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        assert_capability(capabilities, Capability.EMBEDDINGS)

    assert exc_info.value.payload.provider == "anthropic"
    assert "embeddings" in exc_info.value.payload.message

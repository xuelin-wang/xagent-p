from xagent.llm_contracts import LLMErrorPayload, RateLimitError


def test_llm_error_exposes_payload() -> None:
    payload = LLMErrorPayload(
        provider="openai",
        operation="generate",
        status_code=429,
        retryable=True,
        message="rate limited",
    )
    error = RateLimitError(payload)

    assert str(error) == "rate limited"
    assert error.payload.retryable is True

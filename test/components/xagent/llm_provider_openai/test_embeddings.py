import asyncio
import json

import httpx
import pytest

from xagent.llm_batch import EmbeddingRequest
from xagent.llm_config import ProviderConfig
from xagent.llm_contracts import RateLimitError, UnsupportedCapabilityError
from xagent.llm_provider_openai import OpenAIProvider
from xagent.llm_provider_openai.embeddings import (
    request_to_openai_embeddings_payload,
    response_from_openai_embeddings,
)


async def _test_openai_embed_rejects_unknown_model() -> None:
    provider = OpenAIProvider(ProviderConfig(provider="openai", default_model="gpt-5.5"))

    with pytest.raises(UnsupportedCapabilityError):
        await provider.embed(EmbeddingRequest(model="other", inputs=["hello"]))


def test_openai_embed_rejects_unknown_model() -> None:
    asyncio.run(_test_openai_embed_rejects_unknown_model())


def test_request_to_openai_embeddings_payload() -> None:
    payload = request_to_openai_embeddings_payload(
        EmbeddingRequest(
            model="text-embedding-3-small",
            inputs=["hello", "world"],
            dimensions=256,
            metadata={"user": "user-123", "ignored": "value"},
        ),
        "text-embedding-3-small",
    )

    assert payload == {
        "model": "text-embedding-3-small",
        "input": ["hello", "world"],
        "encoding_format": "float",
        "dimensions": 256,
        "user": "user-123",
    }


def test_response_from_openai_embeddings() -> None:
    response = response_from_openai_embeddings(
        {
            "model": "text-embedding-3-small",
            "data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ],
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        },
        "fallback",
    )

    assert response.model == "text-embedding-3-small"
    assert response.dimensions == 2
    assert [vector.index for vector in response.vectors] == [0, 1]
    assert response.vectors[0].embedding == [0.1, 0.2]
    assert response.usage.input_tokens == 4
    assert response.usage.total_tokens == 4


async def _test_openai_embed_posts_embeddings_payload() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    provider = OpenAIProvider(
        ProviderConfig(
            provider="openai",
            default_model="gpt-5.5",
            api_key="test-key",
            base_url="https://openai.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await provider.embed(
        EmbeddingRequest(model="text-embedding-3-small", inputs=["hello"], dimensions=3)
    )

    assert seen["url"] == "https://openai.test/v1/embeddings"
    assert seen["auth"] == "Bearer test-key"
    assert seen["payload"] == {
        "model": "text-embedding-3-small",
        "input": ["hello"],
        "encoding_format": "float",
        "dimensions": 3,
    }
    assert response.dimensions == 3
    assert response.vectors[0].embedding == [0.1, 0.2, 0.3]


def test_openai_embed_posts_embeddings_payload() -> None:
    asyncio.run(_test_openai_embed_posts_embeddings_payload())


async def _test_openai_embed_normalizes_rate_limit_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"x-request-id": "req-embed"},
            json={"error": {"message": "slow down"}},
        )

    provider = OpenAIProvider(
        ProviderConfig(provider="openai", default_model="gpt-5.5", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RateLimitError) as exc_info:
        await provider.embed(EmbeddingRequest(inputs=["hello"]))

    assert exc_info.value.payload.operation == "embed"
    assert exc_info.value.payload.request_id == "req-embed"
    assert exc_info.value.payload.message == "slow down"


def test_openai_embed_normalizes_rate_limit_error() -> None:
    asyncio.run(_test_openai_embed_normalizes_rate_limit_error())

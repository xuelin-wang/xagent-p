import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from xagent.llm_config import ProviderConfig
from xagent.llm_contracts import (
    AuthenticationError,
    GenerateRequest,
    Message,
    RateLimitError,
    Role,
    UnsupportedCapabilityError,
)
from xagent.llm_provider_anthropic import AnthropicProvider
from xagent.llm_structured import StructuredGenerateRequest, response_format_for_model
from xagent.llm_tools import AppToolDefinition, ProviderHostedTool, ToolChoice


class SampleOutput(BaseModel):
    value: str


async def _test_anthropic_generate_posts_messages_payload() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers["x-api-key"]
        seen["version"] = request.headers["anthropic-version"]
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-6",
                "content": [{"type": "text", "text": "answer"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await provider.generate(
        GenerateRequest(
            messages=[
                Message(role=Role.SYSTEM, content="sys"),
                Message(role=Role.USER, content="Hi"),
            ]
        )
    )

    assert seen["url"] == "https://anthropic.test/v1/messages"
    assert seen["api_key"] == "test-key"
    assert seen["version"] == "2023-06-01"
    assert seen["payload"]["system"] == "sys"
    assert seen["payload"]["messages"] == [{"role": "user", "content": "Hi"}]
    assert response.text == "answer"
    assert response.usage.total_tokens == 3


def test_anthropic_generate_posts_messages_payload() -> None:
    asyncio.run(_test_anthropic_generate_posts_messages_payload())


async def _test_anthropic_generate_requires_api_key() -> None:
    provider = AnthropicProvider(
        ProviderConfig(provider="anthropic", default_model="claude-sonnet-4-6")
    )

    with pytest.raises(AuthenticationError):
        await provider.generate(GenerateRequest(messages=[Message(role=Role.USER, content="Hi")]))


def test_anthropic_generate_requires_api_key() -> None:
    asyncio.run(_test_anthropic_generate_requires_api_key())


async def _test_anthropic_generate_normalizes_rate_limit_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"request-id": "req-abc"},
            json={"error": {"message": "rate limited"}},
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RateLimitError) as exc_info:
        await provider.generate(GenerateRequest(messages=[Message(role=Role.USER, content="Hi")]))

    assert exc_info.value.payload.request_id == "req-abc"
    assert exc_info.value.payload.retryable is True
    assert exc_info.value.payload.message == "rate limited"


def test_anthropic_generate_normalizes_rate_limit_error() -> None:
    asyncio.run(_test_anthropic_generate_normalizes_rate_limit_error())


async def _test_anthropic_generate_rejects_unknown_model() -> None:
    provider = AnthropicProvider(ProviderConfig(provider="anthropic", default_model="not-a-model"))

    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        await provider.generate(GenerateRequest(messages=[Message(role=Role.USER, content="Hi")]))

    assert exc_info.value.payload.model == "not-a-model"
    assert exc_info.value.payload.operation == "generate"


def test_anthropic_generate_rejects_unknown_model() -> None:
    asyncio.run(_test_anthropic_generate_rejects_unknown_model())


async def _test_anthropic_generate_posts_app_tools_and_parses_tool_use() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-6",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "lookup",
                        "input": {"id": "abc"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await provider.generate(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="lookup abc")],
            app_tools=[
                AppToolDefinition(
                    name="lookup",
                    description="Lookup a record.",
                    input_schema={
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    },
                )
            ],
            tool_choice=ToolChoice(mode="required", tool_name="lookup"),
        )
    )

    assert seen["payload"]["tools"][0]["name"] == "lookup"
    assert seen["payload"]["tool_choice"] == {"type": "tool", "name": "lookup"}
    assert response.finish_reason == "tool_use"
    assert response.app_tool_calls[0].id == "toolu_1"
    assert response.app_tool_calls[0].arguments == {"id": "abc"}


def test_anthropic_generate_posts_app_tools_and_parses_tool_use() -> None:
    asyncio.run(_test_anthropic_generate_posts_app_tools_and_parses_tool_use())


async def _test_anthropic_generate_posts_provider_tools_and_parses_traces() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-6",
                "content": [
                    {
                        "type": "server_tool_use",
                        "id": "srvtoolu_1",
                        "name": "web_search",
                        "input": {"query": "Anthropic"},
                    },
                    {
                        "type": "web_search_tool_result",
                        "tool_use_id": "srvtoolu_1",
                        "content": [{"title": "Anthropic", "url": "https://www.anthropic.com"}],
                    },
                    {"type": "text", "text": "searched"},
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await provider.generate(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="search")],
            provider_tools=[
                ProviderHostedTool(
                    type="web_search",
                    config={"max_uses": 1},
                )
            ],
        )
    )

    assert seen["payload"]["tools"] == [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": 1}
    ]
    assert response.text == "searched"
    assert response.provider_tool_traces[0].tool_type == "web_search"
    assert response.provider_tool_traces[0].citations[0].url == "https://www.anthropic.com"


def test_anthropic_generate_posts_provider_tools_and_parses_traces() -> None:
    asyncio.run(_test_anthropic_generate_posts_provider_tools_and_parses_traces())


async def _test_anthropic_generate_rejects_unknown_provider_tool() -> None:
    provider = AnthropicProvider(
        ProviderConfig(provider="anthropic", default_model="claude-sonnet-4-6", api_key="test-key")
    )

    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        await provider.generate(
            GenerateRequest(
                messages=[Message(role=Role.USER, content="search")],
                provider_tools=[ProviderHostedTool(type="unknown_tool")],
            )
        )

    assert exc_info.value.payload.message == "Anthropic provider-hosted tool is not supported: unknown_tool."


def test_anthropic_generate_rejects_unknown_provider_tool() -> None:
    asyncio.run(_test_anthropic_generate_rejects_unknown_provider_tool())



async def _test_anthropic_generate_structured_uses_extraction_tool() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-6",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_structured",
                        "name": "SampleOutput",
                        "input": {"value": "ok"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await provider.generate_structured(
        StructuredGenerateRequest(
            messages=[Message(role=Role.USER, content="Return ok.")],
            response_format=response_format_for_model(SampleOutput),
        ),
        SampleOutput,
    )

    assert seen["payload"]["tools"] == [
        {
            "name": "SampleOutput",
            "description": "Extract the requested structured output. Return only fields described by the schema.",
            "input_schema": SampleOutput.model_json_schema(),
        }
    ]
    assert seen["payload"]["tool_choice"] == {"type": "tool", "name": "SampleOutput"}
    assert response.data.value == "ok"
    assert response.raw_json == {"value": "ok"}
    assert response.usage.total_tokens == 15


def test_anthropic_generate_structured_uses_extraction_tool() -> None:
    asyncio.run(_test_anthropic_generate_structured_uses_extraction_tool())


async def _test_anthropic_generate_structured_retries_validation_error() -> None:
    seen_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content))
        value = {} if len(seen_payloads) == 1 else {"value": "ok"}
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-6",
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"toolu_{len(seen_payloads)}",
                        "name": "SampleOutput",
                        "input": value,
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await provider.generate_structured(
        StructuredGenerateRequest(
            messages=[Message(role=Role.USER, content="Return ok.")],
            response_format=response_format_for_model(SampleOutput),
            validation_retries=1,
        ),
        SampleOutput,
    )

    assert response.data.value == "ok"
    assert len(seen_payloads) == 2
    assert "failed validation" in seen_payloads[1]["messages"][-1]["content"]


def test_anthropic_generate_structured_retries_validation_error() -> None:
    asyncio.run(_test_anthropic_generate_structured_retries_validation_error())

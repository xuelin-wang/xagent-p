import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from xagent.llm_config import ProviderConfig, RetryConfig
from xagent.llm_contracts import (
    AuthenticationError,
    GenerateRequest,
    Message,
    RateLimitError,
    Role,
    UnsupportedCapabilityError,
)
from xagent.llm_provider_openai import OpenAIProvider
from xagent.llm_structured import StructuredGenerateRequest, response_format_for_model
from xagent.llm_tools import AppToolDefinition, ProviderHostedTool, ToolChoice, run_app_tool_loop


class SampleOutput(BaseModel):
    value: str


async def _test_openai_generate_posts_responses_payload() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.5",
                "output_text": "answer",
                "status": "completed",
                "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
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

    response = await provider.generate(
        GenerateRequest(messages=[Message(role=Role.USER, content="Hi")])
    )

    assert seen["url"] == "https://openai.test/v1/responses"
    assert seen["auth"] == "Bearer test-key"
    assert seen["payload"]["input"] == [{"role": "user", "content": "Hi"}]
    assert response.text == "answer"
    assert response.usage.total_tokens == 3


def test_openai_generate_posts_responses_payload() -> None:
    asyncio.run(_test_openai_generate_posts_responses_payload())


async def _test_openai_generate_requires_api_key() -> None:
    provider = OpenAIProvider(ProviderConfig(provider="openai", default_model="gpt-5.5"))

    with pytest.raises(AuthenticationError):
        await provider.generate(GenerateRequest(messages=[Message(role=Role.USER, content="Hi")]))


def test_openai_generate_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    asyncio.run(_test_openai_generate_requires_api_key())


async def _test_openai_generate_normalizes_rate_limit_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"x-request-id": "req-123"},
            json={"error": {"message": "slow down"}},
        )

    provider = OpenAIProvider(
        ProviderConfig(provider="openai", default_model="gpt-5.5", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RateLimitError) as exc_info:
        await provider.generate(GenerateRequest(messages=[Message(role=Role.USER, content="Hi")]))

    assert exc_info.value.payload.request_id == "req-123"
    assert exc_info.value.payload.retryable is True
    assert exc_info.value.payload.message == "slow down"


def test_openai_generate_normalizes_rate_limit_error() -> None:
    asyncio.run(_test_openai_generate_normalizes_rate_limit_error())


async def _test_openai_generate_retries_retryable_response() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, json={"error": {"message": "try again"}})
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.5",
                "output_text": "answer",
                "status": "completed",
            },
        )

    provider = OpenAIProvider(
        ProviderConfig(
            provider="openai",
            default_model="gpt-5.5",
            api_key="test-key",
            retry=RetryConfig(jitter=False, initial_delay_seconds=0),
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await provider.generate(GenerateRequest(messages=[Message(role=Role.USER, content="Hi")]))

    assert calls == 2
    assert response.text == "answer"


def test_openai_generate_retries_retryable_response() -> None:
    asyncio.run(_test_openai_generate_retries_retryable_response())


async def _test_openai_generate_rejects_unknown_model() -> None:
    provider = OpenAIProvider(ProviderConfig(provider="openai", default_model="not-a-model"))

    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        await provider.generate(GenerateRequest(messages=[Message(role=Role.USER, content="Hi")]))

    assert exc_info.value.payload.model == "not-a-model"
    assert exc_info.value.payload.operation == "generate"


def test_openai_generate_rejects_unknown_model() -> None:
    asyncio.run(_test_openai_generate_rejects_unknown_model())


async def _test_openai_generate_structured_posts_json_schema_payload() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.5",
                "output_text": '{"value": "ok"}',
                "status": "completed",
                "usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12},
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

    response = await provider.generate_structured(
        StructuredGenerateRequest(
            messages=[Message(role=Role.USER, content="Return ok.")],
            response_format=response_format_for_model(SampleOutput),
        ),
        SampleOutput,
    )

    assert seen["payload"]["text"]["format"]["type"] == "json_schema"
    assert seen["payload"]["text"]["format"]["name"] == "SampleOutput"
    assert response.data.value == "ok"
    assert response.raw_json == {"value": "ok"}
    assert response.usage.total_tokens == 12


def test_openai_generate_structured_posts_json_schema_payload() -> None:
    asyncio.run(_test_openai_generate_structured_posts_json_schema_payload())


async def _test_openai_generate_posts_app_tools_and_parses_function_calls() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.5",
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "lookup",
                        "arguments": '{"id": "abc"}',
                    }
                ],
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
    assert seen["payload"]["tool_choice"] == {"type": "function", "name": "lookup"}
    assert response.app_tool_calls[0].id == "call-1"
    assert response.app_tool_calls[0].arguments == {"id": "abc"}


def test_openai_generate_posts_app_tools_and_parses_function_calls() -> None:
    asyncio.run(_test_openai_generate_posts_app_tools_and_parses_function_calls())


async def _test_openai_app_tool_loop_posts_tool_result() -> None:
    seen_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen_payloads.append(payload)
        if len(seen_payloads) == 1:
            return httpx.Response(
                200,
                json={
                    "model": "gpt-5.5",
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-1",
                            "name": "lookup",
                            "arguments": '{"id": "abc"}',
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={"model": "gpt-5.5", "status": "completed", "output_text": "done"},
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

    async def lookup(arguments: dict) -> str:
        return f"record:{arguments['id']}"

    response = await run_app_tool_loop(
        provider,
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
        ),
        {"lookup": lookup},
    )

    assert response.text == "done"
    assert seen_payloads[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "record:abc",
    }


def test_openai_app_tool_loop_posts_tool_result() -> None:
    asyncio.run(_test_openai_app_tool_loop_posts_tool_result())


async def _test_openai_generate_posts_provider_tools_and_parses_traces() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.5",
                "status": "completed",
                "output_text": "searched",
                "output": [
                    {
                        "type": "web_search_call",
                        "status": "completed",
                        "action": {
                            "query": "OpenAI",
                            "sources": [{"title": "OpenAI", "url": "https://openai.com"}],
                        },
                    }
                ],
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

    response = await provider.generate(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="search")],
            provider_tools=[ProviderHostedTool(type="web_search", config={"external_web_access": False})],
        )
    )

    assert seen["payload"]["tools"] == [{"type": "web_search", "external_web_access": False}]
    assert response.text == "searched"
    assert response.provider_tool_traces[0].tool_type == "web_search"
    assert response.provider_tool_traces[0].citations[0].url == "https://openai.com"


def test_openai_generate_posts_provider_tools_and_parses_traces() -> None:
    asyncio.run(_test_openai_generate_posts_provider_tools_and_parses_traces())


async def _test_openai_generate_rejects_unknown_provider_tool() -> None:
    provider = OpenAIProvider(ProviderConfig(provider="openai", default_model="gpt-5.5", api_key="test-key"))

    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        await provider.generate(
            GenerateRequest(
                messages=[Message(role=Role.USER, content="search")],
                provider_tools=[ProviderHostedTool(type="unknown_tool")],
            )
        )

    assert exc_info.value.payload.message == "OpenAI provider-hosted tool is not supported: unknown_tool."


def test_openai_generate_rejects_unknown_provider_tool() -> None:
    asyncio.run(_test_openai_generate_rejects_unknown_provider_tool())

import pytest

from xagent.llm_contracts import GenerateRequest, Message, Role
from xagent.llm_files import BytesFileSource, CloudFileRef, FileInput, ProviderFileRef
from xagent.llm_provider_anthropic.mapping import (
    file_input_to_anthropic_content_block,
    request_to_anthropic_messages_payload,
    response_from_anthropic_message,
    split_system_and_messages,
)
from xagent.llm_tools import AppToolDefinition, ProviderHostedTool, ToolChoice


def test_split_system_and_messages() -> None:
    system, messages = split_system_and_messages(
        [
            Message(role=Role.SYSTEM, content="sys"),
            Message(role=Role.USER, content="hi"),
            Message(role=Role.TOOL, content="record:abc", tool_call_id="toolu_1"),
        ]
    )

    assert system == "sys"
    assert messages == [
        {"role": "user", "content": "hi"},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "record:abc",
                }
            ],
        },
    ]


def test_request_to_anthropic_messages_payload() -> None:
    payload = request_to_anthropic_messages_payload(
        GenerateRequest(
            messages=[
                Message(role=Role.SYSTEM, content="sys"),
                Message(role=Role.USER, content="hi"),
            ],
            max_output_tokens=50,
            temperature=0.1,
        ),
        "claude-sonnet-4-6",
    )

    assert payload == {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 50,
        "system": "sys",
        "temperature": 0.1,
    }


def test_request_to_anthropic_messages_payload_with_app_tools() -> None:
    payload = request_to_anthropic_messages_payload(
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
        ),
        "claude-sonnet-4-6",
    )

    assert payload["tools"] == [
        {
            "name": "lookup",
            "description": "Lookup a record.",
            "input_schema": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        }
    ]
    assert payload["tool_choice"] == {"type": "tool", "name": "lookup"}


def test_request_to_anthropic_messages_payload_with_provider_tools() -> None:
    payload = request_to_anthropic_messages_payload(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="search")],
            provider_tools=[
                ProviderHostedTool(
                    type="web_search",
                    config={"max_uses": 2, "allowed_domains": ["anthropic.com"]},
                )
            ],
        ),
        "claude-sonnet-4-6",
    )

    assert payload["tools"] == [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 2,
            "allowed_domains": ["anthropic.com"],
        }
    ]


def test_request_to_anthropic_messages_payload_appends_provider_file_input() -> None:
    payload = request_to_anthropic_messages_payload(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="summarize")],
            files=[
                FileInput(
                    source=ProviderFileRef(
                        provider="anthropic",
                        file_id="file_123",
                        media_type="application/pdf",
                    )
                )
            ],
        ),
        "claude-sonnet-4-6",
    )

    assert payload["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "summarize"},
                {
                    "type": "document",
                    "source": {"type": "file", "file_id": "file_123"},
                },
            ],
        }
    ]


def test_file_input_to_anthropic_content_block_maps_bytes() -> None:
    block = file_input_to_anthropic_content_block(
        FileInput(
            source=BytesFileSource(
                filename="note.txt",
                data=b"hello",
                media_type="text/plain",
            )
        )
    )

    assert block == {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "text/plain",
            "data": "aGVsbG8=",
        },
    }


def test_file_input_to_anthropic_content_block_maps_image_bytes() -> None:
    block = file_input_to_anthropic_content_block(
        FileInput(
            source=BytesFileSource(
                filename="image.png",
                data=b"png",
                media_type="image/png",
            )
        )
    )

    assert block["type"] == "image"


def test_file_input_to_anthropic_content_block_rejects_cloud_file() -> None:
    with pytest.raises(ValueError, match="does not support cloud_file references"):
        file_input_to_anthropic_content_block(
            FileInput(source=CloudFileRef(uri="gdrive://doc", media_type="application/pdf"))
        )


def test_response_from_anthropic_message() -> None:
    response = response_from_anthropic_message(
        {
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": "answer"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 2, "output_tokens": 3},
        },
        "fallback",
    )

    assert response.text == "answer"
    assert response.finish_reason == "end_turn"
    assert response.usage.total_tokens == 5


def test_response_from_anthropic_message_extracts_tool_use() -> None:
    response = response_from_anthropic_message(
        {
            "model": "claude-sonnet-4-6",
            "content": [
                {"type": "text", "text": "I will look this up."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "lookup",
                    "input": {"id": "abc"},
                },
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 2, "output_tokens": 3},
        },
        "fallback",
    )

    assert response.text == "I will look this up."
    assert response.finish_reason == "tool_use"
    assert response.app_tool_calls[0].id == "toolu_1"
    assert response.app_tool_calls[0].name == "lookup"
    assert response.app_tool_calls[0].arguments == {"id": "abc"}


def test_response_from_anthropic_message_extracts_provider_tool_traces() -> None:
    response = response_from_anthropic_message(
        {
            "model": "claude-sonnet-4-6",
            "content": [
                {
                    "type": "server_tool_use",
                    "id": "srvtoolu_1",
                    "name": "web_search",
                    "input": {"query": "Anthropic docs"},
                },
                {
                    "type": "web_search_tool_result",
                    "tool_use_id": "srvtoolu_1",
                    "content": [
                        {
                            "type": "web_search_result",
                            "title": "Anthropic",
                            "url": "https://www.anthropic.com",
                        }
                    ],
                },
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 2, "output_tokens": 3},
        },
        "fallback",
    )

    trace = response.provider_tool_traces[0]
    assert trace.tool_type == "web_search"
    assert trace.status == "completed"
    assert trace.input_summary == "Anthropic docs"
    assert trace.output_summary == "1 result(s)"
    assert trace.citations[0].url == "https://www.anthropic.com"

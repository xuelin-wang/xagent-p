from pydantic import BaseModel

from xagent.llm_contracts import GenerateRequest, Message, Role, TextPart
from xagent.llm_files import BytesFileSource, FileInput, ProviderFileRef, UrlFileSource
from xagent.llm_provider_openai.mapping import (
    messages_to_openai_input,
    request_to_openai_responses_payload,
    response_from_openai_responses,
)
from xagent.llm_structured import response_format_for_model
from xagent.llm_tools import AppToolDefinition, ProviderHostedTool, ToolChoice


class SampleOutput(BaseModel):
    value: str


def test_messages_to_openai_input() -> None:
    mapped = messages_to_openai_input(
        [
            Message(role=Role.SYSTEM, content="sys"),
            Message(role=Role.USER, content=[TextPart(text="hi")]),
            Message(role=Role.TOOL, content="tool result", tool_call_id="call-1"),
        ]
    )

    assert mapped == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"type": "function_call_output", "call_id": "call-1", "output": "tool result"},
    ]


def test_request_to_openai_responses_payload() -> None:
    payload = request_to_openai_responses_payload(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="hello")],
            temperature=0.2,
            max_output_tokens=50,
            metadata={"trace": "unit"},
        ),
        "gpt-5.5",
    )

    assert payload == {
        "model": "gpt-5.5",
        "input": [{"role": "user", "content": "hello"}],
        "temperature": 0.2,
        "max_output_tokens": 50,
        "metadata": {"trace": "unit"},
    }


def test_request_to_openai_responses_payload_with_json_schema() -> None:
    payload = request_to_openai_responses_payload(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="hello")],
            response_format=response_format_for_model(SampleOutput),
        ),
        "gpt-5.5",
    )

    assert payload["text"]["format"] == {
        "type": "json_schema",
        "name": "SampleOutput",
        "schema": {
            "title": "SampleOutput",
            "type": "object",
            "properties": {"value": {"title": "Value", "type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        "strict": True,
    }


def test_request_to_openai_responses_payload_with_app_tools() -> None:
    payload = request_to_openai_responses_payload(
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
        "gpt-5.5",
    )

    assert payload["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "description": "Lookup a record.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]
    assert payload["tool_choice"] == {"type": "function", "name": "lookup"}


def test_request_to_openai_responses_payload_with_provider_tools() -> None:
    payload = request_to_openai_responses_payload(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="search")],
            provider_tools=[
                ProviderHostedTool(
                    type="web_search",
                    config={
                        "external_web_access": False,
                        "filters": {"allowed_domains": ["example.com"]},
                    },
                )
            ],
        ),
        "gpt-5.5",
    )

    assert payload["tools"] == [
        {
            "type": "web_search",
            "external_web_access": False,
            "filters": {"allowed_domains": ["example.com"]},
        }
    ]


def test_request_to_openai_responses_payload_with_file_inputs() -> None:
    payload = request_to_openai_responses_payload(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="summarize")],
            files=[
                FileInput(source=ProviderFileRef(provider="openai", file_id="file-123")),
                FileInput(source=UrlFileSource(url="https://example.com/doc.pdf")),
                FileInput(
                    source=BytesFileSource(
                        filename="note.pdf",
                        data=b"hello",
                        media_type="application/pdf",
                    )
                ),
            ],
        ),
        "gpt-5.5",
    )

    assert payload["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "summarize"},
                {"type": "input_file", "file_id": "file-123"},
                {"type": "input_file", "file_url": "https://example.com/doc.pdf"},
                {
                    "type": "input_file",
                    "filename": "note.pdf",
                    "file_data": "data:application/pdf;base64,aGVsbG8=",
                },
            ],
        }
    ]


def test_response_from_openai_responses_uses_output_text() -> None:
    response = response_from_openai_responses(
        {
            "model": "gpt-5.5",
            "output_text": "hello there",
            "status": "completed",
            "usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
        },
        "fallback",
    )

    assert response.text == "hello there"
    assert response.usage.total_tokens == 7


def test_response_from_openai_responses_extracts_function_calls() -> None:
    response = response_from_openai_responses(
        {
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
        "fallback",
    )

    assert response.app_tool_calls[0].id == "call-1"
    assert response.app_tool_calls[0].name == "lookup"
    assert response.app_tool_calls[0].arguments == {"id": "abc"}


def test_response_from_openai_responses_extracts_provider_tool_traces() -> None:
    response = response_from_openai_responses(
        {
            "model": "gpt-5.5",
            "status": "completed",
            "output": [
                {
                    "type": "web_search_call",
                    "status": "completed",
                    "action": {
                        "query": "OpenAI news",
                        "sources": [{"title": "OpenAI", "url": "https://openai.com"}],
                    },
                },
                {
                    "type": "file_search_call",
                    "status": "completed",
                    "queries": ["roadmap"],
                    "results": [{"file_id": "file-1", "filename": "roadmap.md"}],
                },
            ],
        },
        "fallback",
    )

    assert response.provider_tool_traces[0].tool_type == "web_search"
    assert response.provider_tool_traces[0].input_summary == "OpenAI news"
    assert response.provider_tool_traces[0].citations[0].url == "https://openai.com"
    assert response.provider_tool_traces[1].tool_type == "file_search"
    assert response.provider_tool_traces[1].input_summary == "roadmap"
    assert response.provider_tool_traces[1].citations[0].file_id == "file-1"

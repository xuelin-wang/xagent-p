import base64
import json
from pathlib import Path
from typing import Any

from xagent.llm_contracts import GenerateRequest, GenerateResponse, Message, Role, Usage
from xagent.llm_files import (
    BytesFileSource,
    CloudFileRef,
    FileInput,
    LocalFileSource,
    ProviderFileRef,
    UrlFileSource,
)
from xagent.llm_structured import ResponseFormat, ResponseFormatType
from xagent.llm_tools import AppToolCall, AppToolDefinition, Citation, ProviderHostedTool, ProviderToolTrace, ToolChoice


def message_to_openai_input(message: Message) -> dict[str, Any]:
    content = message.content
    if isinstance(content, str):
        text = content
    else:
        text = "\n".join(part.text for part in content)
    if message.role == Role.TOOL and message.tool_call_id:
        return {"type": "function_call_output", "call_id": message.tool_call_id, "output": text}
    return {"role": message.role.value, "content": text}


def messages_to_openai_input(
    messages: list[Message],
    files: list[FileInput] | None = None,
) -> list[dict[str, Any]]:
    mapped = [
        message_to_openai_input(message)
        for message in messages
        if message.role != Role.TOOL or message.tool_call_id
    ]
    if not files:
        return mapped
    file_parts = [file_input_to_openai_content_part(file_input) for file_input in files]
    for item in reversed(mapped):
        if item.get("role") != Role.USER.value:
            continue
        existing_content = item.get("content")
        content_parts: list[dict[str, Any]] = []
        if isinstance(existing_content, str) and existing_content:
            content_parts.append({"type": "input_text", "text": existing_content})
        elif isinstance(existing_content, list):
            content_parts.extend(existing_content)
        item["content"] = [*content_parts, *file_parts]
        return mapped

    mapped.append({"role": "user", "content": file_parts})
    return mapped


def request_to_openai_responses_payload(request: GenerateRequest, model: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": messages_to_openai_input(request.messages, _typed_file_inputs(request.files)),
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_output_tokens is not None:
        payload["max_output_tokens"] = request.max_output_tokens
    if request.stop is not None:
        payload["stop"] = request.stop
    if request.metadata:
        payload["metadata"] = request.metadata
    if request.response_format is not None:
        payload["text"] = {"format": response_format_to_openai_text_format(request.response_format)}
    if request.app_tools:
        payload["tools"] = [
            app_tool_definition_to_openai_tool(tool)
            for tool in request.app_tools
            if isinstance(tool, AppToolDefinition)
        ]
    if request.provider_tools:
        payload.setdefault("tools", []).extend(
            provider_hosted_tool_to_openai_tool(tool)
            for tool in request.provider_tools
            if isinstance(tool, ProviderHostedTool)
        )
    if request.tool_choice is not None:
        payload["tool_choice"] = tool_choice_to_openai_tool_choice(request.tool_choice)
    return payload


def app_tool_definition_to_openai_tool(tool: AppToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": _prepare_strict_json_schema(tool.input_schema),
        "strict": True,
    }


def provider_hosted_tool_to_openai_tool(tool: ProviderHostedTool) -> dict[str, Any]:
    mapped = {"type": tool.type, **tool.config}
    if tool.name is not None:
        mapped["name"] = tool.name
    return mapped


def file_input_to_openai_content_part(file_input: FileInput) -> dict[str, Any]:
    source = file_input.source
    if isinstance(source, ProviderFileRef):
        return {"type": "input_file", "file_id": source.file_id}
    if isinstance(source, UrlFileSource):
        return {"type": "input_file", "file_url": source.url}
    if isinstance(source, BytesFileSource):
        media_type = source.media_type or "application/octet-stream"
        encoded = base64.b64encode(source.data).decode("ascii")
        return {
            "type": "input_file",
            "filename": source.filename,
            "file_data": f"data:{media_type};base64,{encoded}",
        }
    if isinstance(source, LocalFileSource):
        path = Path(source.path)
        media_type = source.media_type or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return {
            "type": "input_file",
            "filename": path.name,
            "file_data": f"data:{media_type};base64,{encoded}",
        }
    if isinstance(source, CloudFileRef):
        raise ValueError("OpenAI file input does not support cloud_file references.")
    raise ValueError(f"Unsupported OpenAI file input source: {type(source).__name__}")


def tool_choice_to_openai_tool_choice(tool_choice: Any) -> str | dict[str, Any]:
    if isinstance(tool_choice, str | dict):
        return tool_choice
    if isinstance(tool_choice, ToolChoice):
        if tool_choice.tool_name:
            return {"type": "function", "name": tool_choice.tool_name}
        return tool_choice.mode
    return tool_choice


def response_format_to_openai_text_format(response_format: ResponseFormat) -> dict[str, Any]:
    if response_format.type == ResponseFormatType.TEXT:
        return {"type": "text"}
    if response_format.type == ResponseFormatType.JSON_OBJECT:
        return {"type": "json_object"}
    if response_format.type == ResponseFormatType.JSON_SCHEMA:
        if response_format.json_schema is None:
            raise ValueError("JSON schema response format requires json_schema.")
        return {
            "type": "json_schema",
            "name": response_format.schema_name or "structured_output",
            "schema": _prepare_strict_json_schema(response_format.json_schema),
            "strict": response_format.strict,
        }
    raise ValueError(f"Unsupported OpenAI response format: {response_format.type}")


def response_from_openai_responses(raw: dict[str, Any], model: str) -> GenerateResponse:
    usage = raw.get("usage") or {}
    return GenerateResponse(
        provider="openai",
        model=raw.get("model") or model,
        text=_extract_output_text(raw),
        app_tool_calls=_extract_function_calls(raw),
        provider_tool_traces=_extract_provider_tool_traces(raw),
        finish_reason=raw.get("status"),
        usage=Usage(
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=usage.get("total_tokens"),
            raw=usage or None,
        ),
        raw_response=raw,
    )


def _extract_output_text(raw: dict[str, Any]) -> str | None:
    output_text = raw.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts) if parts else None


def _extract_function_calls(raw: dict[str, Any]) -> list[AppToolCall]:
    calls: list[AppToolCall] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        name = item.get("name")
        call_id = item.get("call_id") or item.get("id")
        arguments = _parse_arguments(item.get("arguments"))
        if isinstance(name, str) and isinstance(call_id, str):
            calls.append(AppToolCall(id=call_id, name=name, arguments=arguments))
    return calls


def _extract_provider_tool_traces(raw: dict[str, Any]) -> list[ProviderToolTrace]:
    traces: list[ProviderToolTrace] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if not isinstance(item_type, str) or not item_type.endswith("_call"):
            continue
        if item_type == "function_call":
            continue
        traces.append(
            ProviderToolTrace(
                tool_type=_normalize_provider_tool_type(item_type),
                name=item.get("name") if isinstance(item.get("name"), str) else None,
                status=item.get("status") if isinstance(item.get("status"), str) else None,
                input_summary=_provider_tool_input_summary(item),
                output_summary=_provider_tool_output_summary(item),
                citations=_provider_tool_citations(item),
                raw=item,
            )
        )
    return traces


def _normalize_provider_tool_type(item_type: str) -> str:
    return item_type.removesuffix("_call")


def _provider_tool_input_summary(item: dict[str, Any]) -> str | None:
    queries = item.get("queries")
    if isinstance(queries, list):
        return "\n".join(str(query) for query in queries)
    action = item.get("action")
    if isinstance(action, dict):
        query = action.get("query")
        if isinstance(query, str):
            return query
    code = item.get("code")
    return code if isinstance(code, str) else None


def _provider_tool_output_summary(item: dict[str, Any]) -> str | None:
    if isinstance(item.get("results"), list):
        return f"{len(item['results'])} result(s)"
    outputs = item.get("outputs")
    if isinstance(outputs, list):
        return f"{len(outputs)} output(s)"
    return None


def _provider_tool_citations(item: dict[str, Any]) -> list[Citation]:
    citations: list[Citation] = []
    for source in _iter_provider_tool_sources(item):
        if not isinstance(source, dict):
            continue
        citations.append(
            Citation(
                title=source.get("title") if isinstance(source.get("title"), str) else None,
                url=source.get("url") if isinstance(source.get("url"), str) else None,
                file_id=source.get("file_id") if isinstance(source.get("file_id"), str) else None,
                quote=source.get("quote") if isinstance(source.get("quote"), str) else None,
                metadata={
                    key: value
                    for key, value in source.items()
                    if key not in {"title", "url", "file_id", "quote"}
                },
            )
        )
    return citations


def _iter_provider_tool_sources(item: dict[str, Any]) -> list[Any]:
    action = item.get("action")
    if isinstance(action, dict) and isinstance(action.get("sources"), list):
        return action["sources"]
    if isinstance(item.get("results"), list):
        return item["results"]
    return []


def _parse_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        return {}
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _prepare_strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(schema)
    if prepared.get("type") == "object":
        prepared.setdefault("additionalProperties", False)
    return prepared


def _typed_file_inputs(files: list[Any]) -> list[FileInput]:
    return [file_input for file_input in files if isinstance(file_input, FileInput)]

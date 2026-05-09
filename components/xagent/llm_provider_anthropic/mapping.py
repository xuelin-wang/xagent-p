import base64
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
from xagent.llm_tools import AppToolCall, AppToolDefinition, Citation, ProviderHostedTool, ProviderToolTrace, ToolChoice

ANTHROPIC_PROVIDER_TOOL_TYPES = {
    "web_search",
    "web_search_20250305",
}


def split_system_and_messages(
    messages: list[Message],
    files: list[FileInput] | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    mapped: list[dict[str, Any]] = []
    for message in messages:
        content = message.content
        text = content if isinstance(content, str) else "\n".join(part.text for part in content)
        if message.role == Role.SYSTEM:
            system_parts.append(text)
        elif message.role == Role.TOOL:
            if message.tool_call_id:
                mapped.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id,
                                "content": text,
                            }
                        ],
                    }
                )
        else:
            mapped.append({"role": message.role.value, "content": text})
    if files:
        _append_file_inputs(mapped, files)
    return ("\n\n".join(system_parts) or None), mapped


def request_to_anthropic_messages_payload(request: GenerateRequest, model: str) -> dict[str, Any]:
    system, messages = split_system_and_messages(request.messages, _typed_file_inputs(request.files))
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": request.max_output_tokens or 1024,
    }
    if system is not None:
        payload["system"] = system
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.stop is not None:
        payload["stop_sequences"] = request.stop
    if request.app_tools:
        payload["tools"] = [
            app_tool_definition_to_anthropic_tool(tool)
            for tool in request.app_tools
            if isinstance(tool, AppToolDefinition)
        ]
    if request.provider_tools:
        payload.setdefault("tools", []).extend(
            provider_hosted_tool_to_anthropic_tool(tool)
            for tool in request.provider_tools
            if isinstance(tool, ProviderHostedTool)
        )
    if request.tool_choice is not None:
        payload["tool_choice"] = tool_choice_to_anthropic_tool_choice(request.tool_choice)
    return payload


def app_tool_definition_to_anthropic_tool(tool: AppToolDefinition) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
    }


def provider_hosted_tool_to_anthropic_tool(tool: ProviderHostedTool) -> dict[str, Any]:
    tool_type = "web_search_20250305" if tool.type == "web_search" else tool.type
    mapped = {"type": tool_type, "name": tool.name or _provider_tool_default_name(tool.type), **tool.config}
    return mapped


def file_input_to_anthropic_content_block(file_input: FileInput) -> dict[str, Any]:
    source = file_input.source
    if isinstance(source, ProviderFileRef):
        return {
            "type": _anthropic_file_block_type(source.media_type),
            "source": {"type": "file", "file_id": source.file_id},
        }
    if isinstance(source, BytesFileSource):
        return {
            "type": _anthropic_file_block_type(source.media_type),
            "source": {
                "type": "base64",
                "media_type": source.media_type or "application/octet-stream",
                "data": base64.b64encode(source.data).decode("ascii"),
            },
        }
    if isinstance(source, LocalFileSource):
        path = Path(source.path)
        return {
            "type": _anthropic_file_block_type(source.media_type),
            "source": {
                "type": "base64",
                "media_type": source.media_type or "application/octet-stream",
                "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            },
        }
    if isinstance(source, (UrlFileSource, CloudFileRef)):
        raise ValueError(f"Anthropic file input does not support {source.type} references.")
    raise ValueError(f"Unsupported Anthropic file input source: {type(source).__name__}")


def tool_choice_to_anthropic_tool_choice(tool_choice: Any) -> dict[str, Any]:
    if isinstance(tool_choice, dict):
        return tool_choice
    if isinstance(tool_choice, ToolChoice):
        if tool_choice.tool_name:
            return {"type": "tool", "name": tool_choice.tool_name}
        if tool_choice.mode == "required":
            return {"type": "any"}
        return {"type": tool_choice.mode}
    if isinstance(tool_choice, str):
        if tool_choice == "required":
            return {"type": "any"}
        return {"type": tool_choice}
    return {"type": "auto"}


def response_from_anthropic_message(raw: dict[str, Any], model: str) -> GenerateResponse:
    usage = raw.get("usage") or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = None
    if input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return GenerateResponse(
        provider="anthropic",
        model=raw.get("model") or model,
        text=_extract_text(raw),
        app_tool_calls=_extract_tool_use(raw),
        provider_tool_traces=_extract_provider_tool_traces(raw),
        finish_reason=raw.get("stop_reason"),
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            raw=usage or None,
        ),
        raw_response=raw,
    )


def _extract_text(raw: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for block in raw.get("content", []):
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts) if parts else None


def _extract_tool_use(raw: dict[str, Any]) -> list[AppToolCall]:
    calls: list[AppToolCall] = []
    for block in raw.get("content", []):
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        call_id = block.get("id")
        name = block.get("name")
        arguments = block.get("input")
        if isinstance(call_id, str) and isinstance(name, str):
            calls.append(
                AppToolCall(
                    id=call_id,
                    name=name,
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
    return calls


def _extract_provider_tool_traces(raw: dict[str, Any]) -> list[ProviderToolTrace]:
    traces: list[ProviderToolTrace] = []
    pending: dict[str, ProviderToolTrace] = {}
    for block in raw.get("content", []):
        if not isinstance(block, dict):
            continue
        if block.get("type") == "server_tool_use":
            trace = ProviderToolTrace(
                tool_type=_normalize_provider_tool_type(block.get("name")),
                name=block.get("name") if isinstance(block.get("name"), str) else None,
                status="called",
                input_summary=_server_tool_input_summary(block.get("input")),
                raw=block,
            )
            traces.append(trace)
            if isinstance(block.get("id"), str):
                pending[block["id"]] = trace
        elif block.get("type") == "web_search_tool_result":
            tool_use_id = block.get("tool_use_id")
            trace = pending.get(tool_use_id) if isinstance(tool_use_id, str) else None
            if trace is None:
                trace = ProviderToolTrace(tool_type="web_search")
                traces.append(trace)
            trace.status = "completed"
            trace.output_summary = _web_search_output_summary(block)
            trace.citations = _web_search_citations(block)
            trace.raw = {"server_tool_use": trace.raw, "result": block}
    return traces


def _provider_tool_default_name(tool_type: str) -> str:
    if tool_type.startswith("web_search"):
        return "web_search"
    return tool_type


def _normalize_provider_tool_type(name: Any) -> str:
    if isinstance(name, str) and name == "web_search":
        return "web_search"
    return str(name) if name is not None else "unknown"


def _server_tool_input_summary(tool_input: Any) -> str | None:
    if isinstance(tool_input, dict) and isinstance(tool_input.get("query"), str):
        return tool_input["query"]
    return None


def _web_search_output_summary(block: dict[str, Any]) -> str | None:
    content = block.get("content")
    if isinstance(content, list):
        return f"{len(content)} result(s)"
    if isinstance(content, dict) and isinstance(content.get("error_code"), str):
        return content["error_code"]
    return None


def _web_search_citations(block: dict[str, Any]) -> list[Citation]:
    content = block.get("content")
    if not isinstance(content, list):
        return []
    citations: list[Citation] = []
    for result in content:
        if not isinstance(result, dict):
            continue
        citations.append(
            Citation(
                title=result.get("title") if isinstance(result.get("title"), str) else None,
                url=result.get("url") if isinstance(result.get("url"), str) else None,
                metadata={
                    key: value
                    for key, value in result.items()
                    if key not in {"title", "url"}
                },
            )
        )
    return citations


def _append_file_inputs(messages: list[dict[str, Any]], files: list[FileInput]) -> None:
    file_blocks = [file_input_to_anthropic_content_block(file_input) for file_input in files]
    for message in reversed(messages):
        if message.get("role") != Role.USER.value:
            continue
        content = message.get("content")
        if isinstance(content, str):
            message["content"] = [{"type": "text", "text": content}, *file_blocks]
        elif isinstance(content, list):
            message["content"] = [*content, *file_blocks]
        else:
            message["content"] = file_blocks
        return
    messages.append({"role": "user", "content": file_blocks})


def _anthropic_file_block_type(media_type: str | None) -> str:
    if media_type and media_type.startswith("image/"):
        return "image"
    return "document"


def _typed_file_inputs(files: list[Any]) -> list[FileInput]:
    return [file_input for file_input in files if isinstance(file_input, FileInput)]

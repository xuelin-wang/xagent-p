from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from xagent.llm_contracts.usage import Usage


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class Message(BaseModel):
    role: Role
    content: str | list[TextPart]
    name: str | None = None
    tool_call_id: str | None = None


class GenerateRequest(BaseModel):
    model: str | None = None
    messages: list[Message]
    temperature: float | None = None
    max_output_tokens: int | None = None
    stop: list[str] | None = None
    files: list[Any] = Field(default_factory=list)
    app_tools: list[Any] = Field(default_factory=list)
    provider_tools: list[Any] = Field(default_factory=list)
    tool_choice: Any | None = None
    response_format: Any | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    provider: str
    model: str
    text: str | None = None
    app_tool_calls: list[Any] = Field(default_factory=list)
    provider_tool_traces: list[Any] = Field(default_factory=list)
    files: list[Any] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: Usage | None = None
    raw_response: dict[str, Any] | None = None

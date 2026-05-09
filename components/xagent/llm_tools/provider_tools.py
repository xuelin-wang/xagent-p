from typing import Any, Literal

from pydantic import BaseModel, Field


class ProviderHostedTool(BaseModel):
    type: str
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    title: str | None = None
    url: str | None = None
    file_id: str | None = None
    quote: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderToolTrace(BaseModel):
    tool_type: str
    name: str | None = None
    status: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    raw: dict[str, Any] | None = None


class ToolChoice(BaseModel):
    mode: Literal["auto", "none", "required"] = "auto"
    tool_name: str | None = None

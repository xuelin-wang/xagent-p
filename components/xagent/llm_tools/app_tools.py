from typing import Any

from pydantic import BaseModel


class AppToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class AppToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class AppToolResult(BaseModel):
    tool_call_id: str
    name: str
    result: Any
    is_error: bool = False

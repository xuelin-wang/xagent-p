import pytest

from xagent.llm_contracts import AppToolCallValidationError
from xagent.llm_tools import AppToolCall, AppToolDefinition, validate_app_tool_call


def test_validate_app_tool_call_checks_required_fields() -> None:
    definition = AppToolDefinition(
        name="lookup",
        description="Lookup a record.",
        input_schema={"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
    )

    with pytest.raises(AppToolCallValidationError):
        validate_app_tool_call(AppToolCall(id="1", name="lookup", arguments={}), definition)


def test_validate_app_tool_call_passes() -> None:
    definition = AppToolDefinition(
        name="lookup",
        description="Lookup a record.",
        input_schema={"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
    )

    validate_app_tool_call(AppToolCall(id="1", name="lookup", arguments={"id": "abc"}), definition)

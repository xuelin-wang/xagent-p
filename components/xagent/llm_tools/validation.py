from xagent.llm_contracts import AppToolCallValidationError, LLMErrorPayload
from xagent.llm_tools.app_tools import AppToolCall, AppToolDefinition


def validate_app_tool_call(call: AppToolCall, definition: AppToolDefinition) -> None:
    schema = definition.input_schema
    required = schema.get("required", [])
    missing = [field for field in required if field not in call.arguments]
    if missing:
        raise AppToolCallValidationError(
            LLMErrorPayload(
                provider="app",
                operation="validate_app_tool_call",
                message=(
                    f"Invalid arguments for app tool '{definition.name}': "
                    f"missing required fields {missing}."
                ),
                retryable=False,
            )
        )

    properties = schema.get("properties", {})
    for name, property_schema in properties.items():
        expected_type = property_schema.get("type")
        if name not in call.arguments or expected_type is None:
            continue
        value = call.arguments[name]
        if expected_type == "string" and not isinstance(value, str):
            _raise_type_error(definition, name, expected_type)
        if expected_type == "number" and not isinstance(value, int | float):
            _raise_type_error(definition, name, expected_type)
        if expected_type == "integer" and not isinstance(value, int):
            _raise_type_error(definition, name, expected_type)
        if expected_type == "boolean" and not isinstance(value, bool):
            _raise_type_error(definition, name, expected_type)
        if expected_type == "object" and not isinstance(value, dict):
            _raise_type_error(definition, name, expected_type)
        if expected_type == "array" and not isinstance(value, list):
            _raise_type_error(definition, name, expected_type)


def _raise_type_error(definition: AppToolDefinition, field_name: str, expected_type: str) -> None:
    raise AppToolCallValidationError(
        LLMErrorPayload(
            provider="app",
            operation="validate_app_tool_call",
            message=(
                f"Invalid arguments for app tool '{definition.name}': "
                f"field '{field_name}' must be {expected_type}."
            ),
            retryable=False,
        )
    )

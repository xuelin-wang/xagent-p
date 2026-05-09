from xagent.llm_tools import AppToolCall, AppToolDefinition


def test_app_tool_models() -> None:
    definition = AppToolDefinition(
        name="lookup",
        description="Lookup a record.",
        input_schema={"type": "object", "required": ["id"]},
    )
    call = AppToolCall(id="call-1", name="lookup", arguments={"id": "abc"})

    assert definition.name == call.name

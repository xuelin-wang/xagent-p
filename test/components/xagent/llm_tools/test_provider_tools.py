from xagent.llm_tools import ProviderHostedTool, ProviderToolTrace


def test_provider_tool_models() -> None:
    tool = ProviderHostedTool(type="web_search", config={"depth": "low"})
    trace = ProviderToolTrace(tool_type="web_search", status="completed")

    assert tool.type == trace.tool_type

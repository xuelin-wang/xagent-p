import asyncio

from xagent.llm_contracts import GenerateRequest, GenerateResponse, Message, Role
from xagent.llm_tools import AppToolCall, AppToolDefinition, run_app_tool_loop


class ToolThenDoneProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        self.calls += 1
        if self.calls == 1:
            return GenerateResponse(
                provider="fake",
                model="fake-model",
                app_tool_calls=[AppToolCall(id="call-1", name="lookup", arguments={"id": "abc"})],
            )
        return GenerateResponse(provider="fake", model="fake-model", text="done")


async def _test_run_app_tool_loop_executes_until_final_response() -> None:
    async def lookup(arguments: dict) -> str:
        return f"record:{arguments['id']}"

    response = await run_app_tool_loop(
        ToolThenDoneProvider(),
        GenerateRequest(
            messages=[Message(role=Role.USER, content="lookup abc")],
            app_tools=[
                AppToolDefinition(
                    name="lookup",
                    description="Lookup.",
                    input_schema={"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
                )
            ],
        ),
        {"lookup": lookup},
    )

    assert response.text == "done"


def test_run_app_tool_loop_executes_until_final_response() -> None:
    asyncio.run(_test_run_app_tool_loop_executes_until_final_response())

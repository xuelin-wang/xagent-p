import asyncio

from xagent.llm_batch import ConcurrentBatchRequest, generate_many
from xagent.llm_contracts import GenerateRequest, GenerateResponse, Message, Role


class EchoProvider:
    provider_name = "echo"

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(provider="echo", model="echo-model", text=str(request.messages[0].content))


async def _test_generate_many() -> None:
    results = await generate_many(
        EchoProvider(),
        ConcurrentBatchRequest(
            requests=[
                GenerateRequest(messages=[Message(role=Role.USER, content="a")]),
                GenerateRequest(messages=[Message(role=Role.USER, content="b")]),
            ]
        ),
    )

    assert [result.response.text for result in results] == ["a", "b"]


def test_generate_many() -> None:
    asyncio.run(_test_generate_many())

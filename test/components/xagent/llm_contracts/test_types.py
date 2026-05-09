from xagent.llm_contracts import GenerateRequest, Message, Role, TextPart


def test_generate_request_accepts_basic_messages() -> None:
    request = GenerateRequest(
        messages=[
            Message(role=Role.SYSTEM, content="Be concise."),
            Message(role=Role.USER, content=[TextPart(text="Hello")]),
        ],
        metadata={"trace": "unit"},
    )

    assert request.messages[0].role == Role.SYSTEM
    assert request.messages[1].content[0].text == "Hello"
    assert request.metadata == {"trace": "unit"}

from xagent.llm_batch import BatchCreateRequest, BatchRequestItem, BatchStatus
from xagent.llm_contracts import GenerateRequest, Message, Role


def test_batch_models() -> None:
    request = GenerateRequest(messages=[Message(role=Role.USER, content="hello")])
    batch = BatchCreateRequest(items=[BatchRequestItem(custom_id="1", request=request)])

    assert batch.mode == "native"
    assert BatchStatus.SUCCEEDED.value == "succeeded"

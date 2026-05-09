import pytest
from pydantic import ValidationError

from xagent.llm_batch import BatchCreateRequest, BatchRequestItem, BatchStatus
from xagent.llm_contracts import GenerateRequest, Message, Role


def test_batch_models() -> None:
    request = GenerateRequest(messages=[Message(role=Role.USER, content="hello")])
    batch = BatchCreateRequest(items=[BatchRequestItem(custom_id="1", request=request)])

    assert batch.mode == "native"
    assert BatchStatus.SUCCEEDED.value == "succeeded"


def test_batch_create_request_rejects_input_file() -> None:
    request = GenerateRequest(messages=[Message(role=Role.USER, content="hello")])

    with pytest.raises(ValidationError):
        BatchCreateRequest(
            items=[BatchRequestItem(custom_id="1", request=request)],
            input_file={"provider": "openai", "file_id": "file-123"},
        )

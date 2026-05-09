import pytest
from pydantic import BaseModel

from xagent.llm_contracts import StructuredOutputValidationError
from xagent.llm_structured import parse_json_object, validate_structured_output


class SampleOutput(BaseModel):
    value: str


def test_parse_json_object() -> None:
    assert parse_json_object('{"value": "ok"}') == {"value": "ok"}


def test_validate_structured_output() -> None:
    assert validate_structured_output({"value": "ok"}, SampleOutput, provider="test", model="m").value == "ok"


def test_validate_structured_output_raises() -> None:
    with pytest.raises(StructuredOutputValidationError):
        validate_structured_output({}, SampleOutput, provider="test", model="m")

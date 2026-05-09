from pydantic import BaseModel

from xagent.llm_structured import ResponseFormatType, response_format_for_model


class SampleOutput(BaseModel):
    value: str


def test_response_format_for_model() -> None:
    response_format = response_format_for_model(SampleOutput)

    assert response_format.type == ResponseFormatType.JSON_SCHEMA
    assert response_format.schema_name == "SampleOutput"
    assert "properties" in response_format.json_schema

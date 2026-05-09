from typing import Any

from xagent.llm_batch import EmbeddingRequest, EmbeddingResponse, EmbeddingVector
from xagent.llm_contracts import Usage

OPENAI_EMBEDDING_MODELS = {
    "text-embedding-3-small",
    "text-embedding-3-large",
}

DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


def request_to_openai_embeddings_payload(request: EmbeddingRequest, model: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": request.inputs,
        "encoding_format": "float",
    }
    if request.dimensions is not None:
        payload["dimensions"] = request.dimensions
    if request.metadata.get("user"):
        payload["user"] = request.metadata["user"]
    return payload


def response_from_openai_embeddings(raw: dict[str, Any], model: str) -> EmbeddingResponse:
    vectors = [
        EmbeddingVector(index=item["index"], embedding=item["embedding"])
        for item in sorted(raw.get("data", []), key=lambda item: item.get("index", 0))
        if isinstance(item, dict) and isinstance(item.get("embedding"), list)
    ]
    dimensions = len(vectors[0].embedding) if vectors else 0
    usage = raw.get("usage") or {}
    return EmbeddingResponse(
        provider="openai",
        model=raw.get("model") or model,
        vectors=vectors,
        dimensions=dimensions,
        usage=Usage(
            input_tokens=usage.get("prompt_tokens"),
            total_tokens=usage.get("total_tokens"),
            raw=usage or None,
        ),
        raw_response=raw,
    )

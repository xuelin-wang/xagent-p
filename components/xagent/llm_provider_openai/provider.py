from datetime import UTC, datetime
from typing import TypeVar

import httpx

from xagent.llm_batch import (
    BatchCreateRequest,
    BatchJob,
    BatchResults,
    EmbeddingRequest,
    EmbeddingResponse,
)
from xagent.llm_config import ProviderConfig, resolve_api_key
from xagent.llm_contracts import (
    AuthenticationError,
    Capability,
    GenerateRequest,
    GenerateResponse,
    InvalidRequestError,
    LLMErrorPayload,
    Message,
    ModelCapabilities,
    PermissionDeniedError,
    ProviderServerError,
    ProviderTimeoutError,
    RateLimitError,
    Role,
    UnsupportedCapabilityError,
    assert_capability,
)
from xagent.llm_files import (
    BytesFileSource,
    FileDeleteRequest,
    FilePurpose,
    FileUploadRequest,
    UploadedFile,
    read_upload_bytes,
)
from xagent.llm_provider_openai.mapping import (
    request_to_openai_responses_payload,
    response_from_openai_responses,
)
from xagent.llm_provider_openai.batch import (
    OPENAI_BATCH_COMPLETION_WINDOW,
    batch_job_from_openai,
    batch_results_from_openai_jsonl,
    request_to_openai_batch_jsonl,
)
from xagent.llm_provider_openai.embeddings import (
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODELS,
    request_to_openai_embeddings_payload,
    response_from_openai_embeddings,
)
from xagent.llm_provider_openai.files import openai_file_purpose
from xagent.llm_retry import is_retryable_status, parse_retry_after, retry_async, to_httpx_timeout
from xagent.llm_structured import (
    StructuredGenerateRequest,
    StructuredGenerateResponse,
    parse_json_object,
    validate_structured_output,
)

T = TypeVar("T")

OPENAI_TEXT_MODELS = {
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
}

OPENAI_PROVIDER_TOOL_TYPES = {
    "web_search",
    "file_search",
    "code_interpreter",
    "computer_use_preview",
}


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, config: ProviderConfig, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self._transport = transport

    def capabilities(self, model: str | None = None) -> ModelCapabilities:
        selected_model = model or self.config.default_model
        return ModelCapabilities(
            provider=self.provider_name,
            model=selected_model,
            capabilities={
                Capability.TEXT_GENERATION,
                Capability.STRUCTURED_OUTPUT,
                Capability.APP_TOOL_CALLS,
                Capability.PROVIDER_HOSTED_TOOLS,
                Capability.MIXED_APP_AND_PROVIDER_TOOLS,
                Capability.FILE_UPLOAD,
                Capability.FILE_INPUT,
                Capability.EMBEDDINGS,
                Capability.NATIVE_BATCH,
                Capability.CONCURRENT_BATCH,
            },
            provider_tools=OPENAI_PROVIDER_TOOL_TYPES,
        )

    def _resolve_text_model(self, model: str | None, operation: str) -> str:
        selected_model = model or self.config.default_model
        if selected_model in OPENAI_TEXT_MODELS:
            return selected_model
        raise UnsupportedCapabilityError(
            LLMErrorPayload(
                provider=self.provider_name,
                model=selected_model,
                operation=operation,
                message=f"OpenAI text model is not supported: {selected_model}.",
                retryable=False,
            )
        )

    def _check_generate_capabilities(self, request: GenerateRequest) -> str:
        model = self._resolve_text_model(request.model, "generate")
        caps = self.capabilities(model)
        assert_capability(caps, Capability.TEXT_GENERATION, operation="generate")
        if request.app_tools:
            assert_capability(caps, Capability.APP_TOOL_CALLS, operation="generate")
        if request.provider_tools:
            assert_capability(caps, Capability.PROVIDER_HOSTED_TOOLS, operation="generate")
            self._check_provider_tools(request.provider_tools, model)
        if request.app_tools and request.provider_tools:
            assert_capability(caps, Capability.MIXED_APP_AND_PROVIDER_TOOLS, operation="generate")
        if request.files:
            assert_capability(caps, Capability.FILE_INPUT, operation="generate")
        if request.response_format is not None:
            assert_capability(caps, Capability.STRUCTURED_OUTPUT, operation="generate")
        return model

    def _check_provider_tools(self, provider_tools: list, model: str) -> None:
        for tool in provider_tools:
            tool_type = getattr(tool, "type", None)
            if tool_type in OPENAI_PROVIDER_TOOL_TYPES:
                continue
            raise UnsupportedCapabilityError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="generate",
                    message=f"OpenAI provider-hosted tool is not supported: {tool_type}.",
                    retryable=False,
                )
            )

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        model = self._check_generate_capabilities(request)
        self._ensure_supported_generate_fields(request, allow_response_format=True)
        payload = request_to_openai_responses_payload(request, model)
        response = await self._post_responses(payload, model, operation="generate")
        return response_from_openai_responses(response.json(), model)

    async def generate_structured(
        self,
        request: StructuredGenerateRequest,
        output_type: type[T],
    ) -> StructuredGenerateResponse[T]:
        model = self._check_generate_capabilities(request)
        self._ensure_supported_generate_fields(request, allow_response_format=True)
        current = request
        attempts = request.validation_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            payload = request_to_openai_responses_payload(current, model)
            response = await self._post_responses(payload, model, operation="generate_structured")
            generated = response_from_openai_responses(response.json(), model)
            try:
                raw_json = parse_json_object(generated.text or "")
                data = validate_structured_output(
                    raw_json,
                    output_type,
                    provider=self.provider_name,
                    model=generated.model,
                )
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise
                current = current.model_copy(
                    update={
                        "messages": [
                            *current.messages,
                            Message(
                                role=Role.USER,
                                content=(
                                    "The previous structured output failed validation. "
                                    f"Return corrected JSON only. Validation error: {exc}"
                                ),
                            ),
                        ]
                    }
                )
                continue

            return StructuredGenerateResponse(
                provider=self.provider_name,
                model=generated.model,
                data=data,
                raw_json=raw_json,
                usage=generated.usage,
                raw_response=generated.raw_response,
            )

        raise RuntimeError("OpenAI structured generation failed unexpectedly.") from last_error

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        model = request.model or DEFAULT_OPENAI_EMBEDDING_MODEL
        if model not in OPENAI_EMBEDDING_MODELS:
            raise UnsupportedCapabilityError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="embed",
                    message=f"OpenAI embedding model is not supported: {model}.",
                    retryable=False,
                )
            )
        payload = request_to_openai_embeddings_payload(request, model)
        response = await self._post_embeddings(payload, model)
        return response_from_openai_embeddings(response.json(), model)

    async def _post_embeddings(self, payload: dict, model: str) -> httpx.Response:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="embed",
                    message="Missing API key for provider 'openai'.",
                    retryable=False,
                )
            )

        base_url = self.config.base_url or "https://api.openai.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                response = await self._send_with_retries(
                    operation="embed",
                    request=lambda: client.post(
                        "/embeddings",
                        headers={
                            "Authorization": f"Bearer {api_key.get_secret_value()}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="embed",
                    retryable=True,
                    message=f"OpenAI embeddings request timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="embed",
                    retryable=True,
                    message=f"OpenAI embeddings request failed before receiving a response: {exc}",
                )
            ) from exc

        if response.is_error:
            self._raise_response_error(response, model, operation="embed")
        return response

    async def upload_file(self, request: FileUploadRequest) -> UploadedFile:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="upload_file",
                    message="Missing API key for provider 'openai'.",
                    retryable=False,
                )
            )

        filename, data, media_type = read_upload_bytes(request)
        purpose = openai_file_purpose(request.purpose)
        base_url = self.config.base_url or "https://api.openai.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                # Do not retry resource-creating uploads: providers do not document
                # idempotency keys for this endpoint, so a lost response could create duplicates.
                response = await client.post(
                    "/files",
                    headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
                    data={"purpose": purpose},
                    files={"file": (filename, data, media_type or "application/octet-stream")},
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="upload_file",
                    retryable=True,
                    message=f"OpenAI file upload timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="upload_file",
                    retryable=True,
                    message=f"OpenAI file upload failed before receiving a response: {exc}",
                )
            ) from exc

        if response.is_error:
            self._raise_response_error(response, None, operation="upload_file")
        raw = response.json()
        return UploadedFile(
            provider=self.provider_name,
            file_id=raw["id"],
            filename=raw.get("filename"),
            media_type=media_type,
            size_bytes=raw.get("bytes"),
            purpose=request.purpose,
            expires_at=_datetime_from_unix_seconds(raw.get("expires_at")),
            raw_response=raw,
        )

    async def delete_file(self, request: FileDeleteRequest) -> None:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    message="Missing API key for provider 'openai'.",
                    retryable=False,
                )
            )
        if request.provider != self.provider_name:
            raise UnsupportedCapabilityError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    message=f"Cannot delete file for provider '{request.provider}' with OpenAI provider.",
                    retryable=False,
                )
            )

        base_url = self.config.base_url or "https://api.openai.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                # Send once to avoid ambiguous retry outcomes after a successful server-side delete.
                response = await client.delete(
                    f"/files/{request.file_id}",
                    headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    retryable=True,
                    message=f"OpenAI file delete timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    retryable=True,
                    message=f"OpenAI file delete failed before receiving a response: {exc}",
                )
            ) from exc

        if response.is_error:
            self._raise_response_error(response, None, operation="delete_file")

    async def create_batch(self, request: BatchCreateRequest) -> BatchJob:
        endpoint, jsonl = request_to_openai_batch_jsonl(request, self.config.default_model)
        uploaded = await self.upload_file(
            FileUploadRequest(
                source=BytesFileSource(
                    filename="openai-batch-input.jsonl",
                    data=jsonl.encode("utf-8"),
                    media_type="application/jsonl",
                ),
                purpose=FilePurpose.BATCH_INPUT,
            )
        )
        payload = {
            "input_file_id": uploaded.file_id,
            "endpoint": endpoint,
            "completion_window": OPENAI_BATCH_COMPLETION_WINDOW,
        }
        if request.metadata:
            payload["metadata"] = request.metadata
        response = await self._post_batch(payload, operation="create_batch")
        return batch_job_from_openai(response.json())

    async def get_batch(self, batch_id: str) -> BatchJob:
        response = await self._get_batch_response(batch_id)
        return batch_job_from_openai(response.json())

    async def cancel_batch(self, batch_id: str) -> BatchJob:
        response = await self._post_batch({}, operation="cancel_batch", path=f"/batches/{batch_id}/cancel")
        return batch_job_from_openai(response.json())

    async def get_batch_results(self, batch_id: str) -> BatchResults:
        job = await self.get_batch(batch_id)
        raw = job.raw_response or {}
        output_text = await self._download_file_text(raw.get("output_file_id"))
        error_text = await self._download_file_text(raw.get("error_file_id"))
        return batch_results_from_openai_jsonl(
            batch_id=batch_id,
            status=job.status,
            output_text=output_text,
            error_text=error_text,
        )

    async def _post_batch(
        self,
        payload: dict,
        *,
        operation: str,
        path: str = "/batches",
    ) -> httpx.Response:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    message="Missing API key for provider 'openai'.",
                    retryable=False,
                )
            )
        base_url = self.config.base_url or "https://api.openai.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                # Batch create/cancel are provider-side mutations and are not documented
                # as idempotent, so retries are left to callers with their own de-dupe state.
                response = await client.post(
                    path,
                    headers={
                        "Authorization": f"Bearer {api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    retryable=True,
                    message=f"OpenAI batch request timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    retryable=True,
                    message=f"OpenAI batch request failed before receiving a response: {exc}",
                )
            ) from exc
        if response.is_error:
            self._raise_response_error(response, None, operation=operation)
        return response

    async def _get_batch_response(self, batch_id: str) -> httpx.Response:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="get_batch",
                    message="Missing API key for provider 'openai'.",
                    retryable=False,
                )
            )
        base_url = self.config.base_url or "https://api.openai.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                response = await self._send_with_retries(
                    operation="get_batch",
                    request=lambda: client.get(
                        f"/batches/{batch_id}",
                        headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="get_batch",
                    retryable=True,
                    message=f"OpenAI batch get timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="get_batch",
                    retryable=True,
                    message=f"OpenAI batch get failed before receiving a response: {exc}",
                )
            ) from exc
        if response.is_error:
            self._raise_response_error(response, None, operation="get_batch")
        return response

    async def _download_file_text(self, file_id: object) -> str:
        if not isinstance(file_id, str):
            return ""
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="download_file",
                    message="Missing API key for provider 'openai'.",
                    retryable=False,
                )
            )
        base_url = self.config.base_url or "https://api.openai.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                response = await self._send_with_retries(
                    operation="download_file",
                    request=lambda: client.get(
                        f"/files/{file_id}/content",
                        headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="download_file",
                    retryable=True,
                    message=f"OpenAI file download timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="download_file",
                    retryable=True,
                    message=f"OpenAI file download failed before receiving a response: {exc}",
                )
            ) from exc
        if response.is_error:
            self._raise_response_error(response, None, operation="download_file")
        return response.text

    async def _post_responses(
        self,
        payload: dict,
        model: str,
        *,
        operation: str,
    ) -> httpx.Response:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation=operation,
                    message="Missing API key for provider 'openai'.",
                    retryable=False,
                )
            )

        base_url = self.config.base_url or "https://api.openai.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                response = await self._send_with_retries(
                    operation=operation,
                    request=lambda: client.post(
                        "/responses",
                        headers={
                            "Authorization": f"Bearer {api_key.get_secret_value()}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation=operation,
                    retryable=True,
                    message=f"OpenAI request timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation=operation,
                    retryable=True,
                    message=f"OpenAI request failed before receiving a response: {exc}",
                )
            ) from exc

        if response.is_error:
            self._raise_response_error(response, model, operation=operation)
        return response

    def _ensure_supported_generate_fields(
        self,
        request: GenerateRequest,
        *,
        allow_response_format: bool,
    ) -> None:
        unsupported: list[str] = []
        if request.response_format is not None and not allow_response_format:
            unsupported.append("response_format")
        if unsupported:
            raise NotImplementedError(
                "OpenAI generate currently does not support fields: "
                + ", ".join(unsupported)
            )

    async def _send_with_retries(
        self,
        *,
        operation: str,
        request,
    ) -> httpx.Response:
        return await retry_async(
            request,
            self.config.retry,
            should_retry_result=lambda response: is_retryable_status(response.status_code),
            retry_after_from_result=lambda response: parse_retry_after(response.headers.get("retry-after")),
            should_retry_exception=lambda exc: isinstance(exc, (httpx.TimeoutException, httpx.TransportError)),
        )

    def _raise_response_error(self, response: httpx.Response, model: str | None, *, operation: str) -> None:
        raw_error = _safe_json(response)
        message = _error_message(raw_error) or response.text
        request_id = response.headers.get("x-request-id")
        payload = LLMErrorPayload(
            provider=self.provider_name,
            model=model,
            operation=operation,
            status_code=response.status_code,
            request_id=request_id,
            retryable=response.status_code in {408, 429, 500, 502, 503, 504},
            message=message,
            raw_error=raw_error,
        )
        if response.status_code == 401:
            raise AuthenticationError(payload)
        if response.status_code == 403:
            raise PermissionDeniedError(payload)
        if response.status_code == 429:
            raise RateLimitError(payload)
        if 400 <= response.status_code < 500:
            raise InvalidRequestError(payload)
        raise ProviderServerError(payload)


def _safe_json(response: httpx.Response) -> dict | None:
    try:
        loaded = response.json()
    except ValueError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _error_message(raw_error: dict | None) -> str | None:
    if not raw_error:
        return None
    error = raw_error.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(raw_error.get("message"), str):
        return raw_error["message"]
    return None


def _datetime_from_unix_seconds(value: object) -> datetime | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value, tz=UTC)

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
    StructuredOutputValidationError,
    UnsupportedCapabilityError,
    assert_capability,
)
from xagent.llm_files import (
    FileDeleteRequest,
    FileInput,
    FileUploadRequest,
    ProviderFileRef,
    UploadedFile,
    read_upload_bytes,
)
from xagent.llm_provider_anthropic.mapping import (
    ANTHROPIC_PROVIDER_TOOL_TYPES,
    request_to_anthropic_messages_payload,
    response_from_anthropic_message,
)
from xagent.llm_provider_anthropic.batch import (
    batch_job_from_anthropic,
    batch_results_from_anthropic_jsonl,
    request_to_anthropic_batch_payload,
)
from xagent.llm_provider_anthropic.files import ANTHROPIC_FILES_BETA, anthropic_files_beta_header
from xagent.llm_retry import is_retryable_status, parse_retry_after, retry_async, to_httpx_timeout
from xagent.llm_structured import StructuredGenerateRequest, StructuredGenerateResponse, validate_structured_output
from xagent.llm_tools import AppToolDefinition, ToolChoice

T = TypeVar("T")

ANTHROPIC_TEXT_MODELS = {
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
}


class AnthropicProvider:
    provider_name = "anthropic"

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
                Capability.FILE_UPLOAD,
                Capability.FILE_INPUT,
                Capability.NATIVE_BATCH,
                Capability.CONCURRENT_BATCH,
            },
            provider_tools=ANTHROPIC_PROVIDER_TOOL_TYPES,
        )

    def _resolve_text_model(self, model: str | None, operation: str) -> str:
        selected_model = model or self.config.default_model
        if selected_model in ANTHROPIC_TEXT_MODELS:
            return selected_model
        raise UnsupportedCapabilityError(
            LLMErrorPayload(
                provider=self.provider_name,
                model=selected_model,
                operation=operation,
                message=f"Anthropic text model is not supported: {selected_model}.",
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
            if tool_type in ANTHROPIC_PROVIDER_TOOL_TYPES:
                continue
            raise UnsupportedCapabilityError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="generate",
                    message=f"Anthropic provider-hosted tool is not supported: {tool_type}.",
                    retryable=False,
                )
            )

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        model = self._check_generate_capabilities(request)
        self._ensure_text_only_request(request)
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="generate",
                    message="Missing API key for provider 'anthropic'.",
                    retryable=False,
                )
            )

        base_url = self.config.base_url or "https://api.anthropic.com/v1"
        payload = request_to_anthropic_messages_payload(request, model)
        headers = {
            "x-api-key": api_key.get_secret_value(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        if _uses_anthropic_uploaded_file(request):
            headers.update(anthropic_files_beta_header())
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                response = await self._send_with_retries(
                    operation="generate",
                    request=lambda: client.post(
                        "/messages",
                        headers=headers,
                        json=payload,
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="generate",
                    retryable=True,
                    message=f"Anthropic request timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    model=model,
                    operation="generate",
                    retryable=True,
                    message=f"Anthropic request failed before receiving a response: {exc}",
                )
            ) from exc

        if response.is_error:
            self._raise_response_error(response, model)
        return response_from_anthropic_message(response.json(), model)

    async def generate_structured(
        self,
        request: StructuredGenerateRequest,
        output_type: type[T],
    ) -> StructuredGenerateResponse[T]:
        model = self._check_generate_capabilities(request)
        self._ensure_supported_generate_fields(request, allow_response_format=True)
        extraction_tool = _structured_output_tool(request, output_type)
        current = request.model_copy(
            update={
                "response_format": None,
                "app_tools": [*request.app_tools, extraction_tool],
                "tool_choice": ToolChoice(mode="required", tool_name=extraction_tool.name),
            }
        )
        attempts = request.validation_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            response = await self.generate(current)
            raw_json = _structured_tool_input(response, extraction_tool.name)
            try:
                data = validate_structured_output(
                    raw_json,
                    output_type,
                    provider=self.provider_name,
                    model=response.model,
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
                                    f"Call {extraction_tool.name} again with corrected arguments. "
                                    f"Validation error: {exc}"
                                ),
                            ),
                        ]
                    }
                )
                continue

            return StructuredGenerateResponse(
                provider=self.provider_name,
                model=response.model,
                data=data,
                raw_json=raw_json,
                usage=response.usage,
                raw_response=response.raw_response,
            )

        raise RuntimeError("Anthropic structured generation failed unexpectedly.") from last_error

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise UnsupportedCapabilityError(
            LLMErrorPayload(
                provider=self.provider_name,
                model=request.model,
                operation="embed",
                message="Anthropic embeddings are not supported by this wrapper.",
                retryable=False,
            )
        )

    async def upload_file(self, request: FileUploadRequest) -> UploadedFile:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="upload_file",
                    message="Missing API key for provider 'anthropic'.",
                    retryable=False,
                )
            )

        filename, data, media_type = read_upload_bytes(request)
        base_url = self.config.base_url or "https://api.anthropic.com/v1"
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
                    headers={
                        "x-api-key": api_key.get_secret_value(),
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": ANTHROPIC_FILES_BETA,
                    },
                    files={"file": (filename, data, media_type or "application/octet-stream")},
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="upload_file",
                    retryable=True,
                    message=f"Anthropic file upload timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="upload_file",
                    retryable=True,
                    message=f"Anthropic file upload failed before receiving a response: {exc}",
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
            size_bytes=raw.get("size_bytes") or raw.get("bytes"),
            purpose=request.purpose,
            raw_response=raw,
        )

    async def delete_file(self, request: FileDeleteRequest) -> None:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    message="Missing API key for provider 'anthropic'.",
                    retryable=False,
                )
            )
        if request.provider != self.provider_name:
            raise UnsupportedCapabilityError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    message=f"Cannot delete file for provider '{request.provider}' with Anthropic provider.",
                    retryable=False,
                )
            )

        base_url = self.config.base_url or "https://api.anthropic.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                # Send once to avoid ambiguous retry outcomes after a successful server-side delete.
                response = await client.delete(
                    f"/files/{request.file_id}",
                    headers={
                        "x-api-key": api_key.get_secret_value(),
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": ANTHROPIC_FILES_BETA,
                    },
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    retryable=True,
                    message=f"Anthropic file delete timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation="delete_file",
                    retryable=True,
                    message=f"Anthropic file delete failed before receiving a response: {exc}",
                )
            ) from exc

        if response.is_error:
            self._raise_response_error(response, None, operation="delete_file")

    async def create_batch(self, request: BatchCreateRequest) -> BatchJob:
        payload = request_to_anthropic_batch_payload(request, self.config.default_model)
        response = await self._post_batch(
            "/messages/batches",
            payload,
            operation="create_batch",
            files_api=_batch_uses_anthropic_uploaded_file(request),
        )
        return batch_job_from_anthropic(response.json())

    async def get_batch(self, batch_id: str) -> BatchJob:
        response = await self._get_batch_response(f"/messages/batches/{batch_id}", operation="get_batch")
        return batch_job_from_anthropic(response.json())

    async def cancel_batch(self, batch_id: str) -> BatchJob:
        response = await self._post_batch(
            f"/messages/batches/{batch_id}/cancel",
            {},
            operation="cancel_batch",
        )
        return batch_job_from_anthropic(response.json())

    async def get_batch_results(self, batch_id: str) -> BatchResults:
        job = await self.get_batch(batch_id)
        response = await self._get_batch_response(
            f"/messages/batches/{batch_id}/results",
            operation="get_batch_results",
        )
        return batch_results_from_anthropic_jsonl(
            batch_id=batch_id,
            status=job.status,
            text=response.text,
        )

    async def _post_batch(
        self,
        path: str,
        payload: dict,
        *,
        operation: str,
        files_api: bool = False,
    ) -> httpx.Response:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    message="Missing API key for provider 'anthropic'.",
                    retryable=False,
                )
            )
        headers = {
            "x-api-key": api_key.get_secret_value(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        if files_api:
            headers.update(anthropic_files_beta_header())
        base_url = self.config.base_url or "https://api.anthropic.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                # Batch create/cancel are provider-side mutations and are not documented
                # as idempotent, so retries are left to callers with their own de-dupe state.
                response = await client.post(path, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    retryable=True,
                    message=f"Anthropic batch request timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    retryable=True,
                    message=f"Anthropic batch request failed before receiving a response: {exc}",
                )
            ) from exc
        if response.is_error:
            self._raise_response_error(response, None, operation=operation)
        return response

    async def _get_batch_response(self, path: str, *, operation: str) -> httpx.Response:
        api_key = resolve_api_key(self.config)
        if api_key is None:
            raise AuthenticationError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    message="Missing API key for provider 'anthropic'.",
                    retryable=False,
                )
            )
        base_url = self.config.base_url or "https://api.anthropic.com/v1"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=to_httpx_timeout(self.config.timeout),
                transport=self._transport,
            ) as client:
                response = await self._send_with_retries(
                    operation=operation,
                    request=lambda: client.get(
                        path,
                        headers={
                            "x-api-key": api_key.get_secret_value(),
                            "anthropic-version": "2023-06-01",
                        },
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    retryable=True,
                    message=f"Anthropic batch request timed out: {exc}",
                )
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                LLMErrorPayload(
                    provider=self.provider_name,
                    operation=operation,
                    retryable=True,
                    message=f"Anthropic batch request failed before receiving a response: {exc}",
                )
            ) from exc
        if response.is_error:
            self._raise_response_error(response, None, operation=operation)
        return response

    def _ensure_text_only_request(self, request: GenerateRequest) -> None:
        self._ensure_supported_generate_fields(request, allow_response_format=False)

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
                "Anthropic generate currently supports text-only requests; unsupported fields: "
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

    def _raise_response_error(
        self,
        response: httpx.Response,
        model: str | None,
        *,
        operation: str = "generate",
    ) -> None:
        raw_error = _safe_json(response)
        message = _error_message(raw_error) or response.text
        request_id = response.headers.get("request-id")
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


def _uses_anthropic_uploaded_file(request: GenerateRequest) -> bool:
    for file_input in request.files:
        if not isinstance(file_input, FileInput):
            continue
        source = file_input.source
        if isinstance(source, ProviderFileRef) and source.provider == "anthropic":
            return True
    return False


def _batch_uses_anthropic_uploaded_file(request: BatchCreateRequest) -> bool:
    return any(
        isinstance(item.request, GenerateRequest) and _uses_anthropic_uploaded_file(item.request)
        for item in request.items
    )


def _structured_output_tool(
    request: StructuredGenerateRequest,
    output_type: type,
) -> AppToolDefinition:
    return AppToolDefinition(
        name=request.response_format.schema_name or output_type.__name__,
        description="Extract the requested structured output. Return only fields described by the schema.",
        input_schema=request.response_format.json_schema or output_type.model_json_schema(),
    )


def _structured_tool_input(response: GenerateResponse, tool_name: str) -> dict:
    for call in response.app_tool_calls:
        if call.name == tool_name:
            return call.arguments
    raise StructuredOutputValidationError(
        LLMErrorPayload(
            provider=response.provider,
            model=response.model,
            operation="generate_structured",
            message=f"Anthropic structured generation did not call expected tool '{tool_name}'.",
            retryable=False,
            raw_error=response.raw_response,
        )
    )

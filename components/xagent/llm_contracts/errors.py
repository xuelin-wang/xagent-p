from typing import Any

from pydantic import BaseModel


class LLMErrorPayload(BaseModel):
    provider: str
    model: str | None = None
    operation: str
    status_code: int | None = None
    request_id: str | None = None
    retryable: bool = False
    message: str
    raw_error: dict[str, Any] | None = None


class LLMError(Exception):
    def __init__(self, payload: LLMErrorPayload):
        super().__init__(payload.message)
        self.payload = payload


class AuthenticationError(LLMError):
    pass


class PermissionDeniedError(LLMError):
    pass


class RateLimitError(LLMError):
    pass


class ProviderServerError(LLMError):
    pass


class ProviderTimeoutError(LLMError):
    pass


class InvalidRequestError(LLMError):
    pass


class UnsupportedCapabilityError(LLMError):
    pass


class StructuredOutputValidationError(LLMError):
    pass


class AppToolCallValidationError(LLMError):
    pass


class ToolLoopExceededError(LLMError):
    pass


class FileUploadError(LLMError):
    pass


class BatchJobError(LLMError):
    pass

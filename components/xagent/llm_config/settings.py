from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class TimeoutConfig(BaseModel):
    connect: float = 10.0
    read: float = 120.0
    write: float = 30.0
    pool: float = 10.0


class RetryConfig(BaseModel):
    enabled: bool = True
    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 20.0
    multiplier: float = 2.0
    jitter: bool = True
    respect_retry_after: bool = True


class PollingConfig(BaseModel):
    initial_interval_seconds: float = 2.0
    max_interval_seconds: float = 60.0
    timeout_seconds: float | None = None


class ProviderConfig(BaseModel):
    provider: Literal["openai", "anthropic"]
    default_model: str
    api_key: SecretStr | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)

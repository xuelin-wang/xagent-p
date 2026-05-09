from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class LocalFileSource(BaseModel):
    type: Literal["local_path"] = "local_path"
    path: str
    media_type: str | None = None


class BytesFileSource(BaseModel):
    type: Literal["bytes"] = "bytes"
    filename: str
    data: bytes
    media_type: str | None = None


class UrlFileSource(BaseModel):
    type: Literal["url"] = "url"
    url: str
    media_type: str | None = None


class ProviderFileRef(BaseModel):
    type: Literal["provider_file"] = "provider_file"
    provider: str
    file_id: str
    media_type: str | None = None
    filename: str | None = None


class CloudFileRef(BaseModel):
    type: Literal["cloud_file"] = "cloud_file"
    uri: str
    media_type: str | None = None


FileSource = Annotated[
    LocalFileSource | BytesFileSource | UrlFileSource | ProviderFileRef | CloudFileRef,
    Field(discriminator="type"),
]


class FilePurpose(str, Enum):
    PROMPT_INPUT = "prompt_input"
    PROVIDER_FILE_SEARCH = "provider_file_search"
    BATCH_INPUT = "batch_input"
    BATCH_OUTPUT = "batch_output"
    CODE_EXECUTION_INPUT = "code_execution_input"


class FileInput(BaseModel):
    source: FileSource
    purpose: FilePurpose = FilePurpose.PROMPT_INPUT
    name: str | None = None
    description: str | None = None


class FileUploadRequest(BaseModel):
    source: LocalFileSource | BytesFileSource
    purpose: FilePurpose
    metadata: dict[str, str] = Field(default_factory=dict)


class UploadedFile(BaseModel):
    provider: str
    file_id: str
    filename: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    purpose: FilePurpose
    expires_at: datetime | None = None
    raw_response: dict | None = None


class FileDeleteRequest(BaseModel):
    provider: str
    file_id: str


class GeneratedFile(BaseModel):
    provider: str
    file_id: str | None = None
    filename: str | None = None
    media_type: str | None = None
    bytes_data: bytes | None = None
    raw: dict | None = None

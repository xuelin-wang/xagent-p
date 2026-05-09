from xagent.llm_files import (
    BytesFileSource,
    FileInput,
    FilePurpose,
    FileUploadRequest,
    ProviderFileRef,
    read_upload_bytes,
)


def test_file_input_discriminates_provider_file_ref() -> None:
    file_input = FileInput(
        source={
            "type": "provider_file",
            "provider": "openai",
            "file_id": "file-123",
        }
    )

    assert isinstance(file_input.source, ProviderFileRef)
    assert file_input.purpose == FilePurpose.PROMPT_INPUT


def test_read_upload_bytes_from_bytes_source() -> None:
    request = FileUploadRequest(
        source=BytesFileSource(filename="note.txt", data=b"hello", media_type="text/plain"),
        purpose=FilePurpose.PROMPT_INPUT,
    )

    assert read_upload_bytes(request) == ("note.txt", b"hello", "text/plain")

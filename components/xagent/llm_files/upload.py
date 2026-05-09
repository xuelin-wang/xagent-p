from pathlib import Path

from xagent.llm_files.models import BytesFileSource, FileUploadRequest, LocalFileSource


def read_upload_bytes(request: FileUploadRequest) -> tuple[str, bytes, str | None]:
    source = request.source
    if isinstance(source, LocalFileSource):
        path = Path(source.path)
        return path.name, path.read_bytes(), source.media_type
    if isinstance(source, BytesFileSource):
        return source.filename, source.data, source.media_type
    raise TypeError(f"Unsupported upload source: {type(source).__name__}")

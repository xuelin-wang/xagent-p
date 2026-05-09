import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from xagent.llm_batch import BatchCreateRequest, BatchRequestItem, EmbeddingRequest
from xagent.llm_config import DEFAULT_API_KEY_ENV, ProviderConfig
from xagent.llm_contracts import GenerateRequest, Message, Role
from xagent.llm_files import FilePurpose, FileUploadRequest, LocalFileSource
from xagent.llm_registry import LLMClientFactory
from xagent.llm_structured import ResponseFormat, ResponseFormatType


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run xagent LLM provider commands.")
    parser.add_argument("--provider", choices=["openai", "anthropic"], default="openai")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
    subparsers = parser.add_subparsers(dest="command", required=True)

    text = subparsers.add_parser("text", help="Generate text.")
    text.add_argument("prompt")
    text.add_argument("--max-output-tokens", type=int)
    text.add_argument("--temperature", type=float)

    structured = subparsers.add_parser("structured", help="Generate JSON or schema-shaped output.")
    structured.add_argument("prompt")
    structured.add_argument("--schema-name", default="Output")
    structured.add_argument("--schema-json")
    structured.add_argument("--max-output-tokens", type=int)

    embed = subparsers.add_parser("embed", help="Create embeddings.")
    embed.add_argument("inputs", nargs="+")
    embed.add_argument("--dimensions", type=int)

    upload = subparsers.add_parser("upload-file", help="Upload a provider file.")
    upload.add_argument("path")
    upload.add_argument("--media-type")
    upload.add_argument("--purpose", choices=[purpose.value for purpose in FilePurpose], default=FilePurpose.PROMPT_INPUT.value)

    create_batch = subparsers.add_parser("create-batch", help="Create a native text batch from prompts.")
    create_batch.add_argument("prompts", nargs="+")
    create_batch.add_argument("--custom-id-prefix", default="item")

    get_batch = subparsers.add_parser("get-batch", help="Get a native batch job.")
    get_batch.add_argument("batch_id")

    batch_results = subparsers.add_parser("batch-results", help="Get native batch results.")
    batch_results.add_argument("batch_id")
    return parser


async def run(
    argv: list[str],
    *,
    factory: LLMClientFactory | None = None,
    stdout: TextIO = sys.stdout,
) -> int:
    args = build_parser().parse_args(argv)
    provider = (factory or LLMClientFactory()).create(_provider_config(args))
    result = await _dispatch(provider, args)
    print(_to_json(result), file=stdout)
    return 0


def main() -> int:
    return asyncio.run(run(sys.argv[1:]))


async def _dispatch(provider: Any, args: argparse.Namespace) -> Any:
    if args.command == "text":
        return await provider.generate(
            GenerateRequest(
                messages=[Message(role=Role.USER, content=args.prompt)],
                max_output_tokens=args.max_output_tokens,
                temperature=args.temperature,
            )
        )
    if args.command == "structured":
        schema = json.loads(args.schema_json) if args.schema_json else None
        return await provider.generate(
            GenerateRequest(
                messages=[Message(role=Role.USER, content=args.prompt)],
                max_output_tokens=args.max_output_tokens,
                response_format=ResponseFormat(
                    type=ResponseFormatType.JSON_SCHEMA if schema else ResponseFormatType.JSON_OBJECT,
                    schema_name=args.schema_name if schema else None,
                    json_schema=schema,
                ),
            )
        )
    if args.command == "embed":
        return await provider.embed(EmbeddingRequest(inputs=args.inputs, dimensions=args.dimensions))
    if args.command == "upload-file":
        path = Path(args.path)
        return await provider.upload_file(
            FileUploadRequest(
                source=LocalFileSource(path=str(path), media_type=args.media_type),
                purpose=FilePurpose(args.purpose),
            )
        )
    if args.command == "create-batch":
        return await provider.create_batch(
            BatchCreateRequest(
                items=[
                    BatchRequestItem(
                        custom_id=f"{args.custom_id_prefix}-{index}",
                        request=GenerateRequest(messages=[Message(role=Role.USER, content=prompt)]),
                    )
                    for index, prompt in enumerate(args.prompts, start=1)
                ]
            )
        )
    if args.command == "get-batch":
        return await provider.get_batch(args.batch_id)
    if args.command == "batch-results":
        return await provider.get_batch_results(args.batch_id)
    raise ValueError(f"Unsupported command: {args.command}")


def _provider_config(args: argparse.Namespace) -> ProviderConfig:
    return ProviderConfig(
        provider=args.provider,
        default_model=args.model or _default_model(args.provider),
        api_key_env=args.api_key_env or DEFAULT_API_KEY_ENV[args.provider],
        base_url=args.base_url,
    )


def _default_model(provider: str) -> str:
    return {
        "openai": "gpt-5.5",
        "anthropic": "claude-sonnet-4-6",
    }[provider]


def _to_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), separators=(",", ":"))
    return json.dumps(value, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())

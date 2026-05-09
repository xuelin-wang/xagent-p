# LLM API Layer Changes

Date: 2025-05-09

Covered commits:

- `1e5c0f6 Add LLM provider wrapper components`
- `5304843 Fix LLM structured CLI and provider retries`
- `f193feb Remove unsupported batch input file field`
- `7082a02 Move LLM design docs to changelog`
- `884ea7f Document LLM API layer changes`
- `2621117 Harden LLM retry and structured CLI validation`

## Executive Summary

These commits introduce and harden a provider-pluggable LLM API layer under the existing Polylith-style `xagent` namespace. The feature adds common provider contracts, configuration, retries, file abstractions, tool abstractions, structured output helpers, batch APIs, a provider registry, OpenAI and Anthropic provider implementations, a CLI surface, live-test scaffolding, documentation/changelog relocation, safer retry behavior for provider mutations, and full JSON Schema validation for CLI structured output.

The implementation follows the design principle from the original `doc/llm-design.txt`: normalize common request and response shapes while preserving provider-specific behavior, raw responses, capability checks, and explicit unsupported-feature failures.

## Feature Summary

### Common Contracts

The new `xagent.llm_contracts` component defines provider-independent message, generation, capability, usage, and error types. This gives callers one stable surface for OpenAI and Anthropic without erasing provider differences.

### Configuration And Authentication

The new `xagent.llm_config` component adds provider settings, timeout settings, retry settings, polling settings, default API-key environment variables, and API-key resolution.

### Retry And Timeout Layer

The new `xagent.llm_retry` component classifies retryable HTTP statuses, parses `Retry-After`, computes exponential backoff with optional jitter, converts timeout config to `httpx.Timeout`, and now includes both synchronous delay helpers and an async retry loop.

Commit `2621117` narrows provider retry usage so mutation-style provider operations are sent once instead of automatically retried. This protects callers from duplicate uploads or duplicate native batch jobs when providers process a request but the client loses the response.

### File Support

The new `xagent.llm_files` component models local file sources, byte file sources, provider file references, URL file references, file inputs, upload requests, delete requests, and normalized uploaded-file records.

### Tool Support

The new `xagent.llm_tools` component models app-hosted tools, provider-hosted tools, tool choices, tool calls, provider tool traces, basic argument validation, and a bounded tool loop for app-hosted tool execution.

### Structured Output

The new `xagent.llm_structured` component models response format requests, structured generation requests and responses, JSON parsing, schema generation from Pydantic models, and Pydantic-based output validation.

Commit `2621117` hardens the CLI dynamic-schema path by validating `--schema-json` output with `jsonschema.Draft202012Validator` instead of a lossy generated Pydantic model that typed every schema property as `Any`.

### Batch And Embeddings

The new `xagent.llm_batch` component supports embedding requests and responses, concurrent batch execution, native batch job/result models, and polling helpers.

OpenAI embeddings are implemented initially. Anthropic embeddings intentionally raise `UnsupportedCapabilityError`.

### Provider Registry

The new `xagent.llm_registry` component defines the provider protocol, provider registry, default provider registration, and a factory that constructs providers from `ProviderConfig`.

### OpenAI Provider

The OpenAI provider implements:

- Text generation through the Responses API.
- Structured generation using JSON schema response formats.
- Embeddings.
- File upload/delete.
- File inputs.
- App-hosted tools and provider-hosted tools.
- Native batches.
- Batch result download and JSONL normalization.
- Error normalization.
- Retry wrapping for retry-safe HTTP requests.
- No automatic retries for file upload, file delete, batch create, or batch cancel as of commit `2621117`.

### Anthropic Provider

The Anthropic provider implements:

- Text generation through Messages API payloads.
- Structured generation through a forced extraction tool.
- File upload/delete using Anthropic files beta headers.
- File inputs.
- App-hosted tools and provider-hosted tools.
- Native message batches.
- Batch result JSONL normalization.
- Error normalization.
- Retry wrapping for retry-safe HTTP requests.
- No automatic retries for file upload, file delete, batch create, or batch cancel as of commit `2621117`.

### CLI

The new `xagent-llm` CLI supports:

- `text`
- `structured`
- `embed`
- `upload-file`
- `create-batch`
- `get-batch`
- `batch-results`

Commit `5304843` fixes the structured command so it calls `generate_structured(...)` instead of plain `generate(...)`.

Commit `2621117` changes CLI structured validation for `--schema-json` so the provider output is validated against the full JSON Schema, including nested fields, enums, bounds, and additional-property rules.

### Batch Input File Removal

Commit `f193feb` removes public support for `BatchCreateRequest.input_file`. Native batch providers now build and upload batch input from `items`; pre-uploaded batch input files are intentionally unsupported.

### Documentation Move

Commit `7082a02` moves the original LLM design document into `changelogs/20250509-llm-api-layer-design.txt`, adds this change-log file, and adds `changelogs/prompt.txt`.

### Retry And Schema Hardening

Commit `2621117` adds two production hardening changes:

- Provider mutation calls that can create or alter provider resources are sent once rather than automatically retried.
- CLI structured output with `--schema-json` is validated using a real JSON Schema validator.

The commit also adds focused regression tests for both changes and adds the `jsonschema` runtime dependency.

## Rationale

### Why A Provider Wrapper

OpenAI and Anthropic expose similar high-level capabilities, but their request formats, tool semantics, file handling, batch APIs, error headers, and structured-output mechanisms differ. A common wrapper gives the rest of the application one entrypoint while keeping provider-specific mapping isolated in provider components.

### Why Polylith Components

The repository already uses a loose Polylith layout under `components/` and `bases/`. Splitting contracts, config, retry, files, tools, structured output, batch, registry, and provider implementations into separate components keeps dependencies directional and makes future providers easier to add.

### Why Capability Checks

Provider and model features are not interchangeable. The wrapper uses capability checks so unsupported operations fail loudly instead of silently emulating behavior with a different provider or feature.

### Why Raw Responses Are Preserved

Normalized response models are useful for callers, but raw provider responses are preserved for debugging, auditing, provider-specific fields, and future migration work.

### Why Structured Output Uses Different Provider Strategies

OpenAI has a native JSON schema response format. Anthropic structured output is implemented through an extraction tool because that matches Anthropic's tool-use API. The wrapper normalizes the returned structured data while allowing each provider to use its native mechanism.

### Why Batch Input Files Were Removed

`BatchCreateRequest.input_file` implied callers could hand the wrapper a pre-uploaded provider batch input file. The implementation did not support this consistently across providers. Removing it narrows the contract: callers provide `items`, and native providers build/upload the batch input internally.

### Why Mutation Calls Do Not Retry Automatically

OpenAI and Anthropic do not document a reliable idempotency-key contract for the file and batch mutation endpoints used by this wrapper. If a provider processes a request but the client sees a timeout, transport error, or transient server error, an automatic retry can create duplicate files or duplicate batch jobs.

The safer default is to send mutation calls once and let higher-level callers retry only when they have durable deduplication state. Delete calls are also sent once because a lost successful delete followed by a retry can produce ambiguous provider state, such as a later `404`.

### Why CLI Dynamic Schemas Use JSON Schema Validation

The CLI accepts schemas dynamically through `--schema-json`. JSON Schema is the correct runtime contract because OpenAI structured output and Anthropic tool input schemas are JSON Schema based. Direct JSON Schema validation preserves nested object rules, arrays, enums, bounds, required fields, and additional-property restrictions without needing an incomplete schema-to-Pydantic conversion.

### Why Live Tests Are Gated

Live provider tests cost money, need real credentials, and depend on network/provider availability. They are marked `require_env` and gated behind environment variables/API keys so normal test runs remain deterministic.

## Verification History

After the feature work and follow-up fixes, the full local suite was run successfully:

```text
136 passed, 11 skipped, 1 warning
```

The skipped tests are live/env-gated provider tests. The warning is the existing LangChain/Pydantic v1 warning on Python 3.14.

## Commit-by-Commit Changes

### `1e5c0f6 Add LLM provider wrapper components`

Adds the first complete LLM API layer implementation:

- New CLI base under `bases/xagent/llm_cli`.
- New common LLM components under `components/xagent`.
- OpenAI and Anthropic provider implementations.
- Unit tests for contracts, config, retry, files, tools, structured output, batch, registry, provider mapping, providers, and CLI.
- Live integration tests for OpenAI and Anthropic.
- Original design document at `doc/llm-design.txt`.
- Project script and lockfile updates.

### `5304843 Fix LLM structured CLI and provider retries`

Fixes two implementation gaps:

- CLI `structured` now calls `provider.generate_structured(...)`.
- Providers now wrap outbound HTTP requests in `retry_async(...)` with retryable HTTP status and network-exception handling.

Also adds tests for:

- CLI structured dispatch.
- Provider generate retry behavior.
- Async retry helper behavior.

### `f193feb Remove unsupported batch input file field`

Removes unsupported public `BatchCreateRequest.input_file` support:

- Adds `ConfigDict(extra="forbid")` to `BatchCreateRequest`.
- Adds an explanatory code comment.
- Adds a regression test that rejects `input_file`.

### `7082a02 Move LLM design docs to changelog`

Moves documentation into changelogs:

- Moves `doc/llm-design.txt` to `changelogs/20250509-llm-api-layer-design.txt`.
- Adds `changelogs/20250509-llm-api-layer-changes.md`.
- Adds `changelogs/prompt.txt`.

### `884ea7f Document LLM API layer changes`

Rewrites this changelog into a broader summary of the LLM API layer work:

- Summarizes the last committed feature set.
- Adds rationale for the wrapper, Polylith split, capability checks, raw response preservation, structured-output strategy, batch input-file removal, and live-test gating.
- Adds file-by-file and test-by-test explanations.

### `2621117 Harden LLM retry and structured CLI validation`

Hardens two production behaviors:

- Removes automatic retries from provider mutation operations: file upload, file delete, batch create, and batch cancel.
- Adds JSON Schema validation for CLI-provided structured-output schemas.

Also adds:

- `jsonschema>=4.26.0` to runtime dependencies.
- Lockfile entries for `jsonschema` and its transitive dependencies.
- Tests proving provider mutation calls do not retry even when `RetryConfig(max_attempts=2)` is configured.
- Tests proving CLI schema validation enforces nested types, enums, numeric bounds, required fields, `additionalProperties: false`, and invalid-schema rejection.

## Detailed File-by-File Explanation

The following sections explain the changed files from the covered commits. For source files, line references describe the logical line ranges in the resulting files.

### `bases/xagent/llm_cli/__init__.py`

- Line 1: package marker for the `xagent.llm_cli` base so the CLI can be imported and exposed through the project script.

### `bases/xagent/llm_cli/main.py`

- Lines 1-9: import CLI, async, JSON, path, typing, JSON Schema validator classes, and Pydantic helpers.
- Lines 11-16: import shared LLM batch, config, contract, file, registry, and structured-output types.
- Lines 19-56: define the `argparse` parser and subcommands.
- Lines 20-23: add provider, model, base URL, and API-key env override flags.
- Lines 26-29: define `text` generation arguments.
- Lines 31-35: define `structured` generation arguments, including schema name and schema JSON.
- Lines 37-39: define embedding arguments.
- Lines 41-44: define file-upload arguments and map allowed purpose choices from `FilePurpose`.
- Lines 46-48: define native batch creation from prompt arguments.
- Lines 50-54: define batch retrieval/result commands.
- Lines 58-68: implement async `run(...)`, create the provider from config, dispatch the command, serialize result JSON, and return exit code.
- Lines 71-72: expose sync `main()` by running the async entrypoint.
- Lines 76-125: dispatch each CLI command to the provider.
- Lines 77-84: map `text` to `GenerateRequest` and `provider.generate(...)`.
- Lines 85-98: map `structured` to `StructuredGenerateRequest` and, after commit `5304843`, call `provider.generate_structured(...)`.
- Lines 86-95: parse optional schema JSON and build `ResponseFormat`.
- Line 97: build a dynamic output model for CLI structured responses.
- Lines 99-100: map `embed` to `EmbeddingRequest`.
- Lines 101-108: map `upload-file` to `FileUploadRequest` and `LocalFileSource`.
- Lines 109-120: map `create-batch` prompts to `BatchCreateRequest` with `BatchRequestItem` values.
- Lines 121-124: map batch get/results commands to provider calls.
- Lines 128-134: build `ProviderConfig` from CLI args and default API-key env mapping.
- Lines 137-141: provide provider-specific default models.
- Lines 143-145: define `GenericStructuredOutput` for schema-less JSON object output.
- Lines 148-159: define `JsonSchemaStructuredOutput`, a dynamic Pydantic base model that allows arbitrary output fields and validates the full dumped object with a class-level `Draft202012Validator`.
- Lines 162-173: define `_structured_output_type(...)`; schema-less calls still use `GenericStructuredOutput`, while CLI-provided schemas are checked with `Draft202012Validator.check_schema(...)` and attached to a generated schema-backed output type.
- Lines 176-179: serialize Pydantic or plain values as compact JSON.
- Lines 182-183: executable module guard.

Rationale:

- The CLI is a thin operational surface over the provider registry and common contracts.
- The structured CLI fix is important because plain generation bypassed structured validation and response normalization.
- The JSON Schema validation hardening is important because CLI schemas are dynamic and may include nested rules that a lossy Pydantic field map cannot enforce.

### `components/xagent/llm_batch/__init__.py`

- Lines 1-12: re-export batch models and helper functions.
- Lines 14-31: define `__all__` so callers can import the public batch API from `xagent.llm_batch`.

### `components/xagent/llm_batch/concurrent.py`

- Lines 1-4: import asyncio and batch models.
- Lines 7-34: implement `run_concurrent_batch(...)`.
- Lines 8-12: create semaphore and result list.
- Lines 14-27: run each request through `provider.generate(...)`, capture response or normalized error payload.
- Lines 29-34: gather all tasks and return ordered results.

Rationale:

- Provides provider-independent concurrent batching for cases where native provider batches are not desired.

### `components/xagent/llm_batch/models.py`

- Lines 1-5: import datetime, enum, typing, and Pydantic.
- Lines 7-8: import generation and error contracts.
- Lines 10-14: define `EmbeddingRequest`.
- Lines 17-19: define one embedding vector.
- Lines 22-28: define normalized embedding response.
- Lines 31-34: define concurrent batch request settings.
- Lines 37-41: define one concurrent batch result.
- Lines 44-46: define one native batch request item.
- Lines 49-55: define native `BatchCreateRequest`.
- Line 50: after commit `f193feb`, forbid unknown extra fields.
- Line 51: document that pre-uploaded batch input files are intentionally unsupported.
- Lines 52-55: keep model override, item list, mode, and metadata.
- Lines 58-66: define normalized batch statuses.
- Lines 68-76: define normalized batch job.
- Lines 79-83: define one batch result item.
- Lines 86-91: define normalized batch results.

Rationale:

- Keeps embedding and batch contracts provider-independent.
- Forbidding extra fields prevents accidental use of removed `input_file`.

### `components/xagent/llm_batch/polling.py`

- Lines 1-2: import asyncio and time.
- Lines 4-5: import batch status and polling config.
- Lines 8-25: implement `poll_batch_until_terminal(...)`.
- Lines 9-12: calculate timeout and initial interval.
- Lines 14-18: fetch job, return on terminal status, and enforce timeout.
- Lines 19-25: sleep with capped exponential interval growth.

Rationale:

- Provides shared polling behavior without embedding provider-specific batch APIs.

### `components/xagent/llm_config/__init__.py`

- Lines 1-8: re-export config models, default env mapping, auth resolver, and timeout types.
- Lines 10-12: define public exports.

### `components/xagent/llm_config/auth.py`

- Lines 1-3: import environment and secret types.
- Lines 5-8: define default provider API-key environment variables.
- Lines 11-29: implement `resolve_api_key(...)`.
- Lines 12-13: prefer explicit `api_key`.
- Lines 14-22: resolve configured env var.
- Lines 23-29: fall back to provider default env var.

Rationale:

- Makes local tests and runtime providers support explicit secrets and environment-based credentials.

### `components/xagent/llm_config/settings.py`

- Lines 1-3: import typing and Pydantic settings primitives.
- Lines 6-10: define timeout settings.
- Lines 13-20: define retry settings.
- Lines 23-26: define polling settings.
- Lines 29-37: define `ProviderConfig` with provider name, default model, auth, base URL, timeout, retry, and polling settings.

Rationale:

- Centralizes provider construction inputs and keeps provider classes small.

### `components/xagent/llm_contracts/__init__.py`

- Lines 1-35: re-export capabilities, error classes, types, and usage.
- Lines 37-45: define the public contract API.

### `components/xagent/llm_contracts/capabilities.py`

- Lines 1-4: import enum, Pydantic, and error types.
- Lines 7-17: define supported capability names.
- Lines 20-27: define `ModelCapabilities`.
- Lines 30-47: define `assert_capability(...)` that raises `UnsupportedCapabilityError` when a provider/model lacks a required feature.

Rationale:

- Capability gates keep provider differences explicit.

### `components/xagent/llm_contracts/errors.py`

- Lines 1-3: import typing and Pydantic.
- Lines 6-15: define `LLMErrorPayload`.
- Lines 18-21: define base `LLMError`.
- Lines 24-68: define normalized exception subclasses.

Rationale:

- Gives callers a stable error taxonomy while preserving provider, model, status, request ID, retryability, and raw error data.

### `components/xagent/llm_contracts/types.py`

- Lines 1-6: import enum, typing, Pydantic, and usage.
- Lines 9-13: define chat/message roles.
- Lines 16-18: define text content part.
- Lines 21-25: define normalized message.
- Lines 28-39: define normalized generation request.
- Lines 42-52: define normalized generation response.

Rationale:

- Provides the core cross-provider request and response shape.
- Uses `Any` for extension points such as tools, files, and response format to avoid circular component imports.

### `components/xagent/llm_contracts/usage.py`

- Lines 1-3: import typing and Pydantic.
- Lines 6-10: define normalized token usage with raw provider usage preserved.

### `components/xagent/llm_files/__init__.py`

- Lines 1-20: re-export file source, input, upload, delete, and uploaded-file models.
- Lines 21-31: define public exports.

### `components/xagent/llm_files/models.py`

- Lines 1-5: import enum, path, typing, and Pydantic.
- Lines 8-13: define file purpose values.
- Lines 16-20: define local file source.
- Lines 23-27: define bytes file source.
- Lines 30-35: define provider file reference.
- Lines 38-42: define URL file reference.
- Lines 45-49: define file input wrapper.
- Lines 52-55: define file upload request.
- Lines 58-60: define file delete request.
- Lines 63-72: define normalized uploaded file.
- Lines 75-81: define generated file record.

Rationale:

- Decouples file references from provider-specific payload shapes.

### `components/xagent/llm_files/upload.py`

- Lines 1-3: import path and file models.
- Lines 6-13: implement `read_upload_bytes(...)` for local and in-memory byte uploads.

Rationale:

- Keeps provider upload code focused on HTTP payload creation.

### `components/xagent/llm_tools/__init__.py`

- Lines 1-10: re-export app tool, provider tool, loop, and validation APIs.
- Lines 12-17: define public exports.

### `components/xagent/llm_tools/app_tools.py`

- Lines 1-4: import typing and Pydantic.
- Lines 7-11: define app tool definition.
- Lines 14-18: define app tool call.
- Lines 21-22: define callable tool implementation type.

### `components/xagent/llm_tools/provider_tools.py`

- Lines 1-4: import enum, typing, and Pydantic.
- Lines 7-13: define tool-choice modes.
- Lines 16-18: define `ToolChoice`.
- Lines 21-26: define provider-hosted tool request.
- Lines 29-32: define provider tool trace.

### `components/xagent/llm_tools/tool_loop.py`

- Lines 1-7: import contracts and tool models.
- Lines 10-70: implement bounded app-tool execution loop.
- Lines 11-17: index tools and initialize messages.
- Lines 19-31: call provider and return immediately when no app tool calls remain.
- Lines 32-44: enforce iteration limit and resolve tool implementation.
- Lines 45-62: validate arguments, execute the tool, and append tool result messages.
- Lines 63-70: raise normalized errors for missing tools or exceeded loops.

Rationale:

- Keeps automatic app-tool execution outside low-level provider implementations.

### `components/xagent/llm_tools/validation.py`

- Lines 1-4: import typing and tool/error models.
- Lines 7-34: implement simple JSON-schema-like validation for required fields and primitive argument types.
- Lines 37-53: normalize validation failures into `AppToolCallValidationError`.

Rationale:

- Gives app-hosted tool loops a lightweight guard before executing user code.

### `components/xagent/llm_structured/__init__.py`

- Lines 1-10: re-export response format and validation helpers.
- Lines 12-21: define public exports.

### `components/xagent/llm_structured/response_format.py`

- Lines 1-5: import enum, typing, Pydantic, and base contracts.
- Lines 8-12: define response format types.
- Lines 15-20: define `ResponseFormat`.
- Lines 23-25: define `StructuredGenerateRequest`.
- Lines 28-35: define generic `StructuredGenerateResponse`.

### `components/xagent/llm_structured/validation.py`

- Lines 1-7: import JSON, typing, Pydantic, errors, and response format.
- Lines 10-18: build `ResponseFormat` from a Pydantic model schema.
- Lines 21-40: parse raw text as a JSON object and raise structured validation errors for invalid JSON or non-object output.
- Lines 43-63: validate raw JSON against a Pydantic output type and normalize Pydantic validation errors.

Rationale:

- Separates provider response generation from structured parsing and local validation.

### `components/xagent/llm_retry/__init__.py`

- Lines 1-2: re-export retry and timeout helpers.
- Lines 4-10: expose backoff, status classification, retry-after parsing, async retry, and timeout conversion.
- Commit `5304843` adds `retry_async` to the public exports.

### `components/xagent/llm_retry/retry.py`

- Lines 1-8: import date parsing, async sleep, randomness, typing, and retry config.
- Lines 10-13: define type variable and retryable status set.
- Lines 16-19: classify retryable status codes.
- Lines 22-34: parse `Retry-After` as seconds or HTTP-date.
- Lines 37-52: compute exponential backoff delay with optional jitter and max cap.
- Lines 55-90: commit `5304843` adds `retry_async(...)`.
- Lines 64-65: normalize max attempts to at least one.
- Lines 66-77: call the operation and retry configured retryable exceptions.
- Lines 79-88: retry configured retryable results such as 429 or 5xx responses.
- Line 90: defensive error if loop exits unexpectedly.

Rationale:

- Providers can share retry policy without duplicating loops.

### `components/xagent/llm_retry/timeout.py`

- Lines 1-3: import `httpx` and timeout config.
- Lines 6-12: convert project timeout settings to `httpx.Timeout`.

### `components/xagent/llm_registry/__init__.py`

- Lines 1-5: re-export factory, protocol, registry, and default registry.
- Lines 7-10: define public exports.

### `components/xagent/llm_registry/provider_protocol.py`

- Lines 1-12: import protocol typing and request/response models.
- Lines 14-52: define the `LLMProvider` protocol.
- Lines 17-19: require `provider_name` and capabilities.
- Lines 21-31: require text and structured generation.
- Lines 33-41: require embeddings and file operations.
- Lines 43-52: require native batch operations.

Rationale:

- Gives the factory and callers a typed provider interface.

### `components/xagent/llm_registry/registry.py`

- Lines 1-4: import config and provider protocol.
- Lines 7-20: implement `ProviderRegistry`.
- Lines 8-10: initialize constructor map.
- Lines 12-14: register provider constructors.
- Lines 16-20: create provider instances and fail on unknown providers.

### `components/xagent/llm_registry/factory.py`

- Lines 1-5: import config, registry, and provider classes.
- Lines 8-15: build the default registry with OpenAI and Anthropic.
- Lines 18-43: define `LLMClientFactory`.
- Lines 19-21: use a provided registry or default registry.
- Lines 23-43: create a provider from config.

### `components/xagent/llm_provider_openai/__init__.py`

- Lines 1-6: re-export OpenAI provider and mapping helpers.
- Lines 8-9: define public exports.

### `components/xagent/llm_provider_openai/files.py`

- Lines 1-7: map common `FilePurpose` values to OpenAI purpose strings.

### `components/xagent/llm_provider_openai/embeddings.py`

- Lines 1-8: import typing, batch embedding models, and usage.
- Lines 10-14: define default and supported OpenAI embedding models.
- Lines 17-26: convert common embedding request to OpenAI payload.
- Lines 29-46: convert OpenAI embedding response to normalized embedding response.

### `components/xagent/llm_provider_openai/mapping.py`

- Lines 1-15: import typing, contracts, files, structured, and tools.
- Lines 18-64: convert common generation requests to OpenAI Responses API payloads.
- Lines 66-102: map messages, text parts, app tools, and provider tools.
- Lines 104-128: map file inputs to OpenAI input content forms.
- Lines 130-160: map structured response format to OpenAI text format.
- Lines 162-221: convert OpenAI Responses API output to normalized `GenerateResponse`.
- Lines 223-279: extract text, app tool calls, provider traces, generated files, finish reason, and usage.
- Lines 281-302: normalize OpenAI usage and helper fields.
- Lines 304-312: prepare strict JSON schemas for OpenAI by adding strict/additional property defaults.

Rationale:

- Keeps OpenAI request/response translation out of the provider transport class.

### `components/xagent/llm_provider_openai/batch.py`

- Lines 1-11: import JSON, datetime, typing, batch models, contracts, and mapping helpers.
- Lines 13-16: define OpenAI batch completion window.
- Lines 19-70: convert `BatchCreateRequest` items to OpenAI JSONL and endpoint.
- Lines 72-118: convert OpenAI batch jobs to normalized `BatchJob`.
- Lines 120-170: parse OpenAI batch output/error JSONL into normalized `BatchResults`.

Rationale:

- OpenAI native batches require JSONL files; this module owns that provider-specific format.

### `components/xagent/llm_provider_openai/provider.py`

- Lines 1-62: import provider dependencies, contracts, files, mappings, batch helpers, embeddings, retry, timeout, and structured helpers.
- Lines 64-77: define supported text models and provider-hosted tool types.
- Lines 80-105: initialize provider and report capabilities.
- Lines 107-119: resolve supported text model or raise `UnsupportedCapabilityError`.
- Lines 121-136: check generation capabilities for text, tools, files, mixed tools, and structured output.
- Lines 138-151: validate OpenAI provider-hosted tool types.
- Lines 153-158: implement plain generation.
- Lines 160-212: implement structured generation.
- Lines 171-173: post Responses payload; commit `5304843` changes this path to use retry-wrapped `_post_responses`.
- Lines 175-182: parse and validate structured JSON.
- Lines 183-201: on validation failure, append corrective prompt and retry within validation retry count.
- Lines 203-210: return normalized structured response.
- Lines 214-228: implement embeddings.
- Lines 230-284: post embeddings payload, including auth, timeout, retries, and error mapping.
- Lines 286-347: upload files and normalize OpenAI file response; commit `2621117` sends this mutation once instead of through `_send_with_retries(...)`.
- Lines 349-405: delete provider files; commit `2621117` sends this mutation once to avoid ambiguous retry outcomes.
- Lines 406-426: create native batches by building JSONL, uploading it as batch input, and posting batch job payload.
- Lines 428-434: get and cancel native batches.
- Lines 436-446: get batch results by downloading output/error files and parsing JSONL.
- Lines 448-503: post OpenAI batch create/cancel operations with auth, timeout mapping, and error mapping; commit `2621117` removes automatic retries from these provider mutations.
- Lines 505-550: get OpenAI batch status.
- Lines 552-599: download OpenAI file content.
- Lines 601-661: post OpenAI Responses API payloads.
- Lines 663-677: reject unsupported generation fields.
- Lines 678-690: commit `5304843` adds `_send_with_retries(...)` using `retry_async`; after commit `2621117`, this helper remains for retry-safe operations such as generation and reads.
- Lines 692-714: normalize provider error responses into project error classes.
- Lines 717-739: helper functions for safe JSON error parsing, error message extraction, and Unix timestamp conversion.

Rationale:

- The provider coordinates auth, HTTP calls, capability checks, retries, and normalization while delegating provider-specific payload mapping.

### `components/xagent/llm_provider_anthropic/__init__.py`

- Lines 1-4: re-export Anthropic provider.
- Lines 6: define public exports.

### `components/xagent/llm_provider_anthropic/files.py`

- Lines 1-5: define Anthropic files beta header constant and helper.

### `components/xagent/llm_provider_anthropic/mapping.py`

- Lines 1-16: import typing, contracts, files, tools, and usage.
- Lines 18-26: define Anthropic provider tool types.
- Lines 29-105: convert common generation requests to Anthropic Messages payloads.
- Lines 107-164: map message content, text, files, app tools, provider tools, and tool choice.
- Lines 166-253: convert Anthropic response content blocks into normalized text, app tool calls, provider traces, generated files, finish reason, and usage.
- Lines 255-300: helper functions for usage, file content, tool result mapping, and provider trace extraction.

Rationale:

- Encapsulates Anthropic-specific Messages API shape separately from transport/error handling.

### `components/xagent/llm_provider_anthropic/batch.py`

- Lines 1-9: import JSON, datetime, batch models, contracts, errors, and mapping helpers.
- Lines 12-48: convert common batch requests to Anthropic message batch payloads.
- Lines 50-100: convert Anthropic batch jobs to normalized `BatchJob`.
- Lines 102-120: parse Anthropic batch JSONL result lines into normalized `BatchResults`.

### `components/xagent/llm_provider_anthropic/provider.py`

- Lines 1-52: import typing, httpx, batch models, config, contracts, files, mapping, batch helpers, file beta header, retry, structured, and tools.
- Lines 54-60: define supported Anthropic text models.
- Lines 63-86: initialize provider and report capabilities.
- Lines 88-100: resolve supported model.
- Lines 102-117: check generation capabilities.
- Lines 119-132: validate Anthropic provider-hosted tool types.
- Lines 134-195: implement plain generation through `/messages`.
- Lines 164-171: commit `5304843` wraps the Messages call in `_send_with_retries`.
- Lines 197-255: implement structured generation using an extraction tool.
- Lines 204-211: build forced extraction tool request.
- Lines 215-217: call `generate(...)` and pull tool input.
- Lines 218-224: validate tool input against requested output type.
- Lines 225-244: retry structured validation by appending a corrective message.
- Lines 257-266: explicitly reject embeddings for Anthropic.
- Lines 268-330: upload files through Anthropic files API; commit `2621117` sends this mutation once instead of through `_send_with_retries(...)`.
- Lines 332-391: delete provider files; commit `2621117` sends this mutation once to avoid ambiguous retry outcomes.
- Lines 393-425: create, get, cancel, and retrieve native batch results.
- Lines 427-483: post batch create/cancel operations with auth, beta header when needed, timeout mapping, and error mapping; commit `2621117` removes automatic retries from these provider mutations.
- Lines 485-533: get batch or batch result responses.
- Lines 535-551: reject unsupported generate fields.
- Lines 553-565: commit `5304843` adds `_send_with_retries(...)`; after commit `2621117`, this helper remains for retry-safe operations such as generation and reads.
- Lines 567-595: normalize provider error responses.
- Lines 598-658: helpers for safe JSON parsing, uploaded-file detection, batch file detection, structured tool creation, and structured tool input extraction.

### `components/xagent/llm_provider_anthropic/batch.py`

Rationale:

- Anthropic native batches have a provider-specific payload and result JSONL format; this module isolates that logic.

### `pyproject.toml`

- Project scripts section: adds `xagent-llm = "xagent.llm_cli.main:main"`.
- Dependencies: initial LLM layer depends on the existing runtime stack plus `httpx`, `pydantic`, and `pyyaml` already present in the project context.
- Commit `2621117` adds `jsonschema>=4.26.0` as a runtime dependency for CLI structured-output validation.

Rationale:

- Exposes the CLI through the package script mechanism and ensures runtime dependencies are available.
- Keeps JSON Schema validation available in installed CLI environments, not only in tests.

### `uv.lock`

- Adds/updates package lock metadata for the project after adding the LLM components and script metadata.
- Records the package's own dependency/script metadata for reproducible installs.
- Commit `2621117` adds lock entries for `jsonschema`, `attrs`, `jsonschema-specifications`, `referencing`, and `rpds-py`.

### `changelogs/20250509-llm-api-layer-design.txt`

- Contains the original LLM wrapper design document moved from `doc/llm-design.txt`.
- Documents goals, non-goals, component layout, provider support, request/response contracts, retry policy, file support, tools, structured output, batch, provider registry, OpenAI mapping, Anthropic mapping, testing, and delivery plan.

### `changelogs/prompt.txt`

- One-line prompt/changelog artifact added with the documentation move.

### `changelogs/20250509-llm-api-layer-changes.md`

- This file documents the implementation changes, rationale, verification, and per-file explanations.

## Test File Explanations

### CLI Tests

`test/bases/xagent/llm_cli/test_main.py`

- Defines fake factory/provider classes to test CLI dispatch without real providers.
- Verifies the parser exposes all expected commands.
- Verifies each subcommand dispatches to the expected provider method.
- Verifies provider config construction for Anthropic.
- Commit `5304843` updates the fake provider and assertions to cover `generate_structured(...)`.
- Commit `2621117` adds direct tests for `_structured_output_type(...)` to prove CLI schemas enforce nested types, enums, numeric bounds, required fields, `additionalProperties: false`, and invalid-schema rejection.

### Batch Tests

`test/components/xagent/llm_batch/test_models.py`

- Verifies batch models can be constructed.
- Commit `f193feb` adds rejection coverage for `input_file`.

`test/components/xagent/llm_batch/test_concurrent.py`

- Verifies concurrent batch execution returns ordered successful responses.

`test/components/xagent/llm_batch/test_polling.py`

- Verifies polling reaches terminal batch status.

### Config Tests

`test/components/xagent/llm_config/test_auth.py`

- Verifies explicit API key and environment API key resolution.

`test/components/xagent/llm_config/test_settings.py`

- Verifies provider config defaults.

### Contract Tests

`test/components/xagent/llm_contracts/test_capabilities.py`

- Verifies capability assertion success and failure.

`test/components/xagent/llm_contracts/test_errors.py`

- Verifies normalized error payload is retained on exceptions.

`test/components/xagent/llm_contracts/test_types.py`

- Verifies message and generation request/response models.

### File Tests

`test/components/xagent/llm_files/test_file_models.py`

- Verifies local and byte upload source reading.

### Retry Tests

`test/components/xagent/llm_retry/test_retry.py`

- Verifies retryable status classification.
- Verifies `Retry-After` parsing.
- Verifies backoff calculations with and without jitter.
- Commit `5304843` adds async retry-result behavior coverage.

`test/components/xagent/llm_retry/test_timeout.py`

- Verifies timeout config conversion to `httpx.Timeout`.

### Structured Output Tests

`test/components/xagent/llm_structured/test_response_format.py`

- Verifies Pydantic model schema generation for response formats.

`test/components/xagent/llm_structured/test_structured_validation.py`

- Verifies JSON object parsing and Pydantic structured validation failures.

### Tool Tests

`test/components/xagent/llm_tools/test_app_tools.py`

- Verifies app tool definition models.

`test/components/xagent/llm_tools/test_provider_tools.py`

- Verifies provider-hosted tool models.

`test/components/xagent/llm_tools/test_tool_loop.py`

- Verifies app tool loop execution and response continuation.

`test/components/xagent/llm_tools/test_validation.py`

- Verifies required argument and primitive type validation.

### Registry Tests

`test/components/xagent/llm_registry/test_registry.py`

- Verifies provider registration and creation.

`test/components/xagent/llm_registry/test_factory.py`

- Verifies factory construction of configured providers.

### OpenAI Provider Tests

`test/components/xagent/llm_provider_openai/test_capabilities.py`

- Verifies OpenAI capability reporting.

`test/components/xagent/llm_provider_openai/test_mapping.py`

- Verifies common request mapping into OpenAI Responses API payloads.
- Verifies tool, provider tool, file, and structured response format mapping.

`test/components/xagent/llm_provider_openai/test_generate.py`

- Verifies generate payload posting and response normalization.
- Verifies error normalization.
- Verifies structured JSON schema payload posting.
- Commit `5304843` adds retryable-response retry coverage.

`test/components/xagent/llm_provider_openai/test_embeddings.py`

- Verifies embedding payload mapping, response normalization, and unsupported model errors.

`test/components/xagent/llm_provider_openai/test_files.py`

- Verifies file purpose mapping, multipart upload payloads, normalized uploaded files, and delete requests.
- Commit `2621117` adds regression tests proving file upload and file delete are sent once and do not retry when provider mutation responses are 5xx.

`test/components/xagent/llm_provider_openai/test_batch.py`

- Verifies JSONL generation for Responses and Embeddings batch endpoints.
- Verifies batch job normalization.
- Verifies result JSONL parsing.
- Verifies create/get/cancel/results provider flow.
- Commit `2621117` adds regression tests proving native batch create and cancel are sent once and do not retry when provider mutation responses are 5xx.

### Anthropic Provider Tests

`test/components/xagent/llm_provider_anthropic/test_capabilities.py`

- Verifies Anthropic capability reporting.

`test/components/xagent/llm_provider_anthropic/test_mapping.py`

- Verifies common request mapping into Anthropic Messages payloads.
- Verifies app tools, provider tools, file content, tool choice, and response mapping.

`test/components/xagent/llm_provider_anthropic/test_generate.py`

- Verifies generate payload posting and response normalization.
- Verifies error normalization.
- Verifies structured extraction tool behavior.
- Verifies structured validation retry behavior.
- Commit `5304843` adds retryable-response retry coverage.

`test/components/xagent/llm_provider_anthropic/test_files.py`

- Verifies files beta header, uploaded-file references, multipart upload payloads, normalized uploaded files, and delete requests.
- Commit `2621117` adds regression tests proving file upload and file delete are sent once and do not retry when provider mutation responses are 5xx.

`test/components/xagent/llm_provider_anthropic/test_batch.py`

- Verifies Anthropic batch payload generation.
- Verifies batch job normalization.
- Verifies batch result JSONL parsing.
- Verifies create/get/cancel/results provider flow.
- Commit `2621117` adds regression tests proving native batch create and cancel are sent once and do not retry when provider mutation responses are 5xx.

### Live Integration Tests

`test/integration/test_openai_live.py`

- Adds env-gated live tests for OpenAI text generation, structured generation, embeddings, and tool/schema behavior.
- Tests require real credentials and live-test opt-in.

`test/integration/test_anthropic_live.py`

- Adds env-gated live tests for Anthropic text generation, structured generation, and tool/schema behavior.
- Tests require real credentials and live-test opt-in.

## Residual Risks And Follow-Ups

- CLI structured output remains object-oriented because the shared structured parsing path expects JSON objects.
- A future hardening step could reject CLI schemas whose root type is not `"object"` to make that contract explicit before provider calls.
- Live provider tests are skipped unless credentials and live-test flags are configured.
- Future providers should implement the `LLMProvider` protocol and register through `ProviderRegistry`.

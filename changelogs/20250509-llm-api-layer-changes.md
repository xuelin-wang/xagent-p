# LLM API Layer Changes - 2025-05-09

## Scope

This changelog summarizes the current LLM API layer follow-up changes in the working tree. The changes address two review findings:

- Avoid automatic retries for provider mutation calls that can duplicate side effects.
- Validate CLI structured-output responses against the full user-provided JSON Schema.

The working tree also contains an unrelated deletion of `doc/llm-design.txt`. That deletion is not part of the intended feature work described below.

## Feature Summary

### Retry Policy For Provider Mutations

OpenAI and Anthropic provider wrappers no longer automatically retry these mutation-style operations:

- File upload.
- File delete.
- Native batch create.
- Native batch cancel.

Generation and read-style operations still use the existing retry path. Examples include text generation, structured generation through generation calls, batch retrieval, batch result retrieval, and file download.

### CLI JSON Schema Validation

The `xagent-llm structured --schema-json ...` CLI path now validates returned structured data with `jsonschema.Draft202012Validator`.

Before this change, the CLI converted top-level JSON Schema properties into a generated Pydantic model where every property type was `Any`. That preserved only required-vs-optional presence and missed type checks, enums, bounds, nested required fields, and `additionalProperties`.

After this change:

- Valid JSON Schema is checked up front.
- Model output is validated against the full JSON Schema after provider response parsing.
- Invalid model output triggers the existing structured-output validation failure path, allowing the configured validation retry behavior to work with real schema semantics.

### Dependency Update

Added `jsonschema>=4.26.0` as a runtime dependency and updated `uv.lock` with its transitive dependencies.

## Rationale

### Why Mutation Calls Do Not Retry Automatically

OpenAI and Anthropic do not document a reliable idempotency-key contract for the file and batch mutation endpoints used by this wrapper. If a provider processes a request but the client sees a timeout, transport error, or transient server error, an automatic retry can create duplicate files or duplicate batch jobs.

The safer default is to send mutation calls once and let higher-level callers retry only when they have their own durable deduplication state. This keeps the wrapper from silently creating extra provider resources.

Delete calls are also sent once. Although `DELETE` is logically idempotent, provider behavior after a successful-but-lost delete can be ambiguous. A retry might return `404` or another state-dependent error even though the original operation succeeded.

### Why JSON Schema Validation Is Used For CLI Structured Output

The CLI accepts schemas dynamically via `--schema-json`. JSON Schema is the natural contract for that path because:

- OpenAI structured output accepts JSON Schema.
- Anthropic tool `input_schema` is documented as a JSON Schema object.
- Runtime schemas may use nested objects, arrays, enums, bounds, and other JSON Schema keywords.

A schema-to-Pydantic conversion would either be incomplete or require a heavier conversion dependency. Direct JSON Schema validation is smaller, clearer, and matches the user's CLI input exactly.

## Verification

Commands run after the changes:

```bash
PYTHONPATH=. uv run --active pytest -q test/bases/xagent/llm_cli test/components/xagent/llm_provider_openai/test_files.py test/components/xagent/llm_provider_openai/test_batch.py test/components/xagent/llm_provider_anthropic/test_files.py test/components/xagent/llm_provider_anthropic/test_batch.py
```

Result:

```text
35 passed
```

Full suite:

```bash
PYTHONPATH=. uv run --active pytest -q
```

Result:

```text
136 passed, 11 skipped, 1 warning
```

The warning is the existing LangChain/Pydantic v1 warning on Python 3.14.

## File-by-File Explanation

### `bases/xagent/llm_cli/main.py`

Changed import lines:

- Added `ClassVar` because the generated schema-backed model stores a class-level validator instance.
- Removed `create_model` because the CLI no longer builds a field-by-field Pydantic model from schema properties.
- Added `Draft202012Validator` to validate CLI output with JSON Schema draft 2020-12 semantics.
- Added `SchemaError` to reject invalid CLI-provided schemas before making provider calls.
- Added `JsonSchemaValidationError` to convert JSON Schema validation failures into Pydantic validation errors.
- Added `model_validator` to run full-object JSON Schema validation after Pydantic creates the model instance.

Changed `GenericStructuredOutput` area:

- Kept `GenericStructuredOutput` unchanged for the no-schema `json_object` case.
- Added `JsonSchemaStructuredOutput` as the base class for schema-backed dynamic CLI output types.
- Set `model_config = ConfigDict(extra="allow")` so arbitrary fields returned by the provider remain present for schema validation.
- Added `_schema_validator: ClassVar[Draft202012Validator]` so each generated subclass can carry its compiled JSON Schema validator.
- Added `_validate_json_schema()` as an `after` model validator.
- Inside `_validate_json_schema()`, call `self.model_dump(mode="json")` to validate the actual output payload as plain JSON-compatible data.
- On `JsonSchemaValidationError`, raise `ValueError("JSON Schema validation failed: ...")`; Pydantic wraps this into a `ValidationError`, and the existing structured validation layer turns it into `StructuredOutputValidationError`.
- Return `self` when validation succeeds.

Changed `_structured_output_type()`:

- The non-dict schema path still returns `GenericStructuredOutput`, preserving existing behavior when no schema is supplied.
- Removed the previous `properties = schema.get("properties")` logic.
- Removed the previous fallback to `GenericStructuredOutput` when `properties` was missing.
- Removed `required = set(schema.get("required") or [])`.
- Removed the generated `fields` mapping where every schema property was typed as `Any`.
- Removed the `create_model(...)` call based on those lossy fields.
- Added `Draft202012Validator.check_schema(schema)` to validate the schema itself.
- Added `except SchemaError` to raise a clear `ValueError` for invalid schemas.
- Added a dynamic `type(...)` call to create a subclass named from `schema_name` or `"StructuredOutput"`.
- Attached `Draft202012Validator(schema)` as `_schema_validator` on that subclass.

Rationale:

- This makes CLI schema validation faithful to the user's JSON Schema instead of approximating it as a top-level Pydantic model.

### `components/xagent/llm_provider_openai/provider.py`

Changed `upload_file()`:

- Replaced `self._send_with_retries(...)` around `client.post("/files", ...)` with a direct `await client.post(...)`.
- Preserved URL, auth header, purpose data, and multipart file payload.
- Added a comment explaining that resource-creating uploads are not retried because provider idempotency is not documented and lost responses could create duplicates.
- Left timeout and HTTP error mapping unchanged.
- Left response error handling and `UploadedFile` normalization unchanged.

Changed `delete_file()`:

- Replaced `self._send_with_retries(...)` around `client.delete(...)` with a direct `await client.delete(...)`.
- Preserved file URL and auth header.
- Added a comment explaining that delete is sent once to avoid ambiguous outcomes after a server-side success with a lost response.
- Left timeout and HTTP error mapping unchanged.
- Left provider mismatch validation unchanged.
- Left response error handling unchanged.

Changed `_post_batch()`:

- Replaced `self._send_with_retries(...)` around `client.post(path, ...)` with a direct `await client.post(...)`.
- Preserved batch path, bearer auth header, content type, and JSON payload.
- Added a comment explaining that batch create/cancel are provider-side mutations and retries are left to callers with dedupe state.
- Left timeout and HTTP error mapping unchanged.
- Left response error handling unchanged.

Rationale:

- OpenAI file upload and batch creation can create duplicate provider resources if a retry happens after a lost success.
- OpenAI batch cancel and file delete are state-changing operations; automatic retry can obscure the true provider state.

### `components/xagent/llm_provider_anthropic/provider.py`

Changed `upload_file()`:

- Replaced `self._send_with_retries(...)` around `client.post("/files", ...)` with a direct `await client.post(...)`.
- Preserved `x-api-key`, `anthropic-version`, `anthropic-beta`, and multipart file payload.
- Added the same resource-creation/idempotency comment as the OpenAI provider.
- Left timeout and HTTP error mapping unchanged.
- Left response error handling and `UploadedFile` normalization unchanged.

Changed `delete_file()`:

- Replaced `self._send_with_retries(...)` around `client.delete(...)` with a direct `await client.delete(...)`.
- Preserved file URL and Anthropic headers.
- Added the same ambiguous-delete comment as the OpenAI provider.
- Left timeout and HTTP error mapping unchanged.
- Left provider mismatch validation unchanged.
- Left response error handling unchanged.

Changed `_post_batch()`:

- Replaced `self._send_with_retries(...)` around `client.post(path, ...)` with a direct `await client.post(...)`.
- Preserved batch path, Anthropic headers, optional files beta header, and JSON payload.
- Added the same batch mutation/idempotency comment as the OpenAI provider.
- Left timeout and HTTP error mapping unchanged.
- Left response error handling unchanged.

Rationale:

- Anthropic file upload and batch creation can create duplicate provider resources if a retry happens after a lost success.
- Anthropic batch cancel and file delete are state-changing operations with ambiguous retry outcomes.

### `pyproject.toml`

Changed dependency list:

- Added `jsonschema>=4.26.0`.

Rationale:

- The CLI needs a real JSON Schema validator for dynamic `--schema-json` validation.
- This dependency is runtime, not dev-only, because the installed CLI imports and uses it.

### `uv.lock`

Added lock entries:

- `attrs==26.1.0`.
- `jsonschema==4.26.0`.
- `jsonschema-specifications==2025.9.1`.
- `referencing==0.37.0`.
- `rpds-py==0.30.0`.

Changed root package dependency metadata:

- Added `jsonschema` to the editable package dependency list.
- Added `jsonschema>=4.26.0` to `requires-dist`.

Rationale:

- These lockfile changes make the new runtime dependency reproducible for this project.
- The transitive packages are required by `jsonschema` for schema metadata, referencing, and persistent data structures.

### `test/bases/xagent/llm_cli/test_main.py`

Changed imports:

- Added `ValidationError` from Pydantic to assert that schema validation failures surface through the generated Pydantic model.
- Added `_structured_output_type` import so tests can directly exercise the generated dynamic output type.

Added `test_structured_output_type_enforces_json_schema()`:

- Builds a schema with a string enum, integer minimum, nested object, nested required field, top-level required fields, and `additionalProperties: false`.
- Calls `_structured_output_type(...)` to generate a schema-backed output model.
- Validates a good payload and asserts the dumped data matches the original payload.
- Validates a bad payload and expects a Pydantic `ValidationError` containing `"JSON Schema validation failed"`.

Added `test_structured_output_type_rejects_invalid_json_schema()`:

- Passes an invalid schema type.
- Expects `ValueError("Invalid JSON Schema...")`.

Rationale:

- The tests cover the exact gap from the review finding: type checks, enum checks, nested required fields, numeric bounds, and additional property rejection.
- Invalid schema coverage ensures CLI users fail early when passing bad `--schema-json`.

### `test/components/xagent/llm_provider_openai/test_files.py`

Changed imports:

- Added `pytest` for `pytest.raises`.
- Added `RetryConfig` to configure retry attempts in regression tests.
- Added `ProviderServerError` to assert the provider still maps final 5xx responses correctly.

Added `_test_openai_upload_file_does_not_retry_resource_creation()`:

- Counts calls made through `httpx.MockTransport`.
- Always returns a 500 response.
- Configures the provider with `RetryConfig(max_attempts=2)`.
- Calls `upload_file(...)`.
- Expects `ProviderServerError`.
- Asserts only one HTTP call occurred.

Added `test_openai_upload_file_does_not_retry_resource_creation()`:

- Runs the async upload regression test.

Added `_test_openai_delete_file_does_not_retry_ambiguous_delete()`:

- Counts calls made through `httpx.MockTransport`.
- Always returns a 500 response.
- Configures the provider with `RetryConfig(max_attempts=2)`.
- Calls `delete_file(...)`.
- Expects `ProviderServerError`.
- Asserts only one HTTP call occurred.

Added `test_openai_delete_file_does_not_retry_ambiguous_delete()`:

- Runs the async delete regression test.

Rationale:

- These tests prevent future changes from accidentally re-enabling retries for OpenAI file mutations.

### `test/components/xagent/llm_provider_openai/test_batch.py`

Changed imports:

- Added `pytest`.
- Added `RetryConfig`.
- Added `ProviderServerError`.

Added `_test_openai_create_batch_does_not_retry_resource_creation()`:

- Handles the preliminary OpenAI batch input file upload with a successful fake file response.
- Counts only the `/batches` POST calls.
- Returns 500 for `/batches`.
- Configures `RetryConfig(max_attempts=2)`.
- Calls `create_batch(...)`.
- Expects `ProviderServerError`.
- Asserts the batch-create POST happened once.

Added `test_openai_create_batch_does_not_retry_resource_creation()`:

- Runs the async batch-create regression test.

Added `_test_openai_cancel_batch_does_not_retry_resource_mutation()`:

- Counts calls made through `httpx.MockTransport`.
- Always returns 500.
- Configures `RetryConfig(max_attempts=2)`.
- Calls `cancel_batch(...)`.
- Expects `ProviderServerError`.
- Asserts only one HTTP call occurred.

Added `test_openai_cancel_batch_does_not_retry_resource_mutation()`:

- Runs the async batch-cancel regression test.

Rationale:

- These tests guard OpenAI native batch create/cancel from duplicate-prone automatic retries.

### `test/components/xagent/llm_provider_anthropic/test_files.py`

Changed imports:

- Added `pytest`.
- Added `RetryConfig`.
- Added `ProviderServerError`.

Added `_test_anthropic_upload_file_does_not_retry_resource_creation()`:

- Counts calls made through `httpx.MockTransport`.
- Always returns 500.
- Configures `RetryConfig(max_attempts=2)`.
- Calls `upload_file(...)`.
- Expects `ProviderServerError`.
- Asserts only one HTTP call occurred.

Added `test_anthropic_upload_file_does_not_retry_resource_creation()`:

- Runs the async upload regression test.

Added `_test_anthropic_delete_file_does_not_retry_ambiguous_delete()`:

- Counts calls made through `httpx.MockTransport`.
- Always returns 500.
- Configures `RetryConfig(max_attempts=2)`.
- Calls `delete_file(...)`.
- Expects `ProviderServerError`.
- Asserts only one HTTP call occurred.

Added `test_anthropic_delete_file_does_not_retry_ambiguous_delete()`:

- Runs the async delete regression test.

Rationale:

- These tests prevent future changes from accidentally re-enabling retries for Anthropic file mutations.

### `test/components/xagent/llm_provider_anthropic/test_batch.py`

Changed imports:

- Added `pytest`.
- Added `RetryConfig`.
- Added `ProviderServerError`.

Added `_test_anthropic_create_batch_does_not_retry_resource_creation()`:

- Counts calls made through `httpx.MockTransport`.
- Always returns 500.
- Configures `RetryConfig(max_attempts=2)`.
- Calls `create_batch(...)`.
- Expects `ProviderServerError`.
- Asserts only one HTTP call occurred.

Added `test_anthropic_create_batch_does_not_retry_resource_creation()`:

- Runs the async batch-create regression test.

Added `_test_anthropic_cancel_batch_does_not_retry_resource_mutation()`:

- Counts calls made through `httpx.MockTransport`.
- Always returns 500.
- Configures `RetryConfig(max_attempts=2)`.
- Calls `cancel_batch(...)`.
- Expects `ProviderServerError`.
- Asserts only one HTTP call occurred.

Added `test_anthropic_cancel_batch_does_not_retry_resource_mutation()`:

- Runs the async batch-cancel regression test.

Rationale:

- These tests guard Anthropic native batch create/cancel from duplicate-prone automatic retries.

### `doc/llm-design.txt`

Current working-tree status:

- The file is deleted.

Rationale:

- No feature rationale was identified for this deletion during the retry and CLI schema work.
- Treat this as unrelated unless the deletion was intentional.

## Residual Notes

- CLI structured output remains object-oriented because the shared structured parsing path requires JSON objects.
- A future hardening step could reject CLI schemas whose root type is not `"object"` to make that contract explicit.
- Live provider tests remain gated by environment variables and provider API keys.

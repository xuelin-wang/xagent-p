---
name: api-key-fields-use-secretstr
description: Config and dataclass fields holding API keys must use SecretStr | None, not str | None
metadata:
  type: feedback
---

Config model fields and dataclass fields holding API keys must be typed `SecretStr | None`, not `str | None`. Pydantic coerces plain strings to `SecretStr` automatically, and LangChain's `ChatOpenAI` / `OpenAIEmbeddings` require `SecretStr` for their `api_key` parameter. Provider-facing config models should also carry the matching `json_schema_extra={"secret": True, "env_var": "..."}` metadata so config construction can hydrate the secret once and downstream clients do not need to read the environment again. Using `str | None` causes mypy strict-mode errors at every call site.

**Why:** discovered when fixing mypy strict violations — `openai_api_key: str | None` in `CliConfig` and `ApiHttpConfig`, and `api_key: str | None` in `RAGSubagent`, all produced `arg-type` errors against LangChain.

**How to apply:** whenever adding a new config field or dataclass field that holds an API key or secret, use `SecretStr | None = None`. For provider-bound keys, add the provider-specific `env_var` metadata on the config model field and let config construction populate the secret before the client is built. Pydantic handles coercion from environment variables and YAML values automatically.

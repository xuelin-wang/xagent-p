---
name: api-key-fields-use-secretstr
description: Config and dataclass fields holding API keys must use SecretStr | None, not str | None
metadata:
  type: feedback
---

Config model fields and dataclass fields holding API keys must be typed `SecretStr | None`, not `str | None`. Pydantic coerces plain strings to `SecretStr` automatically, and LangChain's `ChatOpenAI` / `OpenAIEmbeddings` require `SecretStr` for their `api_key` parameter. Using `str | None` causes mypy strict-mode errors at every call site.

**Why:** discovered when fixing mypy strict violations — `openai_api_key: str | None` in `CliConfig` and `ApiHttpConfig`, and `api_key: str | None` in `RAGSubagent`, all produced `arg-type` errors against LangChain.

**How to apply:** whenever adding a new config field or dataclass field that holds an API key or secret, use `SecretStr | None = None`. Pydantic handles coercion from environment variables and YAML values automatically.

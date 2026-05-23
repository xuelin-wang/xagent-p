# API Key Fields Use SecretStr

Symbol: ✅

Status: superseded

Config and dataclass fields holding API keys must use `SecretStr | None`, not `str | None`.

Why it matters:
- Pydantic coerces plain strings to `SecretStr` automatically.
- LangChain client constructors expect `SecretStr` for API-key fields.
- Provider API keys should be hydrated once by config construction through explicit secret/env metadata.

Superseded by:
- `mementum/knowledge/implementation-invariants.md`
- `mementum/knowledge/architecture-decisions.md`

Source pointers:
- `components/xagent/llm_config/settings.py`
- `components/xagent/config/loader.py`
- `bases/xagent/api_http/app.py`
- `bases/xagent/langchain_cli/main.py`

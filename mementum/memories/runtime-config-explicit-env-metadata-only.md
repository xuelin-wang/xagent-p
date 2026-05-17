# Runtime Config Uses Explicit Env Metadata

Symbol: 💡

Runtime config should only apply environment-variable overrides to fields that explicitly declare `json_schema_extra={"secret": True, "env_var": "..."}`.

Why it matters:
- Keeps env overrides intentional instead of inferring them from top-level field names.
- Prevents accidental config injection from unrelated environment variables.
- Makes the override contract visible in the config model itself.
- The config path is just the write target after an exact env-var match; it is not part of env-var naming.

Source pointers:
- `components/xagent/config/loader.py`
- `components/xagent/config/strict.py`
- `components/xagent/llm_config/settings.py`

Future implication:
- When adding a config field that should accept env overrides, put the env binding on the field metadata and validate the env name alongside the model.

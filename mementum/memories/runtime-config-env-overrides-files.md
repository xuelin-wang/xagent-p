# Runtime Config Env Overrides Files

Symbol: 💡

Runtime config loads `--config` and `--env` files first, then overlays matching environment variables filtered by top-level config fields.

Why it matters:
- Kubernetes secrets injected through `envFrom` can override config-file values.
- Nested config keys use double underscores, such as `OPENAI__API_KEY`.

Source pointers:
- `components/xagent/runtime_config.py`
- `components/xagent/config.py`
- `projects/langchain_service/README.md`
- `deploy/langchain-service/templates/deployment.yaml`

Future implication:
- When debugging config differences between local files and Kubernetes, check environment variables after checking rendered config files.

---
title: Security and Data Boundaries
status: active
category: security
tags: [security, data, privacy, secrets]
related:
  - project-memory-policy
---

# Security and Data Boundaries

## Purpose

Capture repository-visible data handling rules that affect implementation and deployment.

## Current Understanding

- Never commit secrets, credentials, API keys, private keys, production data, customer data, private user data, raw sensitive logs, runtime records, or large generated artifacts.
- `mementum/` is safe-to-commit engineering context only.
- Runtime config supports YAML config files and env-style files, but environment-variable overrides are now explicit: only fields annotated with `json_schema_extra={"secret": True, "env_var": "..."}` are eligible, and the env var name must match that metadata exactly.
- The loader does not infer env var names from nested field paths; the nested config path is only the destination used after an explicit env-var match.
- Provider API keys are hydrated during config construction from provider-specific config subclasses and then passed through as `SecretStr` values.
- The Helm chart separates non-secret `appConfig` from credentials. Non-secret app config is rendered into a ConfigMap; credentials are injected from a Kubernetes Secret via `envFrom`.
- For shared/dev/prod clusters, docs recommend External Secrets Operator backed by a secret manager rather than committing production keys in Helm values.
- Local `kind` testing can use chart-managed secret creation with `secret.create=true`; this is documented as disposable local use.
- Provider wrappers must not log API keys, raw prompts, raw responses, tool result payloads, file bytes, embedding vectors, or full documents by default.

## Source Pointers

- `AGENTS.md`
- `mementum/knowledge/project-memory-policy.md`
- `components/xagent/config/loader.py`
- `components/xagent/config/runtime.py`
- `components/xagent/llm_config/settings.py`
- `projects/langchain_service/README.md`
- `deploy/langchain-service/values.yaml`
- `deploy/langchain-service/templates/configmap.yaml`
- `deploy/langchain-service/templates/deployment.yaml`
- `deploy/langchain-service/templates/secret.yaml`
- `deploy/langchain-service/templates/externalsecret.yaml`

## Notes for Future Agents

- Treat runtime/provider payloads as data, not project memory.
- Prefer adding tests for redaction or config behavior over documenting sensitive examples.

## To Be Verified

- Project-specific logging/tracing policy is still TODO-level in `README.md`.

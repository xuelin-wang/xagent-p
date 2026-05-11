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
- Runtime config supports YAML config files, env-style files, and environment variables. Environment variables are filtered by top-level config field names before being loaded.
- Nested config environment keys use double underscores, for example `OPENAI__API_KEY` maps to `openai.api_key`.
- The Helm chart separates non-secret `appConfig` from credentials. Non-secret app config is rendered into a ConfigMap; credentials are injected from a Kubernetes Secret via `envFrom`.
- For shared/dev/prod clusters, docs recommend External Secrets Operator backed by a secret manager rather than committing production keys in Helm values.
- Local `kind` testing can use chart-managed secret creation with `secret.create=true`; this is documented as disposable local use.
- Provider wrappers must not log API keys, raw prompts, raw responses, tool result payloads, file bytes, embedding vectors, or full documents by default.

## Source Pointers

- `AGENTS.md`
- `mementum/knowledge/project-memory-policy.md`
- `components/xagent/config.py`
- `components/xagent/runtime_config.py`
- `projects/langchain_service/README.md`
- `deploy/langchain-service/values.yaml`
- `deploy/langchain-service/templates/configmap.yaml`
- `deploy/langchain-service/templates/deployment.yaml`
- `deploy/langchain-service/templates/secret.yaml`
- `deploy/langchain-service/templates/externalsecret.yaml`
- `changelogs/20250509-llm-api-layer-design.txt`

## Notes for Future Agents

- Treat runtime/provider payloads as data, not project memory.
- Prefer adding tests for redaction or config behavior over documenting sensitive examples.

## To Be Verified

- Project-specific logging/tracing policy is still TODO-level in `README.md`.

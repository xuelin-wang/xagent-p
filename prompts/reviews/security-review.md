---
name: security-review
version: 1
status: active
purpose: Review changes for security, privacy, and data-boundary risks.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Security Review

## When to Use

Use this when changes touch authentication, secrets, config, logging, external services, deployment, files, tools, provider payloads, or project memory.

## Prompt

```text
Review the relevant changes for security, privacy, and data-boundary risks.

Before reviewing:
1. Read `AGENTS.md`.
2. Read `mementum/knowledge/security-and-data-boundaries.md` if present.
3. Search `mementum/memories/` for security or data-boundary lessons.
4. Inspect the branch diff and relevant source files.

Check for:
- committed secrets, credentials, keys, tokens, or private keys
- runtime data, private data, production data, raw logs, or large generated artifacts
- unsafe logging of prompts, raw responses, file bytes, tool payloads, or embeddings
- config precedence surprises
- overly broad permissions or secret exposure in deployment files
- missing validation around external input
- provider/API error handling that could leak sensitive data

Output findings first, ordered by severity.
For each finding, include:
- file and line reference
- risk
- exploit or failure scenario
- recommended fix

If no issues are found, state residual risk and any checks not performed.
Do not modify files unless explicitly asked.
```

## Expected Output

- Security findings or explicit no-finding statement.
- Residual risks and unperformed checks.

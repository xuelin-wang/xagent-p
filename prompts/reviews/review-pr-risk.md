---
name: review-pr-risk
version: 1
status: active
purpose: Review a branch or PR for merge risk and rollout concerns.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Review PR Risk

## When to Use

Use this before merging a branch when the main concern is risk, blast radius, or missing validation.

## Prompt

```text
Review the current branch or PR for merge risk.

Inspect:
1. Branch diff against `main`.
2. Relevant source, tests, docs, scripts, and config.
3. `mementum/state.md`.
4. Relevant `mementum/knowledge/` and `mementum/memories/`.

Assess:
- behavior changes
- public API or contract changes
- deployment or config impact
- security or data-handling impact
- migration or compatibility risk
- missing tests or validation
- unrelated files or generated artifacts

Output:
1. Highest-risk findings first.
2. File and line references where possible.
3. Why each risk matters.
4. Recommended mitigation.
5. Suggested validation before merge.

Do not modify files unless explicitly asked.
Do not include secrets, runtime data, private data, raw logs, or large generated artifacts.
```

## Expected Output

- Risk-ranked findings.
- Validation recommendations.
- Merge-readiness summary.

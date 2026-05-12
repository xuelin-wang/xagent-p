# Coding Agent Prompt Library

This directory contains reusable prompts for common coding-agent workflows.

`prompts/` is separate from `mementum/`:

- `prompts/` contains reusable instructions to paste into or invoke with agents.
- `mementum/` contains project memory: what is known, decided, current, risky, or learned.

Prompts can reference project memory. Project memory should not store full reusable workflow prompts.

Project-memory maintenance workflows live in the repo-local `skills/mementum-memory/` skill, not in this prompt library.

## Structure

```text
prompts/
  workflows/    # task execution prompts
  reviews/      # review and comparison prompts
  templates/    # prompt-authoring templates
skills/
  mementum-memory/  # project-memory maintenance skill and workflow references
```

## How to Use

1. Choose the prompt that matches the workflow.
2. Paste or invoke the prompt in a coding-agent session.
3. Let the agent adapt details to the current repo and user request.
4. Improve the prompt when repeated use reveals unclear or missing instructions.

## Starting Set

Workflows:

- `workflows/orient-repo.md`
- `workflows/implement-feature.md`
- `workflows/fix-bug.md`
- `workflows/refactor-code.md`
- `workflows/generate-changelog.md`

Reviews:

- `reviews/review-current-branch.md`
- `reviews/review-pr-risk.md`
- `reviews/compare-branches.md`
- `reviews/security-review.md`
- `reviews/test-coverage-review.md`

## Maintenance

Treat prompts like lightweight source code:

1. Use a prompt during real work.
2. Notice what failed or was unclear.
3. Update the prompt file.
4. Add rationale if the change is important.
5. Commit the prompt change.
6. If the prompt reflects a durable project lesson, update `mementum/` too.

Do not store secrets, credentials, private data, production data, runtime records, raw logs, or large generated artifacts in prompts.

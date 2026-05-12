---
name: synthesize-memories
version: 1
status: active
purpose: Convert repeated short memories into synthesized knowledge.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Synthesize Memories

## When to Use

Use this when multiple short memories point to the same stable convention, workflow, policy, or architectural understanding.

## Prompt

```text
Review `mementum/memories/` and identify repeated or related lessons that should be synthesized into `mementum/knowledge/`.

Process:
1. Read `mementum/memories/README.md`.
2. Read all potentially related memory files.
3. Search `mementum/knowledge/` for an existing page that should receive the synthesis.
4. Inspect source files referenced by the memories when needed.
5. Create or update a concise knowledge page with the stable understanding.
6. Preserve source pointers.
7. Decide whether the original memories should remain, link to the knowledge page, or be marked superseded.

Do not:
- delete useful history without a clear replacement
- merge unrelated lessons
- invent facts beyond source pointers
- store secrets, runtime data, raw logs, private data, or large generated artifacts

After editing, summarize:
1. Memories reviewed.
2. Knowledge page created or updated.
3. Memories left as-is or superseded.
4. Why the synthesis is durable.
```

## Expected Output

- Updated or new knowledge page.
- Clear mapping from repeated memories to synthesized knowledge.
- Supersession notes when applicable.

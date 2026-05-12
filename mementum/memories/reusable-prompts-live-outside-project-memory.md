# Reusable Workflows Live Outside Project Memory

Symbol: 📌

Reusable coding-agent workflow prompts belong under `prompts/`, and project-memory maintenance workflows belong under `skills/mementum-memory/`, not inside `mementum/`.

Why it matters:
- `prompts/` contains task instructions that agents can reuse.
- `skills/mementum-memory/` contains automated project-memory maintenance workflows.
- `mementum/` contains durable project state, decisions, rationale, conventions, pitfalls, and lessons.
- Keeping workflows separate prevents project memory from becoming a prompt or skill library.

Source pointers:
- `prompts/README.md`
- `skills/mementum-memory/SKILL.md`
- `AGENTS.md`
- `mementum/knowledge/architecture-decisions.md`

Future implication:
- Improve reusable prompt instructions in `prompts/`.
- Improve project-memory maintenance workflows in `skills/mementum-memory/`.
- Record durable lessons from workflow use in `mementum/` only when they meet the memory quality bar.

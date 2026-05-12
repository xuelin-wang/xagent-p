# TODO:
* add logs, phoenix tracing, otel non-agent tracing
* test signoz(?) integration, and GCP log collection flow

## Repo Skills Setup

Repo-local skill sources live under `skills/`. The current repo skill is:

- `skills/mementum-memory/`: project-memory maintenance workflows for `mementum/`.

Keep `skills/` as the source of truth. Add symlinks from each agent-specific skill discovery path instead of copying the skill.

### Codex

Codex discovers repo-scoped skills from `.agents/skills/` directories between the current working directory and the repository root. From the repo root:

```bash
mkdir -p .agents/skills
ln -s ../../skills/mementum-memory .agents/skills/mementum-memory
```

Restart Codex if the skill does not appear. Codex also supports user-scoped skills under `$HOME/.agents/skills/`; use a repo-scoped symlink for this project so the skill stays versioned with the repository.

### Claude Code

Claude Code discovers project skills from `.claude/skills/` in the project and personal skills from `$HOME/.claude/skills/`. From the repo root:

```bash
mkdir -p .claude/skills
ln -s ../../skills/mementum-memory .claude/skills/mementum-memory
```

Restart Claude Code if the skill does not appear. Use the project-scoped symlink for this repo so teammates get the same skill source after pulling the repository.

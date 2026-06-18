# Locate Before Edit

Use this prompt before changing any file in this repository.

1. Read `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/AI_WORKFLOW.md`, `docs/ai_collaboration.md`, `docs/FEATURE_MAP.md`, and any relevant ADR.
2. Run `git status --short` and preserve unrelated user, Claude, or Codex changes.
3. Locate the owning layer in `docs/FEATURE_MAP.md` or `docs/UI_MAP.md`.
4. Read the exact files you plan to edit plus the nearest tests.
5. State permitted files, forbidden files, required checks, and rollback plan before editing.

Forbidden without explicit user approval:

- Strategy assumption changes not backed by `research/strategy_synthesis.md`.
- Risk, portfolio, execution, DB schema, live/shadow/demo mode, deployment gate, or frozen artifact changes.
- Broad refactors, formatting churn, branch operations, or deletion of unrelated files.

Completion evidence:

- Changed files listed.
- Tests/checks run or skipped with reason.
- Docs updated when behavior, workflow, or surface area changed.

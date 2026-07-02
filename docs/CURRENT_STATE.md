---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
short and present-tense; history goes to `docs/CHANGELOG_AI.md`, backlog goes to
`docs/KNOWN_ISSUES.md`.

## Snapshot

- Current branch: `codex/pipeline-batch1-stage3`.
- Current task: `tasks/2026-07-03-project-maintenance-tasks.md` M1-M5.
- M1 CI consistency is committed in `df96682`.
- The 2026-07-03 handoff/task docs are preserved in `79c1ddc` before M2.
- M2 hot-state docs and branch/status board slimming is implemented.
- Next: M3 no-DB backtest smoke fixture and M4 monitoring unit tests, then M5
  stocks disposition.

## Active Warnings

- The working tree has unrelated dirty pipeline/research/result files. Do not
  revert, overwrite, or sweep-commit them during M1-M5.
- No strategy, risk, portfolio, execution, deployment gate, or existing result
  artifact is in scope for the maintenance tasks.
- `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, and
  `config/` remain truth sources for strategy/config behavior.

## Current Gaps

- `make backtest-smoke` still needs the M3 frozen no-DB replay fixture.
- Monitoring modules exist but need M4 unit coverage before docs can map tests.
- `src/okx_quant/stocks/` is orphaned in ownership docs; M5 Option A is the
  default docs-only keep decision unless the user explicitly requests deletion.

## How to Update

Overwrite this snapshot when it goes stale. Do not append history.

Related: `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`,
`docs/CONTEXT_INDEX.md`, and `docs/CONTEXT_BUDGET.md`.

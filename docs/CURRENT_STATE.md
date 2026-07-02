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
- Current task: `tasks/2026-07-03-project-maintenance-tasks.md` M1-M5 complete.
- M1 CI consistency is committed in `df96682`.
- The 2026-07-03 handoff/task docs are preserved in `79c1ddc` before M2.
- M2 hot-state docs and branch/status board slimming is committed in `0191c1d`.
- M3 no-DB backtest smoke fixture is committed in `2dea608`.
- M4 monitoring unit tests and M5 stocks Option A mapping are committed in
  `5eb71f8`.

## Active Warnings

- The working tree has unrelated dirty pipeline/research/result files. Do not
  revert, overwrite, or sweep-commit them during maintenance follow-up.
- No strategy, risk, portfolio, execution, deployment gate, or existing result
  artifact is in scope for the maintenance tasks.
- `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, and
  `config/` remain truth sources for strategy/config behavior.

## Current Gaps

- `make` is unavailable in the current Windows sandbox. The equivalent Python
  commands for docs-check and backtest-smoke passed.
- `make backtest-smoke` now runs a tiny no-DB replay fixture, but it is
  `strategy_fill` / `idealized_fill` smoke coverage only, not promotion evidence.
- Monitoring modules now have unit coverage, but production alert readiness still
  requires separate operational validation.
- `src/okx_quant/stocks/` is kept as a docs-mapped research-only sandbox
  (M5 Option A); it is not wired into crypto replay, UI, API, or deployment gates.

## How to Update

Overwrite this snapshot when it goes stale. Do not append history.

Related: `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`,
`docs/CONTEXT_INDEX.md`, and `docs/CONTEXT_BUDGET.md`.

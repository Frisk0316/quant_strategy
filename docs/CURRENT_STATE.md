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

- Current branch: `codex/pipeline-batch1-stage3` (working tree clean; P1-P8 is
  now committed as `dfc7af8`, including the ETH liquidation contract_value fix
  pinned by a seed-spec regression test).
- Current task: `tasks/2026-07-03-project-maintenance-tasks.md` M1-M5 complete
  and Claude-reviewed 2026-07-03 on independent re-run evidence: M1/M3/M4/M5
  accepted; M2 partial — the deleted 2026-06-24→07-01 history was not migrated
  into CHANGELOG_AI (recoverable via `git show 0191c1d^:docs/AI_HANDOFF.md`);
  remediation M2-R1 in the same task file awaits Codex.
- M1 CI consistency is committed in `df96682`.
- The 2026-07-03 handoff/task docs are preserved in `79c1ddc` before M2.
- M2 hot-state docs and branch/status board slimming is committed in `0191c1d`.
- M3 no-DB backtest smoke fixture is committed in `2dea608`.
- M4 monitoring unit tests and M5 stocks Option A mapping are committed in
  `5eb71f8`.
- Parallel pipeline task `tasks/2026-07-03-pipeline-improvement-tasks.md`
  P1-P8 is committed (`dfc7af8`, incl. the ETH ct_val 0.1 fix) and the
  real-data acceptance runs are DONE (2026-07-03, Claude, user-authorized):
  P1 funding backfill 66,041 rows / 22 symbols / 0 gaps; P8 Vision OI history
  262,814 rows each BTC/ETH (2024-01→now); P5 first liquidation ingest with a
  measured **hours-scale** OKX REST window (BTC ≈14h, ETH ≈5h — lossless
  accumulation needs a 2-4h cadence, scheduling = pending user decision);
  advisory reprobe appended improved-but-FAIL funding metrics to taxonomy_002.
  **New root cause:** `build_universe_membership.py` builds `eligible` from
  the thin local parquet mirror (median 2 eligible/day; DB-rebuilt diagnostic
  gives 29) — this underlies E-028 universe=8 and H-004/S5 no-grid-activity.
  P9 (membership builder DB source) added to the task file; the 2024-01
  warmup-edge window question is a spec decision awaiting the user. No
  threshold, gate, or ledger changed; no live/demo/shadow readiness claimed.

## Active Warnings

- The earlier "dirty pipeline worktree" warning is superseded: P1-P8 was
  committed separately as `dfc7af8` and the tree is clean. Maintenance commits
  did not sweep pipeline files (verified in the 2026-07-03 Claude review).
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

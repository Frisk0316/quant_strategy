---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-16
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
**short** and **present-tense** - it is not a changelog (history goes to
`docs/CHANGELOG_AI.md`) and not a backlog (gaps go to `docs/KNOWN_ISSUES.md`).

This file complements `docs/AI_HANDOFF.md`: `AI_HANDOFF.md` is the working
handoff between sessions; this is the one-screen "where are we" that
[[CONTEXT_BUDGET]] marks must-load.

## Snapshot

- **Current goal:** Backtest-correctness validation is focused on active-strategy
  portable signal-point evidence. Unit-level differential-validation tests and a
  dependency-backed all-strategy signal-validation batch are green.
- **Current branch:** `feature/chart-ux-overhaul`.
- **Last known good state:** `tests/unit/test_differential_validation.py` plus the
  signal-validation CLI interface tests pass locally. Batch
  `codex_20260616_signal_validation` produced PASS rows for all active strategies
  under `results/strategy_validation/`.
- **In progress:** `scripts/run_all_strategy_signal_validation.py` has a
  selectable `--engines` CLI, and `make strategy-signal-validation` is the
  standard entrypoint. No existing result artifacts were modified.
- **Active risks:** the batch fixtures verify signal-point portability only. They
  do not validate live execution, queue behavior, fees/slippage, funding
  settlement, PnL parity, WalkForward/CPCV, or DB-backed real-market data. The
  OHLCV rotation fixture emits benign zscore precision warnings from near-identical
  synthetic rows.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, DB schema, API and
  frontend behavior, deployment gates, and existing result artifacts.

## Next steps

- Review the new `results/strategy_validation/*/codex_20260616_signal_validation_three_engine_signal_point/validation_result.json`
  artifacts, then decide whether to promote this fixture batch into a CI check.
- Decide via branch protection whether the `docs` CI job is a required check.
- Backfill lifecycle metadata on the 11 pre-existing metadata-less docs.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].

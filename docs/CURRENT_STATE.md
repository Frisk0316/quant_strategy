---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-17
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

- **Current goal:** Backtest-correctness validation has promoted active-strategy
  portable signal-point fixtures into the CI surface. A manual real-data/source
  provenance gate now exists; the next validation priority is running it with
  canonical DB candles and authoritative `ct_val` evidence, not full execution
  parity.
- **Current branch:** `feature/chart-ux-overhaul`.
- **Last known good state:** `tests/unit/test_differential_validation.py`, the
  signal-validation CLI interface tests, and
  `tests/unit/test_source_provenance_validation.py` pass locally. Batch
  `codex_20260616_signal_validation` produced PASS rows for all active strategies
  under `results/strategy_validation/`.
- **In progress:** `scripts/run_all_strategy_signal_validation.py` has a
  selectable `--engines` CLI, `make strategy-signal-validation` is the standard
  entrypoint, and CI runs the fixture batch with artifacts in runner temp storage.
  `scripts/run_source_provenance_validation.py` gates existing or freshly
  generated differential-validation evidence and fails DB parity `SKIP`. No
  existing result artifacts were modified.
- **Active risks:** the batch fixtures verify signal-point portability only. They
  do not validate live execution, queue behavior, fees/slippage, funding
  settlement, PnL parity, WalkForward/CPCV, or DB-backed real-market data. The
  OHLCV rotation fixture emits benign zscore precision warnings from near-identical
  synthetic rows.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, DB schema, API and
  frontend behavior, deployment gates, and existing result artifacts.

## Next steps

- Run the source-provenance gate against a DB-backed saved run with canonical
  candles and authoritative `ct_val` evidence.
- Configure branch protection so `strategy-signal-validation` is a required check
  after the workflow is pushed; GitHub repository settings are outside the local
  code diff.
- Backfill lifecycle metadata on the 11 pre-existing metadata-less docs.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].

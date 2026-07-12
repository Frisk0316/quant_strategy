---
status: current
type: handoff
owner: human
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Context Handoff: Project Maintenance M1-M5 - 2026-07-03

## Goal (one sentence)
Complete the non-pipeline project maintenance task list M1-M5 without overwriting
parallel pipeline/research work.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: `5eb71f8` for M4/M5, with earlier maintenance
  commits `df96682`, `79c1ddc`, `0191c1d`, and `2dea608`.
- In-progress edits (files): unrelated pipeline/research/result files remain
  dirty in the working tree; do not sweep-commit them with maintenance work.
- What works right now: M1-M5 are implemented and committed; the no-DB replay
  smoke, monitoring tests, full unit suite, docs-check equivalents, and stock
  unit tests passed in this Windows sandbox.
- What does not work / unfinished: `make` is unavailable here, so make targets
  were verified through their equivalent Python/Node commands. Pipeline P1-P8
  still needs Claude review and real DB/network verification.

## Decisions made (and why)
- M5 used Option A - keep `src/okx_quant/stocks/` as a research-only sandbox -
  because there was no explicit human approval to delete code.
- M3 uses a tiny CSV fixture converted to temp parquet at runtime because the
  repository should keep fixture data readable and should not write smoke output
  into `results/`.
- `strategy_fill` / `idealized_fill` is explicitly recorded in smoke artifacts
  because the smoke is execution plumbing coverage, not promotion evidence.

## Open questions / unverified assumptions
- Which remaining dirty pipeline changes are intended for a later P1-P8 commit
  versus superseded scratch work?
- Full `make verify` and `make verify-full` remain unrun in this environment.

## Rules in play (preserve verbatim)
- Invariants touched: none.
- Domain rules touched: none.
- Do-not-touch: no live/shadow/demo gate changes; no strategy assumption changes;
  no edits to existing result artifacts; no edits to `research/` for maintenance.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, `tasks/2026-07-03-project-maintenance-tasks.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/RUNBOOK.md`,
  `docs/KNOWN_ISSUES.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `ruff check src tests backtesting scripts` - passed during M1.
- `pytest tests/unit -q` - passed, 575 tests after M4.
- `pytest tests/test_daily_winner_backtest.py tests/test_ohlcv_rotation.py -q`
  - passed, 32 tests during M1.
- `pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` - passed,
  18 tests during M1.
- `python scripts/smoke/backtest_smoke.py` - passed; verified result, metrics,
  fills artifacts in a temp dir.
- Temporary broken-fixture probe for `scripts/smoke/backtest_smoke.py` - failed
  with exit 1, then fixture was restored and smoke passed.
- `pytest tests/unit/test_monitoring.py -v` - passed, 4 tests.
- `ruff check scripts/smoke/backtest_smoke.py tests/unit/test_monitoring.py src/okx_quant/stocks/__init__.py`
  - passed.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `pytest tests/unit/test_stock_system.py -q` - passed, 5 tests.
- `make backtest-smoke` / `make docs-check` - not runnable here because `make`
  is not installed.

## Approvals
- Human approval needed / obtained: M5 deletion was not approved, so Option A was
  used.

## Next action (single, concrete)
- Have Claude/human review commits `df96682`, `79c1ddc`, `0191c1d`, `2dea608`,
  and `5eb71f8`, then separately review the dirty pipeline P1-P8 worktree.

## Human Learning Notes
Tiny smoke checks are most useful when they are explicit about what they do not
prove. Here, the fixture now catches broken replay/artifact plumbing, but it
remains idealized-fill smoke coverage rather than trading evidence. Also, in a
mixed dirty worktree, stage documentation hunks surgically; whole-file staging
would have swept unrelated pipeline changes.

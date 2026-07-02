---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# AI Handoff

Cross-session memory for Claude and Codex. Keep this file current-state only;
move completed session history to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

## Current Goal

Codex completed `tasks/2026-07-03-project-maintenance-tasks.md` in the user
requested order: M1 -> M2 -> M3/M4 -> M5.

Current status:

- M1 CI consistency is implemented and committed in `df96682`.
- The 2026-07-03 Claude handoff/task docs are preserved in `79c1ddc`, satisfying
  the M2 precondition before this slimming pass.
- M2 docs/governance slimming is committed in `0191c1d`.
- M3 no-DB backtest smoke fixture is committed in `2dea608`.
- M4 monitoring unit tests and M5 stocks Option A mapping are committed in
  `5eb71f8`.

Pipeline improvement work P1-P8 is separate. Its handoff/task files are committed,
but pipeline code/research/result changes that remain dirty in the working tree
are not owned by this maintenance task.

## Current Branch

- Branch: `codex/pipeline-batch1-stage3`.
- Recent commits: `df96682` (M1), `79c1ddc` (7/3 handoff preservation),
  `0191c1d` (M2), `2dea608` (M3), `5eb71f8` (M4/M5).
- Working tree also contains unrelated pre-existing pipeline changes; do not
  overwrite or sweep-commit them.

## Do Not Touch

Without explicit user approval, do not modify:

- `research/` except already-existing uncommitted pipeline work owned elsewhere.
- `results/**` existing artifacts.
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`.
- `src/okx_quant/risk/`, `src/okx_quant/portfolio/`,
  `src/okx_quant/execution/`.
- `config/risk.yaml`, deployment/shadow/demo/live gates, or strategy assumptions.
- Differential-validation implementation unless a current task explicitly lists it.

## Completed Scope

M1 changed only CI/static-check docs surface:
`.github/workflows/ci.yml`, `Makefile`, `docs/KNOWN_ISSUES.md`.

M2 may change only:
`docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/CURRENT_STATE.md`,
`docs/KNOWN_ISSUES.md`, `STATUS.md`, `config/workstreams.yaml`.

M3 may change only:
`scripts/smoke/backtest_smoke.py`, `tests/fixtures/backtest_smoke/**`,
`Makefile`, `docs/KNOWN_ISSUES.md`, `docs/RUNBOOK.md`.

M4 may change only:
`tests/unit/test_monitoring.py`, `docs/FEATURE_MAP.md`.

M5 Option A may change only:
`docs/FEATURE_MAP.md`, `src/okx_quant/stocks/__init__.py`.

## Verification Notes

M1 local evidence:

- `ruff check src tests backtesting scripts` passed.
- `pytest tests/unit -q` passed: 555 tests.
- `pytest tests/test_daily_winner_backtest.py tests/test_ohlcv_rotation.py -q`
  passed: 32 tests.
- `pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` passed:
  18 tests.
- `make frontend-check` could not run because `make` is unavailable in this
  Windows sandbox; each `node --check` command from the target passed manually.

M2 local evidence:

- `python scripts/docs/check_doc_metadata.py`
- `python scripts/docs/check_feature_map_links.py`

M3-M5 local evidence:

- `python scripts/smoke/backtest_smoke.py` passed: replay smoke emitted 2 fills
  and verified `result.json`, `metrics.json`, and `fills.csv` in a temp dir.
- Temporary broken-fixture probe made `scripts/smoke/backtest_smoke.py` fail with
  exit 1, then the fixture was restored and the smoke passed again.
- `pytest tests/unit/test_monitoring.py -v` passed: 4 tests.
- `pytest tests/unit -q` passed: 575 tests.
- `ruff check scripts/smoke/backtest_smoke.py tests/unit/test_monitoring.py src/okx_quant/stocks/__init__.py`
  passed.
- `python scripts/docs/check_doc_metadata.py` passed.
- `python scripts/docs/check_feature_map_links.py` passed.
- `pytest tests/unit/test_stock_system.py -q` passed: 5 tests.
- `make backtest-smoke` and `make docs-check` could not run because `make` is
  unavailable in this Windows sandbox; equivalent Python commands passed.

## Next Steps

1. Claude/human review the M1-M5 maintenance commits and the two handoff files.
2. Review the separate pipeline P1-P8 dirty worktree; do not sweep-commit it
   with maintenance changes.
3. Run full `make verify` / `make verify-full` only in an environment where
   `make`, TimescaleDB, and required data are available.

## Open Questions

- Which dirty pipeline changes are intended for a later P1-P8 commit versus
  already superseded scratch work?

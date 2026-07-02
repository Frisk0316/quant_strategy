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

Codex is executing `tasks/2026-07-03-project-maintenance-tasks.md` in the user
requested order: M1 -> M2 -> M3/M4 -> M5.

Current status:

- M1 CI consistency is implemented and committed in `df96682`.
- The 2026-07-03 Claude handoff/task docs are preserved in `79c1ddc`, satisfying
  the M2 precondition before this slimming pass.
- M2 docs/governance slimming is implemented in the working tree.
- M3 and M4 are next and have disjoint write scopes.
- M5 defaults to docs-only Option A unless the user explicitly chooses deletion.

Pipeline improvement work P1-P8 is separate. Its handoff/task files are committed,
but pipeline code/research/result changes that remain dirty in the working tree
are not owned by this maintenance task.

## Current Branch

- Branch: `codex/pipeline-batch1-stage3`.
- Recent commits: `df96682` (M1), `79c1ddc` (7/3 handoff preservation).
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

## Active Scope

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

For M2, run the docs-check equivalents if `make` is unavailable:

- `python scripts/docs/check_doc_metadata.py`
- `python scripts/docs/check_feature_map_links.py`

## Next Steps

1. Commit M2 after review.
2. Implement M3 frozen no-DB backtest smoke fixture without touching replay/data
   loader semantics or weakening venue-scoped/I19 behavior.
3. Implement M4 monitoring unit tests without changing monitoring source code.
4. Apply M5 Option A docs-only ownership registration for `stocks/` unless the
   user gives an explicit delete decision.

## Open Questions

- For M5, should `src/okx_quant/stocks/` be kept as research-only docs-mapped
  code (Option A, default) or deleted with its script/test (Option B)?
- Which dirty pipeline changes are intended for a later P1-P8 commit versus
  already superseded scratch work?

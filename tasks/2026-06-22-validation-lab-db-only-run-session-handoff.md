# Session Handoff: Validation Lab DB-only saved runs - 2026-06-22

## Implementation summary
Validation Lab now treats saved Backtest Runs as first-class validation candidates. Saved runs call the run-scoped differential-validation endpoint; DB-only runs are materialized from `backtest_artifacts` into a temporary file bundle for validation input, while validation output is written under the run's `validation/` directory. The run detail header now wraps long names safely, and Risk events show a compact reason/symbol/strategy summary.

## Diff scope
- Files added: `tasks/2026-06-22-validation-lab-db-only-run-context-handoff.md`, `tasks/2026-06-22-validation-lab-db-only-run-session-handoff.md`
- Files changed: `src/okx_quant/api/routes_backtest.py`, `frontend/view-validation.js`, `frontend/view-backtest.js`, `frontend/styles.css`, `tests/unit/test_differential_validation.py`, `tests/unit/test_backtest_visual_fallbacks.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`
- Files deleted: none

## Business-rule change?
- No. No Change Manifest required; no PnL/fee/funding/sizing/risk/fill/gate semantics changed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A
- config/: N/A
- ADR: N/A

## Experiments
- HYPOTHESIS_LEDGER entries: none
- EXPERIMENT_REGISTRY entries: none

## Tests / checks run
- `make frontend-check` - not run; `make` is unavailable in this Windows sandbox.
- `make docs-check` - not run; `make` is unavailable in this Windows sandbox.
- Frontend-check equivalent: `node --check` on `frontend/data.js`, `frontend/charts.js`, `frontend/view-config.js`, `frontend/view-backtest.js`, `frontend/view-results.js`, `frontend/view-validation.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`, and `frontend/app.js` - passed.
- Docs-check equivalent: `scripts/docs/check_doc_metadata.py` - passed with 13 existing metadata warnings; `scripts/docs/check_feature_map_links.py` - passed.
- `python -m pytest tests\unit\test_differential_validation.py::test_backtest_api_triggers_and_reads_differential_validation tests\unit\test_differential_validation.py::test_backtest_api_triggers_db_only_differential_validation tests\unit\test_differential_validation.py::test_backtest_api_triggers_strategy_validation tests\unit\test_backtest_visual_fallbacks.py::test_validation_lab_can_run_saved_backtest_records_directly -q` - passed with a pytest cache permission warning.

## Docs updated
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/UI_MAP.md`
- `docs/DATA_FLOW.md`

## Known limitations / risks
- Browser smoke against a live DB-backed server was not run yet.
- DB-only validation still depends on required artifact payloads existing in `backtest_artifacts`.
- Optional reference-engine dependencies can still produce SKIP rows and do not satisfy promotion gates.

## Rollback plan
- Revert the listed code/doc/test files. This removes the DB-only validation bridge, saved-run Validation Lab selector behavior, header wrapping CSS, risk-event summary, and session handoffs without touching trading-core or existing result artifacts.

## Context Handoff
- See `tasks/2026-06-22-validation-lab-db-only-run-context-handoff.md`.

## Questions for human review
- Please browser-smoke a long-title DB-backed run such as `2026/06/22_ma_crossover_btc_usdt_swap_1000shib_usdt_swap` in Validation Lab once the local server and DB are running.

## Next recommended task
- Run a real Validation Lab job on the cited DB-backed run and inspect whether missing reference dependencies or source-data checks block the selected engines.

## Human Learning Notes (required)
When artifact mode defaults to DB, UI surfaces that read `/api/backtest/runs` can see new runs before older validation fixture flows can. Prefer bridging reader workflows to the existing DB payload contract before adding new artifact migrations.

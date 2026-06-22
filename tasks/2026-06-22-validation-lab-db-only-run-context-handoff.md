# Context Handoff: Validation Lab DB-only saved runs - 2026-06-22

## Goal (one sentence)
Make newly saved DB-only backtest records selectable and runnable in Validation Lab without changing validation gates or existing result artifacts.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`
- Last known good commit / state: working tree already contained unrelated `market_data_handler` edits before this task.
- In-progress edits (files): `src/okx_quant/api/routes_backtest.py`, `frontend/view-validation.js`, `frontend/view-backtest.js`, `frontend/styles.css`, tests, docs, and this handoff.
- What works right now: targeted DB-only/run-scoped validation tests pass; the frontend-check equivalent and docs-check equivalent pass.
- What does not work / unfinished: no browser smoke against a live DB-backed server has been run in this session.

## Decisions made (and why)
- Use run-scoped validation for saved Backtest Runs because it handles DB-only runs without coupling them to strategy fixture discovery.
- Materialize DB artifacts into a temporary input directory because existing differential validation expects files and this avoids mutating saved backtest artifacts.
- Keep `fill_all_signals` as research-only guidance because deployment admissibility rules already exclude it.

## Open questions / unverified assumptions
- Real local DB payloads include the required `backtest_artifacts` rows for each selected run.
- Browser layout for very long display names should be visually smoked on the user's viewport.

## Rules in play (preserve verbatim)
- Invariants touched: none.
- Domain rules touched: none.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`, DB schema, existing `results/` artifacts, validation gate/tolerance semantics.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`.
- Owning files / MODULE_BRIEFS: Backtest Result Charts, Backtest API, Validation / Promotion Gates in `docs/FEATURE_MAP.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `make frontend-check` - not run; `make` is unavailable in this Windows sandbox.
- `make docs-check` - not run; `make` is unavailable in this Windows sandbox.
- Frontend-check equivalent: `node --check` on `frontend/data.js`, `frontend/charts.js`, `frontend/view-config.js`, `frontend/view-backtest.js`, `frontend/view-results.js`, `frontend/view-validation.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`, and `frontend/app.js` - passed.
- Docs-check equivalent: `scripts/docs/check_doc_metadata.py` - passed with 13 existing metadata warnings; `scripts/docs/check_feature_map_links.py` - passed.
- `python -m pytest tests\unit\test_differential_validation.py::test_backtest_api_triggers_and_reads_differential_validation tests\unit\test_differential_validation.py::test_backtest_api_triggers_db_only_differential_validation tests\unit\test_differential_validation.py::test_backtest_api_triggers_strategy_validation tests\unit\test_backtest_visual_fallbacks.py::test_validation_lab_can_run_saved_backtest_records_directly -q` - passed with a pytest cache permission warning.

## Approvals
- Human approval obtained in chat to implement the proposed plan.

## Next action (single, concrete)
- Run the full relevant check set (`make frontend-check`, targeted pytest, `make docs-check`) or the Windows equivalents if `make` is unavailable.

## Human Learning Notes
The core mismatch was artifact storage mode: Backtest Runs already merged DB records, while Validation Lab still assumed filesystem fixtures. Bridging at the run-scoped validation endpoint avoids changing strategy-validation semantics.

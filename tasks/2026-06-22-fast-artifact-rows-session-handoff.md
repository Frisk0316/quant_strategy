# Session Handoff: Fast Backtest Artifact Rows - 2026-06-22

## Implementation summary

Implemented Option C as a derived artifact-row read layer. New runs keep writing
existing files/JSONB payloads and best-effort dual-write `backtest_artifact_rows`
using PostgreSQL bulk COPY.
Backtest API endpoints use row-first reads for common chart/table artifacts, fall
back to existing JSONB/file readers, and expose a lightweight `/summary` endpoint
for immediate UI selection. Frontend selection now loads summary first and uses
short in-flight caches for run list and data coverage. Backfill and benchmark
scripts provide the verification path for old runs.

## Diff scope

- Files added: `backtesting/artifact_rows.py`,
  `sql/migrations/0012_backtest_artifact_rows.sql`,
  `scripts/backfill_backtest_artifact_rows.py`,
  `scripts/benchmark_artifact_reads.py`,
  `tests/unit/test_artifact_rows.py`,
  `docs/ADR/0008-fast-backtest-artifact-rows.md`,
  `docs/change_manifests/2026-06-22-fast-backtest-artifact-rows.md`,
  `tasks/2026-06-22-fast-artifact-rows-context-handoff.md`,
  `tasks/2026-06-22-fast-artifact-rows-session-handoff.md`.
- Files changed: `backtesting/artifacts.py`,
  `src/okx_quant/api/routes_backtest.py`, `frontend/data.js`,
  `frontend/view-backtest.js`, `tests/unit/test_backtest_artifact_schema.py`,
  `tests/unit/test_backtest_visual_fallbacks.py`, `docs/ADR/README.md`,
  `docs/AI_HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG_AI.md`,
  `docs/CURRENT_STATE.md`, `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`,
  `docs/RUNBOOK.md`, `docs/UI_MAP.md`.
- Files deleted: none.

## Business-rule change?

- No. Change Manifest added at
  `docs/change_manifests/2026-06-22-fast-backtest-artifact-rows.md` because the
  task changes DB schema/storage behavior. DOC_IMPACT_MATRIX trigger areas:
  A5/A6/A8/A10. Money/risk impact is none.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; no strategy or promotion-evidence change.
- config/: N/A.
- ADR: ADR-0008 added and ADR index updated.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- `pytest tests/unit/test_artifact_rows.py tests/unit/test_backtest_artifact_schema.py tests/unit/test_backtest_visual_fallbacks.py -q` -> 27 passed; pytest cache permission warning only.
- `pytest tests/unit/test_artifact_rows.py -q` -> 5 passed after changing row
  writes from per-row `executemany` to bulk COPY.
- `pytest tests/unit/test_backtesting.py::test_save_backtest_artifacts_writes_validation_to_result_json tests/unit/test_backtesting.py::test_save_backtest_artifacts_mirrors_fill_all_signals_to_idealized_fill tests/unit/test_backtesting.py::test_save_artifacts_records_indicator_warmup_sources -q` -> 3 passed.
- `ruff check backtesting/artifact_rows.py backtesting/artifacts.py src/okx_quant/api/routes_backtest.py scripts/backfill_backtest_artifact_rows.py scripts/benchmark_artifact_reads.py tests/unit/test_artifact_rows.py tests/unit/test_backtest_visual_fallbacks.py tests/unit/test_backtest_artifact_schema.py` -> passed.
- `node --check` for all Makefile frontend modules -> passed.
- `python -B scripts/backfill_backtest_artifact_rows.py --all --limit-runs 1 --dry-run` -> 1 run, 11 artifacts, 11,159 derived rows.
- `python -B scripts/backfill_backtest_artifact_rows.py --help` and `python -B scripts/benchmark_artifact_reads.py --help` -> passed.
- `python scripts/docs/check_doc_metadata.py` -> passed with 13 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` -> passed.
- `python scripts/docs/check_doc_impact.py --strict` -> exited 0 but reported no changed files detected.
- `python scripts/validate_pipeline.py --check-config-only` -> passed.
- `python scripts/smoke/api_smoke.py` -> SKIP; `API_BASE_URL` unset.
- `python scripts/smoke/backtest_smoke.py` -> entrypoint PASS; full replay fixture SKIP.
- `make frontend-check` -> failed because `make` is unavailable in this Windows sandbox; direct `node --check` equivalent was run.

## Docs updated

- `docs/ADR/0008-fast-backtest-artifact-rows.md`
- `docs/change_manifests/2026-06-22-fast-backtest-artifact-rows.md`
- `docs/ADR/README.md`
- `docs/DATA_FLOW.md`
- `docs/RUNBOOK.md`
- `docs/FEATURE_MAP.md`
- `docs/UI_MAP.md`
- `docs/ARCHITECTURE.md`
- `docs/CHANGELOG_AI.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`

## Known limitations / risks

- `DATABASE_URL` was unset, so migration 0012, DB backfill `--verify`, cascade
  delete verification, and API latency benchmark were not run.
- `check_doc_impact.py --strict` reported no changed files detected despite a
  dirty worktree; treat docs-impact as inconclusive in this sandbox.
- Summary endpoint trims the response after reading the result payload. Current
  ADR-0002 results are small, but very old legacy result payloads with embedded
  heavy arrays may still pay an initial read cost.

## Rollback plan

- Revert the added migration/helper/scripts/API/frontend/tests/docs. If migration
  was applied, drop `backtest_artifact_rows`; existing `backtest_artifacts` and
  file artifacts remain the compatibility source and do not require migration.

## Context Handoff

- See `tasks/2026-06-22-fast-artifact-rows-context-handoff.md`.

## Questions for human review

- Which saved run should be used as the canonical DB-backed benchmark target
  after migration/backfill?
- Should summary endpoint be optimized further to read only `backtest_runs` plus
  small artifacts for legacy results with embedded arrays?

## Next recommended task

- Run DB migration/backfill/benchmark in a DB-backed environment and attach the
  JSON timing report plus backfill verification output to the PR/session.

## Human Learning Notes (required)

The fastest safe fix was not to reinterpret artifacts, but to add a disposable
index beside them. That keeps compatibility and trading evidence stable while
making the UI ask the database for only the rows it actually needs.

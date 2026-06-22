# Context Handoff: Fast Backtest Artifact Rows - 2026-06-22

## Goal (one sentence)

Make saved backtest artifacts load quickly by adding a derived row-index read
path without changing trading logic, PnL, fees, funding, sizing, fills, risk, or
validation semantics.

## Current state

- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: pre-existing branch with ADR-0007 and market
  data queue/delete work in progress; no existing result artifacts modified.
- In-progress edits (files): `backtesting/artifact_rows.py`,
  `backtesting/artifacts.py`, `src/okx_quant/api/routes_backtest.py`,
  `frontend/data.js`, `frontend/view-backtest.js`,
  `sql/migrations/0012_backtest_artifact_rows.sql`, backfill/benchmark scripts,
  tests, ADR-0008, Change Manifest, and docs maps/handoffs.
- What works right now: unit/API/static tests pass for row conversion, row-first
  route behavior, summary endpoint, frontend summary-first wiring, and existing
  artifact schema preservation. Dry-run backfill found one saved file-backed run
  and would derive 11,159 rows.
- What does not work / unfinished: real DB migration/backfill `--verify` and API
  latency benchmark were not run because `DATABASE_URL` is unset and no running
  API server was provided in this sandbox.

## Decisions made (and why)

- `backtest_artifact_rows` is a derived read index, not a source of trading
  truth, because existing result JSON/CSV/JSONB contracts must remain stable.
- API endpoints use row records first and fall back to existing JSONB/file
  readers because old runs may not be backfilled yet.
- Frontend run selection uses `/api/backtest/{run_id}/summary` first because the
  page can paint metadata/metrics before chart and table payloads finish.
- Run-scoped differential validation CSV artifacts use artifact types shaped as
  `validation/{validation_id}/{artifact_name}` because they can share the
  `backtest_runs.run_id` foreign key. Strategy-validation artifacts stay
  file-backed because they are not keyed by `backtest_runs.run_id`.

## Open questions / unverified assumptions

- Need DB-backed verification after migration 0012: run
  `scripts/backfill_backtest_artifact_rows.py --all --verify` and compare row
  counts/hashes.
- Need running-API benchmark evidence after DB backfill:
  `scripts/benchmark_artifact_reads.py --run-id <run_id> --symbol <symbol>`.
- Summary endpoint still reads the result payload before trimming; current
  ADR-0002 result payloads are small, but very old legacy results with embedded
  arrays may still pay that initial read cost.

## Rules in play (preserve verbatim)

- Invariants touched: no trading invariant changed; row parity must be count/hash
  equivalent to source artifacts before claiming old runs are fast.
- Domain rules touched: none.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`,
  `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, PnL/fee/funding/sizing
  semantics, deployment gates, and existing result artifacts.

## Context to load next (the reading list)

- Source of truth: `docs/ADR/0008-fast-backtest-artifact-rows.md`,
  `docs/change_manifests/2026-06-22-fast-backtest-artifact-rows.md`,
  `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`.
- Owning files / MODULE_BRIEFS: `backtesting/artifacts.py`,
  `backtesting/artifact_rows.py`, `src/okx_quant/api/routes_backtest.py`,
  `frontend/data.js`, `frontend/view-backtest.js`, `sql/migrations/`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- `pytest tests/unit/test_artifact_rows.py tests/unit/test_backtest_artifact_schema.py tests/unit/test_backtest_visual_fallbacks.py -q` -> 27 passed; pytest cache permission warning only.
- `pytest tests/unit/test_backtesting.py::test_save_backtest_artifacts_writes_validation_to_result_json tests/unit/test_backtesting.py::test_save_backtest_artifacts_mirrors_fill_all_signals_to_idealized_fill tests/unit/test_backtesting.py::test_save_artifacts_records_indicator_warmup_sources -q` -> 3 passed.
- `ruff check ...` on touched Python files/tests -> passed.
- `node --check` for all Makefile frontend modules -> passed.
- `scripts/backfill_backtest_artifact_rows.py --all --limit-runs 1 --dry-run` -> 1 run, 11 artifacts, 11,159 derived rows.
- `scripts/docs/check_doc_metadata.py` -> passed with 13 pre-existing warnings.
- `scripts/docs/check_feature_map_links.py` -> passed.
- `scripts/docs/check_doc_impact.py --strict` -> exited 0 but reported no changed files detected.
- `scripts/validate_pipeline.py --check-config-only` -> passed.
- `scripts/smoke/api_smoke.py` -> SKIP, `API_BASE_URL` unset.
- `scripts/smoke/backtest_smoke.py` -> entrypoints PASS, full replay fixture SKIP.
- `make frontend-check` -> not run; `make` unavailable in this Windows sandbox.

## Approvals

- Human approval needed / obtained: obtained by user selecting Option C and
  requesting implementation on 2026-06-22.

## Next action (single, concrete)

- In a DB-backed shell, apply migration 0012, run
  `python scripts/backfill_backtest_artifact_rows.py --all --include-validation --verify`,
  then run `python scripts/benchmark_artifact_reads.py --run-id <run_id> --symbol <symbol>`.

## Human Learning Notes

The slow-read problem was not in strategy computation; the hot path was loading
whole saved artifacts before applying UI filters. A derived row index gives the
database enough shape to answer the UI question directly while keeping historical
artifact contracts intact.

# Session Handoff: Task 4 DB parity exchange scoping - 2026-06-18

## Implementation summary
Fixed ADR-0007 Task 4 so DB parity actually scopes postgres canonical candle reads to the run exchange. The differential validator already passed `exchange`; this session wired that through `backtesting.data_loader` into `CandleStore.get_canonical_candles(source_primary=...)` and added regression coverage at the data-loader boundary.

## Diff scope
- Files added: `tests/unit/test_data_loader.py`, `tasks/2026-06-18-task4-db-parity-exchange-scope-context-handoff.md`, `tasks/2026-06-18-task4-db-parity-exchange-scope-session-handoff.md`.
- Files changed: `backtesting/data_loader.py`, `src/okx_quant/data/candle_store.py`, `tests/unit/test_differential_validation.py`, `docs/DATA_FLOW.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Files deleted: none.

## Business-rule change?
- Yes. Existing P1 Change Manifest updated at `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`; DOC_IMPACT_MATRIX rows A5/A9 reviewed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, not touched.
- config/: N/A, not touched.
- ADR: N/A, existing ADR-0007 rule is implemented more completely.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `python -m pytest tests/unit/test_data_loader.py -q` -> red run failed before implementation; green run passed 2 tests.
- `python -m pytest tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_data_loader.py -q` -> 51 passed, 1196 warnings.
- `python scripts/docs/check_doc_impact.py --strict` with per-process `safe.directory` config -> passed, 11 changed files.
- `python scripts/docs/check_doc_metadata.py` -> passed with 12 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` -> passed.

## Docs updated
- `docs/DATA_FLOW.md`
- `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- this handoff pair

## Known limitations / risks
- DB-backed end-to-end source-provenance PASS still requires a reachable seeded DB.
- Exchange-scoped canonical reads bypass continuous aggregate views because those views do not carry `source_primary`.
- Existing unrelated dirty file remains: `docs/backtest_external_validation_report_zh.pptx`.

## Rollback plan
- Revert this session's commit or restore the files listed in Diff scope. Do not touch the unrelated PPTX.

## Context Handoff
- See `tasks/2026-06-18-task4-db-parity-exchange-scope-context-handoff.md`.

## Questions for human review
- Should a later DB migration add `source_primary` to canonical aggregate views for faster exchange-scoped parity?

## Next recommended task
- Apply the venue spec migration/seed to a reachable dev DB and run a fresh Binance source-provenance validation.

## Human Learning Notes (required)
The useful fix was one parameter boundary lower than the original validation patch. A green high-level mock test was not enough because it replaced the exact component that dropped `exchange`.

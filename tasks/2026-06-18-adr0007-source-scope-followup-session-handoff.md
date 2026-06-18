# Session Handoff: ADR-0007 Source Scope Follow-up - 2026-06-18

## Implementation summary
Added a narrow regression and evidence field so DB parity proves it compared canonical candles scoped to the run exchange. Updated ADR-0007 Task 6 docs/manifest/runbook/current-state handoff notes so the Binance DB-backed PASS milestone requires `canonical_source_primary == "binance"` and remains blocked only on reachable DB/data.

## Diff scope
- Files added: `tasks/2026-06-18-adr0007-source-scope-followup-context-handoff.md`, `tasks/2026-06-18-adr0007-source-scope-followup-session-handoff.md`.
- Files changed: `backtesting/differential_validation.py`, `backtesting/replay.py`, `tests/unit/test_data_loader.py`, `tests/unit/test_differential_validation.py`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`.
- Files deleted: none.

## Business-rule change?
- Yes, governance/validation evidence shape for ADR-0007 P1. Change Manifest: `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`; DOC_IMPACT_MATRIX strict check passed after `docs/DATA_FLOW.md` was updated.

## Source-of-truth updates
- research/strategy_synthesis.md: unchanged.
- config/: unchanged in this follow-up.
- ADR: unchanged in this follow-up; ADR-0007 remains accepted.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_data_loader.py -q` - red: 1 failed, 3 passed; expected `KeyError: 'canonical_source_primary'`.
- `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_data_loader.py -q` - green: 4 passed, 1 warning.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py tests/unit/test_data_loader.py -q` - 62 passed, 1196 warnings.
- `python scripts/docs/check_doc_impact.py --strict` with per-process `safe.directory` config - passed after the `docs/DATA_FLOW.md` update.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF normalization warnings only.

## Docs updated
- `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and the ADR-0007 Change Manifest.

## Known limitations / risks
- The real DB-backed Binance PASS was not run in this follow-up because no reachable seeded DSN is available in the current environment.
- `db_parity.canonical_source_primary` proves requested source scope, but real evidence still depends on correctly tagged `canonical_candles` rows.

## Rollback plan
- Revert this follow-up commit. That removes the evidence field/test/docs additions without touching migrations, seed data, or strategy logic.

## Context Handoff
- See `tasks/2026-06-18-adr0007-source-scope-followup-context-handoff.md`.

## Questions for human review
- Which DSN should Codex use for the first real Binance DB-backed PASS run?
- Should CI require the source-provenance gate only when a seeded TimescaleDB service is available?

## Next recommended task
- Run the ADR-0007 Binance DB-backed PASS flow from `docs/RUNBOOK.md` once a reachable DSN is available.

## Human Learning Notes (required)
The bug was not just "argument passed"; it was "does the argument constrain the data." Future provenance tests should assert both the call parameter and a result-set difference or emitted scope evidence.

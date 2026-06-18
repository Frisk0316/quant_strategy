# Session Handoff: Binance/Bybit base-unit ct_val - 2026-06-17

## Implementation summary
Implemented the ADR-0007 follow-up that lets unseeded normal Binance/Bybit USDT-M perpetuals resolve `ct_val = 1.0` as authoritative `exchange_base_unit`, while preserving DB-first overrides, leaving OKX fallback behavior unchanged, and requiring DB specs for canonical `1000...` multiplier contracts.

## Diff scope
- Files added: `tasks/2026-06-17-binance-bybit-base-unit-ct-val-context-handoff.md`, `tasks/2026-06-17-binance-bybit-base-unit-ct-val-session-handoff.md`.
- Files changed: `backtesting/replay.py`, `tests/unit/test_replay_ct_val_resolution.py`, `docs/ADR/0007-multi-venue-instrument-specs.md`, `docs/DATA_FLOW.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Files deleted: none.

## Business-rule change?
- Yes. Change Manifest at `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`; DOC_IMPACT_MATRIX checked for A5/backtesting workflow. Existing P1 manifest covers A6/A9/A2/A5/A7/A8/A4.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, not touched.
- config/: N/A, not touched.
- ADR: `docs/ADR/0007-multi-venue-instrument-specs.md` updated with the structural `exchange_base_unit` rule and `1000...` exception.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py -q` -> red run failed as expected before implementation; green run passed 9 tests.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q` -> 58 passed, 1196 warnings.
- `python scripts/docs/check_doc_impact.py --strict` with per-process `safe.directory` config -> passed, 10 changed files.
- `python scripts/docs/check_doc_metadata.py` -> passed with 12 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` -> passed.

## Docs updated
- `docs/ADR/0007-multi-venue-instrument-specs.md`
- `docs/DATA_FLOW.md`
- `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `tasks/2026-06-17-binance-bybit-base-unit-ct-val-context-handoff.md`
- `tasks/2026-06-17-binance-bybit-base-unit-ct-val-session-handoff.md`

## Known limitations / risks
- DB-backed source-provenance PASS still requires a reachable seeded dev DB.
- The structural default intentionally excludes canonical bases starting with `1000`; any other multiplier naming pattern will need explicit DB specs or a follow-up rule.
- Existing unrelated dirty file remains: `docs/backtest_external_validation_report_zh.pptx`.

## Rollback plan
- Revert this session's commit; or revert `backtesting/replay.py`, `tests/unit/test_replay_ct_val_resolution.py`, the docs listed above, and this handoff pair. Do not touch the unrelated PPTX.

## Context Handoff
- See `tasks/2026-06-17-binance-bybit-base-unit-ct-val-context-handoff.md`.

## Questions for human review
- Should the later venue-spec sync explicitly enumerate all multiplier-style Binance contracts beyond `1000...` naming?

## Next recommended task
- Apply the venue specs migration/seed to a reachable dev DB, then run the source-provenance gate against a fresh Binance run.

## Human Learning Notes (required)
The cheapest reliable model is not "seed everything" or "assume 1.0 everywhere"; it is DB-first, then a structural identity only for the plain USDT-M product family, with multiplier symbols forced back to explicit specs.

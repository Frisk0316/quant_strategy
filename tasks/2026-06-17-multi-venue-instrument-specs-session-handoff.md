# Session Handoff: ADR-0007 P1 Tasks 1-6 - 2026-06-17

## Implementation summary
Accepted ADR-0007, added the venue specs table and seed, made replay `ct_val` resolution exchange-aware, tagged replay/source validation provenance with `exchange`, added the Run Backtest exchange selector/payload, and completed Task 6 convergence/docs/manifest verification.

## Diff scope
- Files added: `sql/migrations/0011_venue_instrument_specs.sql`, `sql/seed_venue_instrument_specs.sql`, `tests/unit/test_replay_ct_val_resolution.py`, `tests/unit/test_replay_ct_val_provenance_tag.py`, `tests/unit/test_backtest_request_exchange.py`, `tests/unit/test_multi_venue_convergence.py`, `tasks/2026-06-17-multi-venue-instrument-specs-context-handoff.md`, this file.
- Files changed: `docs/ADR/0007-multi-venue-instrument-specs.md`, `docs/ADR/README.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `backtesting/replay.py`, `backtesting/differential_validation.py`, `tests/unit/test_backtesting.py`, `tests/unit/test_differential_validation.py`, `src/okx_quant/api/routes_backtest.py`, `frontend/view-config.js`, `config/instrument_specs.yaml`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/GOLDEN_CASES.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, `docs/DOMAIN_RULES.md`, `docs/DATA_FLOW.md`, `docs/INVARIANTS.md`, `docs/ai_collaboration.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/KNOWN_ISSUES.md`.
- Files deleted: none.

## Business-rule change?
- Yes. Manifest: `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`; DOC_IMPACT rows A5/A6/A7/A8/A9 are covered.

## Source-of-truth updates
- research/strategy_synthesis.md: not updated; Claude-owned and Task 6/Claude review should decide wording.
- config/: `config/instrument_specs.yaml` now states it is an OKX-only fallback; authoritative P1 venue values live in `venue_instrument_specs(exchange, symbol)`.
- ADR: ADR-0007 marked Accepted.

## Experiments
- HYPOTHESIS_LEDGER entries: H-001 cross-venue notional-sizing convergence.
- EXPERIMENT_REGISTRY entries: E-001 deterministic unit golden case.

## Tests / checks run
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_backtesting.py -q` - 50 passed.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py tests/unit/test_backtesting.py -q` - 51 passed.
- `python -m pytest tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q` - 49 passed.
- `python -m pytest tests/unit/test_backtest_request_exchange.py -q` - 2 passed.
- `node --check frontend/view-config.js` - passed.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py -q` - 56 passed, 1196 warnings.
- `python -m pytest tests/unit/test_backtest_request_exchange.py -q` - 2 passed, 1 warning.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing warnings.
- `python scripts/docs/check_doc_impact.py` - passed, no impact-matrix violations.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF warnings only.

## Docs updated
- ADR/index accepted status, change manifest approval/completion, golden case, hypothesis/experiment registry, domain rules, data flow, invariants, collaboration gate, UI/feature maps, known issues, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, context/session handoffs.

## Known limitations / risks
- `venue_instrument_specs` migration/seed were not applied to a live DB because `DATABASE_URL` and `psql` were unavailable.
- No DB-backed source-provenance PASS was produced.
- Unrelated dirty file remains: `docs/backtest_external_validation_report_zh.pptx`.

## Rollback plan
- Revert commits `171b3f4`, `1aa85e2`, `e7eb3ed`, `519385e`, `7be7f65`, and the final Task 6/handoff commit if created.

## Context Handoff
- See `tasks/2026-06-17-multi-venue-instrument-specs-context-handoff.md`.

## Questions for human review
- Should Claude/human verify seed values against official venue APIs before applying the DB seed to a shared DB?

## Next recommended task
- Apply the migration/seed to a reachable dev DB and run source-provenance validation against a fresh Binance run.

## Human Learning Notes (required)
The project already had partial exchange wiring in API code; the missing frontend payload was the real Task 5 gap. The safer test adjustment was to mark old OKX registry tests as OKX rather than weakening Binance behavior. Task 6's convergence test passed without production-code changes, which confirms the existing notional sizing path already cancels `ct_val` once per-venue specs are threaded in.

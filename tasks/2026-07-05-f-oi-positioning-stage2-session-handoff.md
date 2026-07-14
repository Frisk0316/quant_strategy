---
status: archived
type: handoff
owner: codex
created: 2026-07-05
last_reviewed: 2026-07-05
expires: none
superseded_by: null
---

# Session Handoff: F-OI-POSITIONING Stage-2 Universe OI Probe - 2026-07-05

## Implementation summary
Generalized Binance Vision historical OI ingestion from BTC/ETH to PIT-universe symbols, added a PIT-aware OI Stage-2 probe, backfilled available universe OI datasets, ran the extended probe, and recorded E-036 / H-012 state. The data prerequisite for Task B now passes with 31 OI-good symbols.

## Diff scope
- Files added: `tasks/2026-07-05-f-oi-positioning-stage2-context-handoff.md`, `tasks/2026-07-05-f-oi-positioning-stage2-session-handoff.md`.
- Files changed: `scripts/market_data/download_binance_vision_metrics.py`, `backtesting/pipeline_stage2_registry.py`, `scripts/run_pipeline_stage2_data_probe.py`, focused unit tests, `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`.
- Files deleted: none.

## Business-rule change?
- No DOMAIN_RULES semantics changed. A Change Manifest is still required by DOC_IMPACT_MATRIX A5 because `backtesting/pipeline_stage2_registry.py` changed: `docs/change_manifests/2026-07-05-oi-positioning-stage2-universe-probe.md`. This task does not change PnL, fees, funding cashflow, sizing, fills, risk, gates, strategy assumptions, or deployment policy.

## Source-of-truth updates
- `research/strategy_synthesis.md`: N/A, untouched.
- `config/`: only `config/workstreams.yaml` status text updated for Progress panel honesty.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: H-012 updated.
- EXPERIMENT_REGISTRY entries: E-036 added.

## Tests / checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_binance_vision_metrics.py tests/unit/test_pipeline_stage2_data_probe.py tests/unit/test_pipeline_stage2_registry.py -q` - 15 passed.
- `python -m pytest -p no:cacheprovider tests/unit -k "stage2 or vision or pipeline" -q` - 108 passed, 504 deselected.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate oi --output-root results/stage2_probe_20260705_oi_universe --universe-path data/universe/universe_membership.parquet` - data_availability PASS, 31/10 good symbols.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/validate_pipeline.py --check-config-only` - passed.
- `python scripts/docs/check_doc_impact.py --strict` - no changed files detected in this sandbox; limitation noted.

## Docs updated
- `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`, session/context handoffs.

## Known limitations / risks
- `SHIB-USDT-SWAP` has no `SHIBUSDT` Binance Vision metrics zips and fails the OI data gate. Do not silently substitute `1000SHIBUSDT`.
- E-036 is data availability only; `stage2_status` remains FAIL because distinctness/cost checks have not run. It is not checkpoint, WF/CPCV, or promotion evidence.
- `src/okx_quant/data/candle_store.py` and several spec/plan files were already dirty before this task; they are not part of this implementation.

## Rollback plan
- Revert only this task's code/docs/test changes and drop the new E-036 artifact directory if explicitly requested. Do not touch existing result artifacts or pre-existing unrelated changes.

## Context Handoff
- See `tasks/2026-07-05-f-oi-positioning-stage2-context-handoff.md`.

## Questions for human review
- Should H-012 Stage-3 exclude `SHIB-USDT-SWAP` automatically as an OI data gap, or should Claude revise the spec if it intended `1000SHIBUSDT` as the tradable proxy?

## Next recommended task
- Execute Task B from `tasks/2026-07-04-f-oi-positioning-stage3-codex-plan.md`: family-minting preflight first, then Stage-3 only if MINT remains valid.

## Human Learning Notes (required)
The lazy dataset-id generalization worked, but native market names matter: `SHIB` and `1000SHIB` are not interchangeable for Binance Vision metrics. Good data plumbing should make that mismatch loud instead of "helpfully" guessing.

---
status: current
type: manifest
owner: codex
created: 2026-07-07
last_reviewed: 2026-07-07
expires: none
superseded_by: null
---

# Change Manifest: OI Positioning Stage-3 Runner

## Summary
Added the research-only F-OI-POSITIONING Stage-3 backtest runner, registry wiring, adapter-required validation contract, and checkpoint artifacts for H-012 Task B.

## Business rule(s) affected
Existing rules applied, not changed: R3.1 funding cashflow, R6.3 family-cumulative n_trials, R7.1 no idealized-fill promotion evidence, and I16 ct_val provenance.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting; A9 strategy/research evidence; A11 documentation/governance.

## Files changed
- `backtesting/oi_positioning_backtest.py` - research-only vectorized OI positioning backtest.
- `scripts/run_oi_positioning_checkpoint.py` - Task B family-minting + 4-combo WF/CPCV checkpoint runner.
- `backtesting/pipeline_stage3_registry.py` - registers `F-OI-POSITIONING`.
- `backtesting/differential_validation.py` - declares `oi_positioning` portable validation as adapter-required.
- `tests/unit/` - OI loader/signal/leak/n_trials plus registry/contract coverage.
- `docs/FEATURE_MAP.md`, `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md` - ownership map and E-037/H-012 evidence.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml` - current-state handoff/progress.

## Behavior delta
- Before: H-012 had Stage-2 OI data availability only; no Stage-3 runner or checkpoint evidence.
- After: H-012 has a research-only Stage-3 runner and E-037 checkpoint artifacts; checkpoint1 fails the DSR/PSR statistical gate.
- Money/risk impact: none for live/demo/shadow; research-only backtest artifacts and docs.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, Claude-owned truth source not edited.
- config/: `config/workstreams.yaml` updated only for progress-panel state; no risk/live gates changed.
- ADR: N/A, no major policy or business-rule change.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/EXPERIMENT_REGISTRY.md` - E-037 row.
- [x] `docs/HYPOTHESIS_LEDGER.md` - H-012 family trials/status.
- [x] `docs/FEATURE_MAP.md` - F-OI Stage-3 ownership and file map.
- [x] `docs/AI_HANDOFF.md` - current cross-session state.
- [x] `docs/CURRENT_STATE.md` - short cold-start snapshot.
- [x] `config/workstreams.yaml` - progress panel sync.

## Invariants / golden cases
- Invariants checked: I13/R6.3 n_trials reconciliation via checkpoint1; I16 ct_val provenance via checkpoint1; R7.1 idealized fill false via checkpoint1.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest tests/unit/test_oi_positioning_backtest.py tests/unit/test_pipeline_stage3_registry.py tests/unit/test_pipeline_batch2_contracts.py tests/unit/test_pipeline_batch1_contracts.py tests/unit/test_pipeline_checkpoint1_check.py -q` - 23 passed.
- `python -m pytest tests/unit/test_differential_validation.py -q` - 47 passed.
- `python scripts/run_oi_positioning_checkpoint.py` - wrote E-037 artifacts.
- `python -m scripts.run_pipeline_checkpoint1_check --summary results\idea_batch_20260701_taxonomy_002\f_oi_positioning\summary.json --registry docs\EXPERIMENT_REGISTRY.md --output results\idea_batch_20260701_taxonomy_002\f_oi_positioning\checkpoint1_auto.json` - expected exit 1 because checkpoint status is FAIL.
- `python scripts/validate_pipeline.py --check-config-only` - passed.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py --strict` with temporary `safe.directory` env - passed.
- `git diff --check` - passed; only CRLF normalization warnings.

## Risks and rollback
- Risks: OI Stage-3 DB query is slow on the full 31-symbol window; the runner is research-only and should not be promoted from this checkpoint.
- Rollback: delete the new OI module, runner, tests, E-037 artifacts, and this manifest; revert registry/contract/docs/workstreams changes.

## Approval
- Human approval required: no for research-only Task B implementation; yes before any retry/adapter/demo/shadow/live follow-up.

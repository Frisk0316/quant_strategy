---
status: archived
type: handoff
owner: human
created: 2026-07-07
last_reviewed: 2026-07-07
expires: none
superseded_by: null
---

# Session Handoff: F-OI-POSITIONING Stage-3 Task B - 2026-07-07

## Implementation summary
Implemented the H-012/F-OI-POSITIONING research-only Stage-3 runner, added unit coverage for OI contract-count loading and no same-day trading, registered the family in the Stage-3 runner map, declared portable validation as adapter-required, ran the 4-combo checkpoint, and updated E-037/H-012 plus current-state handoffs.

## Diff scope
- Files added: `backtesting/oi_positioning_backtest.py`, `scripts/run_oi_positioning_checkpoint.py`, `tests/unit/test_oi_positioning_backtest.py`, `docs/change_manifests/2026-07-07-oi-positioning-stage3.md`, this handoff, and the paired context handoff.
- Files changed: `backtesting/pipeline_stage3_registry.py`, `backtesting/differential_validation.py`, `tests/unit/test_pipeline_stage3_registry.py`, `tests/unit/test_pipeline_batch2_contracts.py`, `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`.
- Files deleted: none.

## Business-rule change?
- Yes, research backtesting surface. Change Manifest at `docs/change_manifests/2026-07-07-oi-positioning-stage3.md`; DOC_IMPACT_MATRIX rows A5/A9/A11 apply.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, not edited.
- config/: only `config/workstreams.yaml` progress state updated; no risk/live gate changed.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: H-012 updated to family cumulative n_trials 4, status `testing`.
- EXPERIMENT_REGISTRY entries: E-037 added for F-OI-POSITIONING Stage-3 checkpoint.

## Tests / checks run
- `python -m pytest tests/unit/test_oi_positioning_backtest.py -q` -> 5 passed.
- `python -m pytest tests/unit/test_oi_positioning_backtest.py tests/unit/test_pipeline_stage3_registry.py tests/unit/test_pipeline_batch2_contracts.py tests/unit/test_pipeline_batch1_contracts.py tests/unit/test_pipeline_checkpoint1_check.py -q` -> 23 passed.
- `python -m pytest tests/unit/test_differential_validation.py -q` -> 47 passed.
- `python scripts/run_oi_positioning_checkpoint.py` -> completed full DB-backed E-037 Stage-3 run.
- `python -m scripts.run_pipeline_checkpoint1_check --summary results\idea_batch_20260701_taxonomy_002\f_oi_positioning\summary.json --registry docs\EXPERIMENT_REGISTRY.md --output results\idea_batch_20260701_taxonomy_002\f_oi_positioning\checkpoint1_auto.json` -> expected exit 1; checkpoint status FAIL.
- `python scripts/validate_pipeline.py --check-config-only` -> passed.
- `python -m pytest tests/unit/test_routes_progress.py::test_shipped_workstreams_yaml_is_valid -q` -> 1 passed.
- `python scripts/docs/check_doc_metadata.py` -> passed.
- `python scripts/docs/check_feature_map_links.py` -> passed.
- `python scripts/docs/check_doc_impact.py --strict` with temporary `safe.directory` env -> passed.
- `git diff --check` -> passed; only CRLF normalization warnings.

## Docs updated
- `docs/FEATURE_MAP.md`, `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`, `docs/change_manifests/2026-07-07-oi-positioning-stage3.md`.

## Known limitations / risks
- E-037 is not promotion evidence: DSR 0.7220 and PSR 0.8484 fail the 0.95 gate.
- Full Stage-3 DB query over 31 symbols is slow; this run took about 111 minutes.
- Portable validation remains adapter-required/absent.

## Rollback plan
- Delete the new OI module, runner, tests, manifest, handoff files, and new F-OI result artifacts; revert the registry/contract/docs/workstreams edits.

## Context Handoff
- See tasks/2026-07-07-oi-positioning-stage3-context-handoff.md.

## Questions for human review
- Should H-012 remain `testing`, be refuted, or receive any ex-ante retry rationale?
- Does Claude accept the provisional `MINT` qualitative novelty argument beyond the low correlation score?
- Any concern from leak-lag spot check or the adapter-required portable block reason?

## Next recommended task
- Claude/user checkpoint review of E-037; do not start retry/adapter/demo/shadow/live work before that review.

## Human Learning Notes (required)
Do not treat a quiet full-window DB Stage-3 run as hung after two minutes; the 31-symbol query can be genuinely long. Also, `python -m scripts.run_pipeline_checkpoint1_check` is the reliable invocation on this repo, while direct script execution can miss the repo root on `sys.path`.

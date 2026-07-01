---
status: current
type: manifest
owner: codex
created: 2026-07-01
last_reviewed: 2026-07-01
expires: none
superseded_by: null
---

# Change Manifest: Pipeline Orchestrator

## Summary
Added the advisory pipeline orchestrator that drives `idea_batch.json` through
Stage2 probes, optional Stage3 runners, checkpoint1 automation, and a shortlist
without writing durable ledgers or touching trading-core behavior.

## Business rule(s) affected
R6.3 and R7.4. This adds enforcement around existing trial-count / promotion-gate
honesty; it does not change the rules.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting and A9 validation/gates.

## Files changed
- `backtesting/pipeline_orchestrator.py` - new append-only state driver.
- `backtesting/pipeline_stage2_registry.py` - family-keyed Stage2 probe registry.
- `backtesting/pipeline_stage3_registry.py` - guarded legacy Stage3 runner registry.
- `scripts/run_pipeline_orchestrator.py` - CLI entrypoint.
- `scripts/run_pipeline_stage2_data_probe.py` - thin wrapper over the registry.
- `tests/unit/test_pipeline_orchestrator.py` - orchestrator regression coverage.
- `tests/unit/test_pipeline_stage2_registry.py` - Stage2 registry coverage.
- `tests/unit/test_pipeline_stage3_registry.py` - Stage3 guard coverage.
- `docs/INVARIANTS.md` - new I29.
- `docs/superpowers/pipeline/stage3-implement-backtest.md` - Stage3 registry handoff note.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml` - current-state bookkeeping.
- `tasks/2026-07-01-pipeline-orchestration-driver-context-handoff.md`,
  `tasks/2026-07-01-pipeline-orchestration-driver-session-handoff.md` - session handoff.

## Behavior delta
- Before: `idea_batch.json` sidecars required manual Stage2/Stage3/checkpoint sequencing.
- After: `scripts/run_pipeline_orchestrator.py` can create or resume
  `orchestrator_state.json`, write Stage2/checkpoint sidecars where implemented,
  and render `shortlist.md`; missing implementation moves to explicit awaiting
  statuses.
- Money/risk impact: none. This is an advisory research-pipeline driver and does
  not change PnL, fees, funding, sizing, fills, risk, or deployment gates.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: `config/workstreams.yaml` updated for the Progress panel only; no
  runtime or gate config changed.
- ADR: N/A - no result schema, promotion gate, or business rule changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/INVARIANTS.md` - I29 added.
- [x] `docs/FEATURE_MAP.md` - reviewed; no edit because the approved spec's
  permitted file list did not include it.
- [x] `docs/DATA_FLOW.md` - reviewed; no edit because this writes advisory
  pipeline sidecars, not backtest result schema or API data paths.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no edit because no golden trading case changed.
- [x] ADR-0002/ADR-0005 - reviewed; no edit because no backtest result schema or
  replay validation gate changed.
- [x] `docs/ai_collaboration.md` - reviewed; no edit because deployment and
  human checkpoint policy stay unchanged.
- [x] `docs/EXPERIMENT_REGISTRY.md` - reviewed/read-only; the orchestrator does not write it.

## Invariants / golden cases
- Invariants checked: I29 added; I13/I26/I27/I28 remain in force.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest tests/unit/test_pipeline_orchestrator.py tests/unit/test_pipeline_stage2_registry.py tests/unit/test_pipeline_stage3_registry.py tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py tests/unit/test_pipeline_stage2_data_probe.py -q -p no:cacheprovider` - 45 passed.
- `python -m pytest tests/unit/test_pipeline_stage2_data_probe.py tests/unit/test_pipeline_stage2_registry.py -q -p no:cacheprovider` - 5 passed after restoring the script path bootstrap.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate all` - PASS; existing taxonomy_002 Stage2 artifact hashes unchanged.
- `python scripts/docs/check_doc_metadata.py` - passed with 0 warnings.
- `python scripts/docs/check_feature_map_links.py` - passed, 168 concrete paths checked.
- `python scripts/docs/check_doc_impact.py --strict` with process-local `safe.directory` - passed, 30 changed files and no violations.
- `python scripts/validate_pipeline.py --check-config-only` - passed.
- `make docs-check`, `make docs-impact`, and `make check-config` - not available in this Windows shell (`make` command not found); direct target commands above were run.

## Risks and rollback
- Risks: future Stage3 runners must be registered explicitly per family; until then
  candidates stop at `awaiting_stage3_implementation`.
- Rollback: remove the new orchestrator/registry/CLI/test files, restore
  `scripts/run_pipeline_stage2_data_probe.py`, remove I29, and revert this manifest
  plus current-state/handoff updates.

## Approval
- Human approval required: no for this advisory driver implementation; yes for any
  future change that makes it a deployment or promotion gate.

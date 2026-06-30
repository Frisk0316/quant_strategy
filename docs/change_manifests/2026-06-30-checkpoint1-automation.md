---
status: current
type: manifest
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Change Manifest: Checkpoint 1 Automation

## Summary
Added an advisory Stage 3 checkpoint checker that reads a `summary.json` plus
`docs/EXPERIMENT_REGISTRY.md`, writes `checkpoint1_auto.json`, and blocks
checkpoint advancement when machine-checkable trial, DSR/PSR, idealized-fill,
portable-validation, or ct_val evidence is inconsistent.

## Business rule(s) affected
R6.3 and R7.4. This adds enforcement around existing trial-count and DSR/PSR
rules; it does not change the rules themselves.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting and A9 validation/gates.

## Files changed
- `backtesting/pipeline_checkpoint1.py` - new checkpoint result evaluator.
- `scripts/run_pipeline_checkpoint1_check.py` - new CLI to write the sidecar artifact.
- `tests/unit/test_pipeline_checkpoint1_check.py` - focused regression coverage.
- `docs/INVARIANTS.md` - new I26.
- `docs/superpowers/pipeline/stage3-implement-backtest.md` - Stage 3 handoff hook.
- `docs/change_manifests/2026-06-30-checkpoint1-automation.md` - this manifest.

## Behavior delta
- Before: checkpoint 1 review depended on humans manually reading scattered
  `summary.json` and ledger fields.
- After: future Stage 3 summaries can emit `checkpoint1_auto.json` with
  machine-checkable `PASS`, `FAIL`, or `NEEDS_HUMAN` status plus required human
  review items.
- Money/risk impact: none. This is an advisory research-pipeline checker and
  does not change PnL, fees, funding, sizing, fills, risk, or deployment gates.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - no runtime or gate config changed.
- ADR: N/A - no result schema, promotion gate, or business rule changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/INVARIANTS.md` - I26 added.
- [x] `docs/EXPERIMENT_REGISTRY.md` - reviewed; no edit because the checker reads
  the existing registry instead of changing ledger semantics.
- [x] `docs/FEATURE_MAP.md` - reviewed; no edit because this task's approved scope
  is the Stage 3 template/checker contract, not feature ownership navigation.
- [x] `docs/DATA_FLOW.md` - reviewed; no edit because `checkpoint1_auto.json` is a
  checkpoint sidecar, not a durable backtest result schema change.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no edit because no golden trading case changed.
- [x] ADR-0002/ADR-0005 - reviewed; no edit because no backtest result schema or
  replay validation gate changed.
- [x] `docs/ai_collaboration.md` - reviewed; no edit because human checkpoint and
  deployment gate policy stay unchanged.

## Invariants / golden cases
- Invariants checked: I26 added; I13/I21/I23/I25 remain in force.
- Golden cases affected: N/A.

## Tests / checks run
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests\unit\test_pipeline_checkpoint1_check.py -q` - 5 passed.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing metadata warnings.
- `check_doc_impact.py` via the same Python interpreter plus process-local `safe.directory` git config - passed: 25 changed files, no impact-matrix violations.

## Risks and rollback
- Risks: registry markdown parsing can miss malformed rows; the checker fails or
  asks for human review instead of inferring missing evidence.
- Rollback: remove the two new checker files, the new unit test, I26, the Stage 3
  template paragraph, and this manifest.

## Approval
- Human approval required: no for this advisory checker implementation; yes for
  any future change that makes it a deployment or promotion gate.

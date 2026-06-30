---
status: current
type: manifest
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Change Manifest: Family-Minting Checker

## Summary
Added an advisory family-minting distinctness checker for automatic idea ingestion.
It reads a candidate signal, reference family signals, and the experiment
registry, then recommends ASSIGN, MINT, NEEDS_HUMAN, or SKIP_RECOMMENDED.

## Business rule(s) affected
R6.3 and R7.4. This adds enforcement around existing hidden-trial and DSR/PSR
deflation rules; it does not change the rules themselves.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting and A9 validation/gates.

## Files changed
- `backtesting/pipeline_family_minting.py` - new pure decision helper.
- `scripts/run_pipeline_family_minting_check.py` - new CLI to write the sidecar artifact.
- `tests/unit/test_pipeline_family_minting.py` - focused regression coverage.
- `backtesting/pipeline_checkpoint1.py` - exposes the existing experiment-registry family parser for reuse.
- `docs/INVARIANTS.md` - new I27.
- `docs/change_manifests/2026-06-30-family-minting-checker.md` - this manifest.

## Behavior delta
- Before: automatic idea ingestion had a draft family-minting rule but no
  machine-checkable signal-correlation backstop.
- After: a caller can feed candidate/reference signals into a checker that
  prevents high-correlation relabeling from minting a fresh family budget.
- Money/risk impact: none. This is an advisory research-pipeline checker and
  does not change PnL, fees, funding, sizing, fills, risk, or deployment gates.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - no runtime or gate config changed.
- ADR: N/A - no result schema, promotion gate, or business rule changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/INVARIANTS.md` - I27 added.
- [x] `docs/EXPERIMENT_REGISTRY.md` - reviewed; no edit because the checker reads
  existing family/trial rows instead of changing ledger values.
- [x] `docs/FEATURE_MAP.md` - reviewed; no edit because this is a research-pipeline
  sidecar checker, not a new user-facing feature surface.
- [x] `docs/DATA_FLOW.md` - reviewed; no edit because `family_minting.json` is a
  pre-backtest advisory sidecar, not a backtest result schema change.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no edit because no golden trading case changed.
- [x] ADR-0002/ADR-0005 - reviewed; no edit because no backtest result schema or
  replay validation gate changed.
- [x] `docs/ai_collaboration.md` - reviewed; no edit because deployment gates and
  human publish authority stay unchanged.

## Invariants / golden cases
- Invariants checked: I27 added; I13/I23/I26 remain in force.
- Golden cases affected: N/A.

## Tests / checks run
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests\unit\test_pipeline_family_minting.py tests\unit\test_pipeline_checkpoint1_check.py -q` - 11 passed.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing metadata warnings.
- `check_doc_impact.py` via the same Python interpreter plus process-local `safe.directory` git config - passed: 34 changed files, no impact-matrix violations.
- `make docs-check` / `make docs-impact` - not available in this Windows shell (`make` command not found); direct Python scripts were run instead.

## Risks and rollback
- Risks: the checker only compares caller-supplied reference signals; missing or
  low-quality references can still leave a decision for human review.
- Rollback: remove the new checker, CLI, unit test, I27 row, parser export, and
  this manifest.

## Approval
- Human approval required: no for this advisory checker implementation; yes for
  any future change that turns it into a deployment or promotion gate.

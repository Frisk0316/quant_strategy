---
status: current
type: manifest
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Change Manifest: Idea Generator Front End

## Summary
Added the B-half deterministic idea-generator front end. It enumerates feasible
taxonomy gaps, ranks and caps them to 15 candidates, writes an `idea_batch.json`
sidecar plus a ledger draft, and runs drafted candidates through the existing
family-minting advisory checker.

## Business rule(s) affected
R6.3 and R7.4 reviewed. This preserves existing trial-count and family-budget
rules by reading ledger family status before drafting; it does not change DSR,
PSR, PnL, fee, funding, sizing, fill, risk, or promotion rules.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting.

## Files changed
- `backtesting/pipeline_idea_generator.py` - new taxonomy enumerator/ranker/registrar.
- `scripts/run_pipeline_idea_generator.py` - new CLI to write idea-batch sidecars.
- `tests/unit/test_pipeline_idea_generator.py` - focused regression coverage.
- `docs/superpowers/pipeline/stage1-hypothesis.md` - autonomous-mode and data-firewall appendix.
- `docs/change_manifests/2026-06-30-idea-generator-frontend.md` - this manifest.

## Behavior delta
- Before: taxonomy frontier families had to be manually copied into Stage 1.
- After: a caller can generate a capped advisory batch under
  `results/<batch_id>/idea_batch.json` and `hypothesis_ledger_draft.md`.
- Money/risk impact: none. This is pre-backtest research triage and cannot
  promote, deploy, or trade.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - no runtime or gate config changed.
- ADR: N/A - no business rule, result schema, or promotion gate changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/superpowers/pipeline/stage1-hypothesis.md` - added autonomous-mode/data-firewall boundary.
- [x] `docs/FEATURE_MAP.md` - reviewed; no edit because this is a research-pipeline sidecar, not an app feature surface.
- [x] `docs/DATA_FLOW.md` - reviewed; no edit because `idea_batch.json` is a pre-backtest advisory sidecar.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no edit because no golden trading case changed.
- [x] `docs/INVARIANTS.md` - reviewed; I27 already covers family-minting budget inheritance.
- [x] ADR-0002/ADR-0005 - reviewed; no edit because no backtest result schema or replay validation gate changed.

## Invariants / golden cases
- Invariants checked: I13/I26/I27 remain in force.
- Golden cases affected: N/A.

## Tests / checks run
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests\unit\test_pipeline_idea_generator.py -q` - 5 passed.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m ruff check <new idea-generator/lab files>` - passed.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing metadata warnings.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\docs\check_feature_map_links.py` - passed: 154 concrete paths checked.
- `check_doc_impact.py --strict` via the same Python interpreter plus process-local `safe.directory` git config - passed: 43 changed files, no impact-matrix violations.
- `make docs-check` - not available in this Windows shell (`make` command not found); direct Python scripts were run instead.

## Risks and rollback
- Risks: markdown taxonomy parsing is intentionally small and can miss malformed
  tables; bad rows should be caught during human Stage 1 review.
- Rollback: remove the generator, CLI, unit test, Stage 1 appendix, and this manifest.

## Approval
- Human approval required: no for advisory sidecar generation; yes before any
  generated draft enters the durable hypothesis ledger or a trading workflow.

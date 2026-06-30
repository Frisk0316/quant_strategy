---
status: current
type: manifest
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Change Manifest: Family-Minting K-Budget Wiring

## Summary
Family-minting now reads the `EXPERIMENT_REGISTRY.md` Family K-budget table and
reports real `k_used`, `k_limit`, and `at_k_limit` fields instead of conflating
retry count with family-cumulative `n_trials`.

## Business rule(s) affected
R6.3 and R7.4. This tightens enforcement of existing hidden-trial and
multiple-testing discipline; it does not change the rule thresholds.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting and A9 validation/gates.

## Files changed
- `backtesting/pipeline_checkpoint1.py` - parses Family K-budget rows into the shared family registry.
- `backtesting/pipeline_family_minting.py` - emits true K-budget fields and removes the stale `inherited_K` proxy.
- `tests/unit/test_pipeline_family_minting.py` - covers K-budget parsing and at-limit reporting.
- `docs/FEATURE_MAP.md` - maps the strategy research pipeline automation owning files.
- `docs/KNOWN_ISSUES.md` - marks the K-vs-n_trials wiring gap resolved.
- `docs/change_manifests/2026-06-30-family-minting-k-budget.md` - this manifest.

## Behavior delta
- Before: `family_minting.json` used `inherited_K = inherited_n_trials`, so a
  48-combination family could look like K=48 even though K is retry attempts.
- After: `family_minting.json` reports `k_used`, `k_limit`, and `at_k_limit`
  from the Family K-budget table. `n_trials` remains separate.
- Money/risk impact: none. This is an advisory pre-backtest research-pipeline
  checker and does not change PnL, fees, funding, sizing, fills, risk, or
  deployment gates.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - no runtime or gate config changed.
- ADR: N/A - no result schema, promotion gate, or business rule changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/KNOWN_ISSUES.md` - K-vs-n_trials issue marked resolved.
- [x] `docs/INVARIANTS.md` - reviewed; I27 already requires true K-budget parsing.
- [x] `docs/EXPERIMENT_REGISTRY.md` - reviewed; no value changes, table is read-only source.
- [x] `docs/FEATURE_MAP.md` - reviewed; no ownership change.
- [x] `docs/DATA_FLOW.md` - reviewed; no data/artifact flow change beyond advisory sidecar fields.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no golden trading case changed.
- [x] ADR-0002/ADR-0005 - reviewed; no backtest result schema or replay gate changed.

## Invariants / golden cases
- Invariants checked: I27.
- Golden cases affected: N/A.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py -q` - red first: 3 failed because `k_used` was missing; green after fix: 8 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py tests\unit\test_pipeline_checkpoint1_check.py -q` - 13 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_idea_generator.py -q` - 6 passed after direct-script regression fix.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed, 166 concrete paths checked.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing metadata warnings.
- `check_doc_impact.py --strict` with process-local `safe.directory=C:/quant_strategy` - passed.

## Risks and rollback
- Risks: `at_k_limit` depends on the human-maintained Family K-budget table; if
  that table is stale, the checker will faithfully report stale K status.
- Rollback: revert this manifest plus the changes to
  `backtesting/pipeline_checkpoint1.py`, `backtesting/pipeline_family_minting.py`,
  `tests/unit/test_pipeline_family_minting.py`, and `docs/KNOWN_ISSUES.md`.

## Approval
- Human approval required: no for this advisory checker wiring; yes for any
  future change that makes it a deployment or promotion gate.

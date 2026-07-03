---
status: current
type: manifest
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Change Manifest: XS Trials And Idea Data Probe

## Summary
Fixed two advisory research-pipeline accounting gaps: XS momentum family
registry parsing now inherits the family-cumulative 24-trial budget, and B-half
idea enumeration uses a supplied Stage-2 data-availability probe before falling
back to mechanism-taxonomy text.

## Business rule(s) affected
R6.3 and R7.4. This tightens enforcement of existing hidden-trial and
multiple-testing discipline; it does not change thresholds or promotion gates.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting and A9 validation/gates.

## Files changed
- `backtesting/pipeline_checkpoint1.py` - recognizes explicit family-cumulative
  `n_trials` notes/overrides when building the shared family registry and
  checkpoint expected-trials value.
- `backtesting/pipeline_idea_generator.py` - uses `pipeline_feasibility.py`
  Stage-2 data-availability results when supplied, with taxonomy text as a
  fallback only.
- `tests/unit/test_pipeline_checkpoint1_check.py` - covers XS 24-trial
  inheritance and avoids double-counting cumulative override rows.
- `tests/unit/test_pipeline_family_minting.py` - covers XS family-minting
  inheritance of 24 trials plus K=2/2 at-limit state.
- `tests/unit/test_pipeline_idea_generator.py` - covers probe precedence over
  taxonomy text and fallback behavior.
- `docs/KNOWN_ISSUES.md` - records the two gaps as resolved.
- `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `config/workstreams.yaml` - current-state/ownership updates.
- `docs/change_manifests/2026-06-30-xs-trials-and-idea-probe.md` - this
  manifest.

## Behavior delta
- Before: XS momentum rows E-003/E-004/E-005 each recorded 8 trials, so the
  shared family registry inherited 8 instead of the documented 24 family trials.
  B-half idea enumeration ignored `data_availability_probe` and relied only on
  taxonomy text.
- After: family registry/checkpoint expected trials honor explicit
  family-cumulative row text such as "has at least 24 trials" or
  `family-cumulative n_trials=48`. B-half uses Stage-2 `data_availability`
  PASS/FAIL when supplied and falls back to taxonomy text only when the probe has
  no answer.
- Money/risk impact: none. This is advisory pre-backtest research-pipeline
  accounting and filtering; it does not change PnL, fees, funding, sizing,
  fills, risk, strategies, config gates, or deployment behavior.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: `config/workstreams.yaml` current-state text only; no runtime or gate
  config changed.
- ADR: N/A - no result schema, DB schema, or promotion gate changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/KNOWN_ISSUES.md` - resolved gaps recorded.
- [x] `docs/INVARIANTS.md` - reviewed; I26/I27 already cover family
  cumulative n_trials and family-minting inheritance.
- [x] `docs/EXPERIMENT_REGISTRY.md` - reviewed; no value changes, read-only
  source.
- [x] `docs/FEATURE_MAP.md` - behavior note updated.
- [x] `docs/DATA_FLOW.md` - reviewed; no artifact/data-flow change beyond
  advisory sidecar filtering.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no golden trading case changed.
- [x] ADR-0002/ADR-0005 - reviewed; no backtest result schema or replay gate
  changed.

## Invariants / golden cases
- Invariants checked: I26, I27.
- Golden cases affected: N/A.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py -q` - red first: 5 failed; green after fix: 24 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py tests/unit/test_pipeline_feasibility.py tests/unit/test_pipeline_stage2_check.py -q` - 40 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m ruff check backtesting/pipeline_checkpoint1.py backtesting/pipeline_idea_generator.py tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing metadata warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed, 166 concrete paths checked.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_human_overview.py` - passed, 2 overviews OK.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\validate_pipeline.py --check-config-only` - passed.
- `check_doc_impact.py --strict` with process-local `safe.directory=C:/quant_strategy` - passed, 17 changed files.
- `make docs-check` - not run; `make` is unavailable in this Windows shell.

## Risks and rollback
- Risks: explicit family-cumulative row notes remain human-maintained; a future
  row that omits both a cumulative value and a clear cumulative note can still be
  interpreted by the historical max-row fallback.
- Rollback: revert this manifest plus the changes to
  `backtesting/pipeline_checkpoint1.py`, `backtesting/pipeline_idea_generator.py`,
  the three targeted test files, and the current-state docs listed above.

## Approval
- Human approval required: no for this advisory checker/filter wiring; yes for
  any future change that makes it a deployment or promotion gate.

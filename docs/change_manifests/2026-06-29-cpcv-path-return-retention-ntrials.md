---
status: current
type: manifest
owner: codex
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Change Manifest: CPCV Path-Return Retention and n_trials Provenance

## Summary

Future CPCV outputs retain the raw path returns, or combined returns when path
assembly is unavailable, so DSR can be recomputed from saved artifacts. CPCV and
XS research scan outputs now label whether `n_trials` was caller-declared or only
a grid-size floor.

## Business rule(s) affected

R6.3, R7.4.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow, A9 validation / gates, A11 experiments / research runs.

## Files changed

- `backtesting/cpcv.py` - emit retained return arrays, return lengths, annualizing
  periods, and n_trials provenance fields.
- `backtesting/xs_momentum_backtest.py` - accept `researched_n_trials` and tag
  scan rows/attrs as `caller_declared` or `grid_size_floor`.
- `scripts/recheck_dsr.py` - recompute DSR/PSR from retained CPCV returns and
  print old-to-new DSR.
- `scripts/run_pipeline_batch1_checkpoint.py` - copy retained CPCV fields into
  checkpoint summary `cpcv` blocks with caller-declared family trial provenance.
- `tests/unit/test_cpcv.py`, `tests/unit/test_xs_momentum_backtest.py`,
  `tests/unit/test_pipeline_batch1_contracts.py` - regression coverage.
- `docs/INVARIANTS.md`, `docs/DOC_IMPACT_MATRIX.md`, `docs/KNOWN_ISSUES.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` -
  record the auditability/provenance contract.

## Behavior delta

- Before: CPCV artifacts stored summary DSR/PSR and path Sharpes but not the raw
  return series required to independently recompute DSR. Missing researched
  trial counts could be read as if they were complete.
- After: future CPCV outputs store retained returns plus `n_trials_provenance`
  and `n_trials_is_floor`; recheck tooling recomputes DSR when those fields are
  present. Existing artifacts are not rewritten.
- Money/risk impact: none. No PnL, fee, funding, sizing, risk, fill, strategy,
  config, live/demo/shadow gate, or existing result payload changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; task explicitly forbids research-file
  edits and does not change strategy assumptions.
- config/: N/A; config files and deployment gates are forbidden for this task.
- ADR: N/A; this implements the existing R6.3/R7.4 honesty/auditability policy
  without changing the promotion-gate rule.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/INVARIANTS.md` - added I25 for retained CPCV return auditability.
- [x] `docs/DOC_IMPACT_MATRIX.md` - clarified A5/A9 review rows for CPCV result
  schema and validation provenance.
- [x] `docs/KNOWN_ISSUES.md` - narrowed the remaining gap to historical artifacts
  that predate retained returns.
- [x] `docs/EXPERIMENT_REGISTRY.md` - added required CPCV return/provenance
  fields for future evidence rows.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - updated current handoff.
- [x] `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, ADR-0002/0005/0009 - reviewed;
  no edit needed because owning files and gate policy did not change.

## Invariants / golden cases

- Invariants checked: I13, I21, I23, I25.
- Golden cases affected: N/A.

## Tests / checks run

- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_cpcv.py tests/unit/test_xs_momentum_backtest.py tests/unit/test_pipeline_batch1_contracts.py -q` - red first with missing retained fields/provenance, then passed after implementation.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_cpcv.py tests/unit/test_dsr.py tests/unit/test_xs_momentum_backtest.py tests/unit/test_pipeline_batch1_contracts.py -q` - passed, 16 tests.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\recheck_dsr.py` - passed; scanned 51 DSR rows, 8 CPCV rows, 43 single-run diagnostic rows.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` - exited 0 but reported no changed files because sandbox git lacks `safe.directory`.
- `scripts\docs\check_doc_impact.py` with process-local `safe.directory` env - exited 0 with advisory A5 warning because the executable rule still requires `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, or `docs/GOLDEN_CASES.md`; this task's permitted file list did not allow those edits.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed; Git reported line-ending warnings only.

## Risks and rollback

- Risks: CPCV JSON artifacts become larger because raw return arrays are retained.
  If artifact size becomes measurable pain, add a columnar/compressed artifact
  format in a separate schema task.
- Rollback: revert the changed code/tests/docs and delete this manifest. No
  generated result artifacts require migration or cleanup.

## Approval

- Human approval required: yes before treating any strategy as promotion, demo,
  shadow, or live evidence. Not requested or obtained in this session.

---
status: current
type: handoff
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Session Handoff: DSR All-Strategy Recheck - 2026-06-24

## Implementation summary
Added a repeatable DSR audit script and used it to classify every current
DSR-bearing JSON artifact. The audit found 7 CPCV rows and 38 replay-level
single-run diagnostic rows. Daily Winner CPCV was recomputed from saved returns;
the two pre-fix XS momentum DSR=1.0 artifacts were marked untrusted; the
portfolio-vol XS artifact remains below gate and passes `DSR <= PSR(0)`, but
cannot be independently recomputed from saved summary fields alone.

## Diff scope
- Files added: `scripts/recheck_dsr.py`,
  `tasks/2026-06-24-dsr-allstrategy-recheck-context-handoff.md`,
  `tasks/2026-06-24-dsr-allstrategy-recheck-session-handoff.md`.
- Files changed: `docs/results_validation_manifest.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/KNOWN_ISSUES.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Files deleted: none.

## Business-rule change?
- No. This is an audit/annotation task for an already-fixed DSR business rule.
  No Change Manifest was created. `scripts/docs/check_doc_impact.py` passed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, not touched.
- config/: N/A, not touched.
- ADR: N/A, not changed.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: E-003 marked invalid/superseded; E-004 notes now
  call the stored DSR untrusted; E-005 notes the fixed DSR passes invariant but
  lacks saved raw path returns for independent recomputation.

## Tests / checks run
- `python scripts/recheck_dsr.py` - passed; 45 DSR-bearing JSON rows, 7 CPCV rows,
  38 single-run diagnostic rows.
- `python -m pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py -q` - 3 passed;
  pytest emitted a `.pytest_cache` permission warning.
- `python scripts/docs/check_doc_impact.py` with one-shot `safe.directory` env -
  passed; 8 changed files, no impact-matrix violations.
- `make docs-check PYTHON=...` - failed to start because `make` is not installed.
- `python scripts/docs/check_doc_metadata.py` - passed with 14 pre-existing
  metadata warnings outside this task.
- `python scripts/docs/check_feature_map_links.py` - passed.

## Docs updated
- `docs/results_validation_manifest.md` - added DSR recheck table.
- `docs/EXPERIMENT_REGISTRY.md` - removed the stale supported reading of E-003
  and flagged affected DSR rows.
- `docs/KNOWN_ISSUES.md` - recorded the raw-path-return retention gap.
- `docs/AI_HANDOFF.md` and `docs/CURRENT_STATE.md` - updated current state.

## Known limitations / risks
- XS momentum DSR could not be independently recomputed from the saved artifacts
  because raw path returns were not stored.
- `results/strategy_validation/` is still absent after the approved cleanup; this
  audit only covers current on-disk JSON artifacts.
- No DB-backed validation rerun was attempted.

## Rollback plan
- Revert `scripts/recheck_dsr.py`, this handoff pair, and the docs edits listed
  above. No result payload rollback is needed because no result artifacts were
  modified.

## Context Handoff
- See `tasks/2026-06-24-dsr-allstrategy-recheck-context-handoff.md`.

## Questions for human review
- Should future CPCV artifact schemas be extended to save raw path returns or a
  compact recompute bundle for DSR audits?

## Next recommended task
- Add raw CPCV path-return retention to future validation artifacts, or schedule a
  DB-backed recompute if independent verification of the portfolio-vol XS DSR is
  required.

## Human Learning Notes (required)
DSR auditability depends on saved return distributions, not just reported Sharpe
and DSR. Keeping raw path returns is cheaper than re-running a multi-symbol DB
validation job later.

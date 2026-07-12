---
status: archived
type: handoff
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Session Handoff: XS momentum lookahead fix - 2026-06-24

## Implementation summary
Fixed the XS momentum research runner's daily-to-intraday lookahead leak by
shifting daily targets one full day before intraday expansion. Added a regression
that fails under the old one-bar-only lag and passes under the corrected timing.
Generated a new leak-free review artifact; it does not support promotion because
PSR is below 0.95.

## Diff scope
- Files added: `results/xs_momentum_validation_20260623/SUPERSEDED.md`,
  `results/xs_momentum_validation_20260624_leakfix/*`,
  `tasks/2026-06-24-xs-momentum-lookahead-fix-context-handoff.md`,
  `tasks/2026-06-24-xs-momentum-lookahead-fix-session-handoff.md`.
- Files changed: `backtesting/xs_momentum_backtest.py`,
  `tests/unit/test_xs_momentum_backtest.py`,
  `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Files deleted: none.

## Business-rule change?
- Yes. Change Manifest:
  `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`; DOC_IMPACT_MATRIX
  rows A5 and A11 checked.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, Claude-owned and not permitted.
- config/: unchanged.
- ADR: ADR-0009 reviewed; unchanged.

## Experiments
- HYPOTHESIS_LEDGER entries: not edited; H-002/E-003 are stale and should be
  superseded in a follow-up.
- EXPERIMENT_REGISTRY entries: not edited; `results/xs_momentum_validation_20260624_leakfix/`
  should become the superseding E-003 follow-up entry if Claude/user wants the
  experiment ledger updated.

## Tests / checks run
- `python -m pytest tests/unit/test_xs_momentum_backtest.py::test_daily_close_target_is_not_traded_on_same_day -v` - failed before the fix, passed after the fix.
- `python -m pytest tests/unit/test_xs_momentum_backtest.py tests/unit/test_xs_momentum.py -v` - 12 passed; pytest cache permission warning only.
- `python scripts/docs/check_doc_impact.py` with process-local `safe.directory`
  git config - passed: 10 changed files, no impact-matrix violations.
- Local Postgres leak-free rerun - wrote `results/xs_momentum_validation_20260624_leakfix/`; WF combined OOS Sharpe 0.8825, CPCV overall OOS Sharpe 0.5577, DSR 1.0, PSR 0.7961, `promotion_gate_passed:false`.

## Docs updated
- `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/DATA_FLOW.md`
- paired context/session handoff files under `tasks/`

## Known limitations / risks
- The rerun was reconstructed from the prior inline handoff, not from a durable
  checked-in validation script.
- `docs/HYPOTHESIS_LEDGER.md` / `docs/EXPERIMENT_REGISTRY.md` still need a
  follow-up superseding entry because the leaked E-003 row currently says
  "supported".
- Vol-target under-leverage remains intentionally untouched.

## Rollback plan
- Revert this session's code/test/docs changes.
- Remove `results/xs_momentum_validation_20260624_leakfix/` and
  `results/xs_momentum_validation_20260623/SUPERSEDED.md` if the rerun/fix is
  rejected.

## Context Handoff
- See `tasks/2026-06-24-xs-momentum-lookahead-fix-context-handoff.md`.

## Questions for human review
- Should Claude update H-002/E-003 to mark the leaked run invalid and add the
  leak-free rerun as the superseding experiment?
- Should a durable XS validation rerun script be added, or is inline artifact
  generation acceptable for this research-only phase?
- Should the vol-target quantity decision be resolved before any next rerun?

## Next recommended task
- Claude re-review of the leak-free artifact, then decide whether to retire,
  redesign sizing, or rerun after the vol-target decision.

## Human Learning Notes (required)
The daily bin label was the trap: resample labeled a day's final close at
midnight, so an ordinary one-bar intraday shift still traded on the future close.
Tests for daily-to-intraday strategies need to assert the actual intraday
position schedule, not just final metrics.

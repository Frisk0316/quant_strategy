## Summary

<!-- What does this PR do? One paragraph. -->

## Related Issue

Closes #

## AI Attribution

| Role | Who |
|---|---|
| Planning | <!-- Claude / Human --> |
| Implementation | <!-- Codex / Claude / Human --> |
| Review | <!-- Claude / Human --> |
| Human-confirmed | <!-- yes / no --> |

## Scope — Files Changed

<!-- List every file this PR modifies. -->

-

## Out of Scope — Explicitly Not Changed

<!-- List modules or files that were intentionally left untouched, even if adjacent to the change. -->

-

## Risk

<!-- What existing behavior could this break? If none, say "none identified." -->

## Acceptance Criteria

<!-- Copy from the issue and check each item. Any unmet criteria must be listed explicitly. -->

- [ ] All issue acceptance criteria are satisfied
- [ ] Any unmet criteria listed here:

## Test Plan

- [ ] `pytest tests/unit/ -v` — passed
- [ ] `pytest tests/integration/ -v` — passed (or skipped because: )
- [ ] Replay smoke: `python scripts/run_replay_backtest.py --strategy <name> --start ... --end ...`
- [ ] Frontend smoke: server started, dashboard loaded, no console errors
- [ ] Regression test added or updated for this bug/feature
- [ ] `ruff check src/ tests/` — no new errors

## Doc Sync / Harness

<!-- See docs/DOC_IMPACT_MATRIX.md. A business-rule change is any PnL, fee, funding,
sizing, risk, fill, data-provenance, or gate change. -->

- [ ] Is this a business-rule change? If yes, a Change Manifest is included
      (`docs/change_manifests/<date>-<slug>.md`) and `make docs-impact` passes.
- [ ] `docs/DOC_IMPACT_MATRIX.md` rows for the changed areas were checked and the
      listed docs updated (or explicitly confirmed unchanged in the manifest).
- [ ] Major rule/policy change has an ADR (`docs/ADR/`).
- [ ] Experiments updated `docs/HYPOTHESIS_LEDGER.md` and
      `docs/EXPERIMENT_REGISTRY.md`; new bug classes updated `docs/FAILURE_MODES.md`.
- [ ] `docs/INVARIANTS.md` / `docs/GOLDEN_CASES.md` still hold (or were updated).

## Branch / Version Management

- [ ] Branch name follows `docs/BRANCH_VERSIONING.md`
- [ ] PR is short-lived and scoped to one issue/task
- [ ] Squash merge is appropriate for this PR
- [ ] Branch should be deleted after merge
- [ ] Tag/milestone impact noted, or not applicable

## Screenshots / Logs

<!-- Paste relevant output, equity curve screenshots, or console logs. -->

## Handoff Notes

<!-- What does the next AI session need to know? Update docs/AI_HANDOFF.md before merging. -->

- [ ] `docs/AI_HANDOFF.md` and `docs/CURRENT_STATE.md` updated
- [ ] Context Handoff written (`tasks/CONTEXT_HANDOFF_TEMPLATE.md`) including
      **Human Learning Notes**

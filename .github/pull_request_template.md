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

## Test Plan

- [ ] `pytest tests/unit/ -v` — passed
- [ ] `pytest tests/integration/ -v` — passed (or skipped with reason: )
- [ ] Replay smoke: `python scripts/run_replay_backtest.py --strategy <name> --start ... --end ...`
- [ ] Frontend smoke: server started, dashboard loaded, no console errors
- [ ] Regression test added or updated for this bug/feature
- [ ] `ruff check src/ tests/` — no new errors

## Screenshots / Logs

<!-- Paste relevant output, equity curve screenshots, or console logs. -->

## Handoff Notes

<!-- What does the next AI session need to know? Update docs/AI_HANDOFF.md before merging. -->

- [ ] `docs/AI_HANDOFF.md` updated (Recent Changes, Known Bugs, Next Steps)

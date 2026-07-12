# Session Handoff Template

Copy this at the end of every session. It records what changed and hands off
cleanly. Pair it with a Context Handoff (`tasks/CONTEXT_HANDOFF_TEMPLATE.md`) for
the reading list, and keep `docs/CURRENT_STATE.md` and `docs/AI_HANDOFF.md`
current.

Every session must end with a handoff. **Human Learning Notes are required.**

---

```markdown
---
status: current
type: handoff
owner: <human|claude|codex>
created: <YYYY-MM-DD>
last_reviewed: <YYYY-MM-DD>
expires: none
superseded_by: null
---

# Session Handoff: <title> — <YYYY-MM-DD>

## Implementation summary
<what was done, one paragraph>

## Diff scope
- Files added:
- Files changed:
- Files deleted:

## Business-rule change?
- <yes/no>. If yes: Change Manifest at docs/change_manifests/<...>.md, and
  DOC_IMPACT_MATRIX checked (rows: <ids>).

## Source-of-truth updates
- research/strategy_synthesis.md: <updated / N/A>
- config/: <updated / N/A>
- ADR: <added/updated / N/A>

## Experiments
- HYPOTHESIS_LEDGER entries: <ids / none>
- EXPERIMENT_REGISTRY entries: <ids / none>

## Tests / checks run
- <command> — <result>

## Docs updated
- <docs from the AGENTS.md docs matrix>

## Known limitations / risks
-

## Rollback plan
-

## Context Handoff
- See tasks/CONTEXT_HANDOFF_TEMPLATE.md filled at: <link/path>

## Questions for human review
-

## Next recommended task
-

## Human Learning Notes (required)
<Surprises, gotchas, mental-model updates, anything that should change how we
work next time. Write "none" only if there genuinely is nothing.>
```

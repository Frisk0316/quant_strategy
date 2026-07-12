# Bugfix Template

Copy this for any bug fix. Even a one-line fix must locate the owning layer, add
a regression test, and check whether the bug is a *new class* worth recording in
`docs/FAILURE_MODES.md`.

---

```markdown
---
status: current
type: task
owner: <human|claude|codex>
created: <YYYY-MM-DD>
last_reviewed: <YYYY-MM-DD>
expires: none
superseded_by: null
---

# Bugfix: <title> — <YYYY-MM-DD>

## Symptom
<observed wrong behavior, with a reproduction>

## Diagnosis
- Layer (strategy / signal / risk / portfolio / execution / backtest / API /
  frontend / data / docs):
- Root cause (file:line):
- Is this a known FAILURE_MODES entry? <Fxx / new>

## Locate-before-edit
- Owning files (FEATURE_MAP / MODULE_BRIEFS):
- Permitted files:
- Forbidden files (do not refactor adjacent code):
- Source of truth for correct behavior (config / research / ADR / test):

## Business-rule impact
- Touches DOMAIN_RULES (PnL / fee / funding / sizing / fills / gates)? <ids/no>
- If yes: Change Manifest required + DOC_IMPACT_MATRIX checked.
- Invariant violated and now restored: <INVARIANTS id>

## Fix
<smallest change that restores documented behavior>

## Regression test (required)
- Test added/updated: <path>
- Command: <pytest ...> — <result>

## New failure mode?
- If this is a new class of silent error, add a row to docs/FAILURE_MODES.md
  and strengthen the guarding invariant/test. <done / N/A>

## Rollback plan
- 

## Human Learning Notes
<What made this bug possible; how to prevent the class next time. Required.>
```

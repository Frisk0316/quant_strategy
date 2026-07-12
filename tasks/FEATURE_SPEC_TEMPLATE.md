# Feature Spec Template

Copy this for any non-trivial new feature or design-heavy change. A feature spec
must do **locate-before-edit** and **design-space expansion** before
implementation begins.

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

# Feature Spec: <title> — <YYYY-MM-DD>

## Problem statement (one sentence)
<what must be true after this that is not true now>

## Locate-before-edit
- User-facing behavior / surface changed:
- Owning files (FEATURE_MAP / MODULE_BRIEFS):
- Source of truth for intent (config / research / ADR):
- Tests / Makefile targets that verify it:
- Permitted files:
- Forbidden files:
- Rollback path:

## Design-space expansion (see docs/DESIGN_SPACE.md)
- Constraints (hard / soft):
- Option A — <name>: mechanism / assumes / wrong-if / blast radius
- Option B — <name>: ...
- Option C — smallest change: ...
- Trade-off axis:
- Decision + why:
- Would change if: → HYPOTHESIS_LEDGER H-NNN (if testable)

## Business-rule impact
- Touches DOMAIN_RULES: <ids / none>
- If yes: Change Manifest required + DOC_IMPACT_MATRIX rows <ids>
- ADR required: <yes/no — which>
- Invariants affected: <INVARIANTS ids>
- Failure modes to guard: <FAILURE_MODES ids>
- Golden cases to add/update: <GOLDEN_CASES ids>

## Test plan
- <exact commands>

## Acceptance criteria (binary)
- [ ]
- [ ]

## Docs to update (AGENTS.md docs matrix)
- 

## Risks
- 
```

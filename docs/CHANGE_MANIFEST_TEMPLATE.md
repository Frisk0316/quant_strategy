---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Change Manifest Template

A **Change Manifest** is a short, structured record created for every
business-rule change (any area marked **Manifest? = Yes** in
`docs/DOC_IMPACT_MATRIX.md`). It makes the blast radius of a change auditable
without reading the diff.

## How to use

1. Copy the block below into `docs/change_manifests/<YYYY-MM-DD>-<slug>.md`
   (create the directory if it does not exist).
2. Give the copy its own lifecycle metadata (`status: current`, `type: manifest`).
3. Fill every field. "None" / "N/A" is a valid answer but must be explicit.
4. Reference the manifest from the PR description and the session handoff.

`make docs-impact --strict` treats a business-rule change with no manifest in
the changeset as a violation.

---

```markdown
---
status: current
type: manifest
owner: <human|claude|codex>
created: <YYYY-MM-DD>
last_reviewed: <YYYY-MM-DD>
expires: none
superseded_by: null
---

# Change Manifest: <short title>

## Summary
<one or two sentences: what changed and why>

## Business rule(s) affected
<reference DOMAIN_RULES ids, e.g. R1.1, R3.1 — or "none, mechanical only">

## Trigger area(s) (DOC_IMPACT_MATRIX)
<e.g. A2 portfolio/execution, A5 backtesting>

## Files changed
- <path> — <what/why>

## Behavior delta
- Before: <observable behavior>
- After: <observable behavior>
- Money/risk impact: <PnL / fee / funding / sizing effect, or none>

## Source-of-truth updates
- research/strategy_synthesis.md: <updated / N/A — why>
- config/: <updated / N/A — why>
- ADR: <ADR-xxxx added/updated / N/A — why>

## Docs updated (from DOC_IMPACT_MATRIX row)
- [ ] <doc> — <updated / confirmed unchanged because ...>

## Invariants / golden cases
- Invariants checked: <INVARIANTS ids, or N/A>
- Golden cases affected: <GOLDEN_CASES ids, or N/A>

## Tests / checks run
- <command> — <result>

## Risks and rollback
- Risks: <regression scenarios>
- Rollback: <how to revert; which commit/files>

## Approval
- Human approval required: <yes/no> — <obtained? when?>
```

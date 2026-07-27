---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Process Lessons (append-only)

Format and rules: `docs/ai/MAINTENANCE.md`. Newest at the bottom. When this
file exceeds 150 lines, follow the compaction trigger.

## 2026-07-03 Session-start reading is the biggest silent cost

Trigger: measured ~2,300–3,500 lines of "required" session-start reading.
Wrong: reading every listed doc up front, or silently skipping some.
Right: read only CURRENT_STATE + your routing-table row; state a reason for
anything extra.
Rule: reading a doc outside your routing row requires a one-line reason.

## 2026-07-03 Claims without pasted output caused false "done" reports

Trigger: recurring pattern of "tests should pass now" with no run.
Wrong: reporting completion from intention instead of evidence.
Right: paste the command output tail, or report "not verified".
Rule: no pasted output = not verified = not done.

## 2026-07-18 Uncommitted multi-delivery trees break ex-ante provability

Trigger: E-057 registration order was unprovable because the spec, task,
registry row, and results all sat uncommitted in one shared working tree
alongside a sibling delivery.
Wrong: running an experiment while its ex-ante registration exists only as
uncommitted working-tree text.
Right: commit the registration (spec + registry row) before the run, and
commit each delivery separately.
Rule: ex-ante means committed-before-run; one delivery = one commit.

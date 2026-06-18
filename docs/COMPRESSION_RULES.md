---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Compression Rules

How to compress context (when summarizing, handing off, or approaching the
window limit) **without losing anything that changes correctness**. The guiding
principle: lossy on narrative, lossless on rules, decisions, and state.

## Preserve verbatim (never compress away)

- **Invariants and rules** in play for the current work ([[INVARIANTS]],
  [[DOMAIN_RULES]] ids) — keep the id and the exact constraint.
- **Open decisions** and their options ([[DESIGN_SPACE]]), with the chosen
  option and the "would change if" condition.
- **Current state**: goal, branch, do-not-touch list, in-progress edits, active
  risks ([[CURRENT_STATE]]).
- **Unverified assumptions / open hypotheses** ([[HYPOTHESIS_LEDGER]]).
- **Approvals**: any human approval (or its absence) for risky changes.
- **Exact file paths, commands, and test results** that prove what was checked.

## Safe to compress (lossy)

- Narrative of how a conclusion was reached, once the conclusion is recorded.
- Resolved dead-ends (keep one line: "tried X, rejected because Y").
- Tool-output dumps — replace with the conclusion + the command to reproduce.
- Restated file contents — replace with the path to re-read.

## Compression procedure

1. Before compressing, write/refresh [[CURRENT_STATE]] and, for a session
   boundary, a Context Handoff (`tasks/CONTEXT_HANDOFF_TEMPLATE.md`).
2. Replace narrative with pointers: "see `<file>` for X", not the full X.
3. For each preserved item, keep enough to act without re-reading chat — but
   always cite the file so detail can be recovered.
4. Never let a summary become the *only* record of a rule or decision; the file
   is the record, the summary is the index.

## Anti-rules

- Do not compress a rule into "be careful with PnL" — keep "R1.1: SWAP PnL
  scales by ct_val".
- Do not drop the do-not-touch list to save space.
- Do not treat the post-compression summary as a new source of truth; re-read
  the cited files for any money/risk edit ([[CONTEXT_BUDGET]]).

Related: [[CONTEXT_BUDGET]] · [[CURRENT_STATE]] · `tasks/CONTEXT_HANDOFF_TEMPLATE.md`.

---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Context Budget

Guidance for spending limited context window on the **highest-authority, most
task-relevant** material first, so that compression or a cold start never drops
something that changes correctness.

## Priority tiers

Load in this order; stop expanding once the task is unambiguous.

1. **Must-load (always):** current user instruction + approved scope;
   `docs/CURRENT_STATE.md`; the do-not-touch list (`AI_CONTEXT.md`,
   `docs/AI_HANDOFF.md`); the rules for the area you touch
   (`docs/DOMAIN_RULES.md`, relevant [[INVARIANTS]]).
2. **Task-load (per task):** the owning files (`docs/FEATURE_MAP.md` →
   `docs/MODULE_BRIEFS/`), the relevant Context Pack
   (`docs/CONTEXT_PACKS/`), the enforcing tests, and the source-of-truth doc for
   intent (config / research / ADR).
3. **On-demand:** full architecture, runbook, history, archive. Pull only the
   section you need.
4. **Avoid loading:** chat history as authority, archived/deprecated docs,
   unrelated modules, large generated artifacts.

## Budgeting rules

- **Authority beats volume.** One line of config or an accepted ADR outranks
  paragraphs of plan or chat. Spend budget there first.
- **Summaries point, they don't replace.** A summary must cite the file to read
  for detail; never let a summary become the only record of a rule.
- **Re-read before money/risk edits.** For any business-rule change, re-open the
  exact rule and invariant rather than trusting a remembered summary.
- **One task's worth at a time.** Don't preload the whole repo; load the Context
  Pack for the current task.
- **Refresh `CURRENT_STATE.md` over re-deriving.** Keeping current state in a
  small file is cheaper than reconstructing it from a long transcript.

## Compression triggers

When the window is filling, follow [[COMPRESSION_RULES]]: preserve invariants,
open decisions, and current state verbatim; compress narrative and resolved
detail; and write a Context Handoff (`tasks/CONTEXT_HANDOFF_TEMPLATE.md`) before
detail is lost.

Related: [[CONTEXT_INDEX]] · [[COMPRESSION_RULES]] · [[CURRENT_STATE]].

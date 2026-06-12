---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Critique Protocol

How to pressure-test a plan or diff *before* it is accepted. Critique is a
required step for any design-heavy or business-rule change, not an optional
nicety. The goal is to find the wrong-but-plausible outcome before it ships.

## Self-critique (author, before handing off)

Run this on your own plan or diff:

1. **Invert it.** Ask the [[MENTAL_MODELS]] "invert" question: how would this
   silently produce a wrong result? Check each relevant [[FAILURE_MODES]] row.
2. **Name assumptions.** List what the change assumes. Mark each as
   verified-from-source or unverified. Unverified ones become
   [[HYPOTHESIS_LEDGER]] entries.
3. **Steelman the rejected option.** State the strongest form of the alternative
   you discarded in [[DESIGN_SPACE]]. If it's actually stronger, reconsider.
4. **Check invariants.** Which [[INVARIANTS]] does this touch? Are they still
   guarded by a test?
5. **Blast radius and rollback.** Confirm both are stated.

## Structured critique (reviewer)

Use [[REVIEW_QUESTIONS]] as the checklist. A critique should produce, for each
finding:

- **Severity:** blocker / major / minor / nit.
- **Claim:** what is wrong or unverified.
- **Evidence:** file:line, test result, or rule id — not opinion.
- **Suggested resolution:** smallest fix, or the question that must be answered.

## Rules of engagement

- Critique the artifact, not the author. "This omits ct_val (R1.1)", not "you
  forgot".
- A finding without evidence is a question, not a blocker — phrase it as one.
- "I can't find the flaw" is not "there is no flaw." For money/risk changes,
  default to requiring the invariant test rather than trusting inspection.
- The author must respond to every blocker/major finding explicitly (fix,
  refute with evidence, or accept as known gap in `docs/KNOWN_ISSUES.md`).

## When critique is mandatory

- Any business-rule change (Manifest? = Yes in [[DOC_IMPACT_MATRIX]]).
- Any ADR.
- Any promotion or readiness claim — these get the harshest critique (R7.2).

Related: [[REVIEW_QUESTIONS]] · [[QUESTION_BANK]] · [[FAILURE_MODES]] ·
[[DESIGN_SPACE]].

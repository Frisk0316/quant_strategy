---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Harness Diagnosis — Top 3 Token/Focus/Error Leaks

Measured 2026-07-03 on this repo. This file explains WHY the rules in
`CLAUDE.md` and `docs/ai/MODEL_DISPATCH.md` exist. Re-measure before editing
those rules (commands given per item).

## 1. Session-start reading tax (worst token leak)

**Measured:** the pre-2026-07-03 CLAUDE.md told every session to read
AI_CONTEXT.md (118 lines), AI_HANDOFF.md (172), AI_WORKFLOW.md (287),
ai_collaboration.md (282), CONTEXT_INDEX.md (62), CURRENT_STATE.md (89),
DOC_LIFECYCLE.md (135), plus FEATURE_MAP.md (561) / UI_MAP.md (212) /
DATA_FLOW.md (347) "when needed" — ≈2,300–3,500 lines (~30–50k tokens)
before any work. A small model either burns a quarter of its context on
this, or silently skips files and then violates rules it never read. Both
happen; the second is worse because it looks like compliance.

**Fix (mechanical, any model can follow):** CLAUDE.md now contains a task
routing table. At session start read ONLY `docs/CURRENT_STATE.md` + the
"Next actions" section of `docs/AI_HANDOFF.md`, then only the files in your
task-type row. Reading a file not in your row requires a one-line stated
reason. Re-measure with:
`wc -l CLAUDE.md AGENTS.md docs/CURRENT_STATE.md` (budget: CLAUDE.md ≤150,
always-loaded total ≤500).

## 2. Session-end ceremony fan-out (worst focus leak)

**Measured:** session end previously required touching up to 7 surfaces:
AI_HANDOFF.md, CURRENT_STATE.md, config/workstreams.yaml, a Context Handoff
(55-line template), a separate Session Handoff (60-line template),
CHANGELOG_AI.md, KNOWN_ISSUES.md. This lands exactly when context is
scarcest. Small models respond by duplicating text across files, letting
files drift out of sync, or skipping the step entirely.

**Fix:** CLAUDE.md "Session end" is now a single ordered 5-step pass with
hard length caps (handoff ≤80 lines, AI_HANDOFF delta ≤15 lines,
CURRENT_STATE ≤90 lines total) and merges the two handoff templates into
ONE file per session covering both templates' required fields. If context
is nearly exhausted, do steps 1–3 only and write "steps 4–5 skipped: low
context" into the handoff — a short honest handoff beats a long broken one.

## 3. Self-verification and unbounded retry (worst error source)

**Observed pattern:** with no dispatch rules, the main conversation greps,
reads whole 400–560-line docs, edits, then declares its own work correct
("tests should pass now") without running anything, and retries the same
failing approach indefinitely. In this repo the expensive failure class is
exactly the kind self-review misses: `ct_val` PnL omissions, funding-sign
flips, lookahead leakage — errors that produce plausible-looking output.

**Fix (three mechanical rules, enforced by docs/ai/MODEL_DISPATCH.md):**
1. Claims require pasted command output. "Tests pass" without the pytest
   tail is treated as "tests not run".
2. Verification is done by a fresh-context subagent (`verifier` agent),
   never by the session that wrote the change.
3. Retry budget: max 2 attempts per approach, then either escalate the
   model (with the full failure trail) or change the approach — see
   docs/ai/JUDGMENT_RUBRICS.md §4. Never a third identical retry.

## Honorable mention (fold into #1)

CLAUDE.md and AGENTS.md previously duplicated hard rules and review lists
(two copies drift apart; a model reading one copy misses edits to the
other). Rule now: shared rules live ONLY in AGENTS.md; CLAUDE.md carries
only Claude-specific deltas and routing.

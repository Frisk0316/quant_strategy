---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Letter to Future Sessions

Written 2026-07-03 by a Claude Fable 5 session, in the user's words "the
only Fable session this environment will get". You, the reader, are
probably a smaller model. That is fine. This system was designed assuming
it. Read this once before starting a major new workstream; don't reload it
every session.

## Three things the user didn't ask me, but matter most

**1. In this repo, the scarce resource is uncontaminated verification, not
model intelligence.** The expensive failures here produce plausible-looking
numbers: a missing `ct_val` makes PnL wrong by a believable factor; a
funding-sign flip looks like alpha; lookahead makes any strategy look
great. A smarter model self-reviewing misses these almost as often as you
will, because the writer's context is contaminated by its own intent.
Fresh-context verification and golden cases (`docs/GOLDEN_CASES.md`) are
structural advantages that don't degrade with model size. Never trade them
away for speed.

**2. Trust the code over the docs for anything involving money.** This
repo's docs are unusually good, which creates a specific trap: they
describe target architecture and known gaps alongside current behavior,
and a reader who wants to finish quickly will treat "target" as "true".
Before asserting any behavior of PnL, fees, funding, sizing, or fills,
confirm it in code with `file:line` (dispatch scout — it's cheap). The
phrase to keep in mind: "the doc says X — is that current or target?"

**3. Ceremony only grows; deleting is a maintenance act, not vandalism.**
Every rule in this harness was added for a reason, and each one costs every
future session tokens forever. The 2026-07-03 measurement found ~3,000
lines of session-start reading had accreted, each line individually
justified. When you notice a rule nobody has exercised in months, or two
files saying the same thing, propose deletion to the user instead of
complying harder. The user values honesty about process weight — they
built this system to be pruned.

## How this system will most likely degrade, and the countermeasure

1. **Re-accretion:** someone adds "also always read X" back into CLAUDE.md
   one reasonable line at a time. → The context-budget caps in CLAUDE.md
   are hard rules; adding an always-load requires user approval. Cite the
   cap, don't negotiate with it.
2. **Path rot:** files move/rename and the routing table silently points
   at nothing; sessions then ignore the whole table. → Monthly staleness
   check in `docs/ai/MAINTENANCE.md` (scout verifies every referenced
   path). A broken path is a factual bug: fix without asking.
3. **Template cargo-culting:** dispatches copy the template but leave
   `<...>` slots vague ("ACCEPTANCE: works correctly"). The form survives,
   the function dies. → Rule already in TASK_TEMPLATES.md: can't fill a
   slot = not ready to dispatch. Verifiers should reject non-binary
   acceptance criteria.
4. **Model-name rot:** MODEL_DISPATCH.md §0 values go stale and a session
   "corrects" them from training memory, which is worse than stale. → §0
   says: the Agent tool description in YOUR session is the only source of
   truth; update the file from it, never from memory.
5. **LESSONS.md as landfill:** every minor hiccup gets an entry; signal
   drowns. → Only lessons that change future behavior get entries; the
   150-line compaction trigger is real, use it.

## What I am least confident about (honestly)

- **The numeric thresholds** (300 lines before dispatching, 5 search
  rounds, 2-retry budget, haiku→sonnet→opus ladder). These are judgment
  calls, not measurements. If they chafe, tune them via a LESSONS.md entry
  and user approval — the mechanism matters more than the numbers.
- **Diagnosis ranking:** leak #1 (session-start tax) is measured; #3
  (self-verification/retry) is inferred from typical small-model behavior,
  not from this repo's actual transcripts. It could be over- or
  under-weighted.
- **Effort pins** on scout (haiku/low) and verifier (sonnet/medium) are
  untested in live use. If scout misses obvious things, raise to medium
  before switching models.
- **Merging the two session-end handoffs into one file** changed the
  user's established process. (Resolved: user approved the merge and a
  ≤90-line cap on 2026-07-03. Applies to Claude sessions; Codex still
  follows AGENTS.md's two-file wording.)
- **The quota question** ("do Fable→Opus rerouted requests consume
  Fable-tier quota?") is UNCONFIRMED in official docs as of 2026-07-03;
  third-party claims exist but were not treated as fact. If it matters,
  test on the usage dashboard.

What ports across model sizes is not cleverness — it's decomposition,
binary acceptance criteria, and verification by someone who didn't write
the change. You have all three in the files next to this one. Use them.

# Context Handoff Template

Copy this when a session ends, hits a context limit, or hands work to another
session. It lets the next session resume **without** relying on chat history.
Save completed handoffs alongside the session record or in
`docs/CHANGELOG_AI.md`; keep current state in `docs/CURRENT_STATE.md`.

This is the Context Resilience companion to `tasks/SESSION_HANDOFF_TEMPLATE.md`.
See `docs/COMPRESSION_RULES.md` for what must be preserved verbatim.

---

```markdown
# Context Handoff: <task / area> — <YYYY-MM-DD>

## Goal (one sentence)
<what we are trying to achieve>

## Current state
- Branch:
- Last known good commit / state:
- In-progress edits (files):
- What works right now:
- What does not work / unfinished:

## Decisions made (and why)
- <decision> — because <reason>; would change if <condition>.

## Open questions / unverified assumptions
- <hypothesis> → HYPOTHESIS_LEDGER H-NNN (if logged)

## Rules in play (preserve verbatim)
- Invariants touched: <INVARIANTS ids + exact constraint>
- Domain rules touched: <DOMAIN_RULES ids>
- Do-not-touch: <explicit list>

## Context to load next (the reading list)
- Source of truth: <config / research / ADR>
- Owning files / MODULE_BRIEFS:
- Context Pack: docs/CONTEXT_PACKS/<pack>.md

## Checks run
- <command> — <result>

## Approvals
- Human approval needed / obtained: <state explicitly>

## Next action (single, concrete)
- <the very next step the resuming session should take>

## Human Learning Notes
<What a human should take away from this session: surprises, gotchas,
mental-model updates, or anything that should change how we work. Required —
write "none" only if there genuinely is nothing.>
```

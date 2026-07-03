---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Maintenance Protocol for the AI Governance Files

Who may change what, where lessons go, and when to compact. "You" = any
Claude session, any model size.

## Edit freely (no user approval needed)

- `docs/ai/LESSONS.md` — append-only (format below).
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`
  (milestone status only), `tasks/*handoff*.md` — normal session-end upkeep
  within the length caps in `CLAUDE.md`.
- `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md` — append entries.
- Auto-memory files under the memory directory.

## Ask the user BEFORE changing

- `CLAUDE.md` structure, the routing table, or the context-budget caps.
- `AGENTS.md` (shared contract with Codex).
- `docs/ai/MODEL_DISPATCH.md` thresholds/ladder and
  `docs/ai/JUDGMENT_RUBRICS.md` rules (fixing a factually wrong path or a
  stale model name is allowed without asking; record it in LESSONS.md).
- `.claude/agents/*.md` model/effort pins.
- Anything under `config/` beyond workstream milestone status; all gates.
- Deleting or rewriting `docs/ai/HARNESS_DIAGNOSIS.md` or
  `docs/ai/LETTER_TO_FUTURE_SESSIONS.md`.

## Where lessons go

- **Process lesson** (how to work: dispatch, verification, scope, retries)
  → append to `docs/ai/LESSONS.md`:

  ```text
  ## YYYY-MM-DD <one-line title>
  Trigger: <what happened>
  Wrong: <what the session did or almost did>
  Right: <what it should do>
  Rule: <one enforceable line>
  ```

- **Code bug class** → `docs/FAILURE_MODES.md` plus, where possible, an
  invariant (`docs/INVARIANTS.md`) and a test. Not LESSONS.md.
- **User preference / correction about collaboration** → auto-memory
  (type: feedback), plus LESSONS.md if it changes how sessions work.

## Compaction triggers (check when appending)

- `docs/ai/LESSONS.md` >150 lines → propose promoting recurring lessons
  into `docs/ai/JUDGMENT_RUBRICS.md` (needs user approval), archive the
  promoted entries to `docs/ai/LESSONS_ARCHIVE.md`.
- `CLAUDE.md` >150 lines or always-loaded total >500 → move content out to
  a routed file, immediately.
- `docs/CURRENT_STATE.md` >90 lines or a handoff >90 lines → trim before
  saving; move detail into the task file it belongs to.
- Any `docs/ai/*.md` >250 lines → split or compress; these files are read
  under time pressure by small models.

## Staleness check (cheap, monthly or when something 404s)

Dispatch `scout`: "Verify every file path referenced in CLAUDE.md and
docs/ai/*.md exists; list missing ones." Fix broken paths without asking;
they are factual errors. If a referenced model name no longer appears in
the session's Agent tool description, update `docs/ai/MODEL_DISPATCH.md`
§0 with the current values and note the change in LESSONS.md.

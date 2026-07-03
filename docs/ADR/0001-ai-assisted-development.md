---
status: accepted
type: adr
owner: human
created: 2026-05-11
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# ADR-0001: AI-Assisted Development Workflow

## Status

Accepted — 2026-05-11

## Context

This repository is developed by a human working with two AI systems (Claude and Codex) across multiple sessions. Each AI session starts cold with no memory of previous sessions. Without a structured workflow, this leads to:

- Codex making wide changes beyond the task scope
- Claude reviewing after the fact instead of planning before
- No record of why decisions were made
- Inconsistent engineering decisions across sessions
- Bugs re-introduced because prior fixes weren't documented

## Decision

Adopt the three-role workflow defined in `docs/AI_WORKFLOW.md` and `docs/ai_collaboration.md`:

1. **Claude plans first** — diagnosis, files to change, acceptance criteria, risks. No implementation until the plan is approved.
2. **Codex implements** — only the permitted files, only the stated scope, with tests and a handoff update.
3. **Human merges** — after Claude reviews the diff and the human confirms acceptance criteria are met.

Every task must have a GitHub issue (using the `ai_task` template) with an explicit permitted-files list and out-of-scope list before Codex begins.

`docs/AI_HANDOFF.md` is the cross-session long-term memory. It must be updated before every session ends.

## Enforcement

This ADR is enforced by:

- `.github/ISSUE_TEMPLATE/ai_task.md` — permitted/forbidden file lists per task
- `.github/pull_request_template.md` — AI attribution, scope, acceptance criteria
- `docs/AI_HANDOFF.md` — cross-session memory; updated every session
- CI gates once `.github/workflows/ci.yml` is added (PR4)

## Consequences

**Benefits:**

- Reduced scope creep: Codex has a hard boundary per task
- Reproducible decisions: every change traceable to an issue, a plan, and a reviewer
- Safer core logic: strategies/risk/portfolio require explicit approval to touch
- Faster onboarding of new AI sessions: read HANDOFF → ready to work

**Costs:**

- More overhead per task (issue creation, plan step)
- Slower for trivial one-line fixes
- Requires discipline to update HANDOFF at session end

**Mitigations:**

- For trivial fixes (typos, config values), human can skip issue creation if scope is obvious
- HANDOFF template has a checklist to minimize forgetting

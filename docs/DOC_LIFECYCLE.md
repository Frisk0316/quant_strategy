---
status: current
type: governance
owner: human
created: 2026-05-11
last_reviewed: 2026-05-11
expires: none
superseded_by: null
---

# Documentation Lifecycle Policy

This policy defines how Markdown documentation is created, trusted, reviewed, archived, and deprecated in this repository.

## Purpose

The repository depends on Markdown files for architecture decisions, AI handoff state, implementation plans, reviews, and strategy context. Without lifecycle rules, AI agents may follow stale plans or treat target designs as implemented behavior.

This document governs all `.md` files in the repository unless a narrower policy explicitly overrides it.

## Required Metadata

Every Markdown document should start with lifecycle metadata:

```yaml
---
status: current
type: architecture
owner: human
created: 2026-05-11
last_reviewed: 2026-05-11
expires: none
superseded_by: null
---
```

### Fields

| Field | Meaning |
|---|---|
| `status` | Lifecycle state. Determines whether the document may be used as implementation authority. |
| `type` | Document category, such as `architecture`, `adr`, `plan`, `review`, `runbook`, `handoff`, or `governance`. |
| `owner` | Current responsible owner: `human`, `claude`, `codex`, or a named role. |
| `created` | Creation date in `YYYY-MM-DD` format. |
| `last_reviewed` | Last date the document was checked for accuracy. |
| `expires` | Review or expiry date, or `none` for durable docs. |
| `superseded_by` | Replacement document path or ADR id, or `null`. |

## Status Values

Only these statuses may be used as current source of truth:

- `current`
- `accepted`

These statuses are not implementation authority:

- `draft`
- `proposed`
- `deprecated`
- `archived`

If a document lacks lifecycle metadata, treat it as `draft` until reviewed and classified.

## Authority Rules

When documents conflict, use this order:

1. User instruction in the current task.
2. `research/strategy_synthesis.md` for strategy assumptions.
3. `docs/DOC_LIFECYCLE.md`, `docs/AI_WORKFLOW.md`, and `docs/ai_collaboration.md` for AI workflow and document governance.
4. Accepted ADRs in `docs/ADR/`.
5. Current architecture and runbook docs.
6. `docs/AI_HANDOFF.md` for current state, active risks, and next steps.
7. Draft, proposed, deprecated, archived, plan, and review docs only as historical context.

`config/` remains authoritative for runtime configuration. Documentation must not override config values.

## ADR Rules

ADRs are decision records and should not be deleted.

To replace an ADR:

1. Create or update the superseding ADR.
2. Change the old ADR status.
3. Add a visible status note:

```md
## Status

Superseded by ADR-0009
```

4. Set `superseded_by` in lifecycle metadata when metadata exists.

Proposed ADRs describe target design only. Codex must not implement from a proposed ADR unless the current task explicitly approves that work and lists the permitted files.

## Plans and Reviews

Plans and reviews are temporary coordination artifacts.

| Path | Lifecycle rule |
|---|---|
| `docs/plans/` | After PR merge, consolidate into durable docs or move to `docs/archive/`. |
| `docs/reviews/` | Keep while review findings are active; archive after the findings are resolved or no longer actionable. |
| `docs/archive/` | Historical context only. Not implementation authority. |
| `docs/deprecated/` | Replaced or obsolete docs that should remain discoverable. Not implementation authority. |

Plans and reviews outside `docs/` should be moved into the proper docs directory or deleted once they are no longer active.

## AI Handoff Rules

`docs/AI_HANDOFF.md` must describe only current state:

- Current goal.
- Current branch.
- Last known good commit.
- Active risks and known bugs.
- Current next steps.
- Do-not-touch constraints.

Completed historical notes should be moved to durable docs, archived, or removed. `AI_HANDOFF.md` must not become a permanent changelog.

## Cleanup Checklist

Before merging documentation-heavy PRs:

- [ ] New `.md` files include lifecycle metadata.
- [ ] Status is one of the approved values.
- [ ] Only `current` or `accepted` docs are presented as implementation authority.
- [ ] Completed plans and reviews are archived or consolidated.
- [ ] Superseded ADRs are retained and marked as superseded.
- [ ] `docs/AI_HANDOFF.md` contains current state only.
- [ ] Any document with implementation implications names the authoritative source or test gap.

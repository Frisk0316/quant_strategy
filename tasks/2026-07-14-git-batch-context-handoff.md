---
status: current
type: handoff
owner: codex
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Context Handoff: Git batch commit and push — 2026-07-14

## Goal (one sentence)

Preserve the mixed working tree by separating, committing, and pushing each
workstream without rewriting history or staging unrelated secrets/config.

## Current state

- Branch: `feature/taxonomy003-stage3`, stacked on
  `feature/f-vol-regime-opt-stage2`, which is stacked on
  `codex/pipeline-batch1-stage3`.
- Last known good state: follow-up `d046978`, F-VOL `d66f08a`, Taxonomy_003
  `821f761`; all three remote branches are pushed, with the final shared-state
  and handoff commit added on the Taxonomy_003 branch.
- In-progress edits: none after the final commit/push.
- What works: the original mixed tree is preserved in scoped commits; ignored
  research scripts and new result artifacts explicitly named by handoffs are
  tracked; `.env` is not staged.
- Unfinished: PR creation, review, and merge remain human actions.

## Decisions made (and why)

- Use stacked branches — the shared handoff/state files were authored on top of
  the unmerged PR #9 follow-up and conflict when applied directly to
  `origin/main`; stacking preserves the exact reviewed diff without hand-merging
  or rewriting history. This would change after the follow-up reaches `main`.
- Keep shared ledgers/state in a separate final commit — both F-VOL and
  Taxonomy_003 update the same files, so one state-sync commit is smaller and
  less error-prone than hunk surgery.
- Preserve the E-043 artifact byte-for-byte — existing result artifacts are
  immutable under repository policy; its internal experiment-id mismatch is
  recorded as a limitation rather than silently edited.

## Open questions / unverified assumptions

- The human chooses PR timing. Recommended bases: follow-up → `main`, F-VOL →
  follow-up branch, Taxonomy_003 → F-VOL branch; retarget after each parent
  lands.

## Rules in play (preserve verbatim)

- I13: Trial count is recorded; no hidden trials in selection.
- I15: No live/shadow/demo claim without all gates passed + human approval.
- Domain rules: R6.3 and R7.2 were preserved; no rule changed.
- Do-not-touch: `.env`, strategy/signal/risk/portfolio/execution behavior, DB
  schema, deployment gates, and existing tracked result artifacts.

## Context to load next (the reading list)

- Source of truth: `docs/BRANCH_VERSIONING.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, and the three branch heads above.
- Owning files: shared ledgers/state plus workstream-specific files listed in
  `tasks/2026-07-13-f-vol-regime-opt-stage2-e041-codex-session-handoff.md` and
  `tasks/2026-07-14-taxonomy003-stage3-handoff.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- F-VOL target pytest — `3 passed`.
- Ruff on five research probes plus the F-VOL test — passed.
- Docs metadata, feature-map links, ledger consistency, docs impact — passed.
- Config validation — passed.
- Remote refs and branch tracking — checked after push.

## Approvals

- Human approval obtained in this task to split, commit, and push all pending
  work by branch. No merge, force-push, deployment, retry, or Stage-3 H-014
  authorization was granted.

## Next action (single, concrete)

- Open the `codex/pipeline-batch1-stage3` follow-up PR against `main` first.

## Human Learning Notes

A mixed working tree can be losslessly separated even when shared docs overlap:
commit unique workstream files first, then one shared-state commit. Here the
state files depended on unmerged follow-up commits, so stacked branches avoided
an unsafe manual conflict resolution.

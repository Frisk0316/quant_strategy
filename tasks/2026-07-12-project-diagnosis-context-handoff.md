---
status: archived
type: handoff
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Context Handoff: Project diagnosis and baseline repair — 2026-07-12

## Goal (one sentence)

Leave a truthful, green baseline and an ordered, collaboration-compliant plan
for every material gap found by a whole-project audit.

## Current state

- Branch/HEAD: `codex/pipeline-batch1-stage3` / `7636dd9`; audit start was clean,
  96 ahead and 5 behind `origin/main`.
- In-progress edits: this session's uncommitted audit repair only; see companion
  session handoff for the grouped file list.
- Works now: standalone Manual, frontmatter-free chapters, loopback-only contained
  Progress markdown links, Turtle fraction unit, docs-impact fail-closed/A9/A10, full
  unit/integration/docs/config/frontend/API/backtest/browser checks.
- Unfinished: P0 artifact-ID containment, `ct_val` contract reconciliation,
  invalid-venue fail closed, human branch-integration decision, and inspection /
  restart of the user-owned hung 8080 listener (PID 23696 during audit).

## Decisions made (and why)

- Progress files use a config allow-list plus resolved-root and `.md` checks and
  are enabled only on loopback standalone binds; engine/non-loopback routes remain
  disabled because exposing repository files across a network is unnecessary.
- The Turtle result contract remains fraction-based; the fixed sweep param already
  comes from normalized frontend state, so the reintroduced percentage guess was
  removed instead of weakening the regression.
- Protected artifact/`ct_val`/venue blockers were documented, not partially
  patched: a cross-entrypoint or money-path half-fix would leave a false safety
  claim.
- A11 remains a manual requirement until a ledger validator exists; Git diff
  cannot see every ignored/external experiment artifact.

## Open questions / unverified assumptions

- Human/Claude: approve P0.1–P0.3 scopes in the follow-up task.
- Human: split/merge strategy for the 96-ahead/5-behind branch.
- Claude/human: H-012 checkpoint verdict; H-013 sign-off; E-038 planned-row
  semantics; ADR-0006 status; ADR-0001 issue-policy exception.
- Human operations: Deribit schedulers, daily DVOL ingest-or-retire, Demo key,
  unattended liquidation collection.

## Rules in play (preserve verbatim)

- I15: no live/shadow/demo claim without all gates passed + human approval.
- I32/I33/I34 are planned blockers; they are not implemented by this session.
- No strategy, risk, portfolio, execution, DB schema, deployment gate, research,
  differential-validation implementation, or existing result artifact change.

## Context to load next (the reading list)

- Source/task: `tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
- Current state: `docs/CURRENT_STATE.md`, then `docs/AI_HANDOFF.md` next steps.
- Rules: `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, relevant ADR-0003/0007.
- Owning maps: `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` for P1 governance.

## Checks run

- Full unit: `666 passed`, 1,273 warnings.
- Integration: `38 passed`.
- Ruff: pass; all 12 frontend modules `node --check`: pass.
- Docs metadata, 210 Feature Map paths, 3 Human Overviews, strict doc-impact:
  pass; config: 2 checks pass.
- Backtest smoke: pass, 2 idealized fixture fills, temp artifacts only.
- API smoke on temporary standalone port 8081: 2 endpoints pass.
- Playwright: Manual opens 10 chapters without frontmatter; configured Progress
  task opens; unlisted `README.md` returns 404.

## Approvals

- Current low-risk repair is within the user's whole-project diagnosis/fix scope.
- P0.1/P0.2/P0.3 and Git integration still require the approvals named above.

## Next action (single, concrete)

- Human reviews the new overview/task list and approves or adjusts P0.1 artifact
  containment scope before Codex edits protected validation paths.

## Human Learning Notes

Direct-router tests did not protect parity between the engine and standalone app
factory. A second entrypoint needs a wiring regression. Also, a governance check
that maps Git failure to an empty diff is worse than a visible failure because it
manufactures merge confidence.

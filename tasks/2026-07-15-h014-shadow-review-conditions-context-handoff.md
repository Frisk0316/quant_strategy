---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Context Handoff: H-014 Claude-review conditions — 2026-07-15

## Goal (one sentence)

Close both conditions in `tasks/2026-07-14-shadow-execution-claude-review.md`
without expanding ADR-0011 beyond credential-free, public-data-only shadow use.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: uncommitted scoped follow-up; H-014 shadow and
  R8 accounting tests pass 19/19.
- In-progress edits (files): runner, H-014 test/fixture, frozen-config comment,
  H-014 module/rule/invariant/failure/feature docs, existing Change Manifest,
  and this session's two handoffs.
- What works right now: the recorded DB-shape test reproduces five BTC and five
  ETH E-039 days; sparse-chain and R8.3 failures journal and the sibling
  currency continues.
- What does not work / unfinished: Claude re-review is pending. Scheduler
  registration remains unapproved and blocked. Concurrent P1.4 liquidation
  edits exist in the shared worktree and are not part of this task.

## Decisions made (and why)

- Store compact recorded SQL-return rows in one JSON fixture — it preserves the
  two query shapes with no generator/dependency; reconsider only if fixture
  refresh becomes routine.
- Catch only `ValueError` around construction/validation — these are the
  expected sparse-chain/safety rejections; transport/programming failures still
  fail closed.
- Count `rejected` outside the missed-entry denominator — required by the
  review and consistent with existing `cap_rejected` semantics.

## Open questions / unverified assumptions

- Claude must confirm both review conditions are closed; no research hypothesis
  or experiment changed.

## Rules in play (preserve verbatim)

- Invariants touched: I39 — bounded intents must journal construction/rejection
  outcomes without aborting the sibling currency; I40 — F26 as-of DVOL,
  08:00-session closes, exact prior common day, public-only surface.
- Domain rules touched: R8.3 and R8.7.
- Do-not-touch: `research/`, existing `results/`, frozen config values, private
  endpoints, credentials, orders/broker path, scheduler registration,
  strategy/risk/portfolio, DB schema, and deployment gates.

## Context to load next (the reading list)

- Source of truth: current user task,
  `tasks/2026-07-14-shadow-execution-claude-review.md`, ADR-0011,
  `config/h014_shadow.yaml`, immutable E-039 series.
- Owning files / MODULE_BRIEFS:
  `docs/MODULE_BRIEFS/deribit-shadow-execution.md`, runner and H-014 tests.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` is the only current
  pack; no H-014-specific pack exists.

## Checks run

- H-014 shadow + R8 accounting pytest — 19 passed.
- Ruff on touched Python — passed.
- DVOL as-of and close-boundary one-line mutation proofs — fixture test failed
  for each mutation, then each mutation was reverted.
- Docs metadata, feature links, ledger consistency, strict doc impact — passed.
- Config-only validation — passed.

## Approvals

- Human approval obtained for this scoped review-condition fix. No scheduler,
  private endpoint, order, credential, demo, or live approval exists.

## Next action (single, concrete)

- Claude re-reviews the H-014 follow-up diff against the two binary conditions.

## Human Learning Notes

Recorded query outputs alone cannot execute mutated SQL, so the fixture
connection also pins the F26 predicate and 08:00 grouping text. This makes the
offline parity test sensitive to both input-shape contracts while the recorded
values independently guard ivp/z/RICH reproduction.

---
status: current
type: handoff
owner: codex
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Context Handoff: ADR-0011 H-014 shadow execution — 2026-07-14

## Goal (one sentence)

Operate the accepted H-014 strategy manually against F26-safe DB signals and
Deribit public data, recording conservative hypothetical fills with zero order
or credential capability until the eight-week review gate is met.

## Current state

- Branch: `feature/taxonomy003-stage3` (shared dirty worktree; do not infer
  ownership from branch name).
- Last known good commit / state: `22bdf48`; implementation is uncommitted and
  verified in the shared worktree.
- In-progress edits (files): new `src/okx_quant/execution/deribit_shadow/`,
  config, CLI, test, manifest, maps, runbook, overview, and handoffs.
- What works right now: exact-prior-day DB signal, current-chain intent,
  R8.3 rejection/cap, public-book hypothetical fill, JSONL accounting/report,
  real manual cycle and credentials-free public book smoke.
- What does not work / unfinished: only one valid day in one distinct week
  exists; current BTC/ETH signals were `not_rich`, so no real-cycle fill-bias
  sample exists.

## Decisions made (and why)

- Dedicated thin shadow path — because ADR-0011 makes isolation from every
  broker/private/order surface the primary v1 safety property.
- Import `build_series`, `target_strikes`, and R8 accounting helpers — because
  the task forbids independent derivation and accounting drift.
- Exact prior research day plus 08:00 UTC boundary — because latest-common-day
  fallback produced plausible stale classifications (F39).
- Signal-day-qualified intent IDs — because append-only stale audit rows must
  not block a corrected same-day rerun.
- Eight-week gate needs both 56-day span and eight distinct ISO weeks — because
  two sparse records must not satisfy the exit condition.

## Open questions / unverified assumptions

- No current RICH signal occurred, so live public quote semantics were smoke
  tested independently rather than in a strategy-generated three-leg cycle.
- Claude still needs to review execution conservatism, accounting signs, and
  the F39/I40 boundary; no new research hypothesis was created.

## Rules in play (preserve verbatim)

- Invariants touched: I39 — no naked short put and at most 1.0 open unit per
  symbol; I40 — imported research sequence, F26 as-of, 08:00 UTC price day,
  exact prior day, public-only method allow-list.
- Domain rules touched: R8.3–R8.7.
- Do-not-touch: `research/`, existing result artifacts, DB schema, `risk.yaml`,
  strategy/signal/risk/portfolio code, private endpoints, credentials, orders,
  schedulers, differential validation, and every live/deployment gate.

## Context to load next (the reading list)

- Source of truth: `docs/ADR/0011-deribit-options-shadow-execution.md`,
  `tasks/2026-07-14-deribit-shadow-execution-codex-tasks.md`,
  `config/h014_shadow.yaml`, ADR-0010/R8, and the imported research helpers.
- Owning files / MODULE_BRIEFS:
  `docs/MODULE_BRIEFS/deribit-shadow-execution.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness.md`.

## Checks run

- `python -m pytest tests/unit -q -p no:cacheprovider` — 861 passed, 1 skipped.
- Targeted shadow + R8 tests — 17 passed.
- Ruff on new package/CLI/test — passed.
- Config, doc metadata, feature links, ledger, human overview, and strict doc
  impact — passed.
- Five-day real-DB parity — IVP delta 0; absolute z delta 0.036–0.041.
- Deribit public smoke — 838 BTC instruments; sample had bid/ask/mark.
- Manual cycle/report — valid BTC/ETH `not_rich` records; one valid day in one
  distinct week (0.14-week span); all exit/live gates false; two stale audit
  records ignored.

## Approvals

- Human approval obtained for ADR-0011 shadow-only implementation.
- Human approval still required for any parameter/source change, scheduler,
  private/order capability, future live ADR, and R7.2 live approval.
- Claude review is pending.

## Next action (single, concrete)

- Claude reviews the implementation and evidence before the next manual daily
  cycle; do not propose or register a scheduler.

## Human Learning Notes

Deribit's hourly DVOL endpoint returned HTTP 400 for an unbounded manual fetch,
so freshness recovery needed explicit start/end bounds. A stale classification
can look harmless (`not_rich`) yet both contaminate the 8-week denominator and
block a corrected append-only ID; freshness and identity must therefore be
validated before journaling, not repaired only in the report.

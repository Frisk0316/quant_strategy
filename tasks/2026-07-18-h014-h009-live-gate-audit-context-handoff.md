---
status: current
type: handoff
owner: codex
created: 2026-07-18
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Context Handoff: H-014 / H-009 live-gate audit — 2026-07-18

## Goal (one sentence)

Determine whether H-014/E-052 and H-009 can be put into real-money production
and exposed for further parameter screening without violating the recorded gates.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `3b0a975`; the shared worktree already contains
  unrelated modified and untracked files owned by other sessions.
- In-progress edits (files): only this handoff and its paired session handoff.
- What works right now: H-014's credential-free public-data shadow runner; H-009's
  research checkpoint runner; existing MA/EMA/MACD and Turtle parameter-sweep
  surfaces; config validation and the 30 targeted H-014/H-009 tests.
- What does not work / unfinished: neither H-014 nor H-009 has a permitted
  real-order production path. H-014 has 0.2857 journal weeks / 1 distinct week,
  no bias samples, and no live ADR. H-009 remains below the 0.95 DSR/PSR gate,
  lacks portable validation, and has no engine/UI/live execution entrypoint.

## Decisions made (and why)

- Option A, force-enable live/config: rejected because the engine does not load
  either strategy and changing `system.mode` would expose unrelated enabled
  strategies to real funds.
- Option B, relax the statistical/shadow gates: rejected because it would change
  R7.2/I15 and require a new user-approved ADR while still not supplying a safe
  execution implementation.
- Option C, smallest safe change: chosen — leave H-014 shadow-only and H-009
  testing, make no strategy/config/result/gate mutation, and request a separately
  scoped next task. This changes only if H-014 completes ADR-0011 exit evidence
  and a future live ADR, or H-009 obtains gate-passing registered evidence plus
  portable validation and the full demo/shadow/live sequence.

## Open questions / unverified assumptions

- Does “正式上線” mean real-money trading, or publication to a research-only UI?
- Does “其他參數” mean H-014/H-009 parameters (which consume honest trial/K
  budgets), or the already-supported MA/EMA/MACD/Turtle sweep parameters?

## Rules in play (preserve verbatim)

- Invariants touched: I15 — no live/shadow/demo claim without all gates passed +
  human approval; I23 — candidate CPCV uses at least family-cumulative trials;
  I39/I40 — H-014 remains bounded, public-only, and exact-prior-day shadow.
- Domain rules touched: R7.1-R7.4 and R8.1-R8.7; none changed.
- Do-not-touch: existing `results/**`, `research/**`, strategies/signals/risk/
  portfolio/execution behavior, config modes/gates, and unrelated dirty files.

## Context to load next (the reading list)

- Source of truth: `research/strategy_synthesis.md`, `config/settings.yaml`,
  `config/strategies.yaml`, `config/h014_shadow.yaml`, `docs/ai_collaboration.md`,
  ADR-0010, and ADR-0011.
- Owning files / MODULE_BRIEFS: `docs/MODULE_BRIEFS/deribit-shadow-execution.md`,
  `docs/MODULE_BRIEFS/backtesting-engine.md`, `scripts/run_h014_shadow.py`,
  `scripts/run_funding_xs_dispersion_checkpoint.py`, and
  `backtesting/parameter_sweep.py`.
- Context Pack: no H-014/H-009 pack exists; the harness-scaffolding pack is
  docs/process-only and was read for this audit.

## Checks run

- `scripts/validate_pipeline.py --check-config-only` — PASS (2 checks).
- Targeted H-014 accounting/shadow and H-009 backtest/checkpoint pytest —
  30 passed; pytest cache write warning only.
- Read-only `build_bias_report(results/shadow_h014/journal.jsonl)` — eight-week
  gate false, metrics incomplete, live-ADR discussion false, live approval false.

## Approvals

- Human asked for formal production, but recorded evidence does not satisfy R7.2.
- New approval/scope is needed for either an H-014 shadow scheduler task or a
  research-only screening surface; neither approval can waive missing evidence
  while retaining a live-readiness claim.

## Next action (single, concrete)

- Ask the human to choose and scope the next legal task: continue/schedule
  H-014 shadow-only evidence collection, or build a research-only screening
  surface with explicit parameters and honest trial/K accounting.

## Human Learning Notes

`enabled: true` is not a deployment mechanism here. H-014 is intentionally
outside the live engine, while H-009 is only a vectorized research runner;
switching global mode would trade different strategies and would not launch
either requested candidate.

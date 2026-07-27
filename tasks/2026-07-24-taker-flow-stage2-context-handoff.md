---
status: current
type: handoff
owner: codex
created: 2026-07-24
last_reviewed: 2026-07-24
expires: none
superseded_by: null
---

# Context Handoff: H-022/E-058 taker-flow Stage-2 — 2026-07-24

## Goal (one sentence)

Hand the immutable, Stage-2-only E-058 result to Claude for review without
starting Stage 3 or remediating the source data.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: ex-ante registration `eb4a9db`, probe and
  artifact `d9e89b7`, plus the result-sync commit containing this handoff.
- In-progress edits (files): none for E-058 after the result-sync commit; the
  shared working tree still contains unrelated changes from another session.
- What works right now: Option A parsing, both refusal paths, the four-check
  immutable artifact, and ledger/state synchronization.
- What does not work / unfinished: Claude review is pending. Data availability
  is 23,847/25,587 PIT member-days (0.931997), below the 0.95 gate.

## Decisions made (and why)

- Classify H-022 as `inconclusive`, not refuted or shelved, because only the
  data-availability gate failed.
- Keep family trials at 0 and K at 0/2 because no Stage-3 grid cell ran.
- Do not map SHIBUSDT to 1000SHIBUSDT or backfill ETH/SHIB because E-058 froze
  exact existing-payload parsing and authorized no download, schema change, or
  data remediation.
- Treat H-002 correlation 0.484286 as an advisory mechanism/relabel warning;
  only the two ex-ante R6.6 references gate this probe.

## Open questions / unverified assumptions

- Claude must decide whether the high non-gating H-002 correlation means the
  mechanism is too momentum-like to pursue, even if a later data task were
  separately authorized.
- No assumption is made that missing ETH/SHIB history can or should be repaired.

## Rules in play (preserve verbatim)

- I13: Trial count is recorded; no hidden trials in selection.
- I23: Stage-2 power-screen `n_trials` uses at least the family-cumulative count.
- I42: Undefined required correlation fails closed; it is never treated as zero.
- I45: Candidate-specific power inputs are required before DB/probe/artifact work.
- Domain rules: R2 fees, R3 funding, R6.1 leakage, R6.3 trial accounting, R6.6
  distinctness feasibility, and R7.1 non-promotion evidence.
- Do-not-touch: `research/`, existing result artifacts, schema/migrations,
  trading core, risk/deployment config, and every Stage-3 surface.

## Context to load next (the reading list)

- Source of truth: `tasks/2026-07-24-taker-flow-stage2-codex-tasks.md`,
  `docs/superpowers/specs/2026-07-23-f-taker-flow-hypothesis.md`,
  `docs/HYPOTHESIS_LEDGER.md`, and `docs/EXPERIMENT_REGISTRY.md`.
- Owning files / MODULE_BRIEFS: `backtesting/taker_flow_probe.py`,
  `backtesting/pipeline_stage2_registry.py`, and
  `docs/MODULE_BRIEFS/backtesting.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness.md`.

## Checks run

- Targeted E-058 tests: 27 passed.
- Full unit suite: 954 passed, 1 skipped.
- Full Ruff, config validation, backtest smoke, docs metadata/links/ledger,
  strict doc impact, artifact schema/check-set validation, and diff checks: PASS.
- Real read-only probe: all bounded symbol-year queries completed without a
  probe statement timeout.

## Approvals

- Human approval obtained for E-058 Stage 2 only.
- Stage 3, retry, download/backfill, schema changes, promotion, and deployment
  are not approved.

## Next action (single, concrete)

- Claude reviews the four check results, artifact hash, advisory H-002
  correlation, commit ordering, and data-blocked classification.

## Human Learning Notes

Point-in-time universe membership does not prove feature availability: ETHUSDT
and SHIBUSDT entered the top-30 membership but had no exact-symbol raw taker
payload in this store. The 1000SHIBUSDT history is not a harmless substitute
under a frozen exact-symbol probe. Also, passing numeric distinctness against
the two gating references did not eliminate mechanism ambiguity: the advisory
momentum correlation was materially higher at 0.484286.

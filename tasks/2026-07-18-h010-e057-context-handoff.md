---
status: current
type: handoff
owner: codex
created: 2026-07-18
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Context Handoff: H-010 E-057 Stage 2 — 2026-07-18

## Goal (one sentence)

Run the newly authorized strategy-selection round without gate chasing and stop
H-010 before Stage 3 if its frozen feasibility checks fail.

## Current state

- Branch: `feature/h014-e052-shadow`; no commit was requested or created.
- Last known good state: E-057 artifacts are immutable and all required local
  checks pass; full unit suite is `910 passed, 1 skipped`.
- In-progress edits: the files listed in the paired Session Handoff. The shared
  tree also contains pre-existing dirty OKX promotion/spec/funnel changes; they
  were preserved and not claimed as this task's implementation.
- What works: two-step H-010 calibration/Stage-2 execution, pre-DB evidence
  validation, source-aware full-window coverage, four explicit checks, ledger
  accounting, and fail-closed execution-venue funding.
- What does not work / unfinished: H-010 has no Stage-3 runner by design because
  E-057 failed. There is no OKX funding history in the local DB. Distinctness
  cannot reach 365 common calibration dates after the data prerequisite fails.

## Decisions made (and why)

- Chose the existing pre-registered H-010 family — it was the only current
  frontier unlocked by materially longer, verified source-aware history.
- Split calibration from active Stage 2 — I45 requires the four power inputs
  before active DB access; would change only if ADR-0013 changes.
- Evaluated one L240/Z2 anchor and no alternatives — this provides a cheap cost
  smell without spending or hiding a grid trial.
- Shelved at Stage 2 — 1.3636 bps median gross capture is below 8.0 bps median
  cost across 7,376 episodes, independently of missing funding.
- Did not implement Stage 3 — every Stage-2 check failed and the frozen stop
  rule makes further work gate chasing.

## Open questions / unverified assumptions

- Claude should verify the candle-only synthetic maker-at-next-open calibration
  disclosure and exact 8/11 bps episode-cost convention. It is explicitly
  `idealized_fill=true` and never promotion evidence.
- If OKX funding is later sourced, H-010 should remain shelved unless a genuinely
  new ex-ante mechanism is approved; filling the data gap cannot repair the
  already failed gross-cost inequality.

## Rules in play (preserve verbatim)

- I19/I47: simultaneous venue candles use source-aware identity; no substitution.
- I45: all four candidate-specific power inputs precede active DB access/probe.
- I48: execution-venue funding only; missing OKX settlements fail closed.
- R3.1–R3.4: signed, reconcilable, venue-matched funding cashflow.
- R6.1/R6.3/R6.4/R6.5: no lookahead, honest trials, venue/data provenance.
- R7.1–R7.4: DSR and PSR both gate; idealized evidence is not deployable.
- Do-not-touch: `research/`, live strategy/risk/portfolio/execution, deployment
  gates, `backtesting/differential_validation.py`, existing result artifacts,
  and the pre-existing dirty promotion implementation.

## Context to load next (the reading list)

- Source of truth: `research/strategy_synthesis.md`,
  `docs/superpowers/specs/2026-07-18-f-xvenue-leadlag-hypothesis.md`,
  `tasks/2026-07-18-h010-pipeline-codex-task.md`, ADR-0013/0014, and E-057.
- Owning files: `backtesting/xvenue_leadlag_probe.py`,
  `backtesting/pipeline_stage2_registry.py`, and the backtesting module brief.
- Context Pack: `docs/CONTEXT_PACKS/harness.md`.

## Checks run

- Focused H-010/pipeline suite — `52 passed`.
- Full unit suite — `910 passed, 1 skipped`; skip is the known Windows symlink
  privilege case; warnings are pre-existing numerical/empty-slice warnings.
- Focused Ruff — PASS.
- Docs metadata, feature-map links, ledger consistency, strict doc impact — PASS.
- Config validation and backtest smoke — PASS.
- Full-range read-only candle verifier — PASS at 3,396,960 rows per leg.

## Approvals

- Obtained: user's 2026-07-18 request authorized this strategy-selection round,
  minimal pipeline repair, and conditional Stage 3 only after Stage-2 PASS.
- Not obtained/needed: promotion, demo, shadow, live, external messaging, or
  deployment changes. None were performed.

## Next action (single, concrete)

- Claude reviews E-057's cost calculation, zero-trial accounting, R3.4/F47/I48
  boundary, and stop verdict; do not rerun or retune H-010.

## Human Learning Notes

Perfect candle coverage is only a prerequisite, not edge. Once source identity
was fixed, the cheapest honest test killed H-010 decisively: the median price
capture was about one-sixth of round-trip cost, before funding. The missing OKX
funding exposed a separate provenance trap—having Binance funding in the same
schema does not make it valid for an OKX position. A pipeline that stops before
DSR in this situation is working correctly, not failing to search hard enough.

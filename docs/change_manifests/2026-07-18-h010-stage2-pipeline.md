---
status: current
type: change-manifest
owner: codex
created: 2026-07-18
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Change Manifest: H-010 Stage-2 pipeline completion

## Scope

- Change type: backtesting/validation harness and experiment execution.
- User-visible effect: H-010 can produce a complete fail-closed Stage-2 verdict
  instead of a coverage-only partial result.
- Explicit non-scope: strategy promotion, live/demo/shadow behavior, risk or
  sizing policy, existing artifacts, and differential-validation ownership.

## Impact-matrix review

| Area | Applies | Required action |
|---|---:|---|
| A5 backtest/validation | yes | frozen calibration, next-bar execution tests, immutable result, honest trials |
| A9 research pipeline | yes | Stage-2 registry/tests, ledgers, feature/data/runbook/current-state sync |
| A11 source-aware identity | yes | query only `canonical_candles_by_source`; no resolved substitution; I19/I47 checks |
| PnL/fee/funding/sizing/fills/gates | yes | reuse R2/R3/R6/R7, add a venue-matched funding invariant/failure mode, and record the experiment-specific frozen proxy |
| Major policy change | no | no ADR; ADR-0013 remains authoritative |

The implementation clarification is registered as R3.4/F47/I48: funding must
match the execution venue and cannot be borrowed from the signal venue.

## Current / target / known gap

- Current: H-010 is data-ready but has no complete Stage-2 probe.
- Target: complete data, distinctness, cost, and power checks with I45 inputs
  frozen before active DB access.
- Known gap: a Stage-3 runner is intentionally absent until Stage 2 passes.

## Verification and evidence

- Focused unit tests for source identity, exact t+1 execution, gaps/zero variance,
  cost/funding accounting, fail-closed correlation, evidence hashing, and I45
  pre-DB ordering.
- Existing pipeline Stage-2/orchestrator/power tests.
- `make docs-impact`, `make docs-check`, and targeted Python tests.
- Fresh E-057 artifact and hashes; Stage-3 evidence only on PASS.

## Rollback

Remove the fresh H-010 module/tests/artifacts and revert only the H-010 registry,
script, and documentation hunks. No DB mutation or existing artifact rewrite is
performed.

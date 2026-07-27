---
status: current
type: handoff
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Context Handoff: strategy-finding round — 2026-07-26

## Goal (one sentence)

Use the existing research pipeline to test one previously untried mechanism and
one iteration of a comparatively strong existing strategy, then issue an honest
pass/fail decision from reproducible artifacts.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: HEAD `29d5105`; this session is intentionally
  uncommitted in a working tree that already contained unrelated user/other
  session changes.
- In-progress edits (files): none for this task; implementation, artifacts,
  ledgers, and handoffs are complete.
- What works right now:
  - H-023/F-XS-IDIOVOL has a tested research backtest and immutable Stage-2
    artifact.
  - H-009 retry 1 has source-scoped data evidence, fold-refit WF/CPCV, retained
    paths, checkpoint automation, and reconciled trial/K accounting.
  - Final review artifact:
    `results/strategy_finding_20260726/checkpoint_review.json`.
- What does not work / unfinished:
  - Neither candidate passed.
  - H-023 stopped at Stage-2 power; H-009 failed DSR/PSR at checkpoint 1.
  - No adapter, portable validation, promotion, demo, shadow, or live work is
    authorized.

## Decisions made (and why)

- Selected H-023 BTC-residual low-idiosyncratic-volatility as the new family
  because it uses current PIT/candle/funding data, had no prior pipeline run,
  and required the smallest distinct implementation. Would change only under a
  new pre-registered thesis, not after observing E-062.
- Selected H-009 breadth restoration instead of retuning supported H-014 because
  H-014's next gate is shadow, while H-009 had a marginal prior miss and an
  ex-ante data-only rationale.
- Corrected the stale 28→32 draft before execution: E-031 already included
  1000SHIB, so CC/FIL/M restore 28→31 unique assets and SHIB is deduplicated.
- H-023 verdict: Stage-2 power FAIL (`0.5961 < 0.7134`); zero trials/K.
- H-009 verdict: checkpoint1 FAIL (WF `1.4778`, CPCV `0.9092`, DSR `0.8305`,
  PSR `0.9166`); family `n_trials=8`, K `1/2`.
- Both families are shelved for this round with no retune.

## Open questions / unverified assumptions

- Daily funding cashflow preserves the frozen AVG-to-daily research convention;
  it is not settlement-grade cashflow and must not support promotion.
- Claude may review whether a materially different future H-023 thesis deserves
  a new pre-registration; no retry is implied by the remaining K budget.

## Rules in play (preserve verbatim)

- Invariants touched: I8 (no future data), I20 (PIT membership), I23
  (family-cumulative trials), I24 (fold-local refit), I25 (raw paths), I50
  (consumer-time alias collapse), I52 (funding source matches venue).
- Domain rules touched: R3.1–R3.4, R5.3, R6.1, R6.3, R6.4, R6.7, R7.4.
- Do-not-touch: `research/`; pre-existing result artifacts; strategy/risk/live
  config; differential-validation implementation; unrelated dirty files.

## Context to load next (the reading list)

- Source of truth:
  `docs/superpowers/specs/2026-07-26-strategy-finding-round.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, and
  `results/strategy_finding_20260726/checkpoint_review.json`.
- Owning files / MODULE_BRIEFS:
  `backtesting/xs_idiovol_backtest.py`,
  `scripts/run_strategy_finding_20260726.py`,
  `docs/MODULE_BRIEFS/backtesting-engine.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Full unit suite: `964 passed, 1 skipped`.
- Focused strategy/runner suite: `11 passed`; independent review suite:
  `26 passed`.
- Full Ruff: PASS.
- Docs metadata/link/ledger checks: PASS with one intentional warning that the
  already-hashed pre-registration spec lacks lifecycle frontmatter.
- Strict doc impact: PASS.
- Config check: PASS.
- Backtest smoke: PASS; fixture is explicitly idealized and not promotion
  evidence.
- Checkpoint1 auto: expected FAIL only on DSR/PSR; other six checks PASS.
- `git diff --check`: no whitespace errors; Windows line-ending warnings only.

## Approvals

- Human approval obtained: user authorized this strategy-finding/backtest round.
- Human approval not obtained and still required: any follow-on experiment,
  promotion, deployment, demo, shadow, or live action.

## Next action (single, concrete)

- Claude reviews E-062/E-063 evidence and the disclosed daily-funding research
  convention before anyone proposes another pre-registered round.

## Human Learning Notes

The apparent 28→32 breadth restoration was wrong: SHIB and 1000SHIB are one
economic asset, so the correct target was 31. More breadth improved H-009's WF
Sharpe but worsened CPCV, DSR, and PSR after the honest trial penalty—an example
of why a stronger headline WF number is not a pipeline pass. The shared loader
also had venue-scoped candles but unscoped funding; fixing provenance at the
loader was necessary even though the current frozen window contained only
Binance funding rows.


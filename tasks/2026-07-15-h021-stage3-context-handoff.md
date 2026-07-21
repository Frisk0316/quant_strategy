---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Context Handoff: H-021 Stage-3 checkpoint ① — 2026-07-15

## Goal (one sentence)

Hand the completed, single-run E-056 full-PnL checkpoint to Claude for
adversarial review without permitting a retry or promotion step.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good implementation commit: `9ffe142`; pre-registration commit:
  `f1f5326`.
- In-progress edits: E-056/H-021 records and these handoffs await the final
  records commit.
- What works: I44/G-005, registry, DB event loading, exact R9 accounting,
  four-cell base/stress output, retained refit WF/CPCV paths, family minting,
  and checkpoint automation.
- What does not work / unfinished: the pre-registered statistical and stress
  gates failed. Claude adversarial review and human acceptance of the terminal
  verdict remain.

## Decisions made (and why)

- Mark H-021 `refuted` — both WF and CPCV Sharpes are negative and DSR/PSR are
  far below 0.95; this is stronger than an inconclusive/marginal failure.
- Do not retry — the user explicitly fixed checkpoint ① as terminal regardless
  of margin, and the observed failure is not a data or execution error.
- Keep K at 0/2 — E-056 is the family's first Stage-3 validation, not a retry.

## Open questions / unverified assumptions

- Claude should independently recompute at least one R9 event and confirm that
  equal-mean BTC/ETH pair-NAV aggregation is faithful to the frozen contract.
- Claude should inspect why L3/H1 is selected in folds despite negative
  full-window base/stress PnL; this does not change the failed verdict.

## Rules in play (preserve verbatim)

- I23: candidate CPCV n_trials must be at least family-cumulative trials (12).
- I25: retain raw CPCV path returns/periods/lengths and provenance.
- I41/I43: ≤1s funding canonicalization; missing 8h events fail closed and are
  never compressed.
- I44/R9.1-R9.5: exact 1/P coin PnL, same-bar USD conversion, correct funding
  signs and both cost scenarios; I44 must be green before a grid.
- Do-not-touch: existing results, H-014/shadow, research, strategy/risk/
  portfolio/execution core, config/gates, index substitution, promotion.

## Context to load next (the reading list)

- Source of truth: the H-021 frozen spec plus Stage-3 addendum, ADR-0012,
  H-021/E-056 ledger rows, and `results/h021_stage3_20260715/summary.json`.
- Owning files / MODULE_BRIEFS: `backtesting/xvenue_funding_spread_backtest.py`,
  `docs/MODULE_BRIEFS/backtesting-engine.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` for ledger/docs
  verification only.

## Checks run

- I44 targeted — 2 passed before grid.
- Registry + I44 targeted — 7 passed.
- Full unit — 874 passed, 1 skipped before grid.
- Final full unit rerun — 874 passed, 1 skipped.
- DB preflight — 2,739 complete events per symbol.
- Single E-056 run — completed once; no retry.
- Ledger consistency — 22 H / 57 E / 21 K families PASS after records.
- Checkpoint auto — expected FAIL only at DSR/PSR threshold.

## Approvals

- Human approval obtained for E-056 implementation/run and checkpoint ① stop.
- No approval exists for retry, promotion, demo, shadow, live, or gate changes.

## Next action (single, concrete)

- Claude adversarially reviews commit range `83a8e6e..HEAD` and immutable E-056
  artifacts, then records accept/reject findings without rerunning the grid.

## Human Learning Notes

The funding-only proxy understated some profitable full-PnL cells, but adding
basis PnL did not create stable fold-refit evidence: three cells were positive
under stress while overall WF/CPCV remained negative, and the fold-selected
L3/H1 cell was materially negative. Robust point estimates are not a substitute
for selection-stable OOS evidence.

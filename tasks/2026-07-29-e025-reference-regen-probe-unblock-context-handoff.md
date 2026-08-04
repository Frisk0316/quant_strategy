---
status: current
type: handoff
owner: codex
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Context Handoff: E-025 regeneration and H-024..H-027 probe — 2026-07-29

## Goal (one sentence)

Provide the missing dated E-025 distinctness reference and complete the
authorized four-candidate limited probe without changing frozen signals,
thresholds, trials, or K rules.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`
- Last known good commit / state: `5ac02a8`; all four Stage-2 outcome commits
  and wrap-up checks are complete, with the wrap-up commit pending
- In-progress edits: AI handoff, changelog, workstream, and session/context
  handoff
- What works right now: E-025 has 898 dated returns; whole-batch I49 passes;
  E-064..E-067 each have four-check immutable artifacts and ledger rows
- What does not work / unfinished: no candidate passed Stage 2, so no Stage-3
  artifact exists; Claude review is pending

## Decisions made (and why)

- Regenerated E-025 with the existing C1 runner and its frozen selected params,
  because the task classifies this as reference-only rather than a retry.
- Kept the fixed full-window daily series separate from CPCV OOS paths, because
  they are different statistics and only the former has canonical dates.
- Assigned H-025 to F-OPT-HEDGE-DEMAND, because the mandatory mint-apart abs
  correlation is 0.749580, above the 0.30 threshold.
- Did not add any Stage-3 runner, because all four candidates failed at least
  one Stage-2 check.
- Kept F-VRP-TIMING actual trials=4 and K=0/2, because H-026 used prospective
  `n_trials=8` only for the power screen and never ran its grid.

## Open questions / unverified assumptions

- Claude should confirm H-025's family merge and H-024's `inconclusive`
  classification given its simultaneous data and power failures.

## Rules in play (preserve verbatim)

- Candidate order: H-024, H-025, H-027, H-026.
- Any Stage-2 four-check failure stops that candidate; Stage 3 is pass-only.
- H-026 power uses family-cumulative `n_trials=8`; K is consumed only if its
  Stage-3 grid runs.
- E-025 regeneration changes no H-006 status, experiment row, family trial, or
  K budget.
- No retune, sign flip, promotion, demo, shadow, live, or deployment claim.

## Context to load next (the reading list)

- Source of truth:
  `tasks/2026-07-29-e025-reference-regen-probe-unblock-codex-tasks.md`,
  `tasks/2026-07-28-moneyness-vol-probe-codex-tasks.md`, and
  `docs/superpowers/specs/2026-07-28-deribit-moneyness-vol-probe-hypotheses.md`
- Owning files: `backtesting/moneyness_vol_probe.py`,
  `backtesting/pipeline_stage2_registry.py`, `docs/HYPOTHESIS_LEDGER.md`, and
  `docs/EXPERIMENT_REGISTRY.md`
- Context Pack: no task-specific pack exists; use
  `docs/CONTEXT_PACKS/harness-scaffolding.md`

## Checks run

- E-025 reproduction: 898 rows, exact recorded runner Sharpe, unchanged
  `summary.json` SHA-256
- Whole-batch I49: passed; H-027/E-025 common days=898
- Four artifact SHA/four-check aggregation: passed
- F-PAIRS-OU K row and H-006 row no-drift guard: passed
- Ledger consistency after E-067: 28 hypotheses, 68 experiments, 25 families
- Required probe unit test: 6 passed; C1/probe/registry matrix: 23 passed
- Targeted Ruff, config validation, feature-map links, advisory docs-impact,
  and backtest smoke: passed
- Docs metadata: passed with two pre-existing missing-metadata warnings

## Approvals

- User authorization covers R1 and all four frozen Stage-2 probes plus
  pass-only Stage 3.
- No candidate unlocked Stage 3; no approval exists for retuning or rerunning.

## Next action (single, concrete)

- Claude reviews commits `094742e`, `8f053bb`, `0f572dd`, `084df47`,
  `5ac02a8`, and the wrap-up commit.

## Human Learning Notes

A faithful fixed-parameter daily reference can exactly reproduce the original
runner metric yet have a different daily-series Sharpe and a very different
CPCV OOS Sharpe. Those are different sampling/selection objects, not evidence
of drift.

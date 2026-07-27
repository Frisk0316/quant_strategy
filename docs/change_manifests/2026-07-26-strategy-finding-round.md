---
status: current
type: manifest
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Change Manifest: 2026-07-26 strategy-finding round

## Summary

Added a research-only cross-sectional idiosyncratic-volatility backtest and a
one-off, pre-registered two-direction pipeline runner. The work also fixed the
shared FundingXS PostgreSQL loader so funding rows are scoped to the declared
execution venue before aggregation.

## Business rule(s) affected

- R3.1–R3.4 funding sign, timing, and execution-venue provenance.
- R5.3 / R6.1 signal and execution lag.
- R6.3 / R7.4 honest family-cumulative trials and fold-refit validation.
- R6.4 venue provenance.
- R6.7 consumer-time economic-asset aliases.
- No threshold, promotion, deployment, demo, shadow, or live rule changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)

- A5 backtesting workflow.

## Files changed

- `backtesting/funding_xs_dispersion_backtest.py` — scope PostgreSQL funding
  queries to `source=exchange`.
- `backtesting/xs_idiovol_backtest.py` — research-only H-023 signal and PnL.
- `scripts/run_strategy_finding_20260726.py` — immutable, pre-registered
  Stage-2/Stage-3 batch runner.
- `tests/unit/test_funding_xs_dispersion_backtest.py` — venue-source regression.
- `tests/unit/test_xs_idiovol_backtest.py` — residual ranking and lag golden case.
- `tests/unit/test_run_strategy_finding_20260726.py` — preregistration, alias,
  breadth-restoration, and distinctness guards.
- `docs/GOLDEN_CASES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` —
  G-007, I52, and F55.
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` — H-023 and
  E-060 through E-063 evidence/trial/K accounting.
- `docs/STRATEGY_HISTORY.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  and `config/workstreams.yaml` — human-readable outcome and current-state sync.
- `docs/superpowers/specs/2026-07-26-strategy-finding-round.md` and
  `tasks/2026-07-26-strategy-finding-{preregistration-receipt,context-handoff,session-handoff}.md`
  — frozen design-space decision, pre-run hashes, and session continuity.
- `results/strategy_finding_20260726/` — new E-062/E-063 artifacts only.

## Behavior delta

- Before: the FundingXS DB loader selected venue-scoped candles but could
  aggregate same-symbol funding rows from every stored source.
- After: both intraday and daily funding queries filter to the declared
  execution venue before aggregation.
- Before: no runnable F-XS-IDIOVOL implementation or current-batch adapter
  existed.
- After: H-023 can be screened and, only after four Stage-2 passes, validated
  through the existing fold-refit WF/CPCV helpers.
- Money/risk impact: the loader fix can change research PnL when a DB contains
  multiple funding venues for one symbol. The frozen run's source census found
  only Binance input rows, so it did not change this batch through cross-venue
  removal. No runtime/live strategy uses H-023.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — Claude-owned and not modified; H-023
  is a user-authorized research hypothesis, now shelved at Stage 2.
- `config/`: N/A — no strategy enablement or gate changed.
- ADR: N/A — no major policy, schema, accounting formula, or gate changed.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/GOLDEN_CASES.md` — added G-007.
- [x] `docs/INVARIANTS.md` — added generic venue-scoped funding I52.
- [x] `docs/FAILURE_MODES.md` — added F55.
- [x] `docs/DATA_FLOW.md` — reviewed; confirmed unchanged because both
  candidates consume the existing PIT membership/canonical candle/funding path.
- [x] `docs/FEATURE_MAP.md` — reviewed; confirmed unchanged because the batch
  adds no supported user-facing or runtime feature.

## Invariants / golden cases

- Invariants checked: I8, I20, I23–I25, I50, I52.
- Golden cases affected: new G-007; existing golden outputs unchanged.

## Tests / checks run

- Full unit suite: 964 passed, 1 skipped.
- Focused pytest for FundingXS, XS idio-vol, and batch runner: 11 passed.
- Independent adversarial focused suite: 26 passed.
- Ruff on all changed Python files: passed.
- Ledger consistency: passed with 24 hypotheses and 64 experiments.
- Checkpoint1 automation: expected FAIL for E-063 solely on DSR/PSR threshold;
  the other six checks passed.
- Full docs/config/smoke checks are recorded in the session handoff.

## Risks and rollback

- Risks: daily funding PnL retains the pre-registered AVG-to-daily research
  convention and is not settlement-grade cashflow; H-023 remains research-only.
- Rollback: remove the new H-023/batch files and new result directory, revert
  the two funding SQL predicates and their regression, then revert only the
  H-023/E-060–E-063/G-007/I52/F55 documentation additions. Do not touch
  unrelated pre-existing dirty files.

## Approval

- Human approval required: yes for the strategy-finding experiment; obtained
  through the user's 2026-07-26 request. No promotion or deployment approval
  was requested or obtained.

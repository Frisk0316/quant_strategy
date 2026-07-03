---
status: current
type: manifest
owner: claude
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Change Manifest: Stage-2 Funding Breadth Warmup Window

## Summary
User-approved (2026-07-03) Stage-2 probe window change: the funding
`min_rebalance_breadth` check is evaluated from `START + 30 days`
(`FUNDING_BREADTH_WARMUP_DAYS`, matching `config/universe.yaml`
`warmup_days: 30`) instead of the full window. Warmup-edge days remain fully
recorded in `details.rebalance_breadth` for audit but cannot fail the check.
An all-warmup window fails closed (empty evaluation → min 0 → FAIL).

## Business rule(s) affected
Stage-2 data-availability gate window semantics for F-FUNDING-XS-DISPERSION
(validation gate area). Threshold **values** are unchanged
(`min_good_symbols=10`, `min_rebalance_breadth=10`, coverage/stale ratios
unchanged); only the day set over which breadth-min is computed changed.

## Why
Universe eligibility requires 30 warmup days of history, so during the first
~30 days of the window the point-in-time universe mathematically cannot reach
breadth 10 — the old min-over-full-window definition made the check
unpassable regardless of data quality. Evidence: with a DB-rebuilt universe,
868/898 window days reach breadth ≥ 10 and only the 2024-01 warmup edge
fails (`results/stage2_reprobe_20260703_funding_dbuniverse/`,
2026-07-03 diagnostic).

## Trigger area(s) (DOC_IMPACT_MATRIX)
A9 validation/governance gate semantics; A5 research pipeline automation.

## Files changed
- `backtesting/pipeline_stage2_registry.py` — `FUNDING_BREADTH_WARMUP_DAYS`,
  `FundingThresholds.breadth_warmup_days`, warmup-filtered breadth stats,
  window details (`breadth_warmup_cutoff`, `breadth_days_evaluated/total`).
- `tests/unit/test_pipeline_stage2_data_probe.py` — updated existing breadth
  test day; new `test_funding_breadth_excludes_warmup_edge_days_from_min`
  covering exclusion, audit retention, and all-warmup fail-closed.

## Behavior delta
- Before: breadth min computed over every day in `[START, END)`; first-month
  warmup days could (and always did) force FAIL.
- After: breadth min computed over `[START+30d, END)`; warmup days recorded
  but not judged; empty evaluated set stays FAIL (fail-closed).
- Existing artifacts (`E-028`, `results/stage2_reprobe_20260703_funding*/`)
  were produced under the OLD semantics and are not rewritten; artifacts
  produced after this change carry `breadth_warmup_cutoff` in their window
  details, so the two generations are distinguishable.
- Money/risk impact: none. Advisory research gate only; no strategy, risk,
  portfolio, execution, promotion, demo, shadow, or live behavior changed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A.
- config/: none (warmup constant mirrors existing `config/universe.yaml`).
- ADR: not required — window semantics fix within an advisory Stage-2 probe,
  threshold values unchanged, user explicitly approved 2026-07-03.

## Invariants / golden cases
- Invariants checked: I19 (no cross-venue substitution — untouched), I29
  (orchestrator append-only — reprobe after this change appends new metrics).
- Golden cases affected: N/A.

## Tests / checks run
- `pytest tests/unit/test_pipeline_stage2_data_probe.py tests/unit/test_pipeline_stage2_registry.py tests/unit/test_pipeline_orchestrator.py -q`
- `python scripts/docs/check_doc_metadata.py`

## Risks and rollback
- Risk: a future window with a different START would reuse the module-level
  START for the cutoff (existing registry design; batch-scoped constants).
- Rollback: revert `backtesting/pipeline_stage2_registry.py` and the test
  file plus this manifest.

## Approval
- User approval: **yes, explicit (2026-07-03 「好, 請改起點」)**. Advisory
  research pipeline only; not a live/demo/shadow/deployment gate.

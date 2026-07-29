---
status: current
type: handoff
owner: codex
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Session Handoff: E-025 regeneration and limited-probe completion — 2026-07-29

## Implementation summary

Regenerated E-025's selected C1 pairs-OU combo as 898 dated daily returns with
the existing runner, switched I49 to that CSV, and completed H-024/H-025/H-027/
H-026 in frozen order. Every candidate stopped at Stage 2; E-064..E-067 and
their hypothesis resolutions record the four-check outcomes without retuning.

## Diff scope

- Files added: E-025 `combo_daily_returns.csv` and
  `reference_regen_notes.md`; four Stage-2 artifacts under
  `results/moneyness_vol_probe_20260728/`; this handoff and its paired context
  handoff
- Files changed: `backtesting/moneyness_vol_probe.py`,
  `tests/unit/test_moneyness_vol_probe.py`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/AI_HANDOFF.md`,
  `docs/CHANGELOG_AI.md`, and `config/workstreams.yaml`
- Files deleted: none

## Business-rule change?

- No. The session executes an approved research contract and regenerates a
  missing reference; no PnL, fee, funding, sizing, fill, risk, gate, schema, or
  deployment rule changed.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; research ownership preserved
- `config/`: `config/workstreams.yaml` state-only synchronization
- ADR: N/A

## Experiments

- HYPOTHESIS_LEDGER entries: H-024 inconclusive; H-025 duplicate/refuted and
  assigned to F-OPT-HEDGE-DEMAND; H-027 refuted; H-026 shelved
- EXPERIMENT_REGISTRY entries: E-064, E-065, E-066, E-067
- E-025 regeneration: no experiment row, trial, or K change

## Tests / checks run

- Probe unit tests: 6 passed before execution
- Whole-batch I49: passed, including 898 H-027/E-025 common days
- Per-candidate and aggregate artifact check/SHA validation: passed
- Ledger consistency: passed after each candidate; final 68 experiments
- F-PAIRS-OU/H-006 no-drift guard: passed
- Required probe unit test: 6 passed; C1/probe/registry matrix: 23 passed
- Targeted Ruff, config validation, feature-map links, advisory docs-impact,
  and backtest smoke: passed
- Docs metadata: passed with two pre-existing missing-metadata warnings

## Docs updated

- `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, and
  `config/workstreams.yaml`

## Known limitations / risks

- H-024/H-025 have only 0.770784 valid-feature coverage, so H-024 is
  inconclusive and neither options-flow book has Stage-3 evidence.
- H-027/H-026 have clean data/distinctness but negative frozen proxies; no
  alternative direction or threshold was examined.
- Mandatory handoff files remain a governance-required exception to the
  task's permitted-file list.

## Rollback plan

- Revert the wrap-up and ordered run commits, then `094742e`. This removes only
  new artifacts/rows and restores the old I49 path; the pre-existing E-025
  `summary.json` is byte-identical and needs no restoration.

## Context Handoff

- See
  `tasks/2026-07-29-e025-reference-regen-probe-unblock-context-handoff.md`.

## Questions for human review

- Does Claude accept H-025's family merge and the removal of its never-used
  placeholder K-budget row?
- Does Claude accept H-024 as inconclusive rather than refuted because data
  availability and power both failed?
- Confirm H-026 correctly leaves K=0/2 because Stage 3 never ran.

## Next recommended task

- Claude reviews the six ordered commits; no candidate rerun or retune should
  occur.

## Human Learning Notes (required)

The stronger dated-reference repair did exactly what the governance intended:
it converted a structural stop into a measurable distinctness test without
improving any candidate's economics or silently turning a reference rebuild
into a retry.

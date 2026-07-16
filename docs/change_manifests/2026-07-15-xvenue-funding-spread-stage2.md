---
status: current
type: manifest
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Change Manifest: cross-venue funding-spread Stage 2

## Summary

Adds a research-only, fail-closed Stage-2 probe for C4 cross-venue funding
divergence. It measures aligned funding coverage, feature-level distinctness,
and a correctly gross-normalized two-leg funding/cost proxy; it cannot promote
or run Stage 3 without the missing Deribit tradable-price contract.

## Business rule(s) affected

No rule text changes. Reviewed R2.1 costs, R3.1 funding sign, R6.1 point-in-time
availability, R6.3 honest trials, R7.1 idealized evidence, and R7.2 promotion.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting, A9 validation/gates, and A11 experiments/research runs.

## Files changed

- `backtesting/xvenue_funding_spread_probe.py` — bounded Stage-2 probe.
- `backtesting/pipeline_stage2_registry.py` — registers the new family probe.
- `tests/unit/test_xvenue_funding_spread_probe.py` and pipeline registry tests
  — guard t+1 funding, two-leg gross normalization, turnover, and registration.
- Stage-1/taxonomy specs, ledgers, feature/data maps, current-state docs, and
  handoffs — record the candidate and result without touching research sources.
- `results/idea_batch_20260715_taxonomy_004/**` — generated advisory artifacts.

## Behavior delta

- Before: the general pipeline had no registered C4 Stage-2 implementation.
- After: a taxonomy_004 C4 candidate can run a local DB-backed Stage-2 probe
  and fails closed when full-PnL inputs or any required gate are absent.
- Money/risk impact: none; no live/demo/shadow strategy, config, sizing, risk,
  execution, or deployment behavior changes.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; Claude-owned and unchanged.
- config/: N/A; no strategy or venue settings changed.
- ADR: N/A; no engine/accounting rule or gate policy changed. A future Deribit
  inverse-perpetual implementation would require a separate ADR/manifest.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/HYPOTHESIS_LEDGER.md` and `docs/EXPERIMENT_REGISTRY.md` — H-021/E-053/E-054.
- [ ] `docs/FEATURE_MAP.md` and `docs/DATA_FLOW.md` — update after execution.
- [x] `docs/DOMAIN_RULES.md` — reviewed; no rule-text change required.
- [x] `docs/INVARIANTS.md` — I13, I19, I23, I27, I29, and I41-I43 govern this probe.
- [x] `docs/GOLDEN_CASES.md` — reviewed; no production golden case changes.
- [x] ADR-0002/0005/0007 — reviewed; no schema/gate/engine contract change.

## Invariants / golden cases

- Invariants checked: I13/I23 honest trials, I19 venue identity, I27/I42 family
  distinctness, I29 fail-closed orchestration, and I41-I43 timestamp/gap guards.
- Golden cases affected: none; this is an advisory research probe.

## Tests / checks run

- Targeted unit tests, taxonomy_004 generator, DB-backed orchestrator run and
  bounded F41 reprobe completed; exact commands/results are in the session
  handoff.
- Expanded targeted pytest: 49 passed; touched-file Ruff passed.
- Docs metadata, feature links, ledger consistency, strict doc impact, config
  validation, and frozen-fixture backtest smoke passed via Makefile-equivalent
  Python commands because GNU Make is unavailable on this host.

## Risks and rollback

- Risks: funding-only results omit basis/mark PnL and inverse-collateral effects;
  feature-level correlation is not a final family-minting verdict.
- Rollback: remove the new probe/test/spec/result files and revert the registry
  and governance rows listed above.

## Approval

- Human approval required before Stage 3, any engine/accounting expansion, or
  any demo/shadow/live/config change. Not obtained by this manifest.

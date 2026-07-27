---
status: current
type: manifest
owner: codex
created: 2026-07-24
last_reviewed: 2026-07-24
expires: none
superseded_by: null
---

# Change Manifest: H-022 taker-flow Stage-2 probe

## Summary

Add the E-058 Stage-2-only feasibility probe for F-TAKER-FLOW. It reads the
existing Binance 1m payload in bounded, read-only queries and stops after the
four Stage-2 checks regardless of outcome.

## Business rule(s) affected

- Existing R2 fee, R3 funding, R6.1 leakage, R6.3 trial-accounting, R6.6
  distinctness-feasibility, and R7.1 research-evidence rules are reused.
- No business-rule threshold, result schema, promotion gate, or deployment rule
  changes.

## Trigger area(s) (DOC_IMPACT_MATRIX)

- A5 backtesting.
- A9 research validation/gate tooling.
- A11 experiment registration and result recording.

## Files changed

- `backtesting/taker_flow_probe.py` - bounded Option A parsing and four Stage-2 checks.
- `backtesting/pipeline_stage2_registry.py` - fail-closed registered/direct entry paths.
- `tests/unit/test_taker_flow_probe.py` - parser, signal, and feasibility checks.
- `tests/unit/test_pipeline_stage2_registry.py` - pre-probe/pre-artifact refusal checks.
- `docs/HYPOTHESIS_LEDGER.md` - H-022 registration and final Stage-2 status.
- `docs/EXPERIMENT_REGISTRY.md` - E-058 registration, K/trial accounting, result hash.
- `results/e058_taker_flow_stage2_20260724/stage2_feasibility.json` - new E-058 evidence.
- `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md` - data path and ownership.
- `docs/change_manifests/2026-07-24-taker-flow-stage2.md` - this impact record.
- State and handoff files permitted by the E-058 task - result synchronization only.

## Behavior delta

- Before: H-022 had no executable Stage-2 probe or artifact path.
- After: E-058 parses `market_klines.raw_payload.raw[9]/[10]` without download
  or schema changes, evaluates data, distinctness, cost-after-edge, and power,
  writes one new feasibility artifact, and stops before Stage 3.
- Money/risk impact: none. The probe estimates fees, slippage, and short-leg
  funding for research only; no trading, sizing, risk, or deployment setting changes.

## Source-of-truth updates

- `research/strategy_synthesis.md`: unchanged; research ownership is excluded
  and the user-authorized H-022 spec fixes the tested direction.
- `config/`: no strategy/risk/deployment config change; any workstream edit is
  progress metadata only.
- ADR: N/A; ADR-0002/0005 and existing R6/R7 policy remain unchanged.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DATA_FLOW.md` - bounded raw-payload Stage-2 path added.
- [x] `docs/FEATURE_MAP.md` - E-058 ownership added.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no accounting/result-schema golden case changes.
- [x] `docs/INVARIANTS.md` - reviewed; existing I13/I23/I42/I45 controls apply.
- [x] `docs/DOMAIN_RULES.md` - reviewed; no rule change.
- [x] `docs/ai_collaboration.md` - reviewed; Stage-3 and deployment gates remain closed.
- [x] ADR-0002/0005 - reviewed; no artifact-schema or promotion-gate change.

## Invariants / golden cases

- Invariants checked: I13, I23, I42, I45.
- Golden cases affected: none; the deterministic signal fixture is a unit test,
  not a change to an existing golden case.

## Tests / checks run

- Targeted E-058 probe and registry tests - 27 passed.
- Full unit suite - 954 passed, 1 skipped; warnings are the existing numerical
  precision and empty-slice warnings.
- Repository-wide Ruff, config validation, backtest smoke, docs metadata,
  feature-map links, ledger consistency, `docs-impact --strict`, and
  `git diff --check` - PASS.
- Real read-only E-058 probe - completed all symbol-year chunks without a probe
  statement timeout; Stage-2 FAIL is data-only at 0.931997 coverage.

## Risks and rollback

- Risks: malformed exchange payloads or sparse PIT member-days can reduce
  coverage; insufficient or constant overlap fails closed rather than being
  imputed or treated as zero correlation.
- Rollback: revert the E-058 commits, remove only the new E-058 module, tests,
  and artifact, and revert only the H-022 documentation hunks. The probe is
  read-only, so there is no DB or schema rollback.

## Approval

- Human approval required: yes - obtained 2026-07-24 for Stage 2 only. Stage 3,
  grid execution, DSR/PSR, promotion, and deployment remain unauthorized.

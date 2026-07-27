---
status: current
type: manifest
owner: codex
created: 2026-07-21
last_reviewed: 2026-07-21
expires: none
superseded_by: null
---

# Change Manifest: H-010 Stage-2 distinctness feasibility guard

## Summary

Code-enforce R6.6/I49 before either H-010 Stage-2 probe path runs. Callers must
declare each gating reference's available date range; structurally insufficient
per-reference overlap fails closed before DB/probe/artifact activity.

## Business rule(s) affected

- R6.6: future H-010 distinctness contracts must be structurally satisfiable.
- FX1 clarification: each candidate/reference pair gates independently, matching
  `build_distinctness_check`; `overall_common_days` is advisory only.

## Trigger area(s) (DOC_IMPACT_MATRIX)

- A5 backtesting workflow.
- A9 research validation/gate tooling.

## Files changed

- `backtesting/xvenue_leadlag_probe.py` - shared pre-execution feasibility guard.
- `backtesting/pipeline_stage2_registry.py` - guard both H-010 Stage-2 entry paths.
- `tests/unit/test_xvenue_leadlag_probe.py` - E-057, feasible, joint-zero, and missing-range cases.
- `tests/unit/test_pipeline_stage2_registry.py` - pre-probe/pre-artifact entry-path regressions.
- `docs/DOMAIN_RULES.md` - R6.6 code-enforcement note.
- `docs/INVARIANTS.md` - I49 guarding tests.
- `docs/GOLDEN_CASES.md` - G-006 E-057 structural-refusal case.
- `docs/change_manifests/2026-07-21-b1-distinctness-guard.md` - this impact record.

## Behavior delta

- Before: R6.6/I49 existed only in prose, so a structurally impossible
  distinctness contract could reach the probe and artifact path.
- After: missing declarations or any candidate/reference pair below 365
  achievable common days raises an explicit contract-defect error first. Joint
  overlap is still reported but does not gate independent pair measurements.
- Money/risk impact: none. No PnL, fee, funding, sizing, fill, threshold,
  Stage-3, promotion, demo, shadow, or live behavior changes.

## Source-of-truth updates

- `research/strategy_synthesis.md`: unchanged; no strategy assumption changed.
- `config/`: unchanged; `MIN_COMMON_DAYS=365` remains fixed in code.
- ADR: N/A; this implements the existing R6.6/I49 policy and Claude's FX1
  measurement-consistency ruling rather than adding a new durable policy.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` - R6.6 enforcement point recorded.
- [x] `docs/INVARIANTS.md` - I49 now points to executable regressions.
- [x] `docs/GOLDEN_CASES.md` - G-006 records the E-057 refusal boundary.
- [x] `docs/DATA_FLOW.md` - confirmed unchanged; no data or artifact path changed.
- [x] `docs/FEATURE_MAP.md` - confirmed unchanged; ownership and entry paths are unchanged.
- [x] ADR-0002/0005 - confirmed unchanged; no result schema or replay gate changed.
- [x] `docs/ai_collaboration.md` - confirmed unchanged; deployment gates are untouched.

## Invariants / golden cases

- Invariants checked: I45, I49.
- Golden cases affected: G-006 added; immutable E-057 output remains unchanged.

## Tests / checks run

- Targeted Stage-2 guard/registry unit tests: 24 passed.
- Full `tests/unit/` suite: 927 passed, 1 skipped; full Ruff: passed.
- Metadata, feature-map link, ledger-consistency, and strict doc-impact: passed.
- Backtest smoke: passed (idealized fixture, not promotion evidence).
- E-057 artifact SHA-256 before/after comparison: byte-identical.

## Risks and rollback

- Risks: an inaccurate caller declaration can overstate structural feasibility;
  existing observed-data checks still fail closed on actual common dates.
- Rollback: revert the single B1 guard commit. No DB row, experiment record, or
  result artifact needs migration or deletion.

## Approval

- Human approval required: yes - obtained 2026-07-21. The user authorized the
  B1 guard and, after Claude review, explicitly expanded the whitelist for FX2.

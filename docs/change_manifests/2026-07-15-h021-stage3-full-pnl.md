---
status: current
type: manifest
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Change Manifest: H-021 Stage-3 full-PnL checkpoint

## Summary

Implement the one-run H-021/E-056 research checkpoint using the frozen
cross-venue signal, accepted ADR-0012 inverse-perpetual accounting, and existing
fold-refit/minting/checkpoint harnesses.

## Business rule(s) affected

R3.1, R5.3, R6.1, R6.3, R7.4, and R9.1-R9.6 are implemented unchanged. No rule,
gate, production setting, or strategy assumption changes.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting, A9 validation evidence, A11 experiment, and A12
coin-margined-derivatives research accounting.

## Files changed

- `backtesting/xvenue_funding_spread_backtest.py` — standalone full-PnL runner.
- `backtesting/pipeline_stage3_registry.py` — register the authorized family.
- `tests/unit/test_h021_inverse_perp_accounting.py` — I44/G-005 golden cycle.
- `docs/superpowers/specs/2026-07-15-f-xvenue-funding-spread-hypothesis.md` —
  pre-run Stage-3 addendum only.
- `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md` — ownership,
  data path, run/rollback instructions.
- `docs/GOLDEN_CASES.md`, `docs/INVARIANTS.md` — enforce G-005/I44.
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` — E-056 result
  record after the one run.
- Session/context handoffs — result and Claude review boundary.

## Behavior delta

- Before: H-021 stopped at funding-only Stage 2 and could not measure basis PnL.
- After: one standalone research runner can produce full Binance-linear plus
  Deribit-inverse pair PnL and checkpoint artifacts from venue-scoped marks.
- Money/risk impact: research output only. It adds exact R9 basis/funding/cost
  accounting; no portfolio, execution, risk, engine, config, or deployment path.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — frozen hypothesis spec is the
  user-authorized source; research ownership is forbidden for this task.
- `config/`: N/A — fixed research costs come from the frozen contract, not a
  production configuration change.
- ADR: ADR-0012 already accepted and unchanged.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DATA_FLOW.md` — Stage-3 event/accounting/artifact flow.
- [x] `docs/FEATURE_MAP.md` — runner/registry/test ownership and checkpoint scope.
- [x] `docs/GOLDEN_CASES.md` — G-005 hand-computed cycle.
- [x] `docs/INVARIANTS.md` — I44 now has its enforcing test.
- [x] `docs/RUNBOOK.md` — ordered one-run and checkpoint commands.
- [x] ADR-0002/0005 — reviewed; result schema and replay gates are unchanged.
- [x] ADR-0012 / `docs/DOMAIN_RULES.md` R9 — reviewed; implemented unchanged.
- [x] `docs/FAILURE_MODES.md` — reviewed; no new bug class discovered.
- [x] `docs/KNOWN_ISSUES.md` — reviewed; no durable implementation gap added.

## Invariants / golden cases

- Invariants checked: I4, I19, I23-I25, I27, I41, I43, I44.
- Golden cases affected: G-005 added; existing cases unchanged.

## Tests / checks run

- I44 targeted test — 2 passed before any grid.
- Stage-3 registry + I44 targeted tests — 7 passed.
- Full unit suite — 874 passed, 1 skipped before any grid.
- Remaining run/artifact/docs checks are filled in after E-056.

## Risks and rollback

- Risks: wrong funding sign, lookahead, event compression, mark substitution,
  inverse linearization, or trial-count drift could create plausible false PnL.
- Rollback: revert the H-021 implementation/docs commits. Preserve any generated
  E-056 directory as immutable inspected evidence; never overwrite it.

## Approval

- Human approval required: yes — obtained in the explicit E-056 task on
  2026-07-15. Claude adversarial review remains required after checkpoint ①.

---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Session Handoff: H-021/E-056 Stage-3 full-PnL — 2026-07-15

## Implementation summary

Pre-registered, implemented, tested, and ran the first and only authorized
H-021 Stage-3 full-PnL checkpoint. The exact four-cell R9 runner failed both the
DSR/PSR and stress-selection gates; H-021 is recorded as refuted and remains
promotion-blocked.

## Diff scope

- Files added: H-021 runner, I44 test, A5/A12 Change Manifest, context handoff,
  and session handoff.
- Files changed: Stage-3 registry, frozen spec addendum, Feature/Data Flow,
  RUNBOOK, G-005/I44 docs, H-021 ledger, E-056 registry.
- Files deleted: none.

## Business-rule change?

- Yes: accepted R9 behavior is newly implemented in backtesting. Manifest:
  `docs/change_manifests/2026-07-15-h021-stage3-full-pnl.md`; DOC_IMPACT rows
  A5/A9/A11/A12 checked. No business rule or gate value changed.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; forbidden and unnecessary.
- `config/`: N/A; no production/runtime setting changed.
- ADR: ADR-0012 reused unchanged.

## Experiments

- HYPOTHESIS_LEDGER entries: H-021 cumulative trials 12, status `refuted`.
- EXPERIMENT_REGISTRY entries: E-056; family K stays 0/2.

## Tests / checks run

- I44 targeted: 2 passed before grid.
- Registry + I44 targeted: 7 passed.
- Full unit: 874 passed, 1 skipped before grid.
- Final full unit rerun: 874 passed, 1 skipped.
- Targeted Ruff, docs metadata/links/ledger, strict docs impact: PASS.
- DB preflight: 2,739 events per symbol.
- E-056: executed once; no retry.
- Checkpoint auto: FAIL only because DSR/PSR < 0.95; all structural checks PASS.

## Docs updated

- Frozen spec Stage-3 addendum, manifest, FEATURE_MAP, DATA_FLOW, RUNBOOK,
  GOLDEN_CASES, INVARIANTS, HYPOTHESIS_LEDGER, EXPERIMENT_REGISTRY, handoffs.

## Known limitations / risks

- Standalone research path has no margin/liquidation or portable reference
  adapter; adequate coin collateral is assumed for the unlevered gross-1 pair.
- BTC/ETH pair returns are equal-mean aggregated; Claude should verify this
  interpretation independently.

## Rollback plan

- Revert `f1f5326`, `9ffe142`, and the final records commit. Preserve the
  inspected E-056 directory as immutable failed evidence; never overwrite it.

## Context Handoff

- See `tasks/2026-07-15-h021-stage3-context-handoff.md`.

## Questions for human review

- None before Claude review. A new experiment would require a new ex-ante
  rationale and explicit authorization; this task grants no retry.

## Next recommended task

- Claude adversarial review of accounting, event timing, path retention,
  family minting, stress selection, and the `refuted` verdict.

## Human Learning Notes (required)

Rules-before-code and I44-before-grid caught the high-risk inverse/funding unit
boundary before real data ran. The final failure is therefore useful evidence,
not an infrastructure ambiguity: inputs were complete, accounting was golden-
anchored, and the registered statistical threshold simply was not met.

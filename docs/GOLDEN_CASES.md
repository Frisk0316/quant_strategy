---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Golden Cases

Reference scenarios with **known-correct expected outputs**. They anchor
correctness: when behavior changes, a golden case either still matches (good) or
breaks (investigate before "fixing" the case). Golden cases make the abstract
[[INVARIANTS]] concrete and reviewable.

A golden case is not a substitute for the unit/integration tests that enforce it
— it is the human-readable specification the test encodes.

## Registry

| ID | Scenario | Fixed inputs | Expected output | Guards | Enforcing test |
|---|---|---|---|---|---|
| G-000 | _example: single BTC-SWAP long, open then close at +Δ_ | _ct_val, entry/exit px, fee, qty_ | _realized PnL = qty·ct_val·Δ − fees_ | I1, I2 | _tests/unit/..._ |
| G-001 | Same BTC-SWAP MA crossover replay on OKX vs Binance venue specs | Same strategy/params on a synthetic BTC-USDT-SWAP 1H parquet fixture; OKX `ctVal=0.01`; Binance `ctVal=1.0`; both via `instrument_specs` override | Metrics match within `1e-6` because `ct_val` cancels under notional sizing; any real venue divergence should be lot-rounding/fee/funding, and run validation carries the selected `exchange` | I1, I16 | `tests/unit/test_multi_venue_convergence.py` |

## What makes a good golden case

- **Deterministic.** Fixed inputs, fixed seed, no wall-clock or network
  dependence.
- **Hand-verifiable.** The expected output can be computed by hand or from first
  principles, so it does not just encode current (possibly wrong) behavior.
- **Targets a specific invariant or failure mode.** Cite the [[INVARIANTS]] /
  [[FAILURE_MODES]] id it guards.
- **Small.** The minimal scenario that exercises the property.

## Rules

- Changing a golden case's expected output is a business-rule change: it needs a
  Change Manifest and, if it reflects a rule change, an ADR.
- If a code change breaks a golden case, the default assumption is the code is
  wrong, not the case. Justify any expected-output change explicitly.
- New accounting/fill/funding logic should add a golden case before it is
  considered done.

Related: [[INVARIANTS]] · [[FAILURE_MODES]] · [[EXPERIMENT_REGISTRY]].

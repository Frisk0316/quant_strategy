---
status: current
type: template
owner: codex
created: 2026-06-25
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Stage 2 Template: Feasibility Gate

Role: research, Claude. No implementation beyond cheap probes.

Stage 2 runs before implementation so dead ideas are killed cheaply.

## Checks

All must pass:

- Data availability: required series exist in DB for promotion-grade work or in
  parquet for research-tier pre-screen, for the required universe and window.
  Missing data fails the candidate and records the data gap in the ledger.
- Correlation distinctness: the signal is economically distinct from currently
  enabled strategies and not a relabel of an existing family.
- Cost-after-edge smell test: a cheap sample-window estimate suggests the raw
  signal can plausibly exceed maker plus slippage cost. This is not a backtest.
- Statistical power: use the cost-after-edge plausible annualized net Sharpe,
  frozen-window OOS observation count, independent-bet breadth, and honest
  family-cumulative `n_trials` to compute the smallest observed Sharpe that
  clears both PSR and DSR at 0.95. This is deterministic triage, not a backtest
  or a deployment gate.

## Output

- PASS: proceed to Stage 3.
- FAIL: skip the candidate, record the reason in the ledger, and count 0 grid
  trials for this skipped experiment.

A statistical-power FAIL can be overridden only by written ex-ante rationale.
The artifact retains `measured_status: FAIL`, both Sharpe values, and the
rationale; blank rationale does not override. This mirrors the family retry/K
rule and cannot turn a later Stage 3 statistical failure into a pass.

## Statistical-Power Calculation

The implementation uses the current one-tailed PSR/DSR definition and daily
crypto annualization (`365`). Let `A = n_obs * breadth - 1`,
`q = Phi^-1(0.95)`, and

```text
c(N) = (1-gamma) Phi^-1(1-1/N) + gamma Phi^-1(1-1/(N e))
gamma = 0.5772156649
```

with `c(1)=0`. The ex-ante DSR benchmark is `c(N)/sqrt(A)`. The PSR and DSR
equations are inverted in per-observation Sharpe units, using skew `0` and
Pearson kurtosis `3` unless sample estimates are supplied, then the smallest
valid root is annualized. Breadth multiplying `n_obs` is an explicit planning assumption;
callers must not count the same rebalance twice in both inputs.
The threshold dataclass rejects PSR or DSR probabilities below `0.95`.
For the ratified reference inputs `breadth=1`, `n_obs=900`, `n_trials=4`,
PSR/DSR `0.95`, skew `0`, and kurtosis `3`, the computed annualized floor is
`1.7206`. This is not a hard-coded floor for other inputs.

## Machine-Readable Output

Every Stage 2 run writes `stage2_feasibility.json` beside the candidate output.
The artifact is validated by `scripts/run_pipeline_stage2_check.py`.

Required checks:

- `data_availability`
- `distinctness`
- `cost_after_edge`
- `statistical_power`

For new registry-written artifacts, `stage2_status` is `PASS` only when the
original three checks and `statistical_power` are present and pass. Active
callers reject missing inputs before DB access, probe execution, artifact write,
or candidate status mutation. A defensive direct writer still inserts a
fail-closed missing-input check. Immutable legacy artifacts remain readable.

Existing immutable artifacts are not migrated. The funnel reports a legacy
artifact without `statistical_power` as not power-feasible; every new artifact
written through the Stage 2 registry gets either the computed check or a
fail-closed missing-input check.

The registered data-probe CLI requires `--breadth`, `--n-obs`, `--n-trials`, and
`--plausible-net-sharpe` for one explicit candidate. The orchestrator accepts a
JSON object keyed by `candidate_id`; unimplemented families do not require
fabricated values. Effective trials are the
larger of the registry's realized family cumulative count and the caller's
written ex-ante cumulative count, so planned trials are included but prior
trials cannot be erased. Missing registry family accounting fails closed.

Example:

```json
{
  "schema_version": 1,
  "batch_id": "idea_batch_20260713_taxonomy_003",
  "candidate_id": "C-2-f-onchain-flow",
  "candidate_dir": "f_onchain_flow",
  "hypothesis_id": "H-019",
  "family_id": "F-ONCHAIN-FLOW",
  "checks": [
    {
      "name": "data_availability",
      "status": "PASS",
      "reason": "frozen-window BTC and hash-rate observations are available"
    },
    {
      "name": "distinctness",
      "status": "PASS",
      "reason": "on-chain miner stress is distinct from occupied price families"
    },
    {
      "name": "cost_after_edge",
      "status": "PASS",
      "reason": "plausible annualized net Sharpe after costs is 0.6"
    },
    {
      "name": "statistical_power",
      "status": "FAIL",
      "reason": "plausible_net_sharpe=0.6000 < min_detectable_sharpe=1.7206",
      "details": {
        "breadth": 1.0,
        "n_obs": 900,
        "n_trials": 4,
        "grid_trials_on_unoverridden_fail": 0
      }
    }
  ],
  "stage2_status": "FAIL"
}
```

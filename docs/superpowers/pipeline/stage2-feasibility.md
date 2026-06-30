---
status: current
type: template
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
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

## Output

- PASS: proceed to Stage 3.
- FAIL: skip the candidate, record the reason in the ledger, and count 0 grid
  trials for this skipped experiment.

## Machine-Readable Output

Every Stage 2 run writes `stage2_feasibility.json` beside the candidate output.
The artifact is validated by `scripts/run_pipeline_stage2_check.py`.

Required checks:

- `data_availability`
- `distinctness`
- `cost_after_edge`

`stage2_status` is `PASS` only when all required checks are present and all
required checks have status `PASS`. Missing checks and failed checks both produce
`FAIL`.

Example:

```json
{
  "schema_version": 1,
  "batch_id": "pipeline_batch2_20260625",
  "candidate_id": "c3_sentiment",
  "candidate_dir": "c3_sentiment",
  "hypothesis_id": "H-008",
  "family_id": "F-SENTIMENT",
  "checks": [
    {
      "name": "data_availability",
      "status": "FAIL",
      "reason": "fear_greed_btc event_count=0"
    },
    {
      "name": "distinctness",
      "status": "PASS",
      "reason": "sentiment family is distinct from currently enabled price-only strategies"
    },
    {
      "name": "cost_after_edge",
      "status": "FAIL",
      "reason": "cost smell test cannot run without the required external feature"
    }
  ],
  "stage2_status": "FAIL"
}
```

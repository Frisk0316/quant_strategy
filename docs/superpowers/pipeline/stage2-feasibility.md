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

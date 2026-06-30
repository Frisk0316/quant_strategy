# Paper Scoring Rubric

Use this rubric before an alpha candidate is promoted into a backtest config.
Scores use `0` as unusable and `5` as strongest fit.

## Positive Criteria

| Field | Score 0 | Score 3 | Score 5 |
| --- | --- | --- | --- |
| `evidence_quality` | Anecdotal or untested | Backtest or empirical evidence with caveats | Out-of-sample, robust, or causal evidence |
| `crypto_relevance` | Non-crypto only | Similar market structure | Direct crypto spot/perp evidence |
| `data_availability` | Data unavailable locally | Data can be approximated | Data maps cleanly to existing feeds |
| `implementation_fit` | Requires a new system | Partial fit | Maps to existing backtest paths |
| `cost_awareness` | Ignores fees/slippage | Mentions costs | Models fees, spread, fill, or funding |
| `novelty` | Already covered | Useful variant | Distinct alpha or risk-control angle |

## Risk Penalties

| Field | Score 0 | Score 3 | Score 5 |
| --- | --- | --- | --- |
| `leakage_risk` | No obvious leakage | Some timing ambiguity | Serious lookahead risk |
| `overfit_risk` | Simple and stable | Many parameters | Heavy search or black-box risk |

## Promotion Guidance

- `priority_score >= 3.8`: eligible for alpha candidate spec.
- `priority_score >= 3.2`: keep on watchlist or use as supporting evidence.
- `priority_score < 3.2`: do not prioritize unless it is negative evidence or
  a validation baseline.

Priority does not imply deployability. Any candidate still needs cost-aware,
walk-forward or CPCV validation before parent-framework integration.

---
status: current
type: task
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Paper-data limited-probe post-run governance audit

## Finding

The immutable run artifacts are numerically reproducible, but their Stage-2
power breadth did not comply with ADR-0013. The frozen runner inferred breadth
from the median number of nonzero executed legs. ADR-0013 requires breadth to
be supplied before database access and to count only independently justified
bets; it explicitly leaves BTC/ETH breadth of two unconfirmed.

The pre-registration spec named candidate breadth but did not justify leg
independence. Therefore the reported Stage-2 passes for H-041, H-045, and H-046
are not governance-valid, and their Stage-3 artifacts are diagnostic only.

## Conservative reconciliation

The same retained `n_obs`, sample skew, sample kurtosis, periods/year, and
prospective `n_trials=1` were re-evaluated with `breadth=1`. No strategy
parameter, PnL series, or result artifact was changed.

| Hypothesis | Artifact breadth | Artifact MDS | Breadth-1 MDS | Plausible Sharpe | Corrected power status |
|---|---:|---:|---:|---:|---|
| H-040 | 1 | 0.633390 | 0.633390 | -0.106027 | FAIL |
| H-041 | 2 | 0.451837 | 0.638354 | 0.567076 | **FAIL** |
| H-043 | 10 | 0.332365 | 1.057945 | -0.606531 | FAIL |
| H-044 | 2 | 0.453319 | 0.641359 | -0.085968 | FAIL |
| H-045 | 2 | 0.441050 | 0.618692 | 0.542492 | **FAIL** |
| H-046 | 2 | 0.453966 | 0.642546 | 0.483769 | **FAIL** |

H-042 had zero active observations and already failed data availability; a
power floor was unavailable.

## Evidence interpretation

- The canonical terminal artifacts remain immutable and truthfully describe
  what the frozen runner executed: seven terminal FAILs, with H-041/H-045/H-046
  reaching Stage 3 and failing DSR/PSR.
- Governance reconciliation is stricter: all seven stop at Stage 2 under the
  independently justified `breadth=1` contract. The three Stage-3 metrics may
  guide future data research but cannot serve as gate, near-pass, promotion,
  shadow, demo, or live evidence.
- H-041/H-045/H-046 each retain one family trial because their Stage-3 results
  were actually observed. Invalidating eligibility does not erase selection
  information. K remains 0/2 because each was the family's first validation.
- H-040/H-043/H-044 retain their exact-spec negative-edge interpretation;
  their cost-after-edge failure does not depend on the breadth correction.

## Root-cause repair

`CandidateSpec` now requires an explicit finite positive `power_breadth`, all
current limited-probe candidates conservatively declare `1.0`, the contract is
validated before receipt validation/database access, and `_power_check` no
longer infers breadth from active legs. A focused regression proves that a
two-leg BTC/ETH target still uses breadth one and rejects an invalid breadth.

The frozen run was not rerun or retuned. Its receipt is intentionally stale
after the post-run ledger and source corrections, so it cannot authorize a
second execution.


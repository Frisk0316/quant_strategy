---
status: accepted
type: adr
owner: codex
created: 2026-07-16
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# ADR-0013: Stage-2 Statistical-Power Triage

## Status

Accepted — 2026-07-16 through the user's explicit Task A authorization.
Research-pipeline triage only; no Stage-3, promotion, demo, shadow, or live gate
is relaxed or replaced.

Claude's independently reproduced reference floor and the five-line evaluator
scope expansion were ratified by the user on 2026-07-17.

## Context

Several candidates with short history or low independent-bet breadth reached
Stage 3 before failing PSR/DSR for a limitation predictable from frozen-window
length, plausible cost-after-edge Sharpe, and honest family trial count. That
spends compute and can spend K without adding useful evidence. The check must
run before a backtest, while immutable legacy artifacts and the existing
Stage-3 statistical gate remain intact.

## Decision

1. New artifacts written through the registered Stage-2 path contain a fourth
   `statistical_power` check. Active callers must supply all four candidate-
   specific inputs before DB access, probe execution, artifact write, or status
   mutation. Invalid screen values fail closed in the check; a defensive direct
   writer still cannot serialize a power pass from missing inputs.
2. The check computes the smallest annualized Sharpe clearing both one-tailed
   PSR and DSR at probability `0.95`, using the repository's current equations,
   `365` periods/year, and normal skew/Pearson-kurtosis defaults (`0`/`3`) unless
   explicit sample moments are supplied.
3. Effective observations are `n_obs * breadth`. Breadth means independently
   justified bets; callers must not count the same rebalance in both inputs.
4. Effective trials are the greater of realized family-cumulative trials read
   from `docs/EXPERIMENT_REGISTRY.md` and a written ex-ante cumulative count for
   the candidate being screened. A caller cannot erase prior trials.
5. A measured failure records zero grid trials. It can proceed only with a
   nonblank written ex-ante rationale, while retaining `measured_status: FAIL`,
   both Sharpe values, and the rationale in the artifact.
6. The check can only fail fast or permit Stage 3 to evaluate the unchanged
   gate. It cannot convert a later Stage-3 failure into a pass.
7. Immutable legacy three-check artifacts remain readable and are not migrated.
   The derived funnel treats missing power evidence as not power-feasible.
8. The ratified reference case (`breadth=1`, `n_obs=900`, `n_trials=4`,
   PSR/DSR=0.95, 365 periods/year, skew=0, kurtosis=3) yields an annualized
   minimum detectable Sharpe of `1.7206`. It is a computed case, not a universal
   hard-coded floor.

## Consequences

- Low-power candidates can stop before Stage-3 compute/K, with auditable trial
  provenance and no PnL calculation.
- The direct CLI and funding backfill reject omitted inputs before probing. The
  orchestrator carries a `candidate_id -> inputs` mapping on both first run and
  reprobe; no global or inferred breadth/Sharpe defaults exist.
- Malformed Stage-2 artifacts are isolated in funnel schema v3 under
  `stage2_artifact_errors`; valid families remain observable.
- Independent-bet breadth is the material modeling assumption. BTC/ETH breadth
  of two remains UNCONFIRMED until independence is justified.
- A static funnel projection may summarize all ledger/registry families, but the
  Markdown ledgers remain authoritative and the projection is not promotion
  evidence.
- No existing result artifact, PSR/DSR threshold, Stage-3 grid, PnL rule, or
  deployment gate changes.

## Alternatives considered

- Keep power checks after Stage 3: rejected because predictable failures keep
  consuming compute/K.
- Make power a new promotion gate: rejected because the existing Stage-3 gate
  remains the evidence boundary; this decision is triage only.
- Infer a smaller per-run trial count: rejected because it understates selection
  bias and violates R6.3/I23.

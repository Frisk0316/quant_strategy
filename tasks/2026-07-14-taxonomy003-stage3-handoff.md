---
status: current
type: handoff
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Session Handoff: Taxonomy_003 Stage-3 sweep + H-014 Stage-2 PASS — 2026-07-14

## Goal (one sentence)

Per user authorization: backfill pre-2024 hourly DVOL, run performance
backtests for all six taxonomy_003 candidates end-to-end (Claude solo), and
complete the H-014 Stage-2 calibration.

## Implementation summary

Backfilled hourly DVOL 2021→2024; pre-registered all grids/directions in
`docs/superpowers/specs/2026-07-14-taxonomy003-stage3-specs.md` BEFORE any
run; fetched DefiLlama/Coinbase/blockchain.info signal data; ran E-044..E-049
through `backtesting/pipeline_refit.refit_validation` + family minting via
`research/probes/taxonomy003_stage3.py`. All six MINT; all six FAIL the
DSR/PSR ≥ 0.95 gate. E-043 rerun of the H-014 calibration completed 12/12
pairs with verdict PASS.

## Current state / diff scope

- Nothing committed (tree holds multiple sessions' uncommitted work).
- Added: taxonomy003 spec; `research/probes/{taxonomy003_stage3.py,
  taxonomy003_fetch_external.py}`; six family result dirs +
  `data/` under `results/idea_batch_20260713_taxonomy_003/`;
  `results/stage2_probe_20260714_f_vol_regime_opt_r2/`; this file.
- Changed: HYPOTHESIS_LEDGER (H-014..H-020), EXPERIMENT_REGISTRY
  (E-043..E-049 + 6 K rows), CURRENT_STATE, AI_HANDOFF, workstreams.yaml,
  CHANGELOG_AI. DB: `external_observations` +48,624 hourly DVOL rows.

## Business-rule change? / Source-of-truth updates

No business-rule change. strategy_synthesis.md untouched (nothing survived).
No ADR/config gates. DVOL backfill used the existing documented ingest CLI.

## Experiments

- E-043 stage2_complete/verdict_PASS (H-014). E-044 refuted (H-015),
  E-045 shelved (H-016), E-046 inconclusive (H-017), E-047 refuted (H-018),
  E-048 shelved (H-019), E-049 refuted (H-020). All 0-K originals.

## Decisions made (and why)

- Verdicts follow sign pattern: both-negative OOS → refuted; positive but
  sub-gate → shelved; mixed one-regime → inconclusive. No retry entitlements.
- Minting claim passed as "NEW" (first run mistakenly passed the family id
  and read ASSIGN; corrected and re-run — correlations were tiny either way).

## Open questions / unverified assumptions

- Verifier MINORs: XS ±0.10 cap binds on small-universe days (gross below
  0.5/leg design); vol lever double-lagged (conservative); `leak_shift_path_live`
  field name overclaims. Any K-consuming retry must fix these ex-ante.

## Rules in play / do-not-touch

- I13 (grids pre-registered), I23 (caller-declared n_trials), I26/I27
  (minting, budgets), F26 (published_at as-of). Untouched: strategy/risk/
  execution src, config gates, existing artifacts, other sessions' edits.

## Checks run

- `check_ledger_consistency.py` — pass (21 H / 49 E / 20 K);
  `check_doc_metadata.py` — pass. Fresh-verifier agent on the runner: no
  leakage findings, 3 MINORs (annotated in E-045).

## Approvals

- Obtained: DVOL backfill + six Stage-3 runs (user, 2026-07-14).
- NOT obtained: H-014 Stage-3 (chain data purchase + engine manifest/ADR);
  any retry of the six failed families.

## Next action (single, concrete)

User decides the H-014 path: Tardis chain-history purchase (~$3k/mo Business
or a one-off quote) + authorize the options-backtest MVP (Change Manifest +
ADR first). It is now the only candidate with a passed Stage 2.

## Human Learning Notes (required)

Six pre-registered mechanisms, honestly costed and fold-refit validated, all
failed the anti-overfit gate on 2.5 years — the gate is doing its job; the
temptation to loosen thresholds after seeing 0.70–0.85 DSRs is exactly what
K-budgets exist to stop. Meanwhile the options thread (H-014) passed its
pricing-reality check the same day: real 25Δ/ATM premiums are 0.88–1.03× the
DVOL-synthetic estimate once the IV timestamp is aligned — the edge lives in
regime selection, not in mispriced synthetics.

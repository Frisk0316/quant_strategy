---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Session Handoff: taxonomy_004 cross-venue funding Stage 2 — 2026-07-15

## Implementation summary

Read the repository collaboration/context/governance sources, inventoried the
locally runnable strategy surfaces, generated taxonomy_004 through the existing
idea pipeline, implemented a minimal C4 Stage-2 probe, ran it on local DB data,
fixed and recorded F41 without overwriting evidence, and stopped at the correct
fail-closed boundary. E-054 has complete funding alignment and provisional
distinctness but fails full-data and conservative-cost gates; no full backtest
or deployment work ran.

## Diff scope

- Files added: C4 probe, focused unit test, two specs, manifest, and this C4
  context/session handoff pair.
- Files changed: Stage-2 registry; H/E ledgers; F41-I43; Feature/Data maps;
  AI handoff/current state/changelog/workstreams with C4-only additions.
- Files deleted: none.
- Generated local artifacts: `results/idea_batch_20260715_taxonomy_004/`.
- Concurrent non-C4 worktree changes were preserved and are excluded from this
  task's ownership/rollback.

## Business-rule change?

- No rule text changed; research mechanics were added under existing rules.
  Change Manifest: `docs/change_manifests/2026-07-15-xvenue-funding-spread-stage2.md`.
  DOC_IMPACT rows reviewed: A5, A9, A11.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; not modified.
- config/: only `config/workstreams.yaml` C4 progress metadata; no strategy,
  fee, risk, execution, or deployment config changed.
- ADR: N/A; Stage 3/inverse-perp accounting remains unopened.

## Experiments

- HYPOTHESIS_LEDGER entries: H-021, `inconclusive`, cumulative proxy n_trials=8.
- EXPERIMENT_REGISTRY entries: E-053 invalid (4), E-054 corrected Stage-2 fail
  (4); K remains 0/2.

## Tests / checks run

- Expanded focused pipeline/probe suite: 49 passed.
- Idea generator: 1 selected, 0 skipped in final taxonomy_004 batch.
- DB-backed orchestrator + bounded reprobe: completed; final status Stage-2 FAIL.
- Docs metadata, feature links, ledger consistency, doc impact: passed.
- Ruff on touched Python and config validation: passed; strict doc impact passed.
- Backtest smoke: passed on frozen MA fixture; smoke/idealized only.
- `make docs-check`, `make docs-impact`, `make backtest-smoke`: not runnable
  because GNU Make is absent; exact Python equivalents were used.

## Docs updated

- Stage-1/taxonomy specs, manifest, H/E ledgers, failure modes/invariants,
  Feature Map, Data Flow, AI handoff/current state/changelog/workstreams, and
  paired handoffs.
- UI_MAP/RUNBOOK/GOLDEN_CASES/ADR reviewed; no C4 change required.

## Local strategy inventory

- Replay CLI/API/UI loadable now: `ma_crossover`, `ema_crossover`,
  `macd_crossover`, `funding_carry`, `pairs_trading`,
  `fear_greed_sentiment`, and `cme_gap_fill` (the last requires the existing
  `cme_btc_yfinance` dataset override because config names a missing dataset).
- Separate local runners/API surfaces: `ohlcv_rotation`, `daily_winner`, and
  Turtle. Turtle is parity/validation evidence; Daily Winner is explicitly
  validation-only.
- H-014/F-VOL-REGIME-OPT is the only supported alpha family and can be
  reproduced locally into a new registered scratch output, but its frozen
  artifacts must not be overwritten and it remains promotion-blocked pending
  ADR-0011 shadow evidence.
- `funding_carry`, `pairs_trading`, and sentiment are technically runnable but
  their research hypotheses are refuted/shelved. H-009 funding XS remains
  `testing` below gate and has no safe general rerun CLI; its checkpoint runner,
  OI positioning, and taxonomy_003 runners can overwrite frozen outputs and are
  not listed as directly loadable.

## Known limitations / risks

- Funding proxy omits Deribit perp mark/basis PnL, inverse collateral FX,
  margin/liquidation, ct_val/lot rules, and executable fills.
- Distinctness is a feature proxy, not final MINT/human mechanism review.
- The base-cost positive cells are fragile; conservative costs fail on BTC and
  L9/H2 has only four episodes.
- A future run must start with family cumulative n_trials >=8 and cannot treat
  E-053 as valid evidence.

## Rollback plan

- Revert only the C4 probe/registry/test, C4-specific docs/ledger additions and
  workstream entry, then remove the new taxonomy_004 results directory. Do not
  revert or delete concurrent H-014/liquidation changes. E-053/E-054 evidence
  should remain immutable if governance history is retained.

## Context Handoff

- See `tasks/2026-07-15-xvenue-funding-spread-stage2-context-handoff.md`.

## Questions for human review

- Is a separate task to acquire authoritative historical Deribit perpetual
  prices/specs justified despite the conservative-cost failure?
- Claude should review the economic novelty claim and the 5+2 bps stress; no
  retune should be proposed from the observed four-cell table.

## Next recommended task

- Stop C4. Continue H-014's already-approved manual shadow evidence collection,
  or open a separate Deribit perp data decision only after human/Claude review.

## Human Learning Notes (required)

The pipeline did its job by rejecting a superficially attractive data-rich idea
before an expensive/full runner was built. Exact timestamp matching and missing
0.5 leg normalization were the two ways this candidate could have been made to
look stronger than it is. Counting invalid inspected grids preserved the honest
selection history; keeping K at zero preserved the separate retry policy.

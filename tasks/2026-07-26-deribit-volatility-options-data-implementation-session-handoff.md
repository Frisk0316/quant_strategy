---
status: current
type: handoff
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Session Handoff: Deribit volatility and full option-chain data — 2026-07-26

## Implementation summary

Added BTC/ETH Deribit historical-volatility datasets using the existing external
observation model, changed option-surface snapshots from top-20 OI samples to the
complete normalized current chain, fixed option-flow pagination's missing sort
contract, and topped up the reachable Deribit data in local TimescaleDB.

## Diff scope

- Files added:
  `tasks/2026-07-26-deribit-volatility-options-data-implementation-context-handoff.md`,
  this session handoff.
- Files changed: Deribit external clients, generic external ingestion wiring,
  external dataset config, three unit-test files, and the directly owning data
  docs.
- Files deleted: none.

## Business-rule change?

- No. Existing R6.2 provenance/coverage rules were enforced; no trading,
  accounting, sizing, fill, or gate behavior changed. No Change Manifest or ADR
  was required.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; untouched.
- config/: `config/external_data.yaml` adds optional
  `hv_deribit_btc_1h` / `hv_deribit_eth_1h`.
- ADR: N/A.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- `pytest` targeted Deribit/external suite — 22 passed.
- Targeted `ruff check` — passed.
- `python scripts/validate_pipeline.py --check-config-only` — passed.
- Real ingestion and SQL coverage verification — completed.
- Final docs checks are recorded in the task completion response.

## Docs updated

- `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/RUNBOOK.md`,
  `docs/KNOWN_ISSUES.md`, `docs/manual/40-data-pipeline.md`,
  `docs/FAILURE_MODES.md` (F54), and `docs/INVARIANTS.md` (I51).

## Known limitations / risks

- Historical volatility begins at the public endpoint's recent rolling window;
  it cannot be backfilled to 2024 from this endpoint.
- Full per-strike option-chain history begins with the new snapshots; the two
  older aggregate snapshots cannot be expanded retrospectively.
- BTC/ETH option flow has a provider-visibility gap from
  `2026-07-21T13:00Z` through `2026-07-25T09:00Z`; checkpoints were rewound so
  it remains retryable.
- No scheduled tasks are registered, so data will become stale without manual or
  user-approved scheduled refresh.

## Rollback plan

- Revert the listed code/config/docs/test files; no DB schema rollback is needed.
- Delete only `hv_deribit_btc_1h` / `hv_deribit_eth_1h` observations and the two
  2026-07-26 option-surface snapshot rows if the ingested data itself must be
  removed. Existing DVOL/funding/option-flow upserts are idempotent.

## Context Handoff

- See
  `tasks/2026-07-26-deribit-volatility-options-data-implementation-context-handoff.md`.

## Questions for human review

- Should the four unregistered Deribit refresh tasks remain manual, or should a
  separate explicitly approved operations task register them?

## Next recommended task

- Retry and verify the 93 missing option-flow hourly buckets after the history
  host catches up; do not start strategy work from these datasets without
  Claude review.

## Human Learning Notes (required)

An API returning 1,000 valid trades plus `has_more=true` is not evidence that
pagination is correct. The sort direction must be explicit, and adjacent live
and history endpoints need an overlap audit before coverage is called complete.

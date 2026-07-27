---
status: current
type: handoff
owner: codex
created: 2026-07-27
last_reviewed: 2026-07-27
expires: none
superseded_by: null
---

# Session Handoff: Deribit RV30 history and frontend fetch — 2026-07-27

## Implementation summary

Added separately labeled BTC/ETH 30-day realized-volatility datasets using
contiguous Deribit perpetual hourly closes, backfilled them to 2021, and added
a Deribit BTC/ETH option to the existing frontend fetch queue for DVOL, native
HV, RV30, and current complete option-chain snapshots.

## Diff scope

- Files added: this session handoff and its paired context handoff.
- Files changed: Deribit external client/export wiring, external dataset config,
  data API, Market Data Coverage UI, three targeted test files, and owning
  data/UI/runbook/state/governance docs.
- Files deleted: none.

## Business-rule change?

- No. Existing R6.2 provenance/coverage was enforced. No Change Manifest or ADR
  was required; `docs-impact` passed.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; untouched.
- `config/`: `external_data.yaml` registers on-demand RV30 and
  `workstreams.yaml` records the completed data/UI slice.
- ADR: N/A.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- Targeted pytest: 44 passed.
- Ruff: passed.
- Config-only validation: passed.
- Frontend syntax matrix: passed.
- Docs metadata/feature-map/ledger/impact: passed; one unrelated pre-existing
  metadata warning remains.
- Real DB backfill and coverage verification: passed.
- Real frontend-equivalent Deribit job: 10 dataset refreshes succeeded.

## Docs updated

- `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`,
  `docs/RUNBOOK.md`, `docs/manual/40-data-pipeline.md`,
  `docs/KNOWN_ISSUES.md`, `docs/FAILURE_MODES.md`, `docs/INVARIANTS.md`,
  `docs/CHANGELOG_AI.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.

## Known limitations / risks

- Native HV is still rolling-window only; RV30 is a distinct derived series.
- Option surfaces remain current snapshots, not historical strike chains.
- The in-process fetch queue and cancel flag are unchanged; a running HTTP call
  cannot be interrupted mid-request.

## Rollback plan

- Revert only this task's code/config/docs/test edits. Delete
  `rv30_deribit_btc_1h` / `rv30_deribit_eth_1h` observations and dataset
  registry rows if the derived data itself must be removed; no schema rollback
  is needed.

## Context Handoff

- See
  `tasks/2026-07-27-deribit-rv30-frontend-fetch-context-handoff.md`.

## Questions for human review

- None blocking. The UI needs only a browser reload/visual confirmation.

## Next recommended task

- Visually smoke the Deribit selector and export the two RV30 sheets as `.xlsx`.

## Human Learning Notes (required)

Deribit's long-range index chart silently changes cadence. The safe 1H history
path is an explicitly sourced perpetual-close series with strict continuity,
not interpolation or relabeling.

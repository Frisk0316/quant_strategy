---
status: current
type: handoff
owner: codex
created: 2026-07-31
last_reviewed: 2026-07-31
expires: none
superseded_by: null
---

# Context Handoff: H-039, CFTC COT, and Cboe ingestion - 2026-07-31

## Goal (one sentence)

Complete the user-authorized cross-venue option-IV, CFTC COT, and Cboe
external-data adapters without changing schemas, research results, strategy
behavior, or deployment gates.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good state: targeted unit/config/static checks and official-source
  validation pass; no commit was created.
- In-progress edits: the three external clients, ingest/config wiring, H-039
  snapshot wrapper, tests, task acceptance record, operations/governance docs,
  and this handoff pair.
- What works right now: six H-039 hourly source rows retain full normalized
  chains and use 30d total-variance interpolation; six COT and five Cboe source
  histories parse with the recorded row/range and as-of checks.
- What does not work / unfinished: the configured TimescaleDB endpoint refuses
  connections, so no task row is persisted, no full DB backfill has run, no
  H-039 accumulation window has started, and no scheduler is registered. The
  official Cboe total put/call file is discontinued after 2019-10-04.

## Decisions made (and why)

- Reuse `external_datasets` / `external_observations` and stdlib HTTP/CSV/JSON
  paths because the existing store and client patterns already cover the task.
- Store the complete normalized option chain under `raw_payload.instruments`
  because the task explicitly requires later re-derivation; no new table is
  needed.
- Use source contract-market codes for COT selection because display names can
  drift. Map TFF leveraged-money net and disaggregated Gold managed-money net
  to `value_num` while retaining every source row in `raw_payload`.
- Assign COT publication to the standard following Friday 15:30 ET schedule
  and Cboe publication to observation date +1 day. The former is not proof of
  exact historical holiday release times and remains a documented research-use
  limitation.
- Treat `totalpc.csv` as archive-only because Cboe's official file ends in
  2019; no scrape or invented current replacement is authorized.
- Do not register Task Scheduler until one manual six-dataset DB snapshot
  succeeds; public-API success alone does not start H-039's data clock.

## Open questions / unverified assumptions

- Claude/user should decide whether the standard scheduled COT timestamp is
  sufficient for Stage-2 research or whether an exact holiday-release calendar
  is mandatory.
- A new official current total put/call endpoint would require separate source
  review; the discontinued file must not be treated as current.
- H-039 remains `proposed / data-blocked`; earliest honest Stage 2 is after at
  least 270 persisted daily observations.

## Rules in play (preserve verbatim)

- I57: Bybit settlement-suffixed option symbols must preserve expiry, strike,
  and option type.
- I58: COT publication must remain at least two days after its reference date;
  holiday/reference-date variation must not be rejected as malformed data.
- I59: Cboe header drift and stale/discontinued sources fail closed.
- Domain rules touched: R6.2 external feature publication/as-of provenance.
- Do-not-touch: `research/`, existing `results/`, external-store schema and
  `src/okx_quant/data/external_store.py`, Deribit option-flow implementation,
  strategy/signal/risk/portfolio/execution behavior, config/risk.yaml, and
  live/shadow/demo/deployment gates.

## Context to load next (the reading list)

- Source of truth:
  `tasks/2026-07-31-xvenue-iv-collector-cot-cboe-codex-tasks.md`,
  `docs/superpowers/specs/2026-07-31-xvenue-options-iv-hypothesis.md`,
  `config/external_data.yaml`, `docs/HYPOTHESIS_LEDGER.md`, and
  `docs/DOMAIN_RULES.md`.
- Owning files: `src/okx_quant/data/external_clients/xvenue_options_iv.py`,
  `src/okx_quant/data/external_clients/cftc_cot.py`,
  `src/okx_quant/data/external_clients/cboe.py`,
  `scripts/market_data/ingest_external.py`,
  `scripts/market_data/snapshot_xvenue_options.py`, and the three matching
  unit-test modules.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Targeted pytest including existing external-data tests: 19 passed; pytest
  cache write warning only.
- Targeted Ruff: passed.
- `scripts/validate_pipeline.py --check-config-only`: passed.
- Doc metadata, feature-map links, ledger consistency, and advisory doc impact:
  passed; metadata reported two unrelated pre-existing warnings.
- Adapter dry-runs for xvenue/COT/Cboe: passed.
- Official live/source fetches: all 17 configured datasets parsed; exact
  counts/ranges are recorded in the task file.
- The task's exact single-dataset ingest command reached store initialization
  and failed with `ConnectionRefusedError [WinError 1225]` before any write;
  the Docker service could not be started from this session.

## Approvals

- Human approval obtained through the named 2026-07-31 task request.
- Human activation is still required for Windows Task Scheduler registration.
- No approval exists for a scraped PCR source, proxy history, Stage 2/3,
  strategy changes, or deployment.

## Next action (single, concrete)

- Restore the configured TimescaleDB listener, then run the documented H-039
  six-dataset snapshot and COT/Cboe backfills and verify persisted counts before
  registering any recurring task.

## Human Learning Notes

CFTC report reference dates are normally Tuesday but can differ on holiday
weeks, so rejecting non-Tuesday source rows corrupts valid history. Cboe's
official total put/call CSV is a historical archive, not a current feed. Most
importantly, successful public-source parsing is not DB persistence evidence;
H-039's accumulation clock remains at zero until storage and scheduling work.

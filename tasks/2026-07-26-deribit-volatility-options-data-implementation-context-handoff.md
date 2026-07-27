---
status: current
type: handoff
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Context Handoff: Deribit volatility and option-chain ingestion implementation — 2026-07-26

## Goal (one sentence)

Add Deribit historical volatility, retain complete current BTC/ETH option chains
by expiry/strike/type, and top up all existing Deribit external datasets without
inventing unavailable history.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `29d5105`; implementation is uncommitted in an
  already-dirty worktree.
- In-progress edits (files): `config/external_data.yaml`,
  `scripts/market_data/ingest_external.py`,
  `src/okx_quant/data/external_clients/{__init__,deribit_dvol,deribit_option_flow,deribit_option_surface}.py`,
  three targeted unit-test files, and Deribit sections in the data-flow,
  feature-map, runbook, known-issues, manual, failure-mode, and invariant docs.
- What works right now: `hv_deribit_{btc,eth}_1h` ingest the recent rolling
  public series; latest option snapshots contain all BTC 866 / ETH 678
  instruments sorted by normalized expiry/strike/type; DVOL and funding are
  current through the last completed bucket; option-flow pagination explicitly
  requests descending order.
- What does not work / unfinished: Deribit's history host ends at
  `2026-07-21T12:00Z` while the live host begins at `2026-07-25T10:00Z`, leaving
  93 missing hourly buckets (a 94-hour timestamp jump) for both option-flow
  datasets. Historical
  option-chain snapshots before this implementation are unavailable from the
  live public endpoint. No Windows scheduled tasks were registered.

## Decisions made (and why)

- Reused `external_observations` and the existing DVOL transport instead of
  adding a schema or dependency — the current row/JSON shape covers both needs.
- Stored one aggregate surface row plus its complete organized chain — dynamic
  datasets per strike would explode configuration and still not create history.
- Kept historical-volatility datasets optional — they are new context data and
  do not change strategy or deployment gates.
- Reset both option-flow backfill checkpoints to `2026-07-21T12:00Z` with a
  failed/source-gap marker — a future resume must retry the missing interval
  rather than silently skip it.

## Open questions / unverified assumptions

- When Deribit's history index will expose the 93 missing hourly buckets is
  provider-dependent and unverified.
- Whether historical volatility or full strike-chain features should enter a
  strategy remains Claude/research review; ingestion does not authorize it.

## Rules in play (preserve verbatim)

- Invariants touched: I51 — Deribit option-flow pagination requires explicit
  descending order and a non-overlapping millisecond boundary.
- Domain rules touched: R6.2 data coverage/provenance only; no rule changed.
- Do-not-touch: `research/`, existing result artifacts, strategy/risk/execution
  code, DB schema, live/shadow/demo gates, and unrelated dirty-worktree edits.

## Context to load next (the reading list)

- Source of truth: `config/external_data.yaml`, `docs/DATA_FLOW.md`,
  `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`.
- Owning files / MODULE_BRIEFS:
  `src/okx_quant/data/external_clients/`,
  `scripts/market_data/ingest_external.py`,
  `scripts/market_data/backfill_deribit_option_flow.py`.
- Context Pack: no dedicated market-data pack exists; start from
  `docs/CONTEXT_PACKS/README.md` and the owning files above.

## Checks run

- Targeted Deribit/external tests — 22 passed.
- Targeted Ruff — passed.
- `scripts/validate_pipeline.py --check-config-only` — passed.
- Real-DB coverage query — confirmed row counts, latest buckets, complete chain
  cardinality, and the one remaining option-flow gap.

## Approvals

- User explicitly asked to continue and fill missing data.
- Network/DB ingestion approvals were obtained for each Deribit public-API run.
- No scheduler or deployment approval was requested or inferred.

## Next action (single, concrete)

- After Deribit's history host advances, rerun
  `backfill_deribit_option_flow.py --start 2026-07-21T13:00:00Z --end 2026-07-25T10:00:00Z --resume`
  and verify no gap greater than one hour remains.

## Human Learning Notes

Deribit's live and history trade hosts can temporarily fail to overlap. Also,
the trade endpoint's default order is not a pagination contract: callers must
request `sorting=desc`, or a high-volume interval can look valid while retaining
only one page.

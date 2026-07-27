---
status: current
type: handoff
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Context Handoff: Deribit volatility and option-chain data feasibility — 2026-07-26

## Goal (one sentence)

Determine whether the existing Deribit data pipeline can add Deribit historical
volatility and preserve option data by expiry/strike without changing strategy
or deployment behavior.

## Current state

- Branch: `feature/h014-e052-shadow`
- Last known good commit / state: `592b757`; the working tree already contained
  unrelated user/session changes before this read-only assessment.
- In-progress edits (files): only this context handoff and its paired session
  handoff were added by this session.
- What works right now:
  - BTC/ETH daily and hourly DVOL already use `external_observations`.
  - Local hourly DVOL has 46,651 rows per symbol from 2021-03-24 through
    2026-07-24 08:00 UTC.
  - Deribit option flow has hourly history from 2024-01-01 through
    2026-07-10; H-014 has immutable selected-leg research artifacts and a
    current-chain public shadow path.
  - Deribit's public historical-volatility method is keyless and can reuse the
    existing external adapter/store pattern.
- What does not work / unfinished:
  - No `hv_deribit_*` dataset or adapter exists.
  - The live historical-volatility response measured on 2026-07-26 contains
    384 hourly points from 2026-07-10 12:00 through 2026-07-26 10:00 UTC and
    accepts no start/end bounds, so it is not a long-window backfill source.
  - `optsurf_deribit_{btc,eth}` each hold one 2026-07-11 aggregate snapshot;
    each row preserves only the top 20 instruments by open interest.
  - Current public option books expose every active expiry/strike, but public
    REST does not reconstruct past full-book/OI/IV snapshots. Existing Tardis
    research input is not a managed option-chain DB feed.
  - No standalone Deribit DVOL/funding/option-flow/option-surface scheduled task
    is registered. `quant_h014_shadow_daily` exists but its latest task result
    is non-zero (`0x800710E0`); its log shows stale-signal/DB-availability
    failures.

## Decisions made (and why)

- Treat DVOL as already connected; the immediate problem is freshness, not a
  new data model — because daily/hourly adapters, config, tests, and history
  already exist.
- Add Deribit historical volatility through the existing scalar
  `external_observations` path if implementation is authorized — because the
  endpoint returns timestamp/value rows and needs no new schema.
- Do not call a locally calculated long-history realized-volatility series
  "Deribit historical volatility" without a parity/definition check — because
  the official method documents no configurable lookback or long backfill.
- For current option-chain organization, join active instruments to current
  book summaries by `instrument_name` and key rows by
  currency/expiry/strike/type — because both public endpoints already expose
  the required fields.
- Do not put a full multi-strike history into the existing one-scalar-row
  contract by default. Start with a bounded current snapshot/export; add one
  normalized chain table only when historical per-strike research is explicitly
  approved and a vendor/retention policy is chosen.

## Open questions / unverified assumptions

- Required option-chain history depth, sampling cadence, and fields
  (OI/IV/top-of-book/Greeks/trades) have not been selected.
- Whether a paid historical chain source is acceptable is a human budget/data
  licensing decision.
- Deribit's exact historical-volatility calculation window is not stated on the
  current API reference; the observed 384-point response should not be treated
  as a durable retention guarantee.

## Rules in play (preserve verbatim)

- Invariants touched: none changed. Future option research must preserve I39
  (coin accounting/bounded structures) and I40 (F26-safe DVOL and public-only
  shadow surface).
- Domain rules touched: none changed. Future option consumers remain under
  R6.1 data provenance and R8.1–R8.7 options research/shadow rules.
- Do-not-touch: `research/`, existing `results/**`, strategy/signal/risk/
  portfolio/execution behavior, DB schema, and deployment gates without a
  separately approved implementation task.

## Context to load next (the reading list)

- Source of truth: `AI_CONTEXT.md`, `config/external_data.yaml`,
  `docs/DATA_FLOW.md`, `docs/KNOWN_ISSUES.md`, ADR-0010, and ADR-0011.
- Owning files / MODULE_BRIEFS:
  `src/okx_quant/data/external_clients/deribit_dvol.py`,
  `src/okx_quant/data/external_clients/deribit_option_surface.py`,
  `src/okx_quant/data/external_clients/deribit_option_flow.py`,
  `scripts/market_data/ingest_external.py`,
  `scripts/market_data/snapshot_deribit_options.py`, and
  `docs/MODULE_BRIEFS/deribit-shadow-execution.md`.
- Context Pack: no Deribit-specific Context Pack exists; use the files above.

## Checks run

- `git status --short` — recorded the pre-existing dirty working tree before
  analysis.
- Read-only TimescaleDB aggregate query — confirmed Deribit dataset row counts
  and first/last timestamps; no DB writes.
- Read-only Deribit public API queries — confirmed 384-point BTC/ETH historical
  volatility windows, current DVOL, and active option-chain counts.
- Read-only Task Scheduler query — only `quant_h014_shadow_daily` matched the
  Deribit/H-014 task names; latest result was non-zero.

## Approvals

- Human approval needed / obtained: no implementation approval requested or
  obtained. A DB schema, vendor purchase, scheduled task, or persistent chain
  collector needs a separate explicit scope.

## Next action (single, concrete)

- Human chooses between (A) a minimal no-schema delivery for HV plus current
  option-chain export and freshness repair, or (B) a historical per-strike
  chain workstream with a normalized schema and approved data source.

## Human Learning Notes

DVOL is already a mature historical feed in this repository; the misleading
gap is operational freshness. Deribit's similarly named
`get_historical_volatility` is backward-looking realized volatility and, unlike
DVOL, currently exposes only a short recent window. The repository already has
historical selected option legs for H-014, but those immutable artifacts are not
a reusable all-strike surface.

---
status: current
type: handoff
owner: codex
created: 2026-07-27
last_reviewed: 2026-07-27
expires: none
superseded_by: null
---

# Context Handoff: Deribit RV30 history and frontend fetch — 2026-07-27

## Goal (one sentence)

Provide honest Deribit volatility history back to 2021 and expose a Deribit
BTC/ETH refresh through the existing Market Data Coverage fetch queue.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `5374ce5`; this task is uncommitted in an
  already-dirty worktree.
- In-progress edits (files): Deribit external client/config/ingestion, data API
  and Market Data Coverage UI, targeted tests, owning data/UI/runbook/governance
  docs, and this task's two handoffs.
- What works right now: `rv30_deribit_btc_1h` and
  `rv30_deribit_eth_1h` each contain 48,792 unique rows from
  2021-01-01 00:00Z through 2026-07-26 23:00Z. A real two-day run of the
  frontend-equivalent Deribit job refreshed all 10 selected BTC/ETH datasets.
- What does not work / unfinished: native `hv_deribit_*` still begins at the
  provider's recent rolling window; historical option-chain snapshots remain
  unavailable; no scheduler was registered.

## Decisions made (and why)

- Kept native HV and derived RV30 as separate datasets because Deribit's native
  endpoint cannot request old intervals and mixing methodologies would corrupt
  provenance.
- Derived RV30 from contiguous hourly Deribit perpetual closes because
  `get_index_chart_data?range=all` adaptively downsamples older history to 6h;
  would change if Deribit exposes fixed-resolution historical index prices.
- Reused `external_observations`, the existing on-demand refresh function, and
  the existing fetch queue because no schema or second UI workflow is needed.

## Open questions / unverified assumptions

- Whether Deribit will later expose fixed-resolution hourly index-price history
  remains provider-dependent.

## Rules in play (preserve verbatim)

- Invariants touched: I55 — hourly derived volatility requires a fully
  contiguous hourly source window, exact source/formula provenance, and no
  interpolation or adaptive-history relabeling.
- Domain rules touched: existing R6.2 provenance/coverage only; no rule changed.
- Do-not-touch: research, strategy/risk/execution behavior, DB schema, existing
  result artifacts, schedulers, and demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth: `config/external_data.yaml`, `docs/DATA_FLOW.md`,
  `docs/RUNBOOK.md`.
- Owning files / MODULE_BRIEFS:
  `src/okx_quant/data/external_clients/deribit_dvol.py`,
  `scripts/market_data/ingest_external.py`,
  `src/okx_quant/api/routes_data.py`, `frontend/view-config.js`.
- Context Pack: no dedicated market-data pack; use
  `docs/CONTEXT_PACKS/README.md`.

## Checks run

- Targeted pytest — 44 passed.
- Ruff on changed Python — passed.
- Frontend `node --check` matrix — passed.
- Config validation — passed.
- Docs checks / impact — passed with one unrelated existing metadata warning.
- Real DB coverage SQL — exact unique counts/source/formula confirmed.
- Real frontend-equivalent Deribit job — 10/10 datasets succeeded.

## Approvals

- User explicitly requested the 2021 extension, frontend fetch path, and
  completion of missing data. Network/DB writes were approved interactively.
- No scheduler, strategy, schema, deployment, or trading authority was inferred.

## Next action (single, concrete)

- Reload the frontend, choose Exchange = Deribit, search BTC/ETH, and visually
  confirm the queued job and new RV30 coverage/export rows.

## Human Learning Notes

Deribit's `range=all` index-chart response is complete but not fixed-resolution:
older points are 6h. A row count or long date range is therefore not enough to
claim hourly data; continuity and source-resolution checks must be explicit.

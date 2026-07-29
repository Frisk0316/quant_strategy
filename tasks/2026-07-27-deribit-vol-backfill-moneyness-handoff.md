---
status: current
type: handoff
owner: claude
created: 2026-07-27
last_reviewed: 2026-07-27
expires: none
superseded_by: null
---

# Handoff: Deribit vol backfill + moneyness buckets — 2026-07-27

Merged Context+Session handoff (user-approved single-file format).

## Goal (one sentence)
Backfill long hourly Deribit vol history (DVOL, derived RV30) and add
ATM/ITM/OTM moneyness buckets to option-surface/flow adapters, re-ingesting
optflow history with the new fields.

## Implementation summary
Executed docs/superpowers/plans/2026-07-27-deribit-vol-backfill-and-moneyness.md
via superpowers:subagent-driven-development. Tasks 1-2 were data-only backfills;
Tasks 3-4 added `moneyness_bucket`/`ATM_BAND` + surface OI/IV bucket fields and
per-hour flow premium/trade buckets (strict TDD); Task 5 re-ingested optflow
2024-01→now and surfaced two ingest-CLI endpoint bugs (fixed); Task 6 recorded
facts in config notes + DATA_FLOW.md. Final whole-branch review: clean, 0
critical/important, "Ready to merge: Yes".

## Current state / diff scope
- Branch: `feature/deribit-vol-backfill-moneyness` (from feature/h014-e052-shadow @ e60cb05)
- Commits: f485160 (surface buckets), 3141383 (flow buckets), 70ca942 + 8377889
  (endpoint fixes), 2f6ab9e (docs/config); plus this session-end commit.
- Files changed: deribit_option_surface.py, deribit_option_flow.py,
  ingest_external.py, their tests (+ new test_ingest_external_optflow_endpoint.py),
  config/external_data.yaml (notes), docs/DATA_FLOW.md.
- Data (DB, no artifacts touched): DVOL 1h 2021-03-24→now 46,831 rows ×2;
  rv30 BTC 2018-09-14→now 68,959, ETH 2019-04-14→now 63,871; optflow with
  buckets 2024-01-01→now 22,403/22,402 rows.
- Works now: all 22 external-client/ingest tests green; verified coverage +
  field completeness. Unfinished: ~24 newest rows/dataset lack bucket fields
  (Deribit archive lag), see Next action.

## Decisions made (and why)
- Corr gate (0.9) failed: BTC 0.745 / ETH 0.766, n=395 — USER ACCEPTED as-is
  (16-day overlap of two smooth 30-day estimators = weak statistical evidence).
- Moneyness formula `(strike-index_price)/index_price` deviates from plan text
  — float-exact at the ±2.5% band edge; plan's own literal formula fails its
  own boundary test. Reviewed and confirmed better.
- Endpoint selection `_option_flow_endpoint(start)`: history.deribit.com for
  starts >2 days old, www otherwise — measured: archive lags ~7 d, www holds
  ~24 h; would change if Deribit changes serving windows.
- One pre-existing flow test's exact-equality dict extended with 10 zero-valued
  keys (plan's unconditional field merge makes this unavoidable; minimal edit
  verified; ruling confirmed by final review).

## Rules in play (preserve verbatim)
- No Change Manifest / ADR needed: touched paths not in any Manifest?=Yes row
  of docs/DOC_IMPACT_MATRIX.md; `python scripts/docs/check_doc_impact.py` PASS.
- Do-not-touch honored: no strategies/signals/risk/portfolio/execution,
  config/risk.yaml, backtest artifacts, or deployment gates.
- Hypothesis/experiment ledgers: none (no experiment run; data + adapters only).

## Checks run
- `python -m pytest tests/unit/test_deribit_option_surface.py tests/unit/test_deribit_option_flow.py tests/unit/test_deribit_dvol_client.py -v` — 21/21 PASS
- `python -m pytest tests/unit/test_ingest_external_liquidation.py tests/unit/test_market_ingest.py tests/unit/test_ingest_external_optflow_endpoint.py` — 17/17 PASS
- DB verification: coverage lo/hi/n per dataset (above); missing-atm_premium
  rows: 24/dataset, all within last 8 days, 0 older — PASS
- `python scripts/docs/check_doc_impact.py` — passed, no violations

## Approvals
- Obtained: dirty-tree wrap-up commits; corr<0.9 acceptance (both via explicit
  user answers this session). Needed: merge decision for the branch.

## Next action (single, concrete)
Human decides merge for `feature/deribit-vol-backfill-moneyness`; after ~9 days
(archive catch-up), run one-off
`python scripts/market_data/ingest_external.py --dataset optflow_deribit_{btc,eth} --start <now-9d>`
to close the pre-bucket tail, then drop that caveat from config notes.

## Context to load next
- config/external_data.yaml (dataset notes = fact record), docs/DATA_FLOW.md
  §External Observations Ingestion Flow, this file; SDD ledger deleted (git is
  the record).

## Human Learning Notes (required)
- Deribit serves option trades from two disjoint windows: history.deribit.com
  lags ~a week; www.deribit.com holds only ~24 h. A 1-7-day-old dead zone is
  temporarily un-fetchable — measure endpoint windows before wiring backfills.
- The plan's own reference formula failed its own boundary test (float
  rounding); TDD caught it immediately — keep exact-value edge tests in specs.
- CURRENT_STATE.md is at ~220 lines vs the 90-line cap; this session updated
  content only. A dedicated compaction pass (history → CHANGELOG_AI) is due.

---
status: archived
type: task
owner: claude
created: 2026-07-11
last_reviewed: 2026-07-11
expires: 2026-10-11
superseded_by: null
---

# Codex Task List: Deribit Data Ingestion + Frontend Surfacing

Source research: `research/deribit_data_strategy_research.md` (§1 data survey,
§2 architecture decision, §4 frontend). Claude-authored plan; Codex implements;
Claude reviews the diff. **User sign-off required before starting** (design-
heavy route). Tasks are ordered D1→D5 but D1/D2/D3/D4 are independent; D5
depends on at least one of them having data.

## Global scope rules (apply to every task)

PERMITTED AREAS (per task lists below):
- `src/okx_quant/data/external_clients/` (+ `__init__.py`)
- `scripts/market_data/ingest_external.py`, new `scripts/market_data/*.py`
- `config/external_data.yaml`
- `src/okx_quant/api/routes_data.py` (D5 only), `frontend/` (D5 only)
- `tests/unit/` new test files
- Docs per the AGENTS.md docs-update matrix

FORBIDDEN (do not touch in any task):
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`
- `config/risk.yaml`, deployment/shadow/demo/live gates
- `backtesting/` engine semantics, `results/**` existing artifacts
- `research/` (Claude ownership), differential-validation implementation
- Existing DB rows for other datasets; existing migrations (the
  `external_observations` schema is used as-is — no new tables)

SHARED REQUIREMENTS:
- All timestamps UTC; `observed_at` = market event time, never ingest time.
- Every dataset row records `fields.unit` and provenance; `raw_payload` kept
  bounded (aggregates store a small sample, not the full input batch).
- Rate limiting: ≤5 req/s against Deribit hosts, retry with backoff on HTTP
  429 / error 10028; backfills resumable via `external_ingestion_checkpoints`.
- `fail_on_empty_fetch: true` only where an empty answer is truly an error
  (forward jobs); backfill probes may return empty windows legitimately.
- Check `docs/DOC_IMPACT_MATRIX.md`: if the data-provenance row marks
  Manifest = Yes for new external datasets, create a Change Manifest from
  `docs/CHANGE_MANIFEST_TEMPLATE.md` (precedent:
  `docs/change_manifests/2026-07-07-oi-positioning-stage3.md`).
- Verification (make unavailable in this sandbox): `pytest tests/unit -k
  <new tests>` plus `python scripts/docs/check_doc_metadata.py`,
  `python scripts/docs/check_feature_map_links.py` when docs change; frontend:
  `node --check` on changed JS (D5).
- End every task with the AGENTS.md completion report block.

---

## D1 — Deribit perpetual funding history (backfill + forward)

Task: add `DeribitFundingClient` ingesting hourly funding for BTC-PERPETUAL
and ETH-PERPETUAL into datasets `funding_deribit_btc` / `funding_deribit_eth`.

Required behavior: `public/get_funding_rate_history` (www host) paged over
`[start_timestamp, end_timestamp)`; one row per hourly record with
`value_num = interest_1h`, `fields = {instrument, interest_8h, index_price,
prev_index_price, unit: "rate_1h_decimal"}`. Backfill 2024-01-01 → now
(matches canonical OHLCV window), then forward accumulation via
`ingest_external.py` like the existing built-ins.

PERMITTED FILES: `src/okx_quant/data/external_clients/deribit_funding.py`,
`.../external_clients/__init__.py`, `scripts/market_data/ingest_external.py`,
`config/external_data.yaml`, `tests/unit/test_deribit_funding_client.py`,
docs per matrix.

ACCEPTANCE CRITERIA (binary):
- [ ] Unit tests cover: pagination, UTC parsing, empty-window handling,
      rate/unit fields, checkpoint cursor advance (mock HTTP, no live calls).
- [ ] A real backfill run reports row counts per dataset and coverage
      2024-01-01→now with no gaps > 2h (report the gap scan output).
- [ ] `docs/DATA_FLOW.md` external-data section gains the two datasets.
- [ ] Diff contains only permitted files.

## D2 — Hourly DVOL backfill (config + routing only)

Task: add datasets `dvol_deribit_btc_1h` / `dvol_deribit_eth_1h` reusing the
existing `DeribitDVOLClient` with `resolution: "3600"`, backfilled
2024-01-01 → now, forward-accumulated thereafter.

Required behavior: config entries + `ingest_external.py` routing already
supports the adapter; verify the client paginates via the `continuation`
cursor for multi-year hourly windows — if it does not (current client sends a
single request), extend `DeribitDVOLClient.fetch` to follow `continuation`.

PERMITTED FILES: `config/external_data.yaml`,
`src/okx_quant/data/external_clients/deribit_dvol.py`,
`scripts/market_data/ingest_external.py`,
`tests/unit/test_deribit_dvol_client.py` (extend), docs per matrix.

ACCEPTANCE CRITERIA (binary):
- [ ] Hourly backfill run reports ≥ 20,000 rows per currency for 2024→now and
      the daily datasets are untouched (row counts unchanged).
- [ ] Pagination unit test with a mocked `continuation` response.
- [ ] Diff contains only permitted files.

## D3 — Options surface snapshot (forward accumulation, starts the PIT clock)

Task: add `DeribitOptionSurfaceClient` + scheduled script snapshotting
`public/get_book_summary_by_currency(currency=BTC|ETH, kind=option)` into
`optsurf_deribit_btc` / `optsurf_deribit_eth` (hourly cadence).

Required behavior: one observation per currency per snapshot.
`value_num = total option open_interest` (base units);
`fields = {put_oi, call_oi, pc_oi_ratio, max_pain_strike (computed per the
Deribit insights method from per-strike OI), oi_weighted_mark_iv, spot_index,
n_instruments, unit: "base_contracts"}`. `raw_payload` = top-20 instruments by
OI only. Snapshot script follows the OKX liquidation forward-ingest precedent
(`quant_liq_okx_ingest`); provide the script + RUNBOOK registration
instructions — do NOT register the Windows scheduled task yourself, the user
registers it (system state).

PERMITTED FILES: `src/okx_quant/data/external_clients/deribit_option_surface.py`,
`.../external_clients/__init__.py`, `scripts/market_data/ingest_external.py`
or new `scripts/market_data/snapshot_deribit_options.py`,
`config/external_data.yaml`, `tests/unit/test_deribit_option_surface.py`,
`docs/RUNBOOK.md` + docs per matrix.

ACCEPTANCE CRITERIA (binary):
- [ ] Unit tests: aggregate math (put/call OI, ratio, max pain on a small
      synthetic chain with a hand-computed expected strike), snapshot row
      shape, bounded raw_payload.
- [ ] One live snapshot run stores 2 rows (BTC, ETH) and prints them.
- [ ] RUNBOOK documents the schedule command and the "history starts at first
      snapshot — not backfillable" caveat.
- [ ] Diff contains only permitted files.

## D4 — Options trade tape backfill → hourly flow aggregates

Task: add `DeribitOptionFlowClient` + backfill script reading the full options
tape from `https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time`
(kind=option, count=1000 pages, `has_more` pagination) and storing HOURLY
aggregates per currency into `optflow_deribit_btc` / `optflow_deribit_eth`,
backfilled 2024-01-01 → now, forward-accumulated from www host thereafter.

Required behavior: aggregate per (currency, hour):
`value_num = pc_taker_premium_imbalance = (put_taker_buy_premium −
call_taker_buy_premium) / max(total_taker_buy_premium, ε)`;
`fields = {call_buy_amt, call_sell_amt, put_buy_amt, put_sell_amt,
premium_volume, premium_unit (BTC/ETH for inverse; USDC for linear —
aggregate inverse instruments only in v1 and record the exclusion),
avg_trade_iv, trade_count, liq_trade_count, unit: "imbalance_ratio"}`.
Direction = taker side from `direction`; put/call parsed from instrument name.
Checkpointed and resumable; expect multi-hour runtime at ≤5 req/s — the script
must print progress and survive interruption.

PERMITTED FILES: `src/okx_quant/data/external_clients/deribit_option_flow.py`,
`.../external_clients/__init__.py`,
`scripts/market_data/backfill_deribit_option_flow.py`,
`config/external_data.yaml`, `tests/unit/test_deribit_option_flow.py`,
docs per matrix.

ACCEPTANCE CRITERIA (binary):
- [ ] Unit tests: instrument-name parsing (inverse vs USDC-linear excluded),
      hourly bucketing at UTC boundaries, imbalance formula on synthetic
      trades with hand-computed expected value, resumable checkpoint.
- [ ] Pilot backfill of ONE month (2024-01) completes and reports per-currency
      row counts within [670, 744] (24×31 minus tolerated empty hours) before
      the full run is attempted; full 2024→now backfill reported with row
      counts and gap scan (gaps >6h listed).
- [ ] Aggregation definitions in the docstring match this spec verbatim
      (they are pre-registered researcher inputs — no silent changes).
- [ ] Diff contains only permitted files.

## D5 — API endpoint + frontend "Derivatives context" chart

Task: expose external-dataset time series over HTTP and render Deribit series
in the frontend.

Required behavior: `GET /api/data/external-series?dataset_id=…&start=…&end=…`
in `routes_data.py` returning `{dataset_id, points: [{t, v}], unit}` from
`external_observations` (limit + downsample above 5,000 points, mirroring the
price-series downsampling precedent). Frontend: a "Derivatives context" card
in `view-config.js` next to the data-coverage card: dataset dropdown (built
from the coverage endpoint, deribit datasets first), date range, and
`window.Charts.LineChart` render. Display-only; no backtest artifacts.

PERMITTED FILES: `src/okx_quant/api/routes_data.py`, `frontend/view-config.js`,
`frontend/data.js`, `frontend/charts.js` (only if a new chart variant is truly
needed — prefer existing LineChart), `tests/unit/test_routes_data_external_series.py`,
`docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`.

ACCEPTANCE CRITERIA (binary):
- [ ] API unit test: known rows in, correct points/unit out; empty dataset →
      empty points, not 500; downsampling kicks in above the cap.
- [ ] `node --check` passes on changed frontend files; browser check shows the
      card rendering `dvol_deribit_btc` (screenshot or described manual check).
- [ ] UI_MAP + FEATURE_MAP rows added for the card/endpoint.
- [ ] Diff contains only permitted files.

---

## Explicitly out of scope (do not build)

- Any strategy/signal implementation for C1/C2 (needs a signed-off Stage-1
  spec + H-013 ledger row first — separate future task).
- Per-trade raw storage, order-book capture, Tardis imports, new DB tables.
- WebSocket streaming clients (REST polling suffices at these cadences).
- Any live/demo/shadow/deployment claim or gate change.

## Reporting

Each task ends with the AGENTS.md completion report. Questions for Claude
review should flag: unit ambiguities (premium currency for inverse options),
any endpoint behavior differing from `research/deribit_data_strategy_research.md`
§1, and any rate-limit ceilings observed on history.deribit.com (undocumented).

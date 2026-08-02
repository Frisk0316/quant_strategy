---
status: current
type: task
owner: claude
created: 2026-07-31
last_reviewed: 2026-07-31
expires: none
superseded_by: null
---

# Codex tasks: H-039 cross-venue options-IV collector + CFTC COT + CBOE ingestion

Implementation status (Codex, 2026-07-31): adapters, config, tests, live source
validation, and operations docs are complete. DB acceptance remains blocked
because the configured TimescaleDB endpoint refuses connections and this
session cannot start Docker Desktop. The official Cboe total put/call CSV is
also confirmed discontinued at 2019-10-04; no scraped replacement was used.

Why: user authorized (2026-07-31) building the forward collector for H-039
(`docs/superpowers/specs/2026-07-31-xvenue-options-iv-hypothesis.md`) and
ingesting the two highest-value free sources from the 2026-07-31 screening
round (CFTC COT, CBOE vol stats). FRED core series (DGS2/VIXCLS/DTWEXBGS +
GC=F proxy) were already ingested 2026-07-30 — do NOT redo them.

Every observation day lost before the collector starts is permanently lost
(H-028 lesson), so T1 has priority.

## T1 — Cross-venue options IV/skew hourly collector (H-039)

New adapter `xvenue_options_iv` in
`src/okx_quant/data/external_clients/xvenue_options_iv.py`, driven by the
existing `scripts/market_data/ingest_external.py` registry, snapshotting once
per hour per venue per underlying (BTC, ETH):

- Venues/endpoints (all public, verified live 2026-07-31):
  - OKX `GET /api/v5/public/opt-summary?instFamily={BTC,ETH}-USD` (markVol + greeks)
  - Bybit `GET /v5/market/tickers?category=option&baseCoin={BTC,ETH}` (markIv, greeks, OI)
  - Deribit `GET /api/v2/public/get_book_summary_by_currency?currency={BTC,ETH}&kind=option` (mark_iv, OI)
- Derived fields per snapshot (stored in `fields` JSONB):
  - `atm_iv_30d`: from the two expiries bracketing 30 calendar days, take per
    expiry the mark IV of the strike nearest the underlying/forward, then
    linearly interpolate in total variance × time to 30d. If only one side
    exists, use nearest expiry and set `interp: "nearest"`.
  - `rr_25d`: (call IV at delta nearest +0.25) − (put IV at delta nearest
    −0.25), same expiry interpolation.
  - `oi_total`: sum of open interest across the chain (venue units; record
    unit in `fields.oi_unit`).
- Full instrument-level summary retained in `raw_payload` so metrics can be
  re-derived later (H-031 lesson: never keep only the aggregate).
- Dataset ids: `xvenue_opt_iv_{okx|bybit|deribit}_{btc|eth}` (6 datasets),
  `frequency: hourly`, registered in `config/external_data.yaml` with
  attribution + source_url; `observed_at` = snapshot hour bucket label,
  `published_at` = bucket end.
- Scheduling: same mechanism as the existing 2-hourly `quant_liq_okx_ingest`
  task, but hourly; document the schedule + gap-alert expectation in
  `docs/RUNBOOK.md`.
- A venue endpoint failing must not abort the other venues (per-venue
  try/except, log and continue); a snapshot with <2 venues present is still
  stored (Stage-2 coverage check will judge later).

Acceptance (binary):
- [x] `python scripts/market_data/ingest_external.py --dataset xvenue_opt_iv_okx_btc` (or equivalent invocation) writes >=1 row to `external_observations` with non-null `atm_iv_30d` in fields and full chain in `raw_payload`. Verified by Claude 2026-08-02 (TimescaleDB restarted): all 6 datasets landed; BTC atm_iv_30d 0.3374/0.3386/0.3391 across OKX/Bybit/Deribit (unit normalization consistent), chains 496-866 instruments in raw_payload.
- [x] All 6 datasets registered in `config/external_data.yaml` and land rows in a live smoke run. Verified in DB 2026-08-02.
- [x] Unit test with recorded venue fixtures covers: 30d interpolation between two expiries, nearest-fallback, 25Δ RR sign convention, per-venue failure isolation.
- [x] Hourly schedule documented in `docs/RUNBOOK.md`; `docs/DATA_FLOW.md` external section updated.
- [x] No edits to `src/okx_quant/data/external_store.py` (another session owns it).

## T2 — CFTC COT weekly ingestion

New adapter `cftc_cot` in `src/okx_quant/data/external_clients/cftc_cot.py`
using the Socrata API at `publicreporting.cftc.gov` (no token; public domain).

- Reports: Traders in Financial Futures (TFF), futures-only, for a
  config-listed set of markets — initial list: CME Bitcoin, CME Ether,
  E-mini S&P 500, 10Y Note, U.S. Dollar Index; plus disaggregated Gold.
- One dataset per market: `cot_{slug}` (e.g. `cot_cme_btc`), `frequency:
  weekly`. `observed_at` = official report reference date (normally Tuesday;
  holiday weeks can differ); `published_at` = scheduled release datetime
  (typically Friday 15:30 ET) — this lag is the whole as-of
  correctness of COT, do not shortcut it to Tuesday.
- Backfill full available history (TFF starts 2006; crypto contracts later),
  then incremental weekly.

Acceptance (binary):
- [x] Backfill run lands the full history for all configured markets. Verified in DB by Claude 2026-08-02: cot_cme_btc 434 rows (2018-04-10..2026-07-28), cot_cme_eth 278, cot_es/cot_ust10y/cot_usd_index/cot_gold 1,051 each (2006-06-13..); all rows satisfy published_at >= observed_at + 2 days.
- [x] Every source row satisfies `published_at >= observed_at + 2 days`.
- [x] Unit test with a recorded Socrata fixture covers column mapping and the reference-date/Friday timestamp assignment.
- [x] Datasets registered in `config/external_data.yaml`; `docs/DATA_FLOW.md` updated.

## T3 — CBOE vol statistics ingestion

New adapter `cboe` in `src/okx_quant/data/external_clients/cboe.py` pulling
CBOE's free CSV history endpoints:

- Series: VIX9D, VIX, VIX3M, VIX6M daily closes (term structure), and the
  daily total put/call ratio. (VIXCLS from FRED stays as-is; the CBOE VIX
  series is for term-structure consistency — same-source ratios.)
- Dataset ids: `cboe_vix9d`, `cboe_vix`, `cboe_vix3m`, `cboe_vix6m`,
  `cboe_pcr_total`; `frequency: daily`; conservative `published_at` =
  `observed_at + 1 day` (FRED convention).
- Backfill full CSV history, then incremental daily.

Acceptance (binary):
- [x] Backfill lands full available history per series. Verified in DB by Claude 2026-08-02: cboe_vix 9,241 rows (1990-01-02..2026-07-31), vix9d 3,916, vix3m 4,242, vix6m 4,674, pcr_total 3,253 (ends 2019-10-04 as documented).
- [x] Unit test with recorded CSV fixtures covers parsing and the +1-day published_at convention.
- [x] Datasets registered in `config/external_data.yaml`; `docs/DATA_FLOW.md` updated.
- [x] The official `https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv` ends 2019-10-04. STOP confirmed; no scraped source substituted.

## 2026-07-31 live source evidence

| Dataset | Source rows | Earliest `observed_at` | Latest `observed_at` |
| --- | ---: | --- | --- |
| `xvenue_opt_iv_okx_btc` | 1 | 2026-07-31 09:00 UTC | same |
| `xvenue_opt_iv_okx_eth` | 1 | 2026-07-31 09:00 UTC | same |
| `xvenue_opt_iv_bybit_btc` | 1 | 2026-07-31 09:00 UTC | same |
| `xvenue_opt_iv_bybit_eth` | 1 | 2026-07-31 09:00 UTC | same |
| `xvenue_opt_iv_deribit_btc` | 1 | 2026-07-31 09:00 UTC | same |
| `xvenue_opt_iv_deribit_eth` | 1 | 2026-07-31 09:00 UTC | same |
| `cot_cme_btc` | 433 | 2018-04-10 | 2026-07-21 |
| `cot_cme_eth` | 277 | 2021-04-06 | 2026-07-21 |
| `cot_es` | 1,050 | 2006-06-13 | 2026-07-21 |
| `cot_ust10y` | 1,050 | 2006-06-13 | 2026-07-21 |
| `cot_usd_index` | 1,050 | 2006-06-13 | 2026-07-21 |
| `cot_gold` | 1,050 | 2006-06-13 | 2026-07-21 |
| `cboe_vix9d` | 3,915 | 2011-01-04 | 2026-07-30 |
| `cboe_vix` | 9,240 | 1990-01-02 | 2026-07-30 |
| `cboe_vix3m` | 4,241 | 2009-09-18 | 2026-07-30 |
| `cboe_vix6m` | 4,673 | 2008-01-02 | 2026-07-30 |
| `cboe_pcr_total` | 3,253 | 2006-11-01 | 2019-10-04 |

The six H-039 rows retained full chains of 702 / 644 / 584 / 474 / 854 /
708 instruments respectively and all used `interp = total_variance`. These are
in-memory official-source smokes, not DB row counts.

## PERMITTED FILES

`src/okx_quant/data/external_clients/xvenue_options_iv.py`,
`src/okx_quant/data/external_clients/cftc_cot.py`,
`src/okx_quant/data/external_clients/cboe.py`,
`scripts/market_data/ingest_external.py` (registry wiring only),
`config/external_data.yaml`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
`docs/FEATURE_MAP.md` (new rows), `tests/unit/test_xvenue_options_iv.py`,
`tests/unit/test_cftc_cot.py`, `tests/unit/test_cboe.py`

## FORBIDDEN

`src/okx_quant/data/external_store.py` (in-flight payload_only work, another
session), `src/okx_quant/data/external_clients/deribit_option_flow.py` (same),
`src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
`config/risk.yaml`, existing `results/` artifacts, backtesting engine.

SCOPE LIMIT: ingestion only. No signal/feature/strategy code, no Stage-2
probes, no schema changes to external tables.

REPORT: per AGENTS.md finishing template; include per-dataset row counts,
earliest/latest `observed_at`, and the exact cron/schedule registration for T1.

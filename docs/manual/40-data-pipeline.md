---
status: current
type: manual
owner: human
created: 2026-06-25
last_reviewed: 2026-07-27
expires: none
superseded_by: null
---

# Data pipeline

This chapter is the user-facing version of `docs/DATA_FLOW.md`: it explains
where data comes from, where it is stored, and which UI/API surfaces read it.

## Main flow

```text
exchange REST candles -> ingestion script/API -> DB + optional parquet mirror -> backtest/data loader -> artifact/result -> frontend/API
```

| Data | Source path | Used by |
| --- | --- | --- |
| OHLCV | `scripts/market_data/ingest.py`, Market Data Coverage API | replay backtests, coverage panel, chart artifacts |
| Funding | funding backfill/import scripts, Market Data Coverage API | funding-carry review, replay funding cashflow, validation |
| Venue specs | `venue_instrument_specs`, Binance `exchangeInfo`, `config/instrument_specs.yaml` fallback | sizing, PnL, funding, margin/liquidation, `ct_val` provenance |
| External observations | `scripts/market_data/ingest_external.py`, Deribit/Binance/Alternative.me/FRED/yfinance adapters | data export, external-feature probes, Derivatives context chart |

## Deribit external datasets

Deribit data lives in `external_datasets` / `external_observations` and is
review/data-context input only. The current dataset families are:

| Family | Dataset ids | Meaning | History |
| --- | --- | --- | --- |
| DVOL implied-vol index | `dvol_deribit_btc_1h`, `dvol_deribit_eth_1h` | Hourly Deribit DVOL close, `fields.unit = "dvol_index_points"` | Backfilled from `2024-01-01T00:00:00Z`, then forward-ingested hourly |
| Historical volatility | `hv_deribit_btc_1h`, `hv_deribit_eth_1h` | Deribit annualized historical volatility, `fields.unit = "annualized_percent"` | Recent rolling public window only; accumulate forward |
| Derived realized volatility | `rv30_deribit_btc_1h`, `rv30_deribit_eth_1h` | 30-day sample volatility of 720 contiguous hourly Deribit perpetual log returns, annualized by `sqrt(365*24)` | Backfilled from `2021-01-01T00:00:00Z`; separate from native HV |
| Perpetual funding | `funding_deribit_btc`, `funding_deribit_eth` | BTC/ETH perpetual `interest_1h`, `fields.unit = "rate_1h_decimal"` | Backfilled from `2024-01-01T00:00:00Z`, then forward-ingested hourly |
| Option flow | `optflow_deribit_btc`, `optflow_deribit_eth` | Hourly inverse-option trade-flow aggregate; `value_num` is put-vs-call taker-buy premium imbalance | Backfilled from `2024-01-01T00:00:00Z`, checkpointed/resumable, then forward-ingested hourly |
| Option surface | `optsurf_deribit_btc`, `optsurf_deribit_eth` | Snapshot-only option OI/IV aggregate; fields include max pain and put/call OI ratio, while `raw_payload` retains the full current chain sorted by expiry/strike/type | Forward-only; history starts at the first successful snapshot |

For option flow, `value_num` means:

```text
(put_taker_buy_premium - call_taker_buy_premium) / max(total_taker_buy_premium, epsilon)
```

Point-in-time convention: for bucketed aggregates, `observed_at` is the market
bucket label and `published_at` is the bucket end. Hourly DVOL and option-flow
rows and derived RV30 publish one hour after `observed_at`; daily DVOL
publishes one day after. Deribit funding timestamps are accrual-period end and are safe as both
`observed_at` and `published_at`. This guards failure mode F26.

Backfill/forward commands:

```powershell
python scripts\market_data\ingest_external.py --dataset funding_deribit_btc --dataset funding_deribit_eth --start 2024-01-01T00:00:00+00:00 --end <UTC_END>
python scripts\market_data\ingest_external.py --dataset dvol_deribit_btc_1h --dataset dvol_deribit_eth_1h --start 2024-01-01T00:00:00+00:00 --end <UTC_END>
python scripts\market_data\ingest_external.py --dataset hv_deribit_btc_1h --dataset hv_deribit_eth_1h
python scripts\market_data\ingest_external.py --dataset rv30_deribit_btc_1h --dataset rv30_deribit_eth_1h --start 2021-01-01T00:00:00+00:00 --end <UTC_END>
python scripts\market_data\backfill_deribit_option_flow.py --start 2024-01-01T00:00:00+00:00 --end <UTC_END> --resume
python scripts\market_data\snapshot_deribit_options.py
```

The frontend Market Data Coverage form provides the same bounded operation:
select `Deribit`, search/select BTC and/or ETH, choose the date range, and click
`Confirm and Fetch to DB`. That queued job refreshes DVOL, native HV, derived
RV30, and the current full option-chain snapshot.

For scheduled forward ingest, see `docs/RUNBOOK.md` sections
`Scheduled External Ingest (Deribit option surface)`,
`Scheduled External Ingest (Deribit funding, volatility, option flow)`, and
`Deribit Option Flow Backfill`. The user registers Windows `schtasks`; Codex
does not register workstation tasks during implementation.

## DB vs parquet

- DB-backed ingestion is preferred when `DATABASE_URL` or the Timescale DSN in
  `config/settings.yaml` is reachable.
- Local parquet fallback is for no-DB development and historical compatibility.
- Venue-tagged replay is strict: if a run declares an exchange, candles must
  come from the canonical DB path filtered to that venue.
- Parquet fallback is not promotion evidence when DB parity, source validation,
  or authoritative `ct_val` provenance is required.

## User checks

- Market Data Coverage shows OHLCV/funding/external coverage and fetch jobs.
- Backtest Runs show artifact `data_source`, `validation`, and `ct_val_sources`.
- Validation Lab shows DB parity, source data validation, and portable validation.
- If UI and docs disagree, follow `docs/DATA_FLOW.md` and fresh artifacts.

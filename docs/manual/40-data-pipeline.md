# 資料管線

本專案的資料流以 `docs/DATA_FLOW.md` 為主。任何回測、驗證或前端顯示，都應該能追到「來源、寫入位置、消費者、產物、UI/API」。

## 主流程

```text
exchange REST candles -> ingestion script/API -> DB + optional parquet mirror -> backtest/data loader -> artifact/result -> frontend/API
```

常見來源與用途：

| 資料 | 來源與寫入 | 主要消費者 |
| --- | --- | --- |
| OHLCV | `scripts/market_data/ingest.py`、下載腳本、Market Data Coverage API | replay backtest、coverage panel、chart artifacts |
| funding | funding backfill/import scripts、Market Data Coverage API | funding-carry、replay funding cashflow、validation |
| venue specs | `venue_instrument_specs`、Binance `exchangeInfo` sync、`config/instrument_specs.yaml` fallback | sizing、PnL、funding、margin/liquidation、`ct_val` provenance |
| progress status | local git、`STATUS.md`、linked plan checkboxes | read-only Progress panel |

## DB 與 parquet 的界線

- DB-backed ingestion is preferred when `DATABASE_URL` or the Timescale DSN in `config/settings.yaml` is reachable.
- Local parquet fallback is for no-DB development and historical compatibility.
- Venue-tagged replay is strict: if a run declares an exchange, candles must come from the canonical DB path filtered to that venue.
- Parquet fallback is not promotion evidence when DB parity, source validation, or authoritative `ct_val` provenance is required.

## 使用者檢查點

- 在前端 Market Data Coverage 看 OHLCV/funding coverage and fetch jobs.
- 在 Backtest Runs 檢查 artifact 裡的 `data_source`、`validation`、`ct_val_sources`.
- 在 Validation Lab 檢查 DB parity、source data validation、portable validation result.
- 若 UI 顯示與文件不一致，先查 `docs/DATA_FLOW.md` 與實際 artifact，不要讓前端自行補一個「看起來合理」的答案。

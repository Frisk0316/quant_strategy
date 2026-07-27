---
status: current
type: report
owner: codex
created: 2026-07-23
last_reviewed: 2026-07-23
expires: 2026-10-23
superseded_by: null
---

# Free-data scout report: F-TAKER-FLOW + candidates 2/3

Read-only scouting only. No ingestion, schema change, download, network request,
probe, experiment, ledger update, result artifact, or strategy/deployment change ran.
This report is ready for Claude review; it is not research or promotion evidence.

## Executive result

| Gate | Result | Why |
| --- | --- | --- |
| S1 / CVD probe | **BLOCKED — DB UNCONFIRMED** | The current Binance REST parser preserves kline array slots 9/10 under `market_klines.raw_payload.raw`, but the configured TimescaleDB was unreachable, so existing-row coverage cannot be claimed. |
| S2 / liquidation spec | **NEEDS HUMAN NETWORK STEP** | No local Binance `liquidationSnapshot` file or registered Binance liquidation dataset exists; upstream start, symbols, format, semantics, and counts remain UNCONFIRMED. |
| S3 / term-structure spec | **BLOCKED — DATA + DISTINCTNESS RISK** | No local delivery-futures file exists and repo Binance ingestion excludes non-perpetual contracts. ETH's local perp/spot basis has 0.736744 correlation with the annualized-funding proxy over 898 days; BTC has no common local window. |

## Scope and methods

- Read sources: task/spec, `docs/DATA_FLOW.md`, current governance/ADR context,
  ingestion/storage code, PIT membership, local parquet schemas, and local listener state.
- Local DB attempts: repo config and `.env` point to `localhost:5432`, where no
  process was listening. PostgreSQL listens on 5433, but it is a different instance:
  both repo-config and `.env` credentials failed authentication there. All attempts
  failed before a query and made no write.
- Local file scan: all files under `data/`; exact Binance liquidationSnapshot and
  dated delivery-contract filename patterns only.
- S3 diagnostic: UTC daily `sum(funding_rate) * 365` correlated with UTC daily-last
  `perp_close / spot_close - 1`, using only existing parquet through 2026-06-16.

## FACT — locally verified

### S1: current capture path and local fallback

1. `src/okx_quant/data/exchange_clients/binance_public.py:121-124` maps Binance
   kline array slot 9 to `taker_buy_base_volume`, slot 10 to
   `taker_buy_quote_volume`, and retains the whole array under
   `raw_payload = {"exchange":"binance", "symbol":..., "raw": r}`.
2. `src/okx_quant/data/candle_store.py:647-691` serializes that payload to
   `market_klines.raw_payload`. Therefore the expected DB JSON paths for rows
   written by this current path are:
   - base: `raw_payload #>> '{raw,9}'` (`raw_payload.raw[9]`)
   - quote: `raw_payload #>> '{raw,10}'` (`raw_payload.raw[10]`)
3. The repo has 35 local `data/ticks/*/candles_1m.parquet` files. Their only
   schema variants are OHLCV, optional `vol_ccy`, and an optional saved index;
   **0/35** contain a taker or raw-payload column. Parquet cannot answer S1.
4. `data/universe/universe_membership.parquet` yields this conditional planning
   upper bound if existing DB raw payload cannot be parsed: BTC/ETH 2020-2023 =
   2,922 symbol-days; PIT members 2024 = 9,991, 2025 = 10,627, and
   2026-01-01..06-27 = 5,079; total **28,619 daily file-slots**. This is a
   membership-derived upper bound, not verified Binance Vision availability.

### S2: local liquidation evidence

- Exact local filename scan found **0** Binance `liquidationSnapshot` files.
- Repo config/code registers OKX liquidation forward accumulation, not Binance
  Vision liquidationSnapshot history (`docs/DATA_FLOW.md`, External Observations).
- No local sample exists, so no locally defensible event count per symbol/year exists.

### S3: local delivery/basis evidence

- Exact local filename scan found **0** BTC/ETH dated delivery-futures files.
- `src/okx_quant/api/routes_data.py:635-636` discards Binance instruments whose
  `contractType` is not `PERPETUAL`; `scripts/market_data/backfill_cmc_top_binance.py:256`
  does the same. Current supported ingestion therefore does not capture delivery futures.
- Existing parquet distinctness pre-estimate:

| Base | Common days | Window | corr(annualized funding proxy, perp/spot basis) | Interpretation |
| --- | ---: | --- | ---: | --- |
| BTC | 0 | none | n/a | Local BTC perp parquet begins 2026-06-23, after local funding ends 2026-06-16; cannot estimate. |
| ETH | 898 | 2024-01-01..2026-06-16 | **0.736744** | High collision with the existing funding/basis family; this is a warning, not a term-structure-signal correlation. |

Inputs: `data/funding/binance_universe_funding.parquet`,
`data/ticks/{BTC,ETH}_USDT_SWAP/candles_1m.parquet`, and
`data/ticks/{BTC,ETH}_USDT/candles_1m.parquet`.

## UNCONFIRMED — do not cite as fact

### S1

- **UNCONFIRMED:** whether existing `market_klines` rows actually retain slots
  9/10 for every required year/symbol. Current code proves the intended/current
  write shape, not the historical DB contents.
- **UNCONFIRMED:** whether Binance Vision daily kline zips have the asserted
  columns for every required symbol/day. The task/spec says they do; this session
  did not inspect an upstream file.
- **UNCONFIRMED size:** no Vision daily kline zip is local, so inventing MB/file
  would be unjustified. Once a verified HEAD sample yields mean `Content-Length = H`,
  the conservative compressed-size estimate is `28,619 * H` bytes; actual count
  may be lower where a file does not exist.
- DB blocker reproduction: the scout reports `[WinError 1225]` against the repo
  DSN on 5432; replacing it with 5433 reaches a PostgreSQL server but fails repo
  credential authentication. No S1 YES/NO is claimed until the exact query runs.

### S2

- **UNCONFIRMED:** Binance Vision liquidationSnapshot availability start date.
- **UNCONFIRMED:** actual symbol coverage and whether coverage is continuous.
- **UNCONFIRMED:** CSV header, side/quantity/price meaning, snapshot-vs-event
  semantics, deduplication key, timestamp unit, and per-symbol/year event counts.

### S3

- **UNCONFIRMED:** UM/CM delivery-contract availability start years, contract
  universe, current/historical naming, bar intervals, headers, and row semantics.
- **UNCONFIRMED:** any BTC funding/basis correlation for the intended window.
- **UNCONFIRMED:** distinctness of a delivery-term-structure signal itself. ETH's
  0.736744 result compares funding with perp/spot basis, not delivery-curve returns.

## Exact human verification commands

These commands are intentionally not run in this session.

### Restore S1 local DB evidence (no network download)

Run after the repo TimescaleDB named in `.env` is listening. The script forces
`default_transaction_read_only=on`, uses a 120-second statement timeout, and emits
JSON to stdout only.

```powershell
$dbLine = Get-Content -Encoding UTF8 -LiteralPath .env |
  Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$env:DATABASE_URL = ($dbLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\scout_free_datasets.py
```

Required interpretation: S1 is YES only if each reported 2020-2026 year has no
missing/partial required symbols and `field_coverage == 1.0`. Otherwise use the
reported missing/partial symbol-years as the re-download windows.

### S1 Binance Vision metadata/sample

```powershell
curl.exe -fsSI "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-01.zip"
$zip = Join-Path $env:TEMP 'BTCUSDT-1m-2024-01-01.zip'
curl.exe -fL "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-01.zip" -o $zip
tar.exe -xOf $zip | Select-Object -First 3
```

Record the HEAD `Content-Length`, displayed header/column count, and rows before
using the 28,619-file-slot formula. The second/third commands download one sample;
they require separate human execution after this report review.

### S2 liquidationSnapshot listing, HEAD, and one-file semantics

```powershell
curl.exe -fsS "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?list-type=2&delimiter=%2F&prefix=data/futures/um/daily/liquidationSnapshot/"
curl.exe -fsS "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?list-type=2&max-keys=1000&prefix=data/futures/um/daily/liquidationSnapshot/BTCUSDT/"
curl.exe -fsSI "https://data.binance.vision/data/futures/um/daily/liquidationSnapshot/BTCUSDT/BTCUSDT-liquidationSnapshot-2024-01-01.zip"
$zip = Join-Path $env:TEMP 'BTCUSDT-liquidationSnapshot-2024-01-01.zip'
curl.exe -fL "https://data.binance.vision/data/futures/um/daily/liquidationSnapshot/BTCUSDT/BTCUSDT-liquidationSnapshot-2024-01-01.zip" -o $zip
tar.exe -xOf $zip | Select-Object -First 5
(tar.exe -xOf $zip | Measure-Object -Line).Lines - 1
```

Repeat the symbol-specific listing for ETHUSDT and the intended universe. Follow
`NextContinuationToken` if `IsTruncated=true`; do not infer an earliest date from
a truncated later page.

### S3 delivery-contract listings

```powershell
$um = curl.exe -fsS "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?list-type=2&delimiter=%2F&max-keys=1000&prefix=data/futures/um/daily/klines/"
[regex]::Matches($um, '<Prefix>([^<]+_[0-9]{6}/)</Prefix>') |
  ForEach-Object { $_.Groups[1].Value }
$cm = curl.exe -fsS "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?list-type=2&delimiter=%2F&max-keys=1000&prefix=data/futures/cm/daily/klines/"
[regex]::Matches($cm, '<Prefix>([^<]+_[0-9]{6}/)</Prefix>') |
  ForEach-Object { $_.Groups[1].Value }
```

For every returned BTC/ETH contract, list its interval prefix and inspect one
file exactly as in S1 before recording start year, naming, header, or semantics.

## RECOMMENDATION

### Conditional S1 storage design-space (report only; 8 lines)

1. **Problem:** expose one trustworthy taker-buy base quantity per Binance kline without changing this task's DB.
2. **Constraints:** no migration now; retain provenance; avoid a duplicate high-volume dataset.
3. **Option A — do nothing:** parse `raw_payload.raw[9]` at Stage 2; zero schema blast radius, but JSON scans are slower and depend on verified historical shape.
4. **Option B — one nullable column:** later add `market_klines.taker_buy_base_volume DOUBLE PRECISION`; simplest reusable query, but requires an approved migration/backfill.
5. **Option C — external observations:** store one row/bar; isolates features, but duplicates timestamps/keys and adds millions of rows.
6. **Axis:** minimum reversible change versus query ergonomics and long-run reuse.
7. **Decision:** use A for one bounded probe if S1 becomes YES; choose B only if repeated use makes JSON extraction measurably costly. Do not choose C for this single native kline field.
8. **Would change if:** historical payload shapes are mixed/unusable or several venues need a common aggressor-flow contract; then Claude/user should approve a separate schema ADR/task.

### Gate decisions for Claude

1. Keep the CVD probe blocked until S1 DB output is COMPLETE and YES; current code
   shape alone is insufficient evidence.
2. Do not write a liquidation Stage-1 spec until the S2 human metadata/sample
   commands establish start, symbols, row semantics, and at least sample counts.
3. Do not write a term-structure Stage-1 spec until delivery metadata is verified
   and a delivery-curve signal can be compared directly against funding/basis.
4. Treat ETH `corr=0.736744` as a mechanism-collision warning. It exceeds the
   project's common 0.70 family-collision reference, but is not itself a formal
   minting/distinctness gate for the not-yet-defined candidate.
5. Preferred order: restore S1 DB read -> decide raw parse vs separate capture;
   metadata-only S2/S3 human check -> one reviewed sample -> only then a separate
   ingestion-capture task. No probe comes before those facts.

## Acceptance checklist

- [x] S1 documents exact JSON paths and exactly why existing-row YES/NO is unavailable.
- [x] S1 gives local parquet evidence plus conditional file-count/size formula.
- [x] S2/S3 external claims are all UNCONFIRMED and have exact human commands.
- [x] FACT / UNCONFIRMED / RECOMMENDATION are separate sections.
- [x] No ingestion/schema/download/probe/experiment/result/config/research change.
- [x] Claude review completed — 2026-07-23, verdict APPROVE; see the
      "Claude review 2026-07-23" section below.

## Claude review 2026-07-23 (verdict: APPROVE)

Report quality: honest FACT/UNCONFIRMED separation, zero fabricated dates,
fail-closed DB behavior, scope clean (the co-resident modified files in the
tree belong to the sibling db-coverage-performance session, not this scout).
Scout tests 2/2 pass; the `binance_public.py:121-124` claim was re-read and
confirmed.

**S1 upgraded to qualitative YES by direct reviewer evidence.** The repo DB
returned to service after the scout ran (the scout's FAIL-CLOSED was a real
listener outage plus a 120s statement timeout on the full-coverage query).
Claude sampled `market_klines.raw_payload.raw` for binance 1m rows at
mid-year probes 2020..2026: every sampled row has a 12-element array with
slots 9/10 populated. Historical rows DO retain taker fields → CVD capture
is a zero-download parse (Option A). Full per-symbol-year coverage remains
to be computed inside the Stage-2 probe's data_availability check using
ts-bounded chunk-friendly queries (the scout's single full-scan aggregate
exceeds the 120s timeout; do not reuse that query shape).

Rulings on the three questions:

1. **Option A → B order: RATIFIED.** Parse `raw_payload.raw[9]` for the
   bounded probe; Option B (nullable column) only if repeated use makes JSON
   extraction measurably costly, and then via its own migration ADR. C
   rejected.
2. **Candidate 3 (term structure): DEFERRED, not killed.** 0.736744 is a
   funding-vs-basis proxy, not the candidate signal, so it cannot kill the
   family — but it is a strong collision warning. No acquisition or spec
   work; revisit only if both CVD and liquidation die.
3. **First ingestion-capture task: candidate 2 (liquidation)** — new
   mechanism, no collision warning. Gated on the S2 human network step.

Gate status after this review: CVD Stage-2 probe UNBLOCKED (task to be
specced; must embed the full coverage check + R6.6 ex-ante reference-range
declaration); liquidation spec waits on the S2 human commands; term
structure deferred.

## Verification and handoff

Implementation summary: added one read-only scout, two minimal unit tests, and
this report. The scout makes no HTTP calls and forces DB read-only mode.

Diff scope: only the three task-permitted new files. Business-rule change: no.
Experiment/ledger change: none. Backtest/result artifacts: none.

Checks run:

- `python -m pytest tests\unit\test_scout_free_datasets.py -q -p no:cacheprovider`
  -> `2 passed in 0.60s` (final run).
- `python -m ruff check scripts\scout_free_datasets.py tests\unit\test_scout_free_datasets.py`
  -> `All checks passed!`.
- Makefile-equivalent `docs-check` -> metadata, 247 feature-map paths, and
  ledger consistency all passed.
- Read-only DB scout -> FAIL CLOSED before query for the listener/authentication
  reasons above; no DB result is claimed.
- Local parquet/file diagnostic -> liquidation files 0, delivery files 0,
  BTC common days 0, ETH common days 898/correlation 0.736744.

Rollback: delete the three new permitted files; no data or schema rollback exists.

Questions for Claude review:

1. Does the conditional Option A -> B order preserve the intended S1 provenance?
2. Is ETH's 0.736744 proxy enough to defer candidate 3 pending direct
   delivery-curve distinctness, or should it kill the family before acquisition?
3. After human metadata verification, which candidate (2 or 3) merits the first
   separate ingestion-capture task?

Next action: Claude reviews this report and decides whether the user should first
restore the repo TimescaleDB for S1 or run the metadata-only S2/S3 commands.

Human Learning Notes: the current code already retains Binance taker slots in
raw JSON, but local parquet deliberately strips them; DB availability therefore
decides whether CVD is a zero-download parse or a genuine capture task. Also,
the local ETH basis/funding proxy is strongly correlated, making term structure
high-risk for family duplication before any vendor work is justified.

## Five-line gate handoff

1. CVD probe: **BLOCKED** — current parser path exists, but historical DB raw coverage is UNCONFIRMED.
2. CVD capture: **PENDING CLAUDE** — zero-download raw parse if S1 YES; separate reviewed capture only if NO.
3. Liquidation spec: **NEEDS HUMAN NETWORK STEP** — no local file/count; all upstream facts UNCONFIRMED.
4. Term-structure spec: **BLOCKED** — no delivery data; ETH funding/basis proxy corr is 0.736744, BTC unavailable.
5. Deployment: **NOT APPLICABLE / NOT READY** — no probe, experiment, backtest, promotion, shadow, demo, or live evidence.

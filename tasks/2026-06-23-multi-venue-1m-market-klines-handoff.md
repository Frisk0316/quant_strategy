---
status: current
type: handoff
owner: claude
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Codex Handoff: Multi-venue 1m OHLCV into `market_klines` (cross-venue comparison)

## Task
Bulk-ingest **OKX** and **Bybit** universe 1m klines into the multi-exchange
tables (`market_instruments` + `market_klines`) so the same symbol's bars from
binance / okx / bybit sit **side-by-side at the same timestamp** for cross-venue
comparison. Do **not** collapse them into `canonical_candles` — canonical stays
one-source-per-bar, binance-priority (okx's existing legacy mirror is fine).

This is a **data-ops + one-bugfix** task. The ingestion engine already exists and
already supports all three venues — do not write new downloaders.

## Strategy/spec source
- User decision 2026-06-23: next data step = OKX+Bybit 1m into `market_klines`
  for comparison (not canonical).
- `docs/superpowers/specs/2026-06-23-xs-momentum-universe-design.md` (universe
  list / venue-tagged data); `docs/DATA_FLOW.md` (CandleStore → market_klines).
- Memory: venue/data strategy (binance-primary, multi-venue side-by-side).

## Required behavior
1. For OKX and Bybit, run `scripts/market_data/ingest.py` over the universe
   symbols (the 30 in `config/universe.yaml` / `canonical_candles`) that actually
   list on each venue. Engine = `CandleStore.upsert_market_klines`, resumable via
   checkpoints. Exact interface (verified):
   ```
   python scripts/market_data/ingest.py \
     --exchange {okx|bybit} --dataset klines_1m \
     --symbols <native,comma,separated> \
     --start <ISO or omit for venue default> --end now \
     --direction <forward|backward>
   ```
   - **Symbol format is venue-native**: binance/bybit = `BTCUSDT` (no dash, no
     `-SWAP`); okx = `BTC-USDT-SWAP`. Map normalized `BASE-USDT-SWAP` → native per
     venue.
   - **Auto-skip via listing lookup (user decision 2026-06-23): no manual denylist.**
     Intersect the universe against each venue's live-listed instruments and skip
     anything not listed. **Reuse the existing listing endpoint** —
     `GET /api/data/instruments?exchange=<venue>` (and the clients behind it), do
     not build a new listing query:
     - OKX: already wired (`?exchange=okx` → `OKXPublicClient.get_instruments`,
       returns `state`/`list_time_ms`). Use `state == 'live'`.
     - **Bybit: the listing path does NOT exist yet** — the `/instruments` endpoint
       only branches binance/okx (non-binance falls through to a hardcoded
       `OKXPublicClient`), and `BybitPublicClient` has no `get_instruments`. Add a
       small `BybitPublicClient.get_instruments` + a `bybit` branch in
       `/instruments` mirroring the okx branch (preferred, keeps the pattern
       symmetric). Acceptable fallback if blocked: auto-skip by catching the
       per-symbol ingest "not listed / empty" error.
   - **OKX `klines_1m` REQUIRES `--direction backward`** (ingest.py raises
     otherwise). OKX 1m history starts ~2023-07-01; Bybit ~2020-03-25 — both cover
     the 2024+ research window.
   - okx also mirrors into legacy raw/canonical by design (binance-priority gap-fill
     only, never overwrites binance) — leave that as-is. bybit writes
     market_klines/instruments only.
2. Fix the `/api/data/exchanges` bug: it queries `market_klines.exchange`, a column
   that does not exist (exchange lives on `market_instruments`). Make it derive
   exchange via a JOIN to `market_instruments` (or from `data_source`) so the Run
   Backtest venue dropdown reflects real DB availability instead of silently
   falling back to the hardcoded default list.

## PERMITTED FILES (only edit these)
- `scripts/market_data/ingest.py` — only if a real bug blocks a venue run (prefer
  running it as-is). Optional: a thin `scripts/market_data/ingest_universe.py`
  loop that maps universe → native symbols per venue and shells the commands.
- `src/okx_quant/api/routes_data.py` — the `/exchanges` query fix **and** a `bybit`
  branch in `/instruments` (mirror the okx branch). No other endpoint changes.
- `src/okx_quant/data/exchange_clients/bybit_public.py` — add a `get_instruments`
  method symmetric to `OKXPublicClient.get_instruments` (listing lookup for
  auto-skip). Do not change its kline/funding fetch behavior.
- `tests/unit/test_routes_data*.py` — coverage for the `/exchanges` + `/instruments`
  bybit changes.
- `docs/change_manifests/2026-06-23-multi-venue-1m-market-klines.md` (new).
- `docs/DATA_FLOW.md`, `docs/DOC_IMPACT_MATRIX.md` rows (data-ingestion/provenance).
- `config/universe.yaml` — **READ only** to source the symbol list; do not edit.

## FORBIDDEN (do not touch)
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`
- `src/okx_quant/data/canonical_policy.py` (do NOT change source priority)
- `backtesting/` — especially `data_loader.py` venue-scoping and
  `xs_momentum*.py` (separate, parallel workstream — must not regress)
- `config/risk.yaml`, deployment/live/shadow/demo gates
- Existing result artifacts under `results/`
- Any DB schema migration — `market_instruments`/`market_klines` already support
  per-venue side-by-side; no schema change is needed. Do not bulk-rewrite
  `canonical_candles`.

## SCOPE LIMIT
Ingest okx+bybit 1m into market_klines and fix the `/exchanges` query. Do not
refactor ingest.py, CandleStore, the coverage endpoint, or the canonical layer.
Do not "improve" canonical priority or venue-scoped backtest reads.

## REQUIRED ON COMPLETION
- List changed files and the exact ingest commands actually run (per venue/symbol
  batch), plus row counts achieved.
- Run: `make docs-impact` (confirm the right data-ingestion/provenance row),
  `make check-config` if config touched, and the `/exchanges` unit test.
- Verification query (must show ≥2 venues for a major):
  ```sql
  SELECT mi.normalized_symbol, mi.exchange, COUNT(*) rows,
         MIN(mk.ts)::date, MAX(mk.ts)::date
  FROM market_klines mk JOIN market_instruments mi USING (instrument_id)
  WHERE mk.bar='1m' AND mi.normalized_symbol IN
        ('BTC-USDT-SWAP','ETH-USDT-SWAP','SOL-USDT-SWAP')
  GROUP BY 1,2 ORDER BY 1,2;
  ```
- Create the Change Manifest (data provenance area) and update `docs/DATA_FLOW.md`.
- Commit with an `AI-Origin: Codex` trailer when committing is requested.

## ACCEPTANCE CRITERIA (binary)
- [ ] `market_klines` `klines_1m` exists for **OKX** for every universe symbol
      listed on OKX, covering listing→now within the 2024+ window, `data_source='okx'`.
- [ ] Same for **Bybit** (`data_source='bybit'`) for every universe symbol listed
      on Bybit.
- [ ] The verification query returns **binance + okx (+ bybit)** rows for the same
      `normalized_symbol` at overlapping timestamps for BTC/ETH/SOL.
- [ ] `GET /api/data/exchanges` returns real per-exchange availability/row counts
      (not the hardcoded fallback), with a passing unit test.
- [ ] `canonical_candles` source-priority behavior is unchanged; no binance row was
      overwritten; XS-momentum binance venue-scoped reads still pass.
- [ ] Change Manifest created; `make docs-impact` clean for this change.

## Notes / risks
- Feasibility already de-risked: `ingest.py` imports working
  `OKXPublicClient`/`BybitPublicClient`; okx 638K + binance 34.4M rows already
  coexist in `market_klines`, so the architecture is proven — this is depth + bybit.
- Per-venue listing differs; do not assert all 30 symbols on every venue.
- Public-API rate limits / history caps may cap how far back 1m goes per symbol;
  report actual achieved ranges rather than forcing a fixed start.
- Rollback: this is additive ingestion into market_instruments/market_klines plus
  a read-query fix. Rollback = stop ingestion + revert the `routes_data.py` diff;
  no destructive ops on existing data.

## Resolved decisions
- Symbol skipping = **auto-skip via listing lookup, no manual denylist** (user,
  2026-06-23). Reuse `GET /api/data/instruments`; add the missing bybit listing
  path as scoped above.

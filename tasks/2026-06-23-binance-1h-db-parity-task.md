---
status: current
type: task
owner: claude
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Claude → Codex Task: Unblock DB parity for Binance 1H runs (data gap)

## Task
Make `db_parity` able to PASS for the **Binance BTC-USDT-SWAP 1H** validation-lab
runs by ensuring the DB holds **binance-sourced 1H canonical candles** for the run
window, then running source-provenance / differential validation with the DSN +
DB-parity flag and saving the evidence.

## Why (verified by Claude on 2026-06-23 against the live DB)
DSN `postgresql://quant:changeme@localhost:5432/quant` (port 5432) is reachable.
For `inst_id='BTC-USDT-SWAP'` in `canonical_candles`:

| source_primary | bar | rows | range |
|---|---|---|---|
| okx | 1H | 20928 | 2024-01-01 → 2026-05-21 |
| binance | 1m | 3,536,160 | 2019-09-25 → 2026-06-16 |
| okx | 1m | 1440 | 2024-04-29 (one day) |

There are **zero binance-sourced 1H rows**. The validation-lab runs are tagged
`exchange=binance` and read 1H prices from **parquet** (`./data/ticks`, e.g.
2024-01-01T00 close = 42503.5), which is genuinely Binance and differs from DB
okx 1H (42476.0) by the real venue basis. ADR-0007 scoped DB parity to compare a
run against `source_primary == <run exchange>` canonical candles, so a Binance run
needs **binance 1H** canonical to match against. With only binance 1m + okx 1H in
the DB, db_parity is structurally SKIP/FAIL for these runs:
`ohlcv_source_validation == artifact_pass_db_skipped`.

This is a **data gap, not a config gap** — setting the DSN alone will not pass.

Note also: the existing "durable PASS" artifact
`results/adr0007_binance_btc_1h_db_pass_20260618/.../codex_close_only_db_parity_pass_20260618/validation_result.json`
records `db_parity.status == PASS`, `canonical_source_primary == binance` over
192 bars, but the **current DB has no binance 1H rows**, so that PASS is **not
reproducible against the current DB**. Confirm whether the 192-bar binance 1H
window was a since-removed seed, and either re-seed or mark the artifact stale.

## Strategy/spec source
- `docs/ai_collaboration.md` "Differential validation：資料來源與結論輸出" and the
  ct_val/db_parity gate text (DB parity SKIP ≠ PASS).
- ADR-0007 (multi-venue specs; exchange-scoped canonical reads via `source_primary`).
- `okx_quant.data.canonical_policy` priority `manual > binance > okx > ...`.
- This task does NOT change any gate threshold or tolerance.

## Required behavior
1. Populate **binance 1H canonical candles** for BTC-USDT-SWAP (and ETH-USDT-SWAP
   if you also want EMA/MACD multi-symbol coverage) for at least 2024-01-01 →
   2026-04-30, using the **existing** tooling — prefer locate-before-edit:
   - Option 1 (preferred, data already present): resample the existing
     binance **1m** canonical (3.5M rows) up to **1H** and upsert as
     `source_primary='binance'`, reusing `CandleStore` canonicalization /
     `scripts/_db_writer.py` rather than writing a new path.
   - Option 2: fetch binance 1H directly via `scripts/download_binance_data.py`
     (which already mirrors parquet + canonical and syncs `venue_instrument_specs`).
   - Whichever path: the resulting 1H rows must carry `source_primary='binance'`
     and respect the canonical policy (do not let okx overwrite binance at 1H).
2. Re-run validation with DB parity enabled and the DSN set, on the saved Binance
   1H `strategy_fill` runs (reuse, do not reinvent):
   - `DATABASE_URL=<dsn> DIFF_VALIDATION_ENABLE_DB_PARITY=1 NUMBA_DISABLE_JIT=1 \
      python scripts/run_source_provenance_validation.py --run-id <binance_run_id>`
   - Confirm the run's parquet-sourced `price_series.csv` 1H closes match the new
     DB binance 1H closes within tolerance.
3. Save the passing evidence and point CURRENT_STATE / the report at it.

## PERMITTED FILES (only edit/create these)
- Data ingestion/canonicalization invocation only via existing entrypoints:
  `scripts/download_binance_data.py`, `scripts/_db_writer.py`,
  `src/okx_quant/data/` candle-store canonicalization **only if a 1m→1H resample
  helper must be added** (additive; no schema change; coordinate — this is the one
  src/ exception and must stay within data-layer, not trading-core).
- New helper script if needed: `scripts/resample_binance_1h_canonical.py`.
- `results/**` NEW validation evidence dirs only (do not modify existing artifacts).
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/KNOWN_ISSUES.md` (record the
  data gap + resolution), `docs/RUNBOOK.md` (the re-seed + validate commands).

## FORBIDDEN (do not touch)
- `backtesting/differential_validation.py` gate logic / tolerances.
- Trading-core: `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`,
  `execution/`.
- DB **schema** / migrations (this is data population, not schema).
- Live/shadow/demo or deployment-gate wording, `config/*.yaml`.
- Existing result artifacts (no migration/overwrite); the stale 2026-06-18 PASS
  artifact may only get a `SUPERSEDED.md` note if confirmed unreproducible.

## SCOPE LIMIT
Populate binance 1H canonical + run DB parity + save evidence. Do not change
strategy/execution behavior, do not "fix" the run to read DB instead of parquet,
do not alter gate thresholds. This proves the **source-data leg** (our backtest
fed authoritative Binance data); it is still NOT promotion/live evidence because
the runs are idealized `strategy_fill`.

## REQUIRED ON COMPLETION
- Paste DB row counts before/after for binance 1H BTC-USDT-SWAP.
- Paste the validation output showing `checks.db_parity.status == PASS`,
  `canonical_source_primary == binance`, `ohlcv_source_validation == db_parity_pass`.
- Resolve the stale 2026-06-18 PASS artifact question explicitly.
- Update docs listed above. Confirm `make docs-impact` clean (data population is
  not a business-rule change → no Change Manifest).

## ACCEPTANCE CRITERIA
- [ ] DB has binance-sourced 1H canonical candles for BTC-USDT-SWAP covering
      2024-01-01 → 2026-04-30 (and ETH if multi-symbol parity wanted).
- [ ] `db_parity.status == PASS` with `canonical_source_primary == binance` on at
      least the MA Binance 1H `strategy_fill` run; price_series closes match DB
      binance 1H within tolerance.
- [ ] `ohlcv_source_validation == db_parity_pass` (no longer `artifact_pass_db_skipped`).
- [ ] No edits to gate logic, trading-core, schema, config, or existing artifacts.
- [ ] Stale 2026-06-18 binance-1H PASS artifact reproduced OR marked superseded.

## Reviewer (Claude) risk-checks for the diff
- Canonical policy must not let okx 1H shadow binance 1H (priority binance > okx).
  Verify the new 1H rows actually land as `source_primary='binance'` and are the
  ones the parity read selects.
- 1m→1H resample bar-close/label alignment (right vs left label, UTC) must match
  the parquet the runs used, else closes mismatch and parity falsely fails.
- Do not silently let a SKIP read as PASS — the gate already treats SKIP as fail;
  keep it that way.

## Relationship to the other task
Independent of `tasks/2026-06-23-engine-consistency-smoke-task.md` (engine-logic
leg). Engine-consistency proves we COMPUTE signals like public engines; this
proves we FED authoritative Binance data. Both are needed for a complete
"our backtest is trustworthy" story; neither is promotion evidence alone.

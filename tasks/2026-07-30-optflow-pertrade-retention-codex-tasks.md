---
status: current
type: task
owner: claude
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Retain the full Deribit per-trade option tape (unblocks H-031, H-035)

Why: E-070/E-073 stopped data-blocked because
`src/okx_quant/data/external_clients/deribit_option_flow.py:173-174` caps each
hourly row at the first 20 inverse trades (`sample_rule:
"first_20_inverse_trades_in_hour"`). H-035's whole mechanism is **trade-size**
conditioning and H-031 needs a flow-derived gamma proxy — both require the
full tape.

## Verified feasibility (scouted 2026-07-30, do not re-derive)

- `trade_count` already increments for **every** trade (line 165), so true
  volume is known today: **12,724,097 BTC + 7,378,106 ETH ≈ 20.1M trades**
  over 2024-01→now across 44,805 hourly rows (mean 568/hr BTC, 329/hr ETH;
  p95 1,493/912; max 6,809/4,578).
- Measured per-trade JSONB cost ≈ **97 bytes** → total ≈ **1.5–2.0 GB**. This
  is a manageable size, not a tens-of-GB problem.
- A live read-only probe of `history.deribit.com` for 2024-01-15 returned real
  trades with `has_more:false`, so **a re-backfill can recover the full tape
  for all of 2024-01+**; this is not forward-accrual-only.
- **`external_observations` PK is `(dataset_id, observed_at)`**, so a per-trade
  row-per-trade layout is not possible under the existing hourly dataset_id
  without a new table. Storing the full array in the existing hourly row's
  `raw_payload` JSONB needs **zero migration**.
- **Timestamps are NOT unique:** in 10,000 sampled stored trades, 391 of 500
  hours (78%) contained at least one duplicate-millisecond pair (1,205
  instances), consistent with multi-leg/sweep fills. Any keying, dedup, or
  ordering logic must use **`trade_id`**, never the timestamp alone.

## T1 — Remove the cap, keep the aggregates bit-for-bit identical

Edit `deribit_option_flow.py` so the hourly row retains every inverse trade in
`raw_payload` (drop the `< 20` guard; replace `sample_rule` with an honest
marker such as `"all_inverse_trades_in_hour"`). Aggregate/summary fields must
be computed exactly as today.

**Immutability requirement (critical).** E-064 and E-068 consumed the existing
aggregate fields. The re-backfill upserts over those rows, so a change in any
aggregate value would retroactively alter evidence behind an already-registered
experiment. Before the full re-backfill, prove on a sample that this cannot
happen.

Acceptance (binary):
- [ ] Unit test: for a fixture hour with >20 trades, every trade appears in
      `raw_payload` and the aggregate fields are unchanged versus the current
      capped implementation.
- [ ] Immutability check on ≥3 real historical hours per currency: dump the
      current aggregate fields, re-run the adapter over the same window, and
      show the aggregate values are **numerically identical**. Any difference
      stops the task and is reported to Claude before any bulk re-backfill.
- [ ] `trade_id` is retained on every stored trade.

## T2 — Re-backfill 2024-01-01 → now

Run `scripts/market_data/backfill_deribit_option_flow.py` (or the standard
ingest path it uses) for `optflow_deribit_btc` and `optflow_deribit_eth` from
2024-01-01 to the last complete-bucket hour. Chunk by month, log per chunk,
re-run a failed month once. Expect the newest ~1 day to remain archive-lagged.

Acceptance (binary):
- [ ] Post-backfill row counts unchanged (~22,403 / ~22,402 hourly rows) —
      this is a field-enrichment, not a row-count change.
- [ ] Retained trade total is within a few percent of the 20.1M estimate; the
      per-hour retained count equals `trade_count` for a sampled set of hours.
- [ ] DB size delta reported and in the 1–3 GB range; if it materially exceeds
      that, stop and report.
- [ ] Spot-check that the aggregates on previously-existing rows are unchanged
      (same check as T1, now post-hoc on real re-ingested rows).

## T3 — Docs and impact

Update `config/external_data.yaml` notes for both optflow datasets (retention
changed from a 20-trade sample to the full inverse tape, with the storage
figure), `docs/DATA_FLOW.md`, and `docs/FEATURE_MAP.md`. Run
`python scripts/docs/check_doc_impact.py` and follow whatever it flags —
data-provenance retention may require a Change Manifest; if the matrix says so,
create one from `docs/CHANGE_MANIFEST_TEMPLATE.md`.

**Out of scope:** any change to H-031/H-035 probe modules or any Stage-2 re-run.
Unblocking the data and re-running the probes are separate steps; the re-run
needs its own authorization.

## PERMITTED FILES

`src/okx_quant/data/external_clients/deribit_option_flow.py`,
`tests/unit/test_deribit_option_flow.py`,
`scripts/market_data/backfill_deribit_option_flow.py` (only if chunking needs
it), `config/external_data.yaml` (notes only), `docs/DATA_FLOW.md`,
`docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `config/workstreams.yaml`,
`docs/CHANGELOG_AI.md`, `docs/change_manifests/` (new manifest if required).

## FORBIDDEN

`src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
`config/risk.yaml`, `config/settings.yaml`, `backtesting/**` (including the
probe modules), existing `results/**` artifacts, any ledger row, any Stage-2
or Stage-3 run, any new DB migration (the JSONB path needs none).

REPORT: standard AGENTS.md block, plus the immutability evidence (before/after
aggregate values) and the measured storage delta.

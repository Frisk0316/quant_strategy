---
status: current
type: task
owner: claude
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Fix count-dependent pagination loss, then finish the optflow tape enrichment

Why: the 2026-07-30 enrichment was stopped because the BTC aggregate trade total
moved from 12,724,097 to 12,724,092 (-5). That drift was attributed to an
"upstream archive revision". **That attribution is wrong** and must not be
recorded as fact. The retained trade set is a function of pagination geometry,
so a different chunk window or `count` changes the count with zero upstream
change. Fix the fetch, make the write path structurally unable to touch frozen
aggregates, then finish the enrichment.

## Verified evidence (measured 2026-07-30, do NOT re-derive)

- `deribit_option_flow.py:106` advances pages with
  `params["end_timestamp"] = min_ts - 1`. When a `count`-sized page is truncated
  inside a millisecond that holds several trades, every remaining trade at that
  millisecond is **skipped permanently**. 78% of hours contain duplicate-ms
  pairs, so boundaries land inside ties routinely.
- Live read-only probe, BTC hour `2024-01-10 21:00Z` (stored `trade_count`
  4054), same window and same upstream data:

  | client | `count` | pages | inverse trades |
  | --- | --- | --- | --- |
  | current | 1000 | 5 | **4054** |
  | current | 100 | 41 | **4053** |
  | fixed (inclusive boundary) | 1000 | 6 | 4054 |
  | fixed (inclusive boundary) | 100 | 42 | 4054 |

  The current client is count-dependent; the fix is count-invariant.
- `--chunk-days` (default 1) sets those window boundaries, so a monthly-chunked
  re-ingest and a daily-chunked original ingest are expected to disagree by a
  handful of trades. This fully explains -5 with no archive revision.
- Blast radius of the -5 is **one** experiment: E-064 (H-024). E-068 is
  F-FUNDING-SETTLEMENT-DRIFT on Binance settlements and never consumed optflow —
  the earlier task file was wrong about it. E-064 failed at coverage 0.770784 vs
  0.95, max abs corr 0.189378, net Sharpe 0.171120 vs floor 1.256805; 5 trades
  out of 12.72M cannot move any of those. `results/**` was never written, its
  SHA-256 is intact. **E-064 stands. No re-run is authorized.**
- Current DB state: BTC 22,403 rows / 2,304 enriched hours; ETH 22,402 rows /
  744 enriched hours; `trade_count = jsonb_array_length(raw_payload->'sample')`
  holds on **all** 3,048 enriched rows (0 mismatches). Partial storage 76.0 MB
  for 3,048 hours → full 44,805 hours extrapolates to ~1.1 GB.

## T1 — Make `fetch_trades` count-invariant

In `deribit_option_flow.py:84-110`:

- Advance with the **inclusive** boundary `params["end_timestamp"] = min_ts`
  (the `trades` dict is already keyed by `trade_id`, so re-served rows dedupe).
- Stop when a page adds **no new `trade_id`** (`len(trades) == before`) or when
  `min_ts < _to_ms(start)`. Note `<`, not `<=`: the window's first millisecond
  needs one more sweep page.
- Delete the `seen_ends` set and drop `has_more` from the loop condition — the
  no-new-id guard subsumes both and costs one extra request per chunk.
- Keep `sorting: "desc"` and the `observed_at < start or >= end` range filter
  exactly as they are.

Acceptance (binary):
- [ ] Unit test with a fake `_get` pager whose page boundary falls inside a
      3-trade millisecond tie: assert every trade is retained, and that
      `count=2` and `count=10` return **identical** `trade_id` sets.
- [ ] A single-ms group larger than `count` terminates (no infinite loop) and is
      reported, not silently truncated.
- [ ] Existing `test_option_flow_client_paginates_has_more` still passes, or is
      updated with a stated reason if the boundary change makes its expected
      request sequence obsolete.

## T2 — Payload-only write path for existing rows

`external_store.upsert_observations` (`external_store.py:163-170`) currently
rewrites `value_num`, `fields`, `published_at`, `quality_status` on conflict.
Add `payload_only: bool = False`; when true the `ON CONFLICT DO UPDATE SET`
clause sets **only** `raw_payload` and `ingested_at`. Inserts of genuinely new
`observed_at` rows stay full — a new hour has no frozen evidence.

Add a `--payload-only` flag to `scripts/market_data/backfill_deribit_option_flow.py`
that threads through to the store call.

Acceptance (binary):
- [ ] Unit/integration test: pre-seed one row, upsert with `payload_only=True`
      carrying different `value_num`/`fields`/`published_at`, assert only
      `raw_payload` and `ingested_at` changed.
- [ ] Default behaviour (`payload_only=False`) is byte-identical to today for
      every other dataset; no other caller's signature changes.

## T3 — Finish the enrichment under the frozen-aggregate contract

1. **Before running**, capture the baseline to a file (not to chat):
   ```sql
   select dataset_id, count(*) rows,
          sum((fields->>'trade_count')::bigint) trades,
          round(sum((fields->>'premium_volume')::numeric), 8) premium,
          md5(string_agg(coalesce(value_num::text,'~'), ',' order by observed_at)) vhash
   from external_observations
   where dataset_id in ('optflow_deribit_btc','optflow_deribit_eth')
   group by 1 order by 1;
   ```
2. Run `--payload-only` for both datasets, 2024-01-01 → last complete-bucket
   hour, `--chunk-days 1`, **at most one worker per currency**, log per chunk
   with the `count` and `chunk_days` actually used. Re-run a failed chunk once.

Acceptance (binary):
- [ ] The four fingerprint values per dataset are **identical** to the captured
      baseline. Any difference is a T2 defect: stop and report, do not proceed.
- [ ] Row counts unchanged (22,403 / 22,402).
- [ ] Every row with `sample_rule = 'all_inverse_trades_in_hour'` satisfies
      `jsonb_array_length(raw_payload->'sample') >= (fields->>'trade_count')::int`.
      `>=` is correct and expected: the tape now comes from the fixed fetch
      while the aggregate stays frozen from the older lossy one. Report how many
      rows are strictly `>` and the largest per-row gap.
- [ ] Field proof against the live archive, not just the fake pager: for 3 real
      high-volume hours, fetch with `count=100` and `count=1000` and assert
      identical `trade_id` sets.
- [ ] DB size delta reported; expected ~1.1 GB, stop and report if it exceeds
      3 GB.
- [ ] Newest ~1 day may stay archive-lagged; name it, do not "fix" it.

## T4 — Docs: record the real cause, drop the wrong one

- `docs/KNOWN_ISSUES.md`: new durable entry for the -5. Include the count-
  dependent-pagination cause, that it is localised to the 2,304 BTC enriched
  hours, that the 5 trades also shifted those hours' premium fields and
  `value_num` (it is **not** a trade-count-only drift), the E-064 materiality
  analysis above, that no pre-task DB backup exists so no restoration is
  attempted, and that the frozen aggregates are now immutable by construction.
- Also state that the 2026-07-27 moneyness re-ingest had already overwritten
  every optflow aggregate row consumed by E-044..E-049 with user acceptance, so
  `12,724,097` was itself a post-rewrite value. The -5 is the first time this
  class was **measured**, not the first time it happened.
- Remove the "upstream archive revision" wording from all four places:
  `config/external_data.yaml:217` (BTC notes), the ETH notes' "the paired BTC
  history showed aggregate drift", `docs/AI_HANDOFF.md:306`,
  `docs/CHANGELOG_AI.md:28`.
- `config/external_data.yaml` notes keep only durable facts: full inverse tape
  in `raw_payload` including `trade_id`, the `>=` relationship to the frozen
  `trade_count`, the storage figure, and the endpoint auto-selection. Run state
  ("STOPPED/PARTIAL") belongs in KNOWN_ISSUES, not in config.
- `docs/DATA_FLOW.md`, `docs/RUNBOOK.md` (the `--payload-only` command),
  `docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`.
- Run `python scripts/docs/check_doc_impact.py` and follow what it flags. No ADR
  — this corrects an implementation contract, it does not change policy.

## T5 — Invariants and failure modes

- **Amend I51 in place.** Its current text mandates the bug: "moves the next
  page's inclusive end boundary **below** the oldest accepted millisecond".
  Replace with the count-invariant contract: explicit descending sort, an
  inclusive boundary at the oldest accepted millisecond, `trade_id` dedup, and
  termination on no-new-id — so the retained set does not depend on `count` or
  chunk width. Point it at the new T1 test. Do not add a second invariant that
  contradicts I51.
- Add **F60**: "Paginated tape ingestion advances past the boundary
  millisecond" — a `count`-truncated page inside a duplicate-timestamp group
  silently drops trades, and the loss set depends on chunk/page geometry, so two
  honest ingests of identical upstream data disagree and look like an upstream
  revision. Guard: amended I51 plus the count-invariance regression. Rules:
  R6.2.

**Out of scope:** any H-031/H-033/H-035/H-036 probe module change, any Stage-2
or Stage-3 run, any attempt to restore or fabricate the missing 5 trades, and
any change to E-064's artifact or ledger rows.

## PERMITTED FILES

`src/okx_quant/data/external_clients/deribit_option_flow.py`,
`src/okx_quant/data/external_store.py`,
`scripts/market_data/backfill_deribit_option_flow.py`,
`tests/unit/test_deribit_option_flow.py`, `tests/unit/test_external_store.py`
(create if absent), `config/external_data.yaml` (notes only),
`docs/KNOWN_ISSUES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`,
`docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/AI_HANDOFF.md`,
`config/workstreams.yaml`, `docs/CHANGELOG_AI.md`, `docs/change_manifests/`
(only if the impact check demands one).

## FORBIDDEN

`src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
`config/risk.yaml`, `config/settings.yaml`, `backtesting/**`, `research/**`,
existing `results/**` artifacts, any ledger row, any Stage-2/Stage-3 run, any DB
migration or schema change, any non-`--payload-only` write to the two optflow
datasets over historical hours.

REPORT: standard AGENTS.md block, plus the before/after fingerprint table, the
`count=100` vs `count=1000` field proof, the `sample >= trade_count` gap census,
and the measured storage delta.

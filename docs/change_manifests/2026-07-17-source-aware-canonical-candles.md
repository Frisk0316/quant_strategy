---
status: current
type: manifest
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Change Manifest: Source-Aware Canonical Candles

## Summary

Add a venue-keyed canonical layer without changing the existing resolved
canonical identity or aggregates, then promote the authorized frozen-window OKX
BTC/ETH 1m raw rows. A separately authorized extension promotes the same
`raw_candles` source for `[2020-01-01, 2024-01-01)`; the original no-flag
window remains unchanged.

## Design-space expansion

- **No change:** repeated OKX canonicalization remains a no-op under Binance's
  higher source priority. Rejected because simultaneous venues stay invisible.
- **Change the existing identity:** supports both venues but requires blocking
  work on roughly 96 million rows and redesigns all CAGGs/default consumers.
  Rejected for blast radius and mixed-venue aggregation risk.
- **Read `market_klines`:** already source-aware, but frozen Binance ETH is
  incomplete. Rejected for this task.
- **Additive venue layer:** preserves default semantics and changes only
  explicitly source-aware paths. Chosen.

## Business rules and impact areas

- R6.2/R6.4/R6.5: source parity, no venue substitution, and resolved versus
  source-aware canonical identity.
- DOC_IMPACT areas A5 (pipeline/data consumers), A6 (market-data storage), and
  A9 (data/provenance validation).

## Files and behavior

- Migration `004_venue_canonical_candles.sql` adds the hypertable and view.
- `canonical_policy.py`, `candle_store.py`, and `_db_writer.py` preserve future
  raw dual-writes and corrected-row precedence.
- Source-filtered `CandleStore` reads and H-010 coverage queries use the view.
- The promotion and verifier scripts keep their original default window and
  accept explicit ISO-date `--start`/`--end` bounds. The promotion uses an
  aggregate timestamp-fingerprint preflight plus a single rollback-safe
  transaction; the verifier reports raw gap ranges without cross-venue fill.
- API/CLI pair purge paths remove venue rows.

No PnL, fee, funding, sizing, fill, strategy, Stage-3, result artifact, ledger,
demo, shadow, live, or deployment gate changed.

## Invariants and verification

- I19 and new I47.
- Focused unit tests cover additive DDL, dual-writes, source-aware reads, fixed
  scope, correction protection, and delete behavior.
- Real DB result: BTC/ETH raw and venue rows each 1,293,120, mismatch rows 0,
  coverage/alignment 1.0, resolved OKX rows 0; rerun changes 0 rows.
- 2026-07-18 history extension: BTC/ETH each added 2,103,840 venue rows and
  changed zero resolved rows. The final-code rerun changed zero venue/resolved
  rows. Full `[2020-01-01, 2026-06-17)` verification has raw=venue=3,396,960
  per leg, mismatch rows 0, coverage/alignment 1.0, `raw_missing_rows=0`, and
  `raw_gap_ranges=[]`. No Binance substitution occurred.
- Resolved global counts were identical before/after: `binance/raw=93,445,900`,
  `deribit/raw=2,667,850`, and `okx/raw=333,723`. Historical full-row
  fingerprints (all columns, including version/timestamps) were also identical:

  | symbol | sum seed 0 | sum seed 8675309 | xor seed 0 | xor seed 8675309 |
  | --- | ---: | ---: | ---: | ---: |
  | BTC | 6922127171844427405884 | -2080101344126597082130 | 6686270681133494998 | -8265973953097470366 |
  | ETH | -9333428199128586167704 | 9978010712606342404315 | -6529162263422461476 | -1035038212029364831 |

## Rollback

Stop source-aware writers/readers, delete only OKX BTC/ETH `1m` venue rows in
the half-open window being rolled back (`[2020-01-01, 2024-01-01)` for the
history extension), then revert code/docs. Drop the compatibility view and
venue table only for a full ADR-0014 rollback. Never delete or rewrite `raw_candles`,
`canonical_candles`, CAGGs, ledgers, or existing results.

## Approval

Explicitly authorized by the user on 2026-07-17. Approval is limited to data
promotion and does not authorize H-010 research or deployment work.

The user separately authorized the 2020-2023 extension on 2026-07-18. This
authorization still excludes H-010 Stage-2/Stage-3 execution, results, verdicts,
promotion, and deployment work.

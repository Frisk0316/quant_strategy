---
status: current
type: manifest
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Change Manifest: Source-Aware Canonical Candles

## Summary

Add a venue-keyed canonical layer without changing the existing resolved
canonical identity or aggregates, then promote the authorized frozen-window OKX
BTC/ETH 1m raw rows.

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
- The fixed promotion and verifier scripts enforce exact scope, raw parity,
  resolved-table preservation, coverage, alignment, and idempotence.
- API/CLI pair purge paths remove venue rows.

No PnL, fee, funding, sizing, fill, strategy, Stage-3, result artifact, ledger,
demo, shadow, live, or deployment gate changed.

## Invariants and verification

- I19 and new I47.
- Focused unit tests cover additive DDL, dual-writes, source-aware reads, fixed
  scope, correction protection, and delete behavior.
- Real DB result: BTC/ETH raw and venue rows each 1,293,120, mismatch rows 0,
  coverage/alignment 1.0, resolved OKX rows 0; rerun changes 0 rows.

## Rollback

Stop source-aware writers/readers, delete only OKX BTC/ETH `1m` venue rows in
the authorized half-open window, drop the compatibility view and venue table,
then revert code/docs. Never delete or rewrite `raw_candles`,
`canonical_candles`, CAGGs, ledgers, or existing results.

## Approval

Explicitly authorized by the user on 2026-07-17. Approval is limited to data
promotion and does not authorize H-010 research or deployment work.


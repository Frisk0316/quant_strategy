---
status: accepted
type: adr
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# ADR-0014: Additive Source-Aware Canonical Candles

## Status

Accepted — 2026-07-17 through explicit user authorization for the OKX
raw-to-canonical promotion task. This is a data-provenance decision only; it
does not authorize an H-010 retry, verdict, Stage 3, promotion, or deployment.

## Context

`raw_candles` retains `(source, inst_id, bar, ts)`, while the existing
`canonical_candles` identity is `(inst_id, bar, ts)` and resolves one winner by
source priority. Complete OKX and Binance BTC/ETH rows therefore cannot coexist
in that table. Changing its identity in place would also make the existing
source-agnostic 5m/15m/1H continuous aggregates mix venues and would require a
blocking migration of roughly 96 million rows.

## Decision

1. Keep `canonical_candles` as the priority-resolved default and leave its
   identity and continuous aggregates unchanged.
2. Add `venue_canonical_candles`, keyed by
   `(source_primary, inst_id, bar, ts)`, for exchange-native canonical rows.
3. Add `canonical_candles_by_source`. Existing resolved rows win over a venue
   row with the same source/key; otherwise the venue row is exposed.
4. Explicitly source-aware consumers use that view. Consumers that intentionally
   request the resolved default continue using `canonical_candles` and its
   aggregates.
5. Raw canonicalization dual-writes the venue layer before retaining the
   existing priority-resolved write. Raw refreshes cannot overwrite
   corrected/validated venue rows and unchanged reruns perform zero updates.
6. The authorized data operation is limited to closed OKX BTC/ETH 1m raw rows
   in `[2024-01-01, 2026-06-17)`.

## Consequences

- Binance and OKX can coexist at identical timestamps without changing default
  backtest/CAGG behavior.
- The completed promotion added 1,293,120 OKX rows per symbol; raw parity,
  coverage, and alignment are 1.0 with zero mismatches. Resolved OKX rows remain
  zero, proving the default layer was not replaced.
- Pair purge paths must delete venue rows before deleting instruments.
- No per-source higher-timeframe aggregate is added. Source-aware higher bars
  continue to require explicit stored bars or future approved resampling work.
- `market_klines` was not selected as the H-010 consumer because its frozen
  Binance ETH leg is incomplete.
- These data facts do not change H-010's ledger status or constitute strategy,
  statistical, promotion, demo, shadow, or live evidence.


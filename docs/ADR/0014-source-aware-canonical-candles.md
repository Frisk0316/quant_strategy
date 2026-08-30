---
status: accepted
type: adr
owner: codex
created: 2026-07-17
last_reviewed: 2026-08-06
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
6. The initial authorized data operation was limited to closed OKX BTC/ETH 1m
   raw rows in `[2024-01-01, 2026-06-17)`.

## Amendment — 2026-08-06 historical-window confirmation

The user authorized extending the same additive promotion mechanism back to the
start of the existing OKX raw history. This is a window extension, not a policy
change: closed BTC/ETH 1m rows in `[2020-01-01, 2026-06-17)` are in scope, while
the priority-resolved Binance layer, funding data, and all other symbols remain
unchanged.

Pre-write measurement found that commit `b40f15b` and its 2026-07-18 data run
had already completed the extension. For `[2020-01-01, 2024-01-01)`, each
symbol had 2,103,840 raw rows, zero missing minutes, zero gap runs, and a largest
gap of zero minutes. Two identical 2026-08-06 promotion runs therefore changed
zero venue rows and zero resolved rows. Full-range verification reported
3,396,960 raw and venue rows per symbol, zero OHLCV mismatches, 1.0 coverage and
alignment, no raw gaps, and zero resolved OKX rows. Affected-window Binance
canonical counts remained 3,396,960 per symbol before and after.

Claude reviewed this amendment on 2026-08-06 and ACCEPTED it: the row counts are
internally consistent (1,461 + 898 = 2,359 days x 1,440), the scope statements
match the delivered diff, and nothing is overclaimed. The coverage/alignment and
Binance-count figures are relayed from the Codex verifier run, not independently
re-queried by the reviewer. It does not unshelve H-010, supply missing pre-2024
OKX funding, create research evidence, or alter any promotion/demo/shadow/live
gate.

## Consequences

- Binance and OKX can coexist at identical timestamps without changing default
  backtest/CAGG behavior.
- The 2024+ first pass added 1,293,120 OKX rows per symbol; with the 2020-2023
  extension the venue layer now holds 3,396,960 rows per symbol. Raw parity,
  coverage, and alignment are 1.0 with zero mismatches. Resolved OKX rows remain
  zero, proving the default layer was not replaced.
- Pair purge paths must delete venue rows before deleting instruments.
- No per-source higher-timeframe aggregate is added. Source-aware higher bars
  continue to require explicit stored bars or future approved resampling work.
- `market_klines` was not selected as the H-010 consumer because its frozen
  Binance ETH leg is incomplete.
- These data facts do not change H-010's ledger status or constitute strategy,
  statistical, promotion, demo, shadow, or live evidence.


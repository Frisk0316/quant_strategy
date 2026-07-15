---
status: accepted
type: adr
owner: claude
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# ADR-0012: Coin-Margined (Inverse) Perpetual Accounting for Research Backtests

## Status

Accepted — 2026-07-15, explicit user sign-off in-session ("簽核") of the
R8-style extension flagged in the H-021 advancement plan. Research scope
only; no engine, live, demo, or gate surface. Unblocks the H-021 Stage-3
full-PnL runner once D6 (venue-scoped Deribit perpetual 1m prices) lands and
E-055 passes the data gate.

## Context

H-021/F-XVENUE-FUNDING-SPREAD trades an equal-USD-delta pair: a Binance USDT
linear perp (existing R1 accounting) against a Deribit coin-margined inverse
perp, which the platform has no accounting rules for. The registered ex-ante
rationale for Stage 3 is that E-054's funding-only proxy excluded
basis-convergence PnL; measuring that requires inverse-perp PnL rules fixed
BEFORE any runner code exists. ADR-0010 covers inverse OPTIONS only.

## Decision (DOMAIN_RULES R9, research scope)

1. **Inverse-perp PnL is computed in coin, then converted for pair
   aggregation.** For a position of `N` USD notional over a bar
   `[t−1, t]` with venue-scoped marks `P`: long coin PnL
   `= N × (1/P_{t−1} − 1/P_t)`; short is the negation. No linear
   approximation.
2. **Pair unit of account is USD** (the pair-NAV framing of the frozen H-021
   contract): the Deribit-leg coin PnL converts at the same-bar venue-scoped
   mark — mark-to-market, never averaged or smoothed. (This deliberately
   differs from R8.1's coin unit: a delta-neutral cross-venue PAIR is a
   USD-relative-value object; a coin-denominated overlay on held coin is a
   coin object.)
3. **Funding:** Deribit `interest_1h` rates apply hourly to USD notional and
   settle in coin (`rate × N / P`); long pays positive (R3.1 sign
   convention); summation into Binance 8h windows follows the frozen H-021
   contract verbatim. Binance-leg funding stays under existing R3 rules.
4. **Collateral/margin:** v1 assumes adequate coin collateral, no
   liquidation model, admissible ONLY for unlevered bounded-gross books
   (H-021: 0.5 per leg, gross 1.0, delta-neutral). Any levered or
   directional inverse-perp book first needs a margin-model ADR. The
   short-inverse-perp + coin-collateral synthetic-USD property must be
   stated, not assumed silently, in every runner using this rule.
5. **Costs:** per-leg bps cost model exactly as pre-registered in the
   hypothesis contract (H-021: 2+2 base, 5+2 stress — the stress mirrors
   Deribit's published 5 bps perp taker fee). No idealized maker fills.
6. **Provenance:** Deribit legs price only from `source_primary='deribit'`
   canonical candles (I19 — no substitution, no index proxy); funding only
   from the `funding_deribit_*` datasets with the F41/I41 ≤1s settlement
   canonicalization.

## Consequences

- H-021 Stage-3 can measure full funding + basis PnL honestly; a golden
  hand-computed inverse-perp cycle test is REQUIRED before any grid run
  (I44).
- The R8.1-vs-R9.2 unit split is explicit, preventing silent unit mixing
  between the options book (coin) and cross-venue pairs (USD).
- Nothing here changes engine accounting, gates, or any live surface;
  promotion still runs the full R7.2 sequence.

## Alternatives considered

- Coin unit of account for the pair: rejected — a USD-neutral pair measured
  in coin re-imports the underlying beta the pair removes.
- Linear PnL approximation (treat inverse as linear): rejected — the 1/P
  convexity is precisely where inverse-perp accounting errors hide.
- Defer until after Stage-3 code: rejected — rules-before-code is the
  ADR-0010 lesson this repo already paid for once.

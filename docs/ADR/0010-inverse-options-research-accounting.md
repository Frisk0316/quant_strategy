---
status: accepted
type: adr
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# ADR-0010: Coin-Margined (Inverse) Options Accounting for Research Backtests

## Status

Accepted — 2026-07-14, explicit user sign-off in-session (single decision
covering this ADR, the Stage-3 spec/data extension/E-051 authorization, and
confirmation that the long leg stays OFF and naked short puts are
prohibited). Implementation authority for RESEARCH scope only.

## Context

H-014 (Deribit BTC/ETH inverse-options vol-regime, user-selected final target
= two-sided switch with the put side as a spread) has passed its mechanism
probe (E-039) and real-premium calibration (E-043), and its entry-leg traded
premiums are collected (`results/h014_leg_marks_20260714/`). The platform's
accounting is USDT-margined perp/spot only; Deribit options are coin-settled
(premium, margin, and payoff in BTC/ETH), which is a new DOMAIN_RULES area.
This ADR fixes the accounting conventions BEFORE any backtest code exists so
the Stage-3 run cannot quietly invent them.

## Decision

Research-grade scope only: these rules govern a research backtest module and
its artifacts. Nothing touches `src/okx_quant/` engine accounting, gates, or
live/demo paths; promotion toward the engine would require a new ADR.

1. **Unit of account = coin.** The H-014 book's PnL, returns, Sharpe, and all
   gate statistics are computed in BTC (resp. ETH) terms. USD-equivalent
   series may be reported as context only, never gated on.
2. **Option cashflows (inverse contracts, 1 contract = 1 coin):**
   - Short leg entry: receive `premium_coin` (traded price is already
     coin-denominated on Deribit). Long leg entry: pay `premium_coin`.
   - Expiry settlement uses the **official Deribit delivery price** `S_T`
     (30-min TWAP of the index before 08:00 UTC, fetched from
     `public/get_delivery_prices`): call payoff `max(S_T−K,0)/S_T` coin,
     put payoff `max(K−S_T,0)/S_T` coin. No early exercise (European).
3. **Structures:** covered call = 1 coin collateral + short 1 call (coin loss
   bounded); put side only as a spread (short 25Δ / long 10Δ) so the
   coin-denominated crash tail is capped. Naked short puts are prohibited in
   this family (wrong-way risk recorded in the H-014 spec).
4. **Margin/liquidation:** v1 assumes the 1-coin collateral covers the short
   call and the spread's max loss covers the put side — no liquidation model.
   This is admissible ONLY because both structures have bounded coin loss;
   any unbounded-loss structure would invalidate this assumption and needs a
   margin model first.
5. **Fees (Deribit published schedule, applied per leg):** trade fee
   `min(0.0003 coin, 12.5% × premium_coin)`; settlement fee
   `min(0.00015 coin, 12.5% × premium_coin)` on expiring ITM options.
   Entry price = real traded day-VWAP (spread crossing already embedded);
   no additional slippage haircut on top.
6. **Marks between entry and expiry** (needed for daily validation returns):
   primary = same-instrument daily trade-tape VWAP; fallback when a held
   instrument does not trade that day = Black-Scholes mark at the day's DVOL
   plus the instrument's last observed (trade IV − DVOL) offset, carried
   flat. Fallback usage is counted and reported; a combo where fallback marks
   exceed 30% of position-days is flagged unreliable.
7. **Provenance:** every mark row records source (`trade_vwap` |
   `bs_dvol_offset`), instrument, and timestamps; collected data files are
   immutable inputs (same rule as other `results/` artifacts).

## Consequences

- The Stage-3 run measures what a coin-denominated holder actually keeps,
  matching the user's 幣本位 framing and E-039/E-043 conventions.
- Bounded-loss-only structures let v1 skip margin modeling; this constraint
  must be re-examined before any structure change (recorded as the trigger
  for a follow-up ADR).
- Trade-tape marks make results reproducible from free official data; vendor
  quote data can later tighten marks without changing the accounting rules.
- On acceptance, `docs/DOMAIN_RULES.md` gains a new "Options (research)"
  section registering rules 1–7 with permanent ids, and
  `docs/DOC_IMPACT_MATRIX.md` gains the corresponding trigger row.

## Alternatives considered

- USD unit of account: rejected — contradicts the user's coin-denominated
  covered-call framing and double-counts coin price exposure.
- Mid-quote entry marks from purchased vendor data: deferred — E-043 showed
  traded premiums are within 0.88–1.03× of model marks; purchase adds
  precision, not validity.
- Full margin/liquidation modeling: rejected for v1 — unnecessary for
  bounded-loss structures, large surface for silent errors.

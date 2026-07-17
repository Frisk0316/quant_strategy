---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Domain Rules

Canonical, human-readable statement of the **business rules** that govern this
trading system. A "business rule" is any rule whose violation changes money,
risk, or research conclusions: PnL accounting, fees, funding, sizing, risk
limits, fill semantics, data provenance, or promotion gates.

This file is the **trigger registry** for the Doc Sync Harness. When a change
touches any rule listed here, the change is a *business-rule change* and must:

1. Create or update a Change Manifest (`docs/CHANGE_MANIFEST_TEMPLATE.md`).
2. Check `docs/DOC_IMPACT_MATRIX.md` and update every impacted document.
3. Add or update an ADR if the rule itself changes (not just its code).
4. Confirm the relevant `docs/INVARIANTS.md` entries still hold.

This document records rules, not implementation. Code is authoritative for
*behavior*; `research/strategy_synthesis.md` and `config/` are authoritative for
*intended* values. Where this file and code disagree, record it as a
current/target/known-gap distinction — do not silently "fix" either side.

---

## R1. PnL Accounting

- **R1.1** SWAP PnL must scale by `ct_val`. A position of `q` contracts at price
  `p` represents `q * ct_val` units of the base asset. Omitting `ct_val`
  overstates or understates PnL by the contract multiplier.
- **R1.2** `ct_val` provenance must be traceable to instrument metadata, not a
  hard-coded constant copied between modules.
- **R1.3** Realized and unrealized PnL must reconcile: closing a position must
  move the exact unrealized amount into realized, net of fees and funding.
- **R1.4** For SWAP replay and promotion evidence, the authoritative `ct_val`
  source must match the run's execution venue. `venue_instrument_specs(exchange,
  symbol)` is the DB-backed authority; normal Binance/Bybit USDT-M perpetuals
  may use the structural `exchange_base_unit` identity (`ct_val = 1.0`) after
  DB lookup; canonical `1000...` multiplier contracts still require DB specs.
  `config/instrument_specs.yaml` is an OKX-only fallback and is not
  promotion-grade evidence for other venues.
- **R1.5** `ct_val` validation accepts only finite values in
  `0 < ct_val <= 1e7`. The cap is a corruption guard, not a replacement for
  R1.4 venue-matched provenance. Enforcement points (closed 2026-07-13):
  every explicitly provided multiplier — fill metadata in
  `PositionLedger.on_fill`, caller-supplied replay `instrument_specs`, and the
  DB/config replay paths — goes through the shared `validate_ct_val()` before
  position state or an authoritative provenance label is written. A missing
  fill metadata value may reuse the position's already-validated multiplier;
  a caller override or DB/config row that claims to supply an instrument spec
  must contain a valid multiplier and otherwise fail closed.

Owning code: `src/okx_quant/portfolio/`, `src/okx_quant/execution/`.

## R2. Fees

- **R2.1** Maker and taker fees are distinct; a maker-only strategy must not be
  charged taker fees in backtest or live accounting.
- **R2.2** Fees are a cashflow and must be reflected in equity, not only in a
  summary metric.

## R3. Funding

- **R3.1** Funding cashflow sign convention: a long pays positive funding and
  receives negative funding (and vice versa). Sign errors invert strategy PnL.
- **R3.2** Funding settles on the venue's settlement schedule (8h windows for
  OKX SWAP). A replay shorter than a settlement window understates funding.
- **R3.3** Funding income/expense must be a tracked cashflow, reconcilable to
  `funding_settlement_count`.

## R4. Sizing and Risk

- **R4.1** Position sizing is driven by `config/risk.yaml` and the portfolio
  layer, never by chat memory or ad-hoc constants.
- **R4.2** Reduce-only and risk-limit semantics must not be weakened without an
  ADR and explicit human approval. Reduce-only close orders may bypass the
  single-order fat-finger cap only up to the current position notional; they
  must not increase absolute exposure.
- **R4.3** No exposure-increasing order may exceed configured per-instrument or
  per-portfolio caps.
- **R4.4** Strategy vol-target sizing must target the quantity named by the
  strategy spec. For market-neutral book-level targets, gross leverage is sized
  from estimated book volatility, not median single-name volatility, and an
  explicit max-gross cap must prevent unbounded leverage in calm regimes.

Owning code: `src/okx_quant/risk/`, `src/okx_quant/portfolio/`.

## R5. Fill and Execution Semantics

- **R5.1** Maker-only orders fill only when price trades through, after the
  configured order and cancel latency.
- **R5.2** Partial fills must leave consistent ledger state; no orphan or
  phantom positions.
- **R5.3** Replay fill model must not look ahead: a fill at bar *t* may only use
  information available at or before *t*.
- **R5.4** Backtest execution profiles are explicit: `strategy_fill` is
  research-only immediate full fill for submitted signal orders, while
  `realistic_execution` keeps maker queue, cancel latency, lot/min rounding,
  post-only behavior, and terminal liquidation. `dual_output` runs both against
  the same data/params and writes a comparison artifact.
- **R5.5** Turtle S1/S2 reference semantics are scoped to the research-only
  `backtesting/turtle_backtest.py` runner: same-day ATR, close fills, strict
  `cost < cash` buy gate, static sizing capital, S1 skip-after-win, and no
  forced end liquidation are preserved for parity with `new_startegy_海龜/`.
  These semantics must not be generalized to replay, live, demo, shadow, or
  promotion evidence without a new approved rule change.

## R6. Data Provenance and Leakage

- **R6.1** No lookahead bias or feature leakage in research or replay.
- **R6.2** DB and parquet sources must agree; a source switch must be explicit
  and recorded. For replay `price_series.csv`, DB parity proves agreement on
  timestamped `close` values; OHLCV structure and volume-unit sanity are separate
  artifact/data-quality checks.
- **R6.3** Trial count must be tracked; hidden trials inflate selection bias.
  Stage-2 statistical-power triage must use the family-cumulative `n_trials`
  recorded in `docs/EXPERIMENT_REGISTRY.md`; missing accounting fails closed.
- **R6.4** A run that declares an execution venue must source candles only from
  provenance-tagged data for that venue. Missing venue bars are explicit
  gaps/errors; they must not be silently substituted from another venue or from
  source-less parquet. Omitting the venue selects the configured primary
  exchange; an explicit unknown venue must fail before the run is queued.
- **R6.5** `canonical_candles` is the priority-resolved default identity.
  A consumer that requires simultaneous exchange-native rows must use the
  source-aware canonical identity `(source_primary, inst_id, bar, ts)`; it must
  not reinterpret the resolved default as multi-venue storage. A same-source
  corrected/validated resolved row takes precedence over raw venue data.

## R7. Promotion Gates

- **R7.1** `naive_backtest`, `in_sample`, idealized-fill, and advisory
  validation output are **not** promotion evidence. This includes
  `strategy_fill` artifacts and `dual_output` comparison summaries.
- **R7.2** No live / shadow / demo readiness claim is valid unless every gate in
  `docs/ai_collaboration.md` passes and the human explicitly approves.
- **R7.3** Promotion candidates require reproducible artifacts and
  walk-forward / CPCV evidence.
- **R7.4** DSR must be computed on the same return-series basis as PSR(0), using
  non-overlapping OOS observations for its sample-size term and honest researched
  `n_trials` as the multiple-trial penalty. For the same series, DSR must not
  exceed PSR(0).

## R8. Options (research + shadow) — ADR-0010 / ADR-0011

These rules govern coin-margined (inverse) options research backtests and the
credential-free ADR-0011 H-014 shadow path. They do not authorize engine,
live/demo, private-endpoint, or USDT-perp accounting changes; promotion toward
real execution requires a new ADR and R7.2 approval.

- **R8.1** Unit of account is the coin (BTC/ETH). Gate statistics are computed
  on coin-denominated returns; USD series are context only.
- **R8.2** Expiry settlement uses the official Deribit delivery price; call
  payoff `max(S_T−K,0)/S_T` coin, put payoff `max(K−S_T,0)/S_T` coin;
  European, no early exercise.
- **R8.3** Only bounded-coin-loss structures are allowed (covered call;
  25Δ/10Δ put spread). Naked short puts are prohibited (user-confirmed
  2026-07-14). This bound is what licenses the absence of a margin model;
  any unbounded structure first needs a margin-model ADR. The ADR-0011 shadow
  path rejects an unpaired short-put intent before quote/fill handling and caps
  aggregate open tranches at `1.0` unit per symbol.
- **R8.4** Fees per Deribit's published schedule: trade fee
  `min(0.0003 coin, 12.5% × premium)` per leg; settlement fee
  `min(0.00015 coin, 12.5% × premium)` on expiring ITM options. Entry price
  is the real traded VWAP in research. ADR-0011 shadow sells at live bid and
  buys at live ask; no additional synthetic haircut is added.
- **R8.5** Daily marks: same-instrument trade-tape VWAP first; fallback =
  BS mark at day DVOL plus the instrument's last observed IV offset. Fallback
  usage is counted; a combo above 30% fallback position-days is unreliable.
- **R8.6** Every mark row records its source, instrument, and timestamps;
  collected mark/leg files are immutable inputs.
- **R8.7** ADR-0011 v1 is append-only JSONL shadow evidence using DB F26 as-of
  signals and allow-listed Deribit public market-data methods only. It has no
  credential or order capability. Chain-construction failures journal as
  `missed_entry`; R8.3 intent-set failures journal as `rejected`, which is
  counted separately from and excluded from the missed-entry denominator like
  `cap_rejected`. At least eight weeks of fresh daily records plus fill-bias,
  missed-entry, and mark-tracking metrics unlock only a future live-ADR
  discussion; live still requires R7.2 and explicit user approval.

## R9. Coin-margined perpetuals (research) — ADR-0012

Research-backtest accounting for Deribit inverse perpetuals (currently only
H-021's cross-venue funding-spread pair). No engine/live surface.

- **R9.1** Inverse-perp PnL is exact, in coin: long over a bar
  `= N_usd × (1/P_prev − 1/P_now)`; short is the negation. No linear
  approximation of the 1/P convexity.
- **R9.2** A cross-venue delta-neutral PAIR aggregates in USD: the coin leg
  converts at the same-bar venue-scoped mark, mark-to-market, never smoothed.
  (Deliberate split vs R8.1's coin unit for coin-collateral overlays.)
- **R9.3** Deribit funding: `interest_1h` on USD notional settles in coin
  (`rate × N / P`), long pays positive (R3.1 sign); interval summation per
  the frozen hypothesis contract with F41/I41 ≤1s canonicalization.
- **R9.4** The no-margin/no-liquidation assumption is admissible ONLY for
  unlevered, bounded-gross, delta-neutral books; anything levered or
  directional first needs a margin-model ADR.
- **R9.5** Costs follow the hypothesis's pre-registered per-leg bps model
  (base + stress); no idealized maker fills.
- **R9.6** Deribit legs price only from `source_primary='deribit'` canonical
  candles (I19; no index substitution).

---

## How to use this file

- Adding a rule → also add an `docs/INVARIANTS.md` entry if it is machine- or
  test-checkable, and an ADR if it changes policy.
- Editing a rule's intended value → update `config/` and
  `research/strategy_synthesis.md`, not just this file.
- Editing code under an owning path → this is a business-rule change; follow the
  four steps at the top of this document.

Related: [[DOC_IMPACT_MATRIX]] · [[INVARIANTS]] · [[FAILURE_MODES]] ·
`docs/ai_collaboration.md`.

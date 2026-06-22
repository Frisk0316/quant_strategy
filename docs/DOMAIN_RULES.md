---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
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

## R6. Data Provenance and Leakage

- **R6.1** No lookahead bias or feature leakage in research or replay.
- **R6.2** DB and parquet sources must agree; a source switch must be explicit
  and recorded. For replay `price_series.csv`, DB parity proves agreement on
  timestamped `close` values; OHLCV structure and volume-unit sanity are separate
  artifact/data-quality checks.
- **R6.3** Trial count must be tracked; hidden trials inflate selection bias.

## R7. Promotion Gates

- **R7.1** `naive_backtest`, `in_sample`, idealized-fill, and advisory
  validation output are **not** promotion evidence. This includes
  `strategy_fill` artifacts and `dual_output` comparison summaries.
- **R7.2** No live / shadow / demo readiness claim is valid unless every gate in
  `docs/ai_collaboration.md` passes and the human explicitly approves.
- **R7.3** Promotion candidates require reproducible artifacts and
  walk-forward / CPCV evidence.

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

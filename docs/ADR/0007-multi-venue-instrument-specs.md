---
status: current
type: adr
owner: claude
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# ADR-0007: Multi-Venue Instrument Specifications

## Status

Accepted - 2026-06-17, human-approved for P1 implementation.

## Context

The project originally modelled OKX SWAP contracts, then switched to **Binance
candle data** for availability and now runs mostly on Binance for testing, OKX
secondary. The intended end-state is to ingest candles from **Binance, OKX, and
Bybit** and let the same logical pair be backtested on a chosen venue, with
results expected to converge across venues.

Today the instrument model is single-venue:

- `config/instrument_specs.yaml` is labelled OKX-only and stores one `ct_val`
  per `inst_id` (e.g. `BTC-USDT-SWAP: 0.01`).
- The DB `instruments` table is keyed by `inst_id` with a single
  `contract_value` column.
- `ReplayBacktestEngine._resolve_swap_ct_val` resolves ct_val DB-first
  (`source=db`) → registry yaml (`source=registry`) → hardcoded, with no
  exchange dimension.
- The source-provenance gate
  (`backtesting/differential_validation.py::_validate_ct_val_provenance` and
  `source_data_validation`) reads `result.validation.ct_val_all_authoritative`
  and symbol-keyed `ct_val_sources` and treats `db`/`config_override`/`spot_unit`
  as authoritative.

Two forces make this single-venue model wrong for the goal:

1. **ct_val is a per-venue property.** OKX `BTC-USDT-SWAP` = 0.01, OKX
   `ETH-USDT-SWAP` = 0.1; Binance and Bybit USDT-M perpetuals trade in base
   units, so the effective contract multiplier is **1.0**. The registry's single
   value cannot be correct for more than one venue at a time (it currently lists
   ETH-USDT-SWAP = 0.01, which is wrong for OKX).
2. **ct_val cancels in backtest PnL but not at live execution.** With
   notional-based sizing, `n_contracts = notional / (ct_val·price)` and
   `pnl = n_contracts · Δprice · ct_val`, so `pnl = notional · Δprice / price` —
   independent of ct_val. ct_val only re-enters when a real venue rounds an order
   to its own contract size. The provenance gate is therefore a **live-readiness
   gate, not a backtest-correctness gate**, and must be tagged with the venue it
   attests.

### Decided scoping inputs (from brainstorming, 2026-06-17)

- A backtest run is **single-venue** (one exchange per run; cross-venue
  comparison is across separate runs). Cross-venue-within-one-run (arb/hedging)
  is explicitly out of scope.
- Per-venue specs are **seeded manually for the pairs in use first**, with
  automated per-venue sync deferred to a later phase. The schema is venue-aware
  from day one so later auto-sync is drop-in.

## Options considered (design-space expansion)

**Problem:** the same logical pair must be backtestable on a chosen venue with
that venue's correct contract spec, and the provenance gate must attest the
venue — without rewriting trading-core or the gate's provenance shape.

**Constraints (hard):** DB schema change ⇒ ADR + Change Manifest (DOC_IMPACT
A6); validation-gate change ⇒ ADR + Manifest (A9); do-not-touch trading-core
except via approved P1 task; provenance contract must stay readable by the
existing gate; existing result artifacts must not be mutated.
**Constraints (soft):** minimise blast radius into `portfolio/`,
`execution/`, and `replay.py`.

- **Option A — alter `instruments` table:** add `exchange`, PK becomes
  `(exchange, inst_id)`. Assumes nothing else depends on the single-column PK.
  Wrong if other queries/joins rely on `inst_id` alone. Blast radius: existing
  table identity + backfill of current rows.
- **Option B — new `venue_instrument_specs` table (chosen):** dedicated table
  `(exchange, symbol) → ct_val, lot_size, tick_size, min_size, source,
  updated_at`. Assumes ct_val resolution can be re-pointed to a new query.
  Wrong if a single spec table cannot express future venue-specific fields.
  Blast radius: one new table + one resolver query; `instruments` untouched.
- **Option C — smallest change, config_override only:** pass per-venue specs at
  call time, no schema change. Assumes callers always supply specs. Wrong as a
  persistent model — it does not build the multi-venue data store the goal
  needs. Blast radius: near-zero, but no durable architecture.

**Axis:** durable multi-venue data model vs. migration blast radius.
**Decision:** **Option B.** It builds the real venue-aware store while leaving
the existing `instruments` table and current runs undisturbed, and the resolver
already does DB-first→fallback so it only changes which query runs.
**Would change if:** a near-term need for cross-venue-within-one-run emerges
(would force venue-keyed positions/ledger and reopen Option A-style schema).

## Decision

For the multi-venue architecture, as a **rule** future work must follow:

1. **Venue is a run-level attribute.** A backtest run carries a single
   `exchange` (default `binance`). Position ledger and `ct_val_sources` stay
   **symbol-keyed**; the run records its `exchange` alongside.
2. **Per-venue specs live in a new `venue_instrument_specs` table** keyed by
   `(exchange, symbol)` holding `ct_val, lot_size, tick_size, min_size, source,
   updated_at`. The existing `instruments` table is not repurposed. Seed the
   in-use pairs (Binance + OKX for BTC/ETH) manually as `source=db`
   (authoritative); auto-sync per venue is a later phase using the same table.
3. **Symbol identity is canonical + thin mapping.** The internal key stays the
   existing canonical symbol (e.g. `BTC-USDT-SWAP`); an `(exchange, canonical)
   → native_symbol` map is consulted only where a venue's native symbol differs
   (e.g. Binance `BTCUSDT`). Native symbols appear only at the data-fetch and
   (future) execution boundary.
4. **ct_val resolution becomes venue-aware:** lookup order
   `venue_instrument_specs(exchange, symbol)` (`db`) → `config_override` →
   registry yaml (`registry`, non-authoritative) → hardcoded. Correct per-venue
   values: Binance/Bybit USDT-M perps `ct_val = 1.0` (base-unit); OKX SWAP
   `BTC = 0.01`, `ETH = 0.1`. P1 follow-up: unseeded Binance/Bybit
   normal USDT-M perps may resolve as `exchange_base_unit` (authoritative
   structural `ct_val = 1.0`) after DB lookup; canonical bases that encode a
   1000x multiplier, such as `1000SHIB`/`1000PEPE`, must still use an explicit
   `venue_instrument_specs` row.
5. **The provenance gate stays shape-compatible and gains a venue tag.**
   `_validate_ct_val_provenance` keeps reading `ct_val_all_authoritative` and
   symbol-keyed `ct_val_sources`; the run's `exchange` is propagated into the
   provenance/source-data block so a PASS attests "authoritative ct_val for
   symbol X on exchange Y", and `db_parity` compares against that venue's
   canonical candles. **No P1 change may alter the provenance field shape
   without co-updating this gate in the same change.**

## Non-Goals

- Does **not** authorise cross-venue trading within a single run
  (venue-keyed positions/ledger).
- Does **not** implement per-venue fee/funding precision — that is a separate
  phase (P2) with its own Manifest/ADR.
- Does **not** implement per-venue live execution adapters (P3).
- Does **not** implement automated per-venue spec sync — deferred; only the
  venue-aware schema and manual seeding are in P1 scope.
- Does **not** change strategy logic; cross-venue convergence is expected to
  emerge from notional sizing, not from per-venue strategy branches.
- Does **not** claim any strategy is live-ready.

## Consequences

- New trading-core surface in P1: `replay.py` ct_val resolution gains an
  `exchange` parameter; `portfolio` reads specs unchanged (still symbol-keyed
  per run). Touches DOC_IMPACT A2/A5/A6/A7/A8/A9 → Change Manifest required.
- **New golden case:** the same strategy/params on Binance vs OKX must produce
  identical metrics except lot-rounding (fee/funding divergence is deferred to
  P2). This becomes a `docs/GOLDEN_CASES.md` entry and a
  `docs/HYPOTHESIS_LEDGER.md` entry when P1 runs it.
- A genuine DB-backed source-provenance PASS becomes producible once a venue's
  specs are seeded as `db` and that venue's canonical candles exist — unblocking
  the open Codex question ("which saved run for the first DB-backed artifact?")
  with a venue-correct answer instead of a registry-fallback run.
- Tests that must keep passing: `tests/unit/test_differential_validation.py`,
  `tests/unit/test_source_provenance_validation.py`, and replay ct_val
  provenance tests; P1 adds venue-resolution and convergence coverage.
- Rollback: the table and resolver changes are additive; reverting P1 restores
  single-venue (`exchange=okx`/registry) behaviour. This ADR alone changes no
  behaviour.

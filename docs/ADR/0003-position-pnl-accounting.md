---
status: accepted
type: adr
owner: human
created: 2026-05-11
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# ADR-0003: Position and PnL Accounting

## Status

Accepted — 2026-05-11

## Context

OKX perpetual swaps (USDT-margined, `instType=SWAP`) are contract-denominated, not coin-denominated. Each contract represents `ct_val` units of the base currency. For `BTC-USDT-SWAP`, `ct_val = 0.01` (1 contract = 0.01 BTC).

Failing to apply `ct_val` produces a factor-of-100 error in PnL and notional calculations. This error is silent — the output looks like a valid number.

## Decision

All PnL and notional calculations MUST follow these formulas:

### SWAP instruments (`instType == SWAP`)

```
unrealized_pnl = size × ct_val × (last_price − avg_entry)
notional       = abs(size) × last_price × ct_val
```

where `size` is in **contracts** (positive = long, negative = short).

### SPOT instruments

```
unrealized_pnl = size × (last_price − avg_entry)
notional       = abs(size) × last_price
```

where `size` is in **base currency units**.

### Realized PnL (on partial/full close)

```
closed_qty      = min(abs(fill_sz), abs(size_before))
realized_pnl    = closed_qty × ct_val × (fill_px − avg_entry) × sign(size_before)
net_realized_pnl = realized_pnl − fee
```

### Funding cashflow

Position size convention: positive size = long, negative size = short.

```
funding_cashflow = -perp_size × ct_val × funding_rate × mark_price
```

The leading negative sign ensures:

- Long perp (`perp_size > 0`) **pays** funding when `funding_rate > 0`
- Short perp (`perp_size < 0`) **receives** funding when `funding_rate > 0`

Numeric example:

```
perp_size    = -0.25 contracts   (short)
ct_val       =  0.01
mark_price   =  40,000 USDT
funding_rate =  0.0001

funding_cashflow = -(-0.25) × 0.01 × 40,000 × 0.0001
                 = +0.01 USDT

A short perp receives +0.01 USDT when funding rate is positive.
```

### Source of ct_val

`ct_val` is fetched from OKX REST `/api/v5/public/instruments` at engine startup and stored per `inst_id` in the instrument registry. **Never hardcode `ct_val`.** Use `validate_ct_val()` from `portfolio/sizing.py` which asserts `0 < ct_val ≤ 1`.

## Consequences

- `PositionLedger.on_fill()` is the single implementation of this accounting. Do not duplicate it.
- Any code that computes PnL or notional outside `PositionLedger` must use the same formulas
- The highest-priority regression test is: given a known BTC-USDT-SWAP position with `ct_val=0.01`, price move of +1000 USDT on 0.25 contracts → `unrealized_pnl == 2.5` (not 250)
- Changes to this accounting require explicit Claude plan + regression test before merge

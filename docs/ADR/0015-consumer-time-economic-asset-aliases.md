---
status: accepted
type: adr
owner: codex
created: 2026-07-24
last_reviewed: 2026-07-24
expires: none
superseded_by: null
---

# ADR-0015: Consumer-Time Economic-Asset Aliases

## Status

Accepted — 2026-07-24 through the user's explicit E-058 repair / E-059 task.
This changes universe identity handling only; it does not authorize E-059
before T1 verification or authorize Stage 3.

## Context

The immutable PIT membership parquet can select both `SHIB-USDT-SWAP` and
Binance's tradable `1000SHIB-USDT-SWAP` on the same day. Rewriting history would
destroy input provenance, while consuming both rows double-weights one economic
asset and inflates coverage denominators.

## Decision

1. Keep the membership parquet byte-for-byte unchanged.
2. Store exchange-scoped same-asset aliases in code and apply them at universe
   consumption time.
3. Collapse aliases after PIT eligibility and top-N selection, preserve order,
   keep the canonical tradable contract once, and do not refill from rank N+1.
4. For Binance, map `SHIB-USDT-SWAP` to `1000SHIB-USDT-SWAP`.
5. T2 supplies the pure alias helper. The E-059 probe may consume it only after
   T1 coverage verification passes; broader consumers remain a recorded gap.

## Consequences

- Historical membership provenance stays reproducible.
- E-059 must recompute its effective member-day denominator from collapsed
  membership rather than patch E-058's count.
- Other universe consumers can still double-count aliases until separately
  reviewed and wired; this task does not change their evidence or artifacts.
- No strategy formula, threshold, trial/K budget, schema, or deployment gate
  changes.

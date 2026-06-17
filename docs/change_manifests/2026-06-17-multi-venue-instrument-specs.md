---
status: current
type: manifest
owner: claude
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Change Manifest: Multi-venue instrument specifications

> **P1 implementation manifest.** This manifest records the blast radius of the
> multi-venue work decided in [ADR-0007](../ADR/0007-multi-venue-instrument-specs.md).

## Summary
Introduce an `exchange` dimension so the same logical pair can be backtested on
a chosen single venue (Binance/OKX/Bybit) with that venue's correct
`ct_val/lot/tick/min`, via a new `venue_instrument_specs` table, with the
ct_val provenance gate tagged by venue. Normal Binance/Bybit USDT-M perps may
resolve `ct_val = 1.0` from the structural base-unit contract identity without
per-symbol seeding; canonical `1000...` multiplier contracts still require a DB
row.

## Business rule(s) affected
- R1.1-R1.4 (PnL/sizing/accounting): ct_val multiplier resolution becomes
  venue-aware. Values themselves are unchanged in backtest PnL (ct_val cancels
  under notional sizing); the rule change is *provenance*, not accounting.
- R2-R5 reviewed: no fee, funding, sizing/risk, or fill-semantics rule changes;
  the structural source only changes `ct_val` provenance for normal
  Binance/Bybit USDT-M perps.
- R7 (validation/gates): ct_val authoritative source + db_parity become
  venue-scoped.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A6 (DB schema — Manifest + ADR), A9 (validation gate — Manifest + ADR), A2
(portfolio/execution read path), A5 (backtesting/replay resolution), A7 (API
request gains `exchange`), A8 (frontend venue selector), A4 (config default/
allowed exchanges).

## Files changed
- P0 (this change): `docs/ADR/0007-multi-venue-instrument-specs.md` (added),
  `docs/ADR/README.md` (index row), this manifest (added).
- P1 implementation: `sql/migrations/0011_venue_instrument_specs.sql`,
  `sql/seed_venue_instrument_specs.sql`, `backtesting/replay.py`,
  `backtesting/differential_validation.py`,
  `src/okx_quant/api/routes_backtest.py`, `frontend/view-config.js`,
  `config/instrument_specs.yaml`, `tests/unit/test_replay_ct_val_resolution.py`,
  `tests/unit/test_replay_ct_val_provenance_tag.py`,
  `tests/unit/test_differential_validation.py`,
  `tests/unit/test_backtest_request_exchange.py`,
  `tests/unit/test_multi_venue_convergence.py`, and the docs checked below.

## Behavior delta
- Before: ct_val resolves single-venue (DB `instruments.contract_value` →
  OKX-labelled registry); provenance is venue-blind.
- After: ct_val resolves per `(exchange, symbol)`; a run is single-venue and its
  provenance PASS attests the venue. For Binance/Bybit normal USDT-M perps with
  no DB row, `exchange_base_unit` is authoritative `ct_val = 1.0`; canonical
  `1000...` multiplier contracts fall through and require explicit DB specs.
- Money/risk impact: **none in backtest PnL** (ct_val cancels under notional
  sizing). Impact is at live execution and in which runs can pass the
  live-readiness provenance gate. Per-venue fee/funding divergence is deferred
  to P2 and out of this manifest.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A for P0; P1 should note the venue/contract
  assumption and the cross-venue convergence expectation.
- config/: `config/settings.yaml` already defaults `storage.primary_exchange` to
  `binance`; P1 documents `config/instrument_specs.yaml` as an OKX-only fallback.
- ADR: ADR-0007 accepted for P1 implementation on 2026-06-17.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DATA_FLOW.md` — P1 (new table + venue in resolution path)
- [x] `docs/DOMAIN_RULES.md` — P1 (venue-aware ct_val provenance rule)
- [x] `docs/FEATURE_MAP.md` — P1 (venue selection ownership)
- [x] `docs/INVARIANTS.md` — P1 (per-venue ct_val authoritative invariant)
- [x] `docs/ai_collaboration.md` — P1 (ct_val gate venue tagging)
- [x] `docs/UI_MAP.md` — P1 (frontend venue selector)
- [x] `docs/KNOWN_ISSUES.md` — P1 (close registry-only ct_val provenance gap)
- [x] `docs/ADR/README.md` — P0, index row added

## Invariants / golden cases
- Invariants checked: I1 and I16.
- Golden cases affected: G-001 cross-venue convergence case (same
  strategy/params, Binance vs OKX; identical metrics within `1e-6`).

## Tests / checks run
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py -q` - red run
  failed as expected before implementation: Binance/Bybit base-unit resolution
  and `exchange_base_unit` authority were missing.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q` - 58 passed, 1196 warnings (existing OHLCV zscore precision warnings plus pytest cache permission warning).
- `python scripts/docs/check_doc_impact.py --strict` with per-process
  `safe.directory` config - passed: 10 changed file(s), no impact-matrix violations.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed: 93 concrete path(s) checked.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py -q` - 56 passed, 1196 warnings (existing OHLCV zscore precision warnings plus pytest cache permission warning).
- `python -m pytest tests/unit/test_backtest_request_exchange.py -q` - 2 passed, 1 pytest cache permission warning.
- `node --check frontend/view-config.js` - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed; Git reported CRLF normalization warnings only.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_doc_impact.py` with `safe.directory` env - passed: 18 changed file(s), no impact-matrix violations.
- DB-backed end-to-end source-provenance PASS: not run in this local session because
  `DATABASE_URL` and `psql` were unavailable; requires seeded DB and fresh run.

## Risks and rollback
- Risks: provenance field shape drifting from the gate if P1 splits across
  sessions (ADR-0007 forbids this); seeding a wrong per-venue ct_val (mitigated
  by db_parity + authoritative source requirement); accidentally treating
  `1000...` multiplier contracts as base-unit identity; accidentally repurposing
  `instruments` instead of the new table.
- Rollback: P0 is additive docs — delete the two files and the index row. P1
  rollback restores single-venue resolution (additive table/resolver).

## Approval
- Human approval required: **yes**. ADR-0007 is accepted for P1 implementation.
  Obtained? Yes - user approved ADR-0007 P1 on 2026-06-17.

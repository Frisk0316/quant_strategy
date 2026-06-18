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
- R1.1/R1.2/R1.4 (PnL/sizing/accounting): ct_val multiplier resolution becomes
  venue-aware. Values themselves are unchanged in backtest PnL (ct_val cancels
  under notional sizing); the rule change is *provenance*, not accounting.
- R2-R5 reviewed: no fee, funding, sizing/risk, or fill-semantics rule changes;
  the structural source only changes `ct_val` provenance for normal
  Binance/Bybit USDT-M perps.
- R6.2/R7.2 reviewed: ct_val authoritative source + db_parity become
  venue-scoped validation evidence.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A6 (DB schema — Manifest + ADR), A9 (validation gate — Manifest + ADR), A2
(portfolio/execution read path), A5 (backtesting/replay resolution), A7 (API
request gains `exchange`), A8 (frontend venue selector), A4 (config default/
allowed exchanges).

## Files changed
- P0 (this change): `docs/ADR/0007-multi-venue-instrument-specs.md` (added),
  `docs/ADR/README.md` (index row), this manifest (added).
- P1 implementation commits:
  - `171b3f4` - `sql/migrations/0011_venue_instrument_specs.sql`,
    `sql/seed_venue_instrument_specs.sql`, ADR/manifest index updates.
  - `1aa85e2` - `backtesting/replay.py`,
    `tests/unit/test_backtesting.py`,
    `tests/unit/test_replay_ct_val_resolution.py`.
  - `e7eb3ed` - `backtesting/replay.py`,
    `tests/unit/test_replay_ct_val_provenance_tag.py`.
  - `519385e` - `backtesting/differential_validation.py`,
    `tests/unit/test_differential_validation.py`.
  - `7be7f65` - `src/okx_quant/api/routes_backtest.py`,
    `frontend/view-config.js`, `tests/unit/test_backtest_request_exchange.py`.
  - `71cd90c` - convergence golden case and docs:
    `tests/unit/test_multi_venue_convergence.py`,
    `config/instrument_specs.yaml`, `docs/DATA_FLOW.md`,
    `docs/DOMAIN_RULES.md`, `docs/EXPERIMENT_REGISTRY.md`,
    `docs/FEATURE_MAP.md`, `docs/GOLDEN_CASES.md`,
    `docs/HYPOTHESIS_LEDGER.md`, `docs/INVARIANTS.md`,
    `docs/KNOWN_ISSUES.md`, `docs/UI_MAP.md`,
    `docs/ai_collaboration.md`, `docs/AI_HANDOFF.md`,
    `docs/CURRENT_STATE.md`, and task handoffs.
  - `9bef416` - Binance/Bybit base-unit `ct_val` structural default:
    `backtesting/replay.py`, ADR/docs updates, and
    `tests/unit/test_replay_ct_val_resolution.py`.
  - `967f362` - DB parity exchange scoping follow-up:
    `backtesting/data_loader.py`, `src/okx_quant/data/candle_store.py`,
    `tests/unit/test_data_loader.py`, `tests/unit/test_differential_validation.py`,
    docs, and task handoffs.
- P1 closeout docs in this session: `docs/DOMAIN_RULES.md`,
  `docs/ai_collaboration.md`, `docs/GOLDEN_CASES.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/KNOWN_ISSUES.md`,
  `config/instrument_specs.yaml`, this manifest, and final handoffs.

## Behavior delta
- Before: ct_val resolves single-venue (DB `instruments.contract_value` →
  OKX-labelled registry); provenance is venue-blind.
- After: ct_val resolves per `(exchange, symbol)`; a run is single-venue and its
  provenance PASS attests the venue. For Binance/Bybit normal USDT-M perps with
  no DB row, `exchange_base_unit` is authoritative `ct_val = 1.0`; canonical
  `1000...` multiplier contracts fall through and require explicit DB specs.
  DB candle parity reads canonical candles with `source_primary` filtered to the
  run exchange when `result.validation.exchange` is present.
- Money/risk impact: **none in backtest PnL** (ct_val cancels under notional
  sizing). Impact is at live execution and in which runs can pass the
  live-readiness provenance gate. Per-venue fee/funding divergence is deferred
  to P2 and out of this manifest.

## Source-of-truth updates
- research/strategy_synthesis.md: unchanged; no strategy assumption changed.
  Cross-venue convergence is recorded in `docs/GOLDEN_CASES.md`,
  `docs/HYPOTHESIS_LEDGER.md`, and `docs/EXPERIMENT_REGISTRY.md`.
- config/: `config/settings.yaml` already defaults `storage.primary_exchange` to
  `binance`; P1 documents `config/instrument_specs.yaml` as an OKX-only fallback
  and points authoritative per-venue specs to `venue_instrument_specs`.
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

Closeout notes:
- `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`,
  `docs/INVARIANTS.md`, and `docs/EXPERIMENT_REGISTRY.md` were reviewed in
  this closeout and were already current from P1 commits.
- `docs/DOMAIN_RULES.md`, `docs/ai_collaboration.md`, `docs/KNOWN_ISSUES.md`,
  `docs/GOLDEN_CASES.md`, `docs/HYPOTHESIS_LEDGER.md`, and
  `config/instrument_specs.yaml` were updated in this closeout.
- Real rule sub-ids confirmed: R1.1/R1.2/R1.4, R6.2, and R7.2. R2-R5 were
  reviewed with no fee, funding, sizing/risk, or fill-semantics rule change.

## Invariants / golden cases
- Invariants checked: I1, I12, and I16.
- Golden cases affected: G-001 cross-venue convergence case (same
  strategy/params, Binance vs OKX; identical metrics within `1e-6` because
  `ct_val` cancels under notional sizing, modulo real venue lot rounding).

## Tests / checks run
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py -q` - red run
  failed as expected before implementation: Binance/Bybit base-unit resolution
  and `exchange_base_unit` authority were missing.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q` - 58 passed, 1196 warnings (existing OHLCV zscore precision warnings plus pytest cache permission warning).
- `python -m pytest tests/unit/test_data_loader.py -q` - red run failed before implementation because postgres candle loading did not forward exchange and `CandleStore.get_canonical_candles()` had no `source_primary` filter.
- `python -m pytest tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_data_loader.py -q` - 51 passed, 1196 warnings (existing OHLCV zscore precision warnings plus pytest cache permission warning).
- `python scripts/docs/check_doc_impact.py --strict` with per-process
  `safe.directory` config - passed: 11 changed file(s), no impact-matrix violations.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed: 93 concrete path(s) checked.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py -q` - 56 passed, 1196 warnings (existing OHLCV zscore precision warnings plus pytest cache permission warning).
- `python -m pytest tests/unit/test_backtest_request_exchange.py -q` - 2 passed, 1 pytest cache permission warning.
- `node --check frontend/view-config.js` - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed; Git reported CRLF normalization warnings only.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_doc_impact.py` with `safe.directory` env - passed: 18 changed file(s), no impact-matrix violations.
- Closeout verification, 2026-06-18:
  - `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py tests/unit/test_data_loader.py -q` - 61 passed, 1196 warnings (existing OHLCV zscore precision warnings plus pytest cache permission warning).
  - `python scripts/docs/check_doc_impact.py --strict` with per-process
    `safe.directory` config - passed: 12 changed file(s), no impact-matrix violations.
  - `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing lifecycle metadata warnings.
  - `python scripts/docs/check_feature_map_links.py` - passed: 93 concrete path(s) checked.
- DB-backed end-to-end Binance source-provenance PASS, 2026-06-18: **BLOCKED,
  not passed**. No gate was loosened. Evidence:
  - `asyncpg.connect("postgresql://quant:changeme@localhost:5432/quant")`
    failed with `ConnectionRefusedError: [WinError 1225]`.
  - `.env` `DATABASE_URL` points at the same repo `quant` DSN on port 5432;
    port 5432 refused connections.
  - Local `postgresql-x64-18` is running on port 5433, but repo `quant`
    credentials from `.env` failed with `InvalidPasswordError`.
  - `docker ps` reported Docker daemon not running; `Start-Service
    com.docker.service` failed with `Cannot open com.docker.service service`.
  - Therefore `sql/migrations/0011_venue_instrument_specs.sql`,
    `sql/seed_venue_instrument_specs.sql`, the fresh Binance backtest, and
    `scripts/run_source_provenance_validation.py` could not be run to PASS in
    this session. A reachable seeded DSN is still required.

## Risks and rollback
- Risks: provenance field shape drifting from the gate if P1 splits across
  sessions (ADR-0007 forbids this); seeding a wrong per-venue ct_val (mitigated
  by db_parity + authoritative source requirement); accidentally treating
  `1000...` multiplier contracts as base-unit identity; accidentally comparing
  canonical DB candles from the wrong exchange; accidentally repurposing
  `instruments` instead of the new table.
- Rollback: P0 is additive docs — delete the two files and the index row. P1
  rollback restores single-venue resolution (additive table/resolver).

## Approval
- Human approval required: **yes**. ADR-0007 is accepted for P1 implementation.
  Obtained? Yes - user approved ADR-0007 P1 on 2026-06-17.

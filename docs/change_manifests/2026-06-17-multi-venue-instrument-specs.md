---
status: current
type: manifest
owner: claude
created: 2026-06-17
last_reviewed: 2026-06-18
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
- `d48361c` - P1 Task 6 docs/manifest closeout:
  `docs/DATA_FLOW.md`, `docs/DOMAIN_RULES.md`, `docs/FEATURE_MAP.md`,
  `docs/GOLDEN_CASES.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/INVARIANTS.md`, `docs/KNOWN_ISSUES.md`, `docs/UI_MAP.md`,
  `docs/ai_collaboration.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`,
  `config/instrument_specs.yaml`, and task handoffs.
- Source-scoped evidence follow-up in this change:
  `backtesting/differential_validation.py`, `backtesting/replay.py`,
  `tests/unit/test_data_loader.py`, `tests/unit/test_differential_validation.py`,
  `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, this manifest, and task handoffs.
- Close-only DB parity input-contract follow-up:
  `backtesting/differential_validation.py`,
  `tests/unit/test_differential_validation.py`, `docs/DATA_FLOW.md`,
  `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`,
  `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`, `docs/ai_collaboration.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`, this
  manifest, and task handoffs.
- Durable DB parity PASS evidence:
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/`.
- Superseded diagnostic artifact marker:
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/adr0007_binance_btc_1h_db_pass_20260618_source_provenance/SUPERSEDED.md`.
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
  run exchange when `result.validation.exchange` is present, and the
  `db_parity` check reports `canonical_source_primary` so the Binance DB-backed
  PASS must prove it compared Binance-tagged canonical candles. For replay
  `price_series.csv`, DB parity compares timestamped `close` values only; O/H/L
  flattening and volume-unit differences are handled by artifact/data-quality
  checks instead of the canonical close provenance check.
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
- [x] `docs/FAILURE_MODES.md` — close-only db_parity guard recorded for
  close-flattened artifacts
- [x] `docs/CHANGELOG_AI.md` — durable history for close-only db_parity follow-up

Closeout notes:
- `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`,
  `docs/INVARIANTS.md`, and `docs/EXPERIMENT_REGISTRY.md` were reviewed in
  this closeout and were already current from P1 commits.
- `docs/DOMAIN_RULES.md`, `docs/ai_collaboration.md`, `docs/KNOWN_ISSUES.md`,
  `docs/GOLDEN_CASES.md`, `docs/HYPOTHESIS_LEDGER.md`, and
  `config/instrument_specs.yaml` were updated in this closeout.
- `docs/RUNBOOK.md` now records the ADR-0007 Binance DB-backed PASS flow:
  apply migration + seed, run a fresh Binance backtest, enable DB parity, and
  require `checks.db_parity.canonical_source_primary == "binance"`.
- `docs/AI_HANDOFF.md` and `docs/CURRENT_STATE.md` now mark P1 code/docs
  closeout as complete locally and move the Binance DB-backed PASS blocker to
  reachable DB/data state.
- Close-only follow-up reviewed `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`,
  `docs/ai_collaboration.md`, ADR-0005, and ADR-0007. No new ADR was added
  because this restores the like-for-like DB parity input contract rather than
  changing deployment-gate policy or ADR-0002 result schema.
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
- Source-scoped DB parity evidence red run, 2026-06-18:
  `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_data_loader.py -q`
  - 1 failed, 3 passed, 2 warnings. Expected failure:
  `KeyError: 'canonical_source_primary'`, proving the test caught missing
  source-scoped output.
- Source-scoped DB parity evidence green run, 2026-06-18:
  `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_data_loader.py -q`
  - 4 passed, 1 warning.
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
- Source-scope follow-up verification, 2026-06-18:
  - `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py tests/unit/test_data_loader.py -q` - 62 passed, 1196 warnings (existing OHLCV zscore precision warnings plus pytest cache permission warning).
  - `python scripts/docs/check_doc_impact.py --strict` with per-process
    `safe.directory` config - passed: 12 changed file(s), no impact-matrix violations.
  - `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing lifecycle metadata warnings.
  - `python scripts/docs/check_feature_map_links.py` - passed: 93 concrete path(s) checked.
  - `git -c safe.directory=C:/quant_strategy diff --check` - passed; Git reported CRLF normalization warnings only.
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
  - When rerun with a reachable DSN, the PASS evidence must include
    `source_data_validation.checks.db_parity.canonical_source_primary ==
    "binance"`; exit 0 alone is insufficient.
- DB-backed Binance source-provenance rerun, 2026-06-18: **FAIL, not PASS**.
  No gate was loosened. Evidence:
  - Repo DSN on port 5432 later became reachable; port 5433 still rejected the
    repo `quant` credentials.
  - `psql ... -f sql/migrations/0011_venue_instrument_specs.sql` returned
    `CREATE TABLE`; `psql ... -f sql/seed_venue_instrument_specs.sql` returned
    `INSERT 0 4`.
  - Fresh run:
    `python scripts/run_replay_backtest.py --strategy ma_crossover --symbol BTC-USDT-SWAP --bar 1H --exchange binance --start 2026-06-01 --end 2026-06-09 --save-artifacts --run-id adr0007_binance_btc_1h_db_pass_20260618`
    with `BACKTEST_ARTIFACT_MODE=both` produced 192 bars and
    `result.validation.exchange == "binance"`.
  - Source-provenance gate:
    `python scripts/run_source_provenance_validation.py --run-id adr0007_binance_btc_1h_db_pass_20260618 --engines vectorbt,backtrader --validation-id adr0007_binance_btc_1h_db_pass_20260618_source_provenance`
    with `NUMBA_DISABLE_JIT=1` exited 1:
    `source_data_validation=FAIL`, `ct_val_provenance=PASS`,
    `db_parity=FAIL`, `ohlcv_source_validation=artifact_warn`.
  - Positive source-scope evidence: `db_parity.exchange == "binance"` and
    `db_parity.canonical_source_primary == "binance"`.
  - Blocking mismatch: `BTC-USDT-SWAP` artifact rows = 192, DB rows = 192,
    missing/extra rows = 0, value_mismatches = 768. First row example:
    artifact OHLC = `73855.0/73855.0/73855.0/73855.0`; DB Binance 1m-derived
    1H OHLC = `73653.2/74070.5/73620.0/73855.0`.
- Close-only DB parity follow-up, 2026-06-18:
  - Direct DB assertion on saved run
    `adr0007_binance_btc_1h_db_pass_20260618`: artifact rows = 192, DB rows =
    192, matched rows = 192, close mismatches = 0.
  - Red test:
    `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_uses_close_only_for_close_flattened_artifacts -q`
    failed as expected before implementation with
    `ohlcv_source_validation == "artifact_warn"`.
  - Teeth test confirmation:
    `test_reference_replay_uses_db_canonical_prices_when_enabled` mutates
    `close` only and asserts `db_parity.status == "FAIL"` with
    `value_mismatches == 1`.
  - Green slice:
    `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_differential_validation.py::test_db_parity_uses_close_only_for_close_flattened_artifacts tests/unit/test_differential_validation.py::test_reference_replay_uses_db_canonical_prices_when_enabled -q`
    - 3 passed, 1 pytest cache permission warning.
  - Temp `scripts/run_source_provenance_validation.py` run with output under
    `%TEMP%` timed out after 240s before producing output; no existing
    `results/` artifact was modified.
  - Temp source-data gate rerun with `--engines nautilus` and output under
    `%TEMP%\codex_close_only_temp_validation` passed:
    `source_data_validation=PASS`, `ct_val_provenance=PASS`,
    `db_parity=PASS`, `canonical_source_primary=binance`, and
    `ohlcv_source_validation=db_parity_pass`. This was source-data evidence only;
    it was not used as a vectorbt/backtrader signal-quorum claim.
  - Durable source-data gate rerun with `--engines nautilus` wrote
    `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`
    and passed with `source_data_validation=PASS`, `ct_val_provenance=PASS`,
    `db_parity=PASS`, `canonical_source_primary=binance`,
    `value_mismatches=0`, and `ohlcv_source_validation=db_parity_pass`.
  - Existing-result gate check:
    `python scripts/run_source_provenance_validation.py --validation-result results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`
    - PASS.
  - Old FAIL artifact marked superseded:
    `results/adr0007_binance_btc_1h_db_pass_20260618/validation/adr0007_binance_btc_1h_db_pass_20260618_source_provenance/SUPERSEDED.md`
    points reviewers to the durable PASS artifact.

## Risks and rollback
- Risks: provenance field shape drifting from the gate if P1 splits across
  sessions (ADR-0007 forbids this); seeding a wrong per-venue ct_val (mitigated
  by db_parity + authoritative source requirement); accidentally treating
  `1000...` multiplier contracts as base-unit identity; accidentally comparing
  canonical DB candles from the wrong exchange; accidentally treating artifact
  O/H/L or quote-volume units as like-for-like DB candle fields; accidentally
  repurposing `instruments` instead of the new table.
- Rollback: P0 is additive docs — delete the two files and the index row. P1
  rollback restores single-venue resolution (additive table/resolver).

## Approval
- Human approval required: **yes**. ADR-0007 is accepted for P1 implementation.
  Obtained? Yes - user approved ADR-0007 P1 on 2026-06-17.

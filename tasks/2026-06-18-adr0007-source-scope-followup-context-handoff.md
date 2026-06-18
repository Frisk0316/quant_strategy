# Context Handoff: ADR-0007 Source Scope Follow-up - 2026-06-18

## Goal (one sentence)
Close the Task 6 follow-up gaps by proving DB parity is source-scoped, documenting the Binance DB-backed PASS flow, and keeping P1 handoff state current.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: `d48361c` plus this follow-up diff; prior Task 4 repair commit is `967f362`.
- In-progress edits (files): `backtesting/differential_validation.py`, `backtesting/replay.py`, `tests/unit/test_data_loader.py`, `tests/unit/test_differential_validation.py`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and the ADR-0007 manifest.
- What works right now: source-scoped regression tests pass; DB parity output includes `canonical_source_primary`; docs describe the Binance DB-backed PASS evidence requirement.
- What does not work / unfinished: real DB-backed Binance PASS now reaches DB/seed and proves `canonical_source_primary == "binance"`, but fails because replay artifact OHLC collapses to close/mid while DB canonical candles preserve true OHLC.

## Decisions made (and why)
- Emit `checks.db_parity.canonical_source_primary` because exit 0 alone cannot prove canonical candle reads were scoped to the run exchange.
- Keep the Binance DB-backed PASS blocked on artifact/canonical OHLC mismatch; loosening DB parity would hide the exact data-provenance bug this follow-up protects.

## Open questions / unverified assumptions
- Whether to fix replay `price_series.csv` to carry true OHLC or to change the DB parity input contract remains unresolved.

## Rules in play (preserve verbatim)
- Invariants touched: I16 / ADR-0007 per-venue ct_val and source-provenance evidence must match the run execution venue.
- Domain rules touched: R1.1/R1.2/R1.4, R6.2, R7.2.
- Do-not-touch: `research/`, strategy/signal/risk/portfolio/execution behavior, DB schema/migrations, deployment gates, and existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `docs/ADR/0007-multi-venue-instrument-specs.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `docs/RUNBOOK.md`.
- Owning files / MODULE_BRIEFS: `backtesting/differential_validation.py`, `backtesting/data_loader.py`, `src/okx_quant/data/candle_store.py`, `backtesting/replay.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_data_loader.py -q` - red: 1 failed, 3 passed; expected `KeyError: 'canonical_source_primary'`.
- `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_data_loader.py -q` - green: 4 passed, 1 warning.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py tests/unit/test_data_loader.py -q` - 62 passed, 1196 warnings.
- `python scripts/docs/check_doc_impact.py --strict` with per-process `safe.directory` config - passed after `docs/DATA_FLOW.md` update.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF normalization warnings only.

## Approvals
- Human approval needed / obtained: ADR-0007 P1 approval was already obtained on 2026-06-17; this follow-up stays inside that scope.

## Next action (single, concrete)
- Fix replay artifact OHLC semantics or the DB parity input contract, then rerun the Binance BTC-USDT-SWAP 1H source-provenance validation and verify `db_parity.canonical_source_primary == "binance"` plus `db_parity.status == "PASS"`.

## Human Learning Notes
The fake loader test was not enough; a useful regression must prove the filter changes the result set or exposes the chosen source in the artifact. Source scoping is data provenance, not just a function argument.

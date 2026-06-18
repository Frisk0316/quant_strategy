# Context Handoff: ADR-0007 multi-venue instrument specs P1 - 2026-06-17

## Goal (one sentence)
Implement ADR-0007 P1 so `ct_val` resolution and provenance are exchange-aware for single-venue backtest runs.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`
- Last known good commit / state: Tasks 1-6 are locally implemented, verified, and committed on this branch.
- In-progress edits (files): ADR-0007 P1 Task 6 docs/test/handoff edits only; unrelated dirty file remains `docs/backtest_external_validation_report_zh.pptx`.
- What works right now: SQL migration/seed exists; replay resolves DB specs by `(exchange, symbol)`; non-OKX runs no longer fall back to OKX registry; provenance/source gates surface `exchange`; Run Backtest UI sends `exchange`; convergence golden case passes for OKX vs Binance `ctVal`.
- What does not work / unfinished: DB seed was not applied in this shell; no DB-backed source-provenance PASS was produced.

## Decisions made (and why)
- Kept Binance from using OKX registry fallback because ADR-0007 requires venue-correct specs.
- Updated legacy replay tests to opt into OKX registry explicitly because those tests assert OKX fallback behavior.
- Recorded `config/instrument_specs.yaml` as an OKX-only fallback; authoritative multi-venue values belong in `venue_instrument_specs(exchange, symbol)`.

## Open questions / unverified assumptions
- Whether the seed values should be verified against live venue APIs before applying to a shared DB.
- Which fresh Binance run should be used for the first DB-backed source-provenance PASS once a DSN is available.

## Rules in play (preserve verbatim)
- Invariants touched: I1 (`ct_val` affects SWAP PnL/notional), I16 (`ct_val` authoritative source matches run exchange).
- Domain rules touched: R1.1-R1.4, R7.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/risk.yaml`, existing `results/**`.

## Context to load next
- Source of truth: `docs/ADR/0007-multi-venue-instrument-specs.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `docs/superpowers/plans/2026-06-17-multi-venue-instrument-specs-p1.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` sections Backtest Run UI, Validation / Promotion Gates, Result Artifacts.
- Context Pack: no specific pack exists for ADR-0007 yet; start from `docs/CONTEXT_INDEX.md`.

## Checks run
- `python -m pytest tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q` - 49 passed.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py tests/unit/test_backtesting.py -q` - 51 passed.
- `python -m pytest tests/unit/test_backtest_request_exchange.py -q` - 2 passed.
- `node --check frontend/view-config.js` - passed.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py -q` - 56 passed, 1196 warnings.
- `python -m pytest tests/unit/test_backtest_request_exchange.py -q` - 2 passed, 1 warning.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing warnings.
- `python scripts/docs/check_doc_impact.py` with env safe.directory - passed, no impact-matrix violations.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF warnings only.

## Approvals
- Human approval needed / obtained: obtained for ADR-0007 P1 on 2026-06-17.

## Next action (single, concrete)
- Apply the migration/seed to a reachable dev DB and run source-provenance validation against a fresh Binance run to produce the first DB-backed PASS.

## Human Learning Notes
The branch briefly picked up the separate price-chart commit; it was preserved on `codex/fix-price-chart-universal` and removed from the ADR-0007 branch. Windows sandbox also hides git changes from scripts unless safe.directory is provided through Git config/env. The convergence golden case passed without production-code changes because Task 1-5 had already wired the sizing/provenance path correctly.

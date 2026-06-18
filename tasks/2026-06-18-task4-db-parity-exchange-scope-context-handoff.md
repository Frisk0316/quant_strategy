# Context Handoff: Task 4 DB parity exchange scoping - 2026-06-18

## Goal (one sentence)
Finish ADR-0007 Task 4 by making DB candle parity actually filter canonical candles by the run exchange, not just surface the exchange field.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: `9bef416` fixed Binance/Bybit base-unit `ct_val`; this session repairs Task 4 DB parity scoping and should be read with the session's final commit.
- Changed files: `backtesting/data_loader.py`, `src/okx_quant/data/candle_store.py`, `tests/unit/test_data_loader.py`, `tests/unit/test_differential_validation.py`, `docs/DATA_FLOW.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and this handoff pair.
- What works right now: `load_candles(... backend="postgres", exchange="binance")` forwards exchange to `_load_candles_pg`; `_load_candles_pg` forwards it as `source_primary`; `CandleStore.get_canonical_candles()` filters SQL by `source_primary`.
- What does not work / unfinished: DB-backed source-provenance PASS still needs a reachable seeded TimescaleDB/Postgres DB and fresh Binance run.

## Decisions made (and why)
- Use existing `canonical_candles.source_primary` as the exchange filter because the schema already records canonical source and no schema change is needed.
- When `source_primary` is requested, `get_canonical_candles()` reads `canonical_candles` directly instead of continuous aggregate views because those views do not include `source_primary`.

## Open questions / unverified assumptions
- Whether continuous aggregate views should later include `source_primary` for faster exchange-scoped DB parity. Not needed for this fix.

## Rules in play (preserve verbatim)
- Invariants touched: I12 - DB and parquet sources agree for the same instrument/range. I16 - A SWAP run's authoritative `ct_val` source matches the run execution venue.
- Domain rules touched: R6.2, R7.2; R1.4 context.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, DB schema/migrations, deployment gates, existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `docs/ADR/0007-multi-venue-instrument-specs.md`, `docs/DATA_FLOW.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Canonical Candle Pipeline and Validation / Promotion Gates.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests/unit/test_data_loader.py -q` -> red run failed before implementation; green run passed 2 tests.
- `python -m pytest tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_data_loader.py -q` -> 51 passed, 1196 warnings.
- `python scripts/docs/check_doc_impact.py --strict` with per-process `safe.directory` config -> passed, 11 changed files.
- `python scripts/docs/check_doc_metadata.py` -> passed with 12 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` -> passed.

## Approvals
- Human approval needed / obtained: user asked Codex to fix the incomplete Task 4 on 2026-06-18.

## Next action (single, concrete)
- Apply the venue spec migration/seed to a reachable dev DB and run a fresh Binance DB-backed source-provenance validation.

## Human Learning Notes
Task 4's first implementation surfaced `exchange` but did not prove the lower data-loader boundary used it. Boundary tests are needed at every handoff where a parameter crosses modules.

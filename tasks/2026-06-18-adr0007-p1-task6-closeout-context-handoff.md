# Context Handoff: ADR-0007 P1 Task 6 closeout - 2026-06-18

## Goal (one sentence)
Finish ADR-0007 P1 closeout docs/manifest and run the DB-backed Binance source-provenance milestone if a reachable DB is available.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: code commits through `967f362` implement Tasks 1-5, convergence, Binance/Bybit base-unit `ct_val`, and DB parity exchange scoping.
- In-progress edits (files): docs/manifest closeout files and this handoff pair.
- What works right now: unit/golden/docs verification passes locally; `exchange_base_unit` is documented as authoritative for normal Binance/Bybit USDT-M perps.
- What does not work / unfinished: DB-backed Binance source-provenance PASS could not run because no reachable repo DB DSN was available.

## Decisions made (and why)
- Do not add a migration for aggregate views because `get_canonical_candles(source_primary=...)` deliberately bypasses views that lack `source_primary`.
- Do not loosen source-provenance or db_parity gates to force a PASS; missing DB access is an environment blocker, not a validation success.

## Open questions / unverified assumptions
- Whether the user will provide a reachable dev DB DSN or start Docker/Postgres with the repo `quant` credentials.

## Rules in play (preserve verbatim)
- Invariants touched: I1 - SWAP PnL scales by `ct_val`; I12 - DB and parquet sources agree for the same instrument/range; I16 - A SWAP run's authoritative `ct_val` source matches the run execution venue.
- Domain rules touched: R1.1/R1.2/R1.4, R6.2, R7.2.
- Do-not-touch: `research/`, strategy/signal/risk/portfolio/execution code, deployment gates, existing result artifacts, unrelated `docs/backtest_external_validation_report_zh.pptx`.

## Context to load next (the reading list)
- Source of truth: `docs/ADR/0007-multi-venue-instrument-specs.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `docs/CURRENT_STATE.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Backtest Run UI, Canonical Candle Pipeline, Validation / Promotion Gates.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py tests/unit/test_data_loader.py -q` -> 61 passed, 1196 warnings.
- `python scripts/docs/check_doc_impact.py --strict` with per-process `safe.directory` config -> passed, 12 changed files.
- `python scripts/docs/check_doc_metadata.py` -> passed with 12 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` -> passed.
- DB checks: port 5432 refused repo DSN; port 5433 PostgreSQL rejected repo `quant` credentials; Docker daemon unavailable.

## Approvals
- Human approval needed / obtained: ADR-0007 accepted 2026-06-17; user asked for Task 6 closeout on 2026-06-18.

## Next action (single, concrete)
- Provide or start a reachable dev DB DSN, apply `sql/migrations/0011_venue_instrument_specs.sql` and `sql/seed_venue_instrument_specs.sql`, then run a fresh Binance source-provenance validation.

## Human Learning Notes
The code path was ready, but the milestone is dependency-backed: without an actual DB carrying Binance-tagged canonical candles, a PASS would be fake. The useful next setup check is "can asyncpg connect to the repo DSN?" before running replay/validation.

# Context Handoff: Binance/Bybit base-unit ct_val - 2026-06-17

## Goal (one sentence)
Allow normal Binance/Bybit USDT-M perpetuals to resolve `ct_val = 1.0` structurally without per-symbol DB seeding while preserving DB overrides and OKX behavior.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: ADR-0007 P1 tasks are locally implemented; this follow-up adds `exchange_base_unit` structural ct_val provenance for normal Binance/Bybit USDT-M perps.
- In-progress edits (files): `backtesting/replay.py`, `tests/unit/test_replay_ct_val_resolution.py`, `docs/ADR/0007-multi-venue-instrument-specs.md`, `docs/DATA_FLOW.md`, `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and this handoff pair.
- What works right now: resolver unit coverage passes for Binance BNB, Bybit SOL, DB override, OKX registry fallback, 1000x multiplier rejection without DB, and `exchange_base_unit` authority.
- What does not work / unfinished: DB-backed source-provenance PASS is still unverified without a reachable TimescaleDB/Postgres DSN and canonical/spec seed application.

## Decisions made (and why)
- Normal Binance/Bybit `*-USDT-SWAP` symbols resolve to `(1.0, "exchange_base_unit")` after DB lookup because USDT-M quantity is base-unit and there is no contract multiplier.
- Canonical bases starting with `1000` fall through to the existing `ValueError` unless DB specs exist, because Binance multiplier contracts such as `1000SHIB`/`1000PEPE` are not base-unit identity.
- OKX resolution remains DB -> registry -> hardcoded BTC/ETH -> raise.

## Open questions / unverified assumptions
- First DB-backed source-provenance PASS still needs a fresh Binance run against a reachable seeded dev DB.

## Rules in play (preserve verbatim)
- Invariants touched: I1 - SWAP PnL scales by `ct_val`; a ct_val change moves PnL proportionally. I16 - A SWAP run's authoritative `ct_val` source matches the run execution venue.
- Domain rules touched: R1.1-R1.4, R7; R2-R5 reviewed unchanged.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, deployment gates, existing result artifacts, differential-validation implementation.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/ADR/0007-multi-venue-instrument-specs.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Backtest Run UI / Validation sections; `docs/DATA_FLOW.md` Venue Instrument Spec Flow.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py -q` -> red run failed as expected before implementation, then green run passed 9 tests.
- `python -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q` -> 58 passed, 1196 warnings.
- `python scripts/docs/check_doc_impact.py --strict` with per-process `safe.directory` config -> passed, 10 changed files.
- `python scripts/docs/check_doc_metadata.py` -> passed with 12 pre-existing warnings.
- `python scripts/docs/check_feature_map_links.py` -> passed.

## Approvals
- Human approval needed / obtained: user explicitly requested this follow-up on 2026-06-17 and requested commit with `AI-Origin: Codex`.

## Next action (single, concrete)
- Run a fresh DB-backed Binance source-provenance validation after applying `sql/migrations/0011_venue_instrument_specs.sql` and `sql/seed_venue_instrument_specs.sql` to a reachable dev DB.

## Human Learning Notes
The strict "seed every Binance/Bybit symbol" rule was too strong for normal USDT-M perps because base-unit quantity is structural, but multiplier-style symbols (`1000...`) still need explicit venue specs.

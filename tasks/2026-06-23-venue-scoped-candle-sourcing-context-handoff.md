---
status: archived
type: handoff
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Context Handoff: Venue-Scoped Candle Sourcing - 2026-06-23

## Goal (one sentence)
Enforce that a venue-tagged replay run loads candles only from that venue's provenance-tagged canonical series and fails loudly on missing venue bars.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: pre-existing branch plus local venue-scoped candle sourcing fix; no commit made in this session.
- In-progress edits (files): `backtesting/data_loader.py`, `backtesting/replay.py`, `scripts/run_replay_backtest.py`, `scripts/run_validation_lab_signal_order_check.py`, `src/okx_quant/api/routes_backtest.py`, `tests/unit/test_data_loader.py`, docs listed in the paired session handoff, new regenerated result artifacts.
- What works right now: regenerated MA/EMA/MACD runs with suffix `_venue_scoped_pg_20260623` have 2024-04-29 00:00 `price_series.close == 63229.2`; MA source-provenance DB parity PASS has 20,400 artifact rows, 20,400 DB rows, `canonical_source_primary == "binance"`, and 0 mismatches.
- What does not work / unfinished: Nautilus full execution/PnL parity remains out of scope; `strategy_fill` evidence is still idealized and not promotion/live evidence.

## Decisions made (and why)
- Venue-scoped candle loads force canonical Postgres rather than source-less parquet because parquet does not retain venue provenance.
- Missing venue bars raise explicit errors because cross-venue substitution hides source-data failures.
- Legacy in-process no-DSN fixture configs can still fall back to parquet when no exchange is explicitly passed into candle loading; explicit CLI/API venue paths stay strict.

## Open questions / unverified assumptions
- None for this task.

## Rules in play (preserve verbatim)
- Invariants touched: I19 - a venue-tagged run loads candles only from that venue's provenance-tagged canonical series; source-less parquet or another venue cannot substitute missing bars.
- Domain rules touched: R6.2, R6.4.
- Do-not-touch: `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`; fill/PnL/fee/funding/sizing math; `backtesting/differential_validation.py`; `config/*.yaml`; DB schema/migrations; existing result artifact contents.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, ADR-0007.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` entries for Backtest Run UI and Canonical Candle Pipeline; `backtesting/data_loader.py`; `backtesting/replay.py`.
- Context Pack: none specific exists for this area; `docs/CONTEXT_PACKS/README.md` confirms no candle-source pack yet.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_backtesting.py -q` - PASS, 49 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py tests\unit\test_backtest_request_exchange.py tests\unit\test_multi_venue_convergence.py tests\unit\test_backtest_visual_fallbacks.py -q` - PASS, 38 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_engine_consistency_smoke.py` - PASS.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - PASS with 14 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - PASS.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py --strict` with Git safe-directory env - PASS.
- Regeneration and MA DB parity validation - PASS; evidence path in Current state above.

## Approvals
- Human approval needed / obtained: obtained by explicit user task request on 2026-06-23.

## Next action (single, concrete)
- Ask Claude/human to review the venue-scoped source fix and decide whether EMA/MACD also need source-provenance DB parity artifacts, or whether MA is sufficient for this report slice.

## Human Learning Notes
Repairing data did not repair evidence because the replay read path still omitted venue provenance. For source-data bugs, verify both storage contents and the loader dispatch/path that consumes them.

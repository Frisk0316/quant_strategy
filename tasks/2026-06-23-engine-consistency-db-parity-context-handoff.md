---
status: current
type: handoff
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Context Handoff: Engine Consistency Smoke + Binance 1H DB Parity — 2026-06-23

## Goal (one sentence)
Make technical-strategy engine consistency repeatable offline and unblock Binance BTC-USDT-SWAP 1H DB parity evidence.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: branch equals `origin/codex/impl-multi-venue-instrument-specs`; work is uncommitted.
- In-progress edits (files): `Makefile`, `scripts/run_engine_consistency_smoke.py`, `scripts/resample_binance_1h_canonical.py`, `tests/unit/test_engine_consistency_smoke.py`, `tests/fixtures/engine_consistency/**`, docs/handoff files.
- What works right now: `scripts/run_engine_consistency_smoke.py` passed locally in 27.581s for MA/EMA/MACD against vectorbt+backtrader. MA and EMA fixtures each cover 960 bars with 5 signals; MACD covers 120 bars with 5 signals.
- What does not work / unfinished: the 2024-04-29 Binance 1H data gap is filled, but existing validation-lab artifacts were generated before the repair. Old MA source provenance now has `db_rows=20400`, `missing_in_db=0`, `value_mismatches=24`; regenerate/revalidate artifacts before citing PASS.

## Decisions made (and why)
- Use `tests/fixtures/engine_consistency/` for frozen fixtures because `results/*/` is ignored and the fixture should be commit-friendly.
- Keep engine smoke out of default `smoke`/`verify` despite ~28s runtime because existing smoke targets are lightweight.
- Add a small resample helper instead of changing validation logic because the DB task is data population, not gate behavior.

## Open questions / unverified assumptions
- The missing 24 DB hours were the 2024-04-29 one-day gap. It was repaired with direct Binance 1H download; old artifacts still carry pre-repair prices.
- Approval/usage limit blocked further DB diagnostics after the failed source-provenance run.

## Rules in play (preserve verbatim)
- Invariants touched: I12 — DB-backed source parity agrees on timestamped close values for the same instrument/range; OHLCV structure is checked separately.
- Domain rules touched: R6.2 — DB and parquet sources must agree; a source switch must be explicit and recorded.
- Do-not-touch: `backtesting/differential_validation.py`, trading core, config, schema/migrations, deployment gates, existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/ai_collaboration.md`, ADR-0007.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Validation / Promotion Gates and Canonical Candle Pipeline.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_engine_consistency_smoke.py -q` — 2 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_engine_consistency_smoke.py` - PASS in 27.581s.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\resample_binance_1h_canonical.py --dsn postgresql://quant:changeme@localhost:5432/quant --dry-run` — before counts confirmed no Binance 1H rows.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\resample_binance_1h_canonical.py --dsn postgresql://quant:changeme@localhost:5432/quant` — seeded 20,400 Binance 1H rows.
- DB-backed MA source-provenance validation with vectorbt — FAIL; evidence path `results/validation_lab_ma_crossover_btc_binance_1h_20260622_maxord250_pospct1_strategyfill/validation/codex_binance_1h_db_parity_20260623/validation_result.json`.

## Approvals
- Human approval needed / obtained: User requested both tasks; further DB diagnostics were blocked by escalation/usage limit, not by user denial.

## Next action (single, concrete)
- Regenerate the validation-lab Binance 1H artifacts from the repaired data, then rerun `run_source_provenance_validation.py` until `db_parity.status == PASS`.

## Human Learning Notes
The 1m->1H resample fixed the broad source gap; the remaining 2024-04-29 gap was filled with direct Binance 1H data. The next blocker is stale pre-repair validation artifacts, not DB coverage.

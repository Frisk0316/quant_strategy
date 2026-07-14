---
status: archived
type: handoff
owner: codex
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Context Handoff: Source Provenance Validation - 2026-06-17

## Goal (one sentence)
Add the smallest real-data/source-provenance gate before attempting Nautilus full execution parity.

## Current state
- Branch: `feature/chart-ux-overhaul`.
- Last known good state: targeted source-provenance, strategy-signal, and differential-validation tests pass locally.
- In-progress edits (files): `scripts/run_source_provenance_validation.py`, `tests/unit/test_source_provenance_validation.py`, `Makefile`, `docs/RUNBOOK.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, plus this handoff pair. The previous CI fixture-gate edits are still in the same working tree.
- What works right now: an existing `validation_result.json` can be gated for real-data/source provenance, and a saved run can be validated then gated through the same CLI.
- What does not work / unfinished: no DB-backed artifact was generated in this session, so there is no confirmed PASS real-data provenance artifact yet. GitHub branch protection still needs repository settings to require `strategy-signal-validation` after push. Nautilus matching-engine/PnL/funding parity remains out of scope.

## Decisions made (and why)
- Added a thin CLI over existing differential-validation output because `source_data_validation`, `ct_val_provenance`, `db_parity`, and `ohlcv_source_validation` already exist in the core result.
- Made DB parity `SKIP` fail this gate because fixture/no-DB evidence must not count as real-data provenance.
- Did not add this gate to CI yet because passing evidence requires a reachable DB DSN and seeded canonical candles.

## Open questions / unverified assumptions
- Which saved run should be used for the first real DB-backed source-provenance artifact?
- Whether the current local/CI database has the needed canonical candle coverage for that run's symbols and bar.

## Rules in play (preserve verbatim)
- Invariants touched: I14, I15 as review constraints only; no business-rule behavior changed.
- Domain rules touched: R7 as a validation-evidence boundary only; no promotion-gate rule changed.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`, DB schema, deployment gates, existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/RUNBOOK.md`, `docs/ai_collaboration.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Validation / Promotion Gates; `backtesting/differential_validation.py`; `scripts/run_source_provenance_validation.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_source_provenance_validation.py -q` - 4 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_source_provenance_validation.py tests\unit\test_all_strategy_signal_validation.py tests\unit\test_differential_validation.py -q` - 50 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_source_provenance_validation.py --help` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 11 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` - passed; no changed business-rule files detected.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF warnings only.

## Approvals
- Human approval obtained in chat: yes to making `strategy-signal-validation` a required branch protection check and yes to prioritizing real-data/source provenance before Nautilus full execution parity.

## Next action (single, concrete)
- Run `scripts/run_source_provenance_validation.py --run-id <run_id> --validation-id <validation_id>` with `DIFF_VALIDATION_ENABLE_DB_PARITY=1` and a reachable `DIFF_VALIDATION_DB_DSN` for a saved run with canonical candle coverage.

## Human Learning Notes
The important boundary is now executable: fixture validation can be CI-required, but real-data provenance requires DB-backed candle parity. A `source_data_validation.status == PASS` fixture result is still not enough when DB parity is `SKIP`.

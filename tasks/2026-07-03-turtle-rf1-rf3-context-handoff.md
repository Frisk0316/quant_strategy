---
status: archived
type: handoff
owner: human
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Context Handoff: Turtle RF1-RF3 remediation - 2026-07-03

## Goal (one sentence)
Finish Claude's RF1-RF3 remediation for the research-only Turtle platform integration and prepare a turtle-scoped commit that excludes the parallel funding-xs-dispersion stream.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good state: working tree after RF1-RF3 verification; commit still pending at handoff creation.
- In-progress edits: turtle implementation/RF files, turtle docs/state files, and this handoff; funding-xs-dispersion edits are present in the working tree but must not be staged with turtle.
- What works right now: full unit suite, Turtle golden parity, frontend syntax, docs metadata/link checks, config-only validation, and current-code DB-backed Turtle single run/sweep smoke.
- What does not work / unfinished: the turtle-scoped commit is the next step; the pre-existing 8080 server may be stale and should not be used as evidence for this diff.

## Decisions made (and why)
- Added only one declarative `turtle` entry to `REFERENCE_VALIDATION_CONTRACTS` because Claude/user approved that narrow RF1 scope; no differential-validation implementation logic changed.
- Used a native `input type="range"` plus existing `LineChart` for the invest_pct scrub because it is the smallest UI that satisfies RF2 and reuses the local chart stack.
- Compared checked-in fixture CSVs in tests without regenerating them because RF3 explicitly forbids fixture regeneration or hand edits.
- Started a temporary server on port 8081 for DB smoke because port 8080 was already occupied by an older process; current-code evidence must come from the current working tree.

## Open questions / unverified assumptions
- Whether to stop or refresh the pre-existing port 8080 server is outside this task; it may still be serving stale code.

## Rules in play (preserve verbatim)
- Invariants touched: I31 - Turtle S1/S2 reference semantics stay isolated to the research-only Turtle runner.
- Domain rules touched: R5.5 - Turtle S1/S2 reference semantics are scoped to the research-only `backtesting/turtle_backtest.py` runner.
- Do-not-touch: do not modify `research/`; do not change live, shadow, demo, deployment gates, strategy config, risk, portfolio, or differential-validation implementation; do not regenerate or hand-edit `tests/fixtures/turtle/`; do not stage funding-xs-dispersion stream files.

## Context to load next (the reading list)
- Source of truth: `tasks/2026-07-03-turtle-strategy-platform-tasks.md`, `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, `config/`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Turtle Research Runner, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `backtesting/turtle_backtest.py`, `src/okx_quant/api/routes_backtest.py`, `frontend/view-config.js`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `pytest tests/unit/test_differential_validation.py::test_reference_validation_contract_covers_all_declared_strategies -q` -> failed before RF1, then passed after RF1.
- `pytest tests/unit/test_turtle_backtest.py -q` -> 10 passed.
- `pytest tests/unit/test_turtle_backtest.py tests/unit/test_routes_backtest_turtle.py tests/unit/test_differential_validation.py::test_reference_validation_contract_covers_all_declared_strategies tests/unit/test_differential_validation.py::test_reference_validation_contract_declares_all_engine_portability_paths -q` -> 16 passed.
- `pytest tests/unit/test_turtle_backtest.py tests/unit/test_differential_validation.py -q` -> 58 passed, 1215 warnings after review fixes.
- `pytest tests/unit -q` -> 599 passed, 1221 warnings.
- Full frontend syntax loop for the 12 Makefile frontend files -> passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` -> passed, 0 warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` -> passed, 192 concrete paths checked.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` -> exit 0, reported no changed files detected.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\validate_pipeline.py --check-config-only` -> passed.
- DB smoke on temporary current-code server `http://127.0.0.1:8081`: Turtle single run job `9280c98a` done with 2 orders; Turtle sweep job `1289a6dd` done with 2 combinations and `rows.csv`, `equity_curves.csv`, `summary.json`.

## Approvals
- Human approval already recorded in the task/handoff for the single declarative Turtle validation contract entry.

## Next action (single, concrete)
- Stage only turtle/RF files and commit with required AI metadata, excluding funding-xs-dispersion files and hunks.

## Human Learning Notes
The 8080 smoke initially exposed a `Timestamp` serialization error, but current working-tree code already had ISO conversion; the cause was a stale pre-existing 8080 server. For API smoke after frontend/backend edits, prefer a fresh temporary port or restart the target server before treating failures as current-diff evidence. Review also showed that advisory engine role is not enough to keep a validation contract nonportable; the engine status itself must be `not_targeted`.

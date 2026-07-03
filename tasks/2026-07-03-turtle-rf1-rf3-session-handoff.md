# Session Handoff: Turtle RF1-RF3 remediation - 2026-07-03

## Implementation summary
Implemented Claude's RF1-RF3 fixes for the research-only Turtle platform integration: RF1 fixed the API allow-list scrape collision and added the approved declarative Turtle validation contract; RF2 added the invest_pct sweep scrub UI and five Turtle heatmaps; RF3 wired the checked-in golden Turtle fixtures into parity tests without changing the fixture files.

## Diff scope
- Files added: `tasks/2026-07-03-turtle-rf1-rf3-context-handoff.md`, `tasks/2026-07-03-turtle-rf1-rf3-session-handoff.md`.
- Files changed: `src/okx_quant/api/routes_backtest.py`, `backtesting/differential_validation.py`, `frontend/view-config.js`, `tests/unit/test_turtle_backtest.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/GOLDEN_CASES.md`, `docs/CHANGELOG_AI.md`.
- Files deleted: none.

## Business-rule change?
- No new business-rule change in RF1-RF3. The broader Turtle research-runner rule is already documented as R5.5/I31 and covered by `docs/change_manifests/2026-07-03-turtle-strategy-runner.md`; docs-impact was run advisory and exited 0 while reporting no changed files detected.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, not modified.
- config/: `config/workstreams.yaml` updated for honest Turtle workstream status.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none for RF1-RF3.
- EXPERIMENT_REGISTRY entries: none for RF1-RF3.

## Tests / checks run
- `pytest tests/unit/test_differential_validation.py::test_reference_validation_contract_covers_all_declared_strategies -q` -> red before RF1, green after RF1.
- `pytest tests/unit/test_turtle_backtest.py -q` -> 10 passed.
- `pytest tests/unit/test_turtle_backtest.py tests/unit/test_routes_backtest_turtle.py tests/unit/test_differential_validation.py::test_reference_validation_contract_covers_all_declared_strategies tests/unit/test_differential_validation.py::test_reference_validation_contract_declares_all_engine_portability_paths -q` -> 16 passed.
- `pytest tests/unit/test_turtle_backtest.py tests/unit/test_differential_validation.py -q` -> 58 passed, 1215 warnings after review fixes.
- `pytest tests/unit -q` -> 599 passed, 1221 warnings.
- Full frontend syntax loop for the 12 Makefile frontend files -> passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` -> passed, 0 warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` -> passed, 192 concrete paths checked.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` -> exit 0, reported no changed files detected.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\validate_pipeline.py --check-config-only` -> passed.
- DB smoke on temporary current-code server `http://127.0.0.1:8081`: Turtle single run job `9280c98a` done; Turtle sweep job `1289a6dd` done with `rows.csv`, `equity_curves.csv`, `summary.json`.

## Docs updated
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/GOLDEN_CASES.md`, `docs/CHANGELOG_AI.md`, and this handoff pair.

## Known limitations / risks
- The port 8080 server was pre-existing and appeared stale; current-code DB smoke used a temporary 8081 server, which was stopped afterward.
- `make` is not installed in this PowerShell shell, so Makefile targets were expanded into their direct commands.
- `scripts/docs/check_doc_impact.py` exited 0 but reported no changed files detected; do not interpret that as a strict changed-file impact audit.

## Rollback plan
- Revert the turtle/RF commit once made, or before commit restore the listed RF files from HEAD and remove the two RF handoff files. Leave funding-xs-dispersion files untouched.

## Context Handoff
- See `tasks/2026-07-03-turtle-rf1-rf3-context-handoff.md`.

## Questions for human review
- Should the pre-existing 8080 server be restarted or left alone for the next UI manual check?

## Next recommended task
- Stage only turtle/RF files and commit with AI-Origin metadata, excluding all funding-xs-dispersion files/hunks.

## Human Learning Notes (required)
When a DB/API smoke failure contradicts the current working tree, verify the serving process before debugging code. This session's first sweep smoke hit a stale 8080 process; a fresh 8081 server proved the current Turtle sweep artifact path was clean. Review also showed that advisory engine role is not enough to keep a validation contract nonportable; the engine status itself must be `not_targeted`.

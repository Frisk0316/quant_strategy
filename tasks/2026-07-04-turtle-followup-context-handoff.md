---
status: current
type: handoff
owner: human
created: 2026-07-04
last_reviewed: 2026-07-04
expires: none
superseded_by: null
---

# Context Handoff: Turtle follow-up Codex pass - 2026-07-04

## Goal (one sentence)
Complete the Codex implementation plan in `tasks/2026-07-04-turtle-followup-codex-plan.md` without changing Turtle strategy assumptions, trading-core behavior, risk config, or existing result artifacts.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: pre-existing branch state plus uncommitted Turtle follow-up edits; no commit made.
- In-progress edits (files): Turtle API/UI/tests, sweep parity script, docs/state/handoffs, generated UI screenshots.
- What works right now: numeric-string epoch markers, symbol-filtered marker endpoint, Turtle `invest_pct` live slider sync, explicit Turtle risk/execution/`fill_all_signals` ignore recording, CI-portable verbatim-reference sweep golden subset, Tier A sweep parity, surface fixed-param title/hover text.
- What does not work / unfinished: Tier B user CSV fingerprint does not match DB-synthesized daily input; treat as data provenance mismatch, not a port mismatch.

## Decisions made (and why)
- Turtle remains a research-only standalone runner because the original platform integration scope explicitly excluded replay/trading-core/gate changes.
- Risk overrides, execution profile, and `fill_all_signals` are ignored for Turtle and recorded as such because `_run_turtle_job` never consumed them and wiring them into the engine was out of scope.
- Marker endpoints read precomputed marker artifacts unfiltered and apply final symbol filtering after normalized marker construction because DB/file row filters can otherwise hide valid Turtle markers.
- Tier B parity stops on fingerprint mismatch because tuning DB data to force a user CSV match would create false provenance confidence.

## Open questions / unverified assumptions
- The exact input behind `new_startegy_*/index_parameter_result_full (3).csv` remains unknown; DB 1m synthesis did not reproduce it.

## Rules in play (preserve verbatim)
- Invariants touched: no trading invariant semantics changed; marker display guard added through `tests/unit/test_routes_backtest_turtle.py`; CI reference parity guard added through `tests/unit/test_turtle_backtest.py::test_sweep_metric_rows_match_verbatim_reference_golden_subset`.
- Domain rules touched: none semantically; `docs/change_manifests/2026-07-04-turtle-followup-parity-ui.md` records the A5 presentation/validation touch.
- Do-not-touch: `research/`, `results/**`, `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/risk.yaml`, deployment/shadow/demo/live gates.

## Context to load next (the reading list)
- Source of truth: `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, `config/`, `tests/fixtures/turtle/README.md`.
- Owning files / MODULE_BRIEFS: `src/okx_quant/api/routes_backtest.py`, `backtesting/turtle_backtest.py`, `frontend/view-config.js`, `tests/unit/test_routes_backtest_turtle.py`, `tests/unit/test_turtle_backtest.py`, `scripts/turtle/validate_sweep_parity.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_routes_backtest_turtle.py -q` -> 9 passed; local result-artifact tests are skip-gated when gitignored files are absent.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_turtle_backtest.py -q` -> 14 passed; includes verbatim-reference golden subset.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_turtle_backtest.py tests\unit\test_routes_backtest_turtle.py -q` -> 23 passed.
- `node --check frontend\view-config.js` and frontend-check equivalent node syntax sweep -> passed.
- `scripts/turtle/validate_sweep_parity.py` -> Tier A PASS, 27 columns match.
- `scripts/turtle/validate_sweep_parity.py --reference-csv "new_startegy_*/index_parameter_result_full (3).csv"` -> Tier B fingerprint failed; DB 1m coverage reported and mismatch treated as data provenance.
- Browser check on patched local server port 8082 -> `212 markers`, `investPctValue=33.3`, screenshots in `tasks/`.

## Approvals
- Human approval needed / obtained: no live/deployment approval requested or obtained; escalations approved only for `polars` install and Playwright browser verification.

## Next action (single, concrete)
- If continuing this stream, review/commit the Turtle follow-up diff after final verification and fresh-context review.

## Human Learning Notes
The manual screenshot requirement caught a second marker bug that unit-only work would have missed: the unfiltered marker endpoint worked, but the UI uses a symbol-filtered call. For file/DB artifacts, normalize rows before filtering whenever the filter key can be represented differently across storage paths.

---
status: archived
type: handoff
owner: claude
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Context Handoff: Turtle (海龜) platform integration planning — 2026-07-03

## 2026-07-03 Codex implementation update

T1-T5 are implemented in the working tree. Core files:
`backtesting/turtle_backtest.py`,
`tests/unit/test_turtle_backtest.py`,
`src/okx_quant/api/routes_backtest.py`,
`tests/unit/test_routes_backtest_turtle.py`,
`frontend/data.js`, `frontend/view-config.js`, `frontend/charts.js`,
`frontend/vendor/plotly.min.js`, and
`docs/change_manifests/2026-07-03-turtle-strategy-runner.md`.

Verification run so far: focused turtle pytest and Node syntax checks passed.
`py_compile` could not write `__pycache__` in the sandbox, so syntax was checked
with in-memory `compile()`. DB-backed manual run/sweep smoke was not run because
it needs a running server and 1D candles.

Next action: Claude/human review against
`tasks/2026-07-03-turtle-strategy-platform-tasks.md`, then optional DB-backed
manual run/sweep smoke.

## Goal (one sentence)

Port the user's standalone turtle backtest (`new_startegy_海龜/`) into the
platform with all parameters UI-editable, a sweep that replaces the
console-interactive `sweep_params_interactive_full`, an `invest_pct` slider
to 100%, and dual sweep visualization (native heatmaps + plotly surface.html).

## Current state

- Branch: `codex/pipeline-batch1-stage3`.
- Last known good state: parallel session committed M2-R1 (`21cc3c9`) and
  P1-P9; tree was clean before this planning session.
- In-progress edits (files, all uncommitted, this session):
  `docs/superpowers/specs/2026-07-03-turtle-platform-design.md` (new),
  `tasks/2026-07-03-turtle-strategy-platform-tasks.md` (new),
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`,
  this handoff + session handoff.
- What works right now: planning complete; spec + T1–T5 task file ready for
  Codex. No code written.
- What does not work / unfinished: implementation not started; parity
  fixtures do not exist yet.

## Decisions made (and why)

- **Standalone runner, daily_winner precedent** (new
  `backtesting/turtle_backtest.py` + `routes_backtest.py` job), NOT a
  replay-engine strategy — because parity with the reference implementation
  is the acceptance bar and the replay engine's fill/risk model would change
  the numbers; would change if the user later asks for a live-path turtle.
- **pandas port, polars/plotly NOT added to Python deps** — repo is
  pandas-only; fixtures generated once in a scratch venv; would change only
  with explicit user approval of new deps.
- **Visualization = BOTH** native SVG heatmaps and vendored
  `frontend/vendor/plotly.min.js` powering a per-sweep `surface.html`
  artifact — explicit user choice (AskUserQuestion 2026-07-03) over
  heatmap-only or plotly-only.
- **invest_pct slider 0.1–100%, default 1%, hint ≤25%** — user wants to drag
  and watch final equity; sweep invest_pct axis requires the 4 window params
  fixed so the scrub is well-defined.
- **Bar locked to 1D UTC** — reference system is daily-only.
- **`initial_fund` dropped** — reference docx §9 documents it as unused.
- **Reference quirks preserved** (same-day ATR, close fills, strict `<` cash
  gate, S1 skip-after-win, S1-before-S2 ordering, no end liquidation, mdd on
  own_capital+whole_asset filter_zero) — parity over "improvement".

## Open questions / unverified assumptions

- Assumed the daily_winner Postgres daily-aggregation path yields UTC-midnight
  days identical to the reference `resample_to_daily`; T1/T2 must verify.
- Default symbol BTC-USDT-SWAP, venue = platform primary, sweep caps
  5000/20000 — stated as proceed-unless-user-objects defaults in the spec.

## Rules in play (preserve verbatim)

- Do-not-touch: `src/okx_quant/strategies|signals|risk|portfolio|execution/`,
  `config/risk.yaml`, `config/strategies.yaml`, `backtesting/replay.py`,
  `backtesting/parameter_sweep.py`, `backtesting/daily_winner_backtest.py`,
  `backtesting/artifacts.py`, `new_startegy_海龜/` (read-only reference),
  `research/`, durable ledgers, existing `results/**`.
- Sweep validity constraints (reference): `sys1>leave1`, `sys2>leave2`,
  `sys2>sys1`, `leave1>=5`, `leave2>=5`, `leave2>leave1`.
- polars/plotly must not enter `pyproject.toml`.

## Context to load next (the reading list)

- Source of truth: `new_startegy_海龜/trading_target_func.py`
  (`turtle_trading_system_full`, lines 413–719; sweep 2688–2891) + the docx.
- Spec: `docs/superpowers/specs/2026-07-03-turtle-platform-design.md`.
- Task file: `tasks/2026-07-03-turtle-strategy-platform-tasks.md`.
- Precedent code: `_run_daily_winner_job` in
  `src/okx_quant/api/routes_backtest.py` (~line 590), `_sweep_jobs` registry
  (~line 42/2456), `frontend/view-config.js` strategy param specs (~line 939)
  and `ParameterSweepPanel` (~line 986), `frontend/data.js` registry (~line 75).

## Checks run

- `python scripts/docs/check_doc_metadata.py` — see session handoff (run at
  session end).
- No code/tests to run — planning-only session.

## Approvals

- User approved: applying turtle to the platform, UI-adjustable params,
  sweep replacement, invest_pct slider to ~100%, visualization choice "both".
- NOT approved / not claimed: any live/demo/shadow path, promotion, new
  Python deps.

## Next action (single, concrete)

- Codex executes T1 in `tasks/2026-07-03-turtle-strategy-platform-tasks.md`
  (pandas port + golden parity fixture); T2–T4 are blocked until the parity
  test passes.

## Human Learning Notes

- The reference implementation's `sweep_params_interactive_full` drives
  everything through console `input()` — the platform sweep panel replaces
  exactly that interaction (fix-or-range per window param), so the UI design
  maps 1:1 onto a workflow the user already knows.
- `invest_pct` above ~25% mostly hits the reference's cash gate
  (`cost < money_in_hand`), so "drag to 100%" will show plateauing equity —
  this is honest reference behavior, surfaced as a UI hint instead of being
  "fixed".
- A parallel session rewrote AI_HANDOFF/CURRENT_STATE/workstreams mid-session
  (M2-R1 + P9 commits); re-reading before editing avoided clobbering it.

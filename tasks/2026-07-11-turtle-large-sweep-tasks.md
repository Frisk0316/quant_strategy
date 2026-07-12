---
status: archived
type: task
owner: codex
created: 2026-07-11
last_reviewed: 2026-07-11
expires: none
superseded_by: null
---

# Turtle Large Sweep: Batched Execution + Cap Raise

Task: Let the Turtle sweep run the full 4-window grid (262,080 raw /
115,200 valid combos) by executing in resumable batches, instead of
rejecting it at the hardcoded caps.

Strategy/spec source: user request 2026-07-11 (this file); reference
behavior `new_startegy_海龜/trading_target_func.py::sweep_params_interactive_full`.
No strategy/business-rule change: sweep mechanics only, per-combo results
must stay bit-identical to the current engine.

Required behavior (example): grid S1 enter `5~30`, S2 enter `31~60`,
S1 exit `5~20`, S2 exit `5~25`, fixed `single/both_sys_unit_limit=4`,
`own_capital=10000`, `invest_pct=25%`, `min_position=0.0001`, `fee=0.003`,
`atr_period=20` → submitted from the frontend, accepted (no
"raw candidates exceed cap" error), executed to completion in batches with
live progress, producing `rows.csv` with all 115,200 valid rows and a
ranked top-results table.

Current blockers (file:line, verified 2026-07-11):
- `backtesting/turtle_backtest.py:804` `max_raw_candidates=20000` hardcoded;
  checked at `:826` against the PRE-filter Cartesian product, while the
  frontend shows the post-filter valid count — confusing UX.
- `max_combinations` request field capped at 10000
  (`src/okx_quant/api/routes_backtest.py` ParameterSweepRequest validation).
- `run_turtle_sweep` (`backtesting/turtle_backtest.py:858`) is one
  in-process loop: no checkpoint, no resume, no cancel, single core;
  frontend estimate for the full grid is ~24h.

Design requirements (implementation details are Codex's choice):
1. Validate against the POST-filter valid-combo count, not the raw product.
   Keep A cap (guardrail against accidental multi-day runs) but make it a
   request field with a sane default (suggest default 20,000 valid; hard
   ceiling ≥200,000) so the full grid is possible but explicit.
2. Batched/checkpointed execution: persist completed rows per batch under
   `results/turtle_sweeps/<sweep_id>/`; after a server restart the sweep is
   resumable (new request with same sweep_id continues, or an explicit
   resume flag). Cancel between batches must work.
3. Progress: job status reports completed/total and ETA while running.
4. Consider multiprocessing across combos for wall-clock (optional; if
   added, per-combo outputs must remain deterministic and ordered).
5. Large-result handling: `summary.json` must stay parseable and modest
   (top_results + counts + artifact names; do NOT inline 115k rows —
   full rows live in `rows.csv` only). Frontend: keep existing 2-free-param
   heatmaps / invest_pct scrub unchanged; for >2 free params show the
   top-results table + artifact download links only.

PERMITTED FILES (only edit these):
- backtesting/turtle_backtest.py
- src/okx_quant/api/routes_backtest.py
- frontend/view-config.js, frontend/data.js (sweep UI/progress only)
- tests/unit/test_turtle_backtest.py, tests/unit/test_routes_backtest_turtle.py
- docs/RUNBOOK.md, docs/UI_MAP.md, docs/FEATURE_MAP.md (matching rows only)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/, src/okx_quant/signals/, src/okx_quant/risk/,
  src/okx_quant/portfolio/, src/okx_quant/execution/, config/risk.yaml
- tests/fixtures/turtle/ (golden fixtures are frozen)
- backtesting/differential_validation.py (other session owns it)
- Existing result artifacts under results/

SCOPE LIMIT: sweep execution mechanics only; no change to per-combo turtle
math, params, metrics, or golden parity behavior; no adjacent refactoring.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run: `python -m pytest tests/unit/test_turtle_backtest.py tests/unit/test_routes_backtest_turtle.py -q`
  and paste the output tail.
- Update docs per the AGENTS.md docs-update matrix (RUNBOOK sweep commands,
  UI_MAP sweep panel behavior) or state "n/a: <why>".
- Do NOT commit unless the user asks in that session.

ACCEPTANCE CRITERIA (binary):
- [ ] The example grid above is accepted end-to-end from the frontend and
      runs (verified at least through several batches + resume + cancel;
      a full 115,200-combo completion run may be left running and reported).
- [ ] A small grid (e.g. 416 raw / 270 valid) produces rows byte-identical
      to the pre-change engine (regression test comparing batched vs
      single-pass output on a fixture frame).
- [ ] Kill the server mid-sweep → restart → resume → final rows.csv has all
      valid combos exactly once (test or scripted proof).
- [ ] Existing 2-free-param heatmap sweep and invest_pct-axis sweep still
      work in the browser (DB-backed manual check — this also closes the
      outstanding "DB-backed manual sweep validation" item from
      tasks/2026-07-08-turtle-polish-context-handoff.md).
- [ ] Turtle golden/parity tests pass unchanged.
- [ ] Diff contains only permitted files.

REPORT: changed files, test output tail, assumptions made, measured
per-combo runtime and projected full-grid wall-clock, anything UNCONFIRMED
or skipped.

---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# AI Handoff

Cross-session memory for Claude and Codex. Keep this file current-state only;
move completed session history to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

## Current Goal

Both tracked streams are complete and committed as of 2026-07-04. Full
narrative history moved to `docs/CHANGELOG_AI.md` (see "2026-07-03 - M2-R1
Reviewed, Accepted, And Committed" and "2026-07-03/04 - Pipeline P1-P9 Full
Cycle + First Stage-1 Spec From Taxonomy").

**Repo maintenance (M1-M5 + M2-R1):** all committed (`df96682`, `79c1ddc`,
`0191c1d`, `2dea608`, `5eb71f8`, `21cc3c9`). Claude-reviewed and accepted on
independent re-verification. No outstanding action.

**Strategy research pipeline (P1-P9):** all committed (`dfc7af8`, `6997aba`,
`14976d4`, and the in-progress P9 + Stage-1 spec commit). Result:
`F-FUNDING-XS-DISPERSION` (`H-009`) is the first taxonomy-sourced candidate
to clear Stage-2 `data_availability` (E-030: 32 eligible symbols, 28 good,
breadth min 24/median 27 vs threshold 10). `stage2_status` stays FAIL —
`distinctness` (vs `F-FUNDING-CARRY`) and `cost_after_edge` have not run.
Stage-1 spec with the full mechanism-distinctness argument:
`docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`.

**Next action (Codex):** run the family-minting distinctness checker for
`F-FUNDING-XS-DISPERSION` vs the `F-FUNDING-CARRY` reference signal first;
then implement Stage 3 by reusing `xs_momentum_backtest.py`'s PIT-universe
loader, corrected vol-targeting, and leak-fixed daily-shift as the skeleton
(swap the ranking signal to trailing funding APR); pre-registered grid = 4
combos (`L in [7,14] days, Q in [0.20,0.30]`); stop at checkpoint (1); no
adapter/promotion/demo/shadow/live claim without Claude/user review of the
Stage-3 evidence.

**Turtle (海龜) platform integration — NEW workstream (planned 2026-07-03,
Claude):** the user's standalone turtle system (`new_startegy_海龜/`,
`turtle_trading_system_full` long version) is to be ported into the platform
as a research-only standalone runner following the daily_winner precedent
(NOT replay-engine, NOT `src/okx_quant/strategies/`, no
`config/strategies.yaml` entry): pandas port + golden parity fixture in a new
`backtesting/turtle_backtest.py`, single-run + sweep wiring in
`routes_backtest.py`, frontend form with an `invest_pct` slider to 100%, and
a sweep that replaces the console-interactive `sweep_params_interactive_full`
(fix-or-range windows + optional invest_pct axis). Dual visualization per
user decision: native SVG heatmaps + vendored-plotly `surface.html` artifact.
Parity with the reference implementation is the acceptance bar; its quirks
(same-day ATR, close fills, cash gate, S1 skip-after-win, no end liquidation)
are preserved deliberately. polars/plotly must NOT become Python deps
(fixtures come from a one-off scratch venv). Spec:
`docs/superpowers/specs/2026-07-03-turtle-platform-design.md`. Codex tasks:
`tasks/2026-07-03-turtle-strategy-platform-tasks.md` (T1–T5; T1 parity gate
blocks T2–T4).

Implementation update (2026-07-03 Codex): T1-T5 are implemented in the working
tree. New code lives in `backtesting/turtle_backtest.py`,
`src/okx_quant/api/routes_backtest.py`, `frontend/data.js`,
`frontend/view-config.js`, `frontend/charts.js`, and
`frontend/vendor/plotly.min.js`; tests are
`tests/unit/test_turtle_backtest.py` and
`tests/unit/test_routes_backtest_turtle.py`. Narrow pytest and Node syntax
checks passed locally; DB-backed manual run/sweep smoke still needs a running
server with 1D candles.

2026-07-03 Claude review: **APPROVED WITH REQUIRED FIXES (3).** Independent
evidence, not self-report: the reviewer extracted the reference
`turtle_trading_system_full` verbatim into a polars scratch venv and ran it on
a 600-day seeded fixture with two param sets (default + cash-gate stress) —
the pandas port matched **exactly** (17 columns, ints exact, floats rtol
1e-9, final equity identical: 49365.150060 / 7034.345421). Fixture + expected
CSVs are now checked in under `tests/fixtures/turtle/` (with provenance
README). Sweep artifacts smoke-verified in-process (rows.csv, surface.html
with 5 metrics + /vendor/plotly.min.js ref, equity_curves.csv for the
invest_pct axis). 30 focused tests pass, node --check passes, docs checks
3/3 green, no forbidden file touched, plotly v2.35.2 MIT vendored and
excluded from FRONTEND_JS. Required fixes before commit: **RF1** full-suite
regression — `test_reference_validation_contract_covers_all_declared_
strategies` FAILS because (a) the new local `allowed` variable in
`_turtle_sweep_base_params` hijacks the test's regex scrape of the API
allow-list (rename it), and (b) declared strategy `turtle` needs a minimal
declarative `REFERENCE_VALIDATION_CONTRACTS` entry (touching
`backtesting/differential_validation.py` was task-FORBIDDEN — scope
amendment limited to one declarative registry entry, **user-approved
2026-07-03**).
**RF2** the user's core ask — the invest_pct 拉桿 scrub UI (final_equity vs
invest_pct chart + slider switching the per-value equity curve) — is NOT
implemented in TurtleSweepPanel even though equity_curves data is complete.
**RF3** wire the checked-in golden fixture into a parity test in
`tests/unit/test_turtle_backtest.py` (T1 acceptance). Minor (non-blocking):
dashboard heatmaps show 3 of 5 metrics; fixed-vs-range invest_pct unit
inconsistency in the sweep grid (scalar must be a fraction, range is
percent — a bare "25" 400s); heatmap lacks hover/click detail; warmup hint
hardcodes 55d.

RF completion update (2026-07-03 Codex): RF1-RF3 are implemented in the
working tree. RF1 renamed the turtle sweep local parameter set and added the
single approved declarative `turtle` reference-validation contract entry. RF2
added the `invest_pct` final-equity line chart, slider scrub, selected equity
curve, and expanded Turtle heatmaps to 5 metrics. RF3 wires
`tests/fixtures/turtle/daily_ohlc.csv` plus default/stress expected CSVs
into the parity test without regenerating or editing fixtures. Targeted checks
are green. Closure verification now also passed: `pytest tests/unit -q` (598
passed), full frontend JS syntax loop (12 files), docs metadata/link checks,
config-only validation, and current-code DB-backed Turtle API smoke on a
temporary 8081 server (single run done; 2-row `invest_pct` sweep done with
`rows.csv`, `equity_curves.csv`, and `summary.json`). Remaining closure is the
turtle-scoped commit; do not stage the parallel funding-xs-dispersion stream.

**Known pending items (not blocking, tracked in KNOWN_ISSUES/RUNBOOK):**
liquidation ingest (`quant_liq_okx_ingest`) is Interactive-only (runs only
while logged in) — an unattended/service mode is a separate decision if
needed; the 4 point-in-time-eligible symbols with zero funding history
(`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP) can be backfilled the same way as the
other 28 if a later grid needs them.

## Current Branch

- Branch: `codex/pipeline-batch1-stage3`.
- Recent commits: `df96682` (M1), `79c1ddc` (7/3 handoff preservation),
  `0191c1d` (M2), `2dea608` (M3), `5eb71f8` (M4/M5), `21cc3c9` (M2-R1),
  `dfc7af8`/`6997aba`/`14976d4` (pipeline P1-P8 + real-data runs + warmup
  window), plus an in-progress commit for P9 + the F-FUNDING-XS-DISPERSION
  Stage-1 spec.
- Working tree additionally contains the uncommitted 2026-07-03 turtle
  planning docs (spec, task file, handoffs, these state-file updates); commit
  on user request.

## Do Not Touch

Without explicit user approval, do not modify:

- `research/` except explicit user-approved research tasks.
- `results/**` existing artifacts.
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`.
- `src/okx_quant/risk/`, `src/okx_quant/portfolio/`,
  `src/okx_quant/execution/`.
- `config/risk.yaml`, deployment/shadow/demo/live gates, or strategy assumptions.
- Differential-validation implementation unless a current task explicitly lists it.

## Verification Notes

M1-M5 + M2-R1 verification evidence (test counts, docs-check output, smoke
reproduction) moved to `docs/CHANGELOG_AI.md` — that stream is closed. P1-P9
verification evidence (test counts, real-run row counts, doc-impact checks)
is likewise in `docs/CHANGELOG_AI.md`.

`make` remains unavailable in this Windows sandbox; use the equivalent
Python commands (`python scripts/docs/check_doc_metadata.py`,
`python scripts/docs/check_feature_map_links.py`,
`python scripts/docs/check_doc_impact.py --strict`) or `pytest` directly.
Full `make verify` / `make verify-full` still needs an environment with
`make`, TimescaleDB, and required data.

## Next Steps

1. Codex: run the family-minting distinctness checker for
   `F-FUNDING-XS-DISPERSION` vs `F-FUNDING-CARRY`, then implement Stage 3
   per the hand-off in
   `docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`.
2. If a later grid needs the 4 not-yet-backfilled symbols
   (`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP), rerun
   `scripts/market_data/backfill_universe_funding.py` for them.
3. Decide whether the `quant_liq_okx_ingest` Windows task needs an
   unattended/service mode (currently Interactive-only).
4. Codex: implement the turtle platform integration per
   `tasks/2026-07-03-turtle-strategy-platform-tasks.md` (T1 first — the
   golden parity fixture gates T2–T4); Claude reviews against the spec's
   semantics contract.

2026-07-03 update: turtle implementation plus RF1-RF3 fixes are present in the
working tree and verified. The next turtle action is a turtle-scoped commit
that excludes the parallel funding-xs-dispersion stream.

## Open Questions

- None currently open.

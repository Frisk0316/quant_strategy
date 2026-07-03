---
status: current
type: spec
owner: claude
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Turtle (海龜) Strategy Platform Integration — Design Spec

Author: Claude (planning). Implementer: Codex.
Task file: `tasks/2026-07-03-turtle-strategy-platform-tasks.md`.

## Goal

Port the user's standalone turtle dual-system trend backtest
(`new_startegy_海龜/trading_target_func.py :: turtle_trading_system_full`)
into the backtest platform so that:

1. A single turtle backtest is runnable from the Run Backtest UI with **all 11
   parameters editable**, including an `invest_pct` slider that goes to 100%.
2. The platform's sweep flow **replaces the console-interactive**
   `sweep_params_interactive_full` (fix-or-range per window parameter, same
   validity constraints, same output columns).
3. Sweep results get **both** visualizations (user decision 2026-07-03):
   native SVG heatmaps in the dashboard **and** a reference-style standalone
   Plotly 3D-surface HTML artifact per sweep.

**Truth source:** `new_startegy_海龜/trading_target_func.py` (long/full
version) and `new_startegy_海龜/sweep_params_interactive_full_函式說明文件.docx`.
Parity with the reference implementation is the acceptance bar. Do not
"improve" its trading semantics.

## Non-goals

- No short version (`turtle_trading_system_full_short`), no
  `find_plateau` / `evaluate_single_strategy_system1` / `bm_monte_carlo` /
  `evaluate_all` ports. The sweep CSV keeps the reference column names so the
  user's existing offline tools still consume it.
- No replay-engine (`backtesting/replay.py`) integration, no entry in
  `config/strategies.yaml`, no `src/okx_quant/strategies/` file. This is a
  **research-only standalone runner** following the `daily_winner` precedent.
- No multi-symbol portfolio; one instrument per run (reference semantics).
- No live/demo/shadow path, no promotion-gate claims.

## Architecture (daily_winner precedent)

```text
frontend (data.js registry + view-config.js form/sweep panel)
   └─ POST /api/backtest/run          strategy="turtle"  → _run_turtle_job
   └─ POST /api/backtest/sweep        strategy="turtle"  → _run_turtle_sweep_job
        (branch BEFORE _validate_parameter_sweep_request; replay sweep untouched)
backtesting/turtle_backtest.py        pandas port + metrics + grid + sweep
   └─ daily bars: DB canonical candles aggregated to UTC daily OHLC
      (same Postgres daily-aggregation path daily_winner uses; DB required)
artifacts
   └─ single run: standard ADR-0002 run dir (result.json, price_series,
      indicator_series, trades, equity) → existing results UI renders it
   └─ sweep: results/turtle_sweeps/<sweep_id>/ summary.json + rows.csv
      (+ equity_curves.csv, + surface.html when applicable)
```

New module `backtesting/turtle_backtest.py` public surface (names indicative):

- `TurtleParams` — the 11 reference parameters (below).
- `run_turtle_backtest(daily_df, params) -> TurtleResult` — per-day frame,
  trade events, metrics.
- `expand_turtle_grid(spec) -> (combos, skipped)` — validity constraints + caps.
- `run_turtle_sweep(daily_df, spec, base_params, progress_cb) -> summary`.
- `render_surface_html(rows, x_col, y_col) -> str` — Plotly template.

## Parameters (UI defaults = the user's example call)

| Param | Default | UI control |
| --- | --- | --- |
| enter_term_sys1 | 20 | int input |
| enter_term_sys2 | 55 | int input |
| leave_term_sys1 | 10 | int input |
| leave_term_sys2 | 20 | int input |
| single_sys_unit_limit | 4 | int input |
| both_sys_unit_limit | 4 | int input |
| own_capital | run form capital field (default 50000) | existing capital input |
| invest_pct | 0.01 | **slider 0.1%–100%, step 0.1%**, hint「實務建議 ≤25%；拉高觀察 final equity」 |
| min_position | 0.0001 | float input |
| fee | 0.003 | float input |
| atr_period | 20 | int input |

`initial_fund` from the reference sweep signature is **dropped** (documented
unused in the reference docx §9).

Bar is fixed to **1D (UTC daily)** — the reference system is daily-only. The
run form locks the bar selector for turtle; the API rejects other bars (400).
The first `max(enter_term_sys2, atr_period)` days of the range are rolling
warmup with no signals (reference behavior); the form shows a hint.

## Semantics contract (parity quirks preserved deliberately)

1. Entry signal: day `high >` `shift(1)` rolling max of highs over the enter
   window (`min_periods = window`, matching polars `rolling_max(window_size)`).
   Exit signal: day `low <` `shift(1)` rolling min over the leave window, OR
   `close <= stop_loss`.
2. All fills at that day's **close**. Buy cost `close*size*(1+fee)`, sell
   revenue `close*size*(1-fee)`.
3. ATR = rolling mean of true range over `atr_period`, **not shifted** —
   same-day ATR feeds sizing and stops (reference behavior; keep).
4. `unit_size = floor((own_capital*invest_pct/(ATR+close))/min_position)*min_position`.
   `own_capital` is static — no compounding of unit size.
5. Pyramid when `close >= last_add_price + 0.5*ATR`, capped by
   `single_sys_unit_limit` and `both_sys_unit_limit`; stop resets to
   `close - 2*ATR` on every entry/add.
6. Cash gate: entry/add only when `cost < money_in_hand` (strict `<`).
7. S1 has skip-after-winning-trade (`skip_next`); S2 does not.
8. S1 logic is evaluated before S2 within a day; `total_units` interacts
   across systems in that order (order matters — keep).
9. No forced liquidation at range end; final equity includes open position
   value.
10. `equity = money_in_hand + s1_position_value + s2_position_value`;
    `whole_asset = cumulative_profit + position values`; `realized_pnl`
    updates on closes only; a trade wins iff `revenue > total_cost`.
11. Warmup rows (any null among ATR/rolling extremes) are flat and skipped.
12. `mdd = calc_mdd(own_capital + whole_asset, filter_zero=True)` (reference).
13. Sweep validity constraints: `sys1 > leave1`, `sys2 > leave2`,
    `sys2 > sys1`, `leave1 >= 5`, `leave2 >= 5`, `leave2 > leave1`.
14. Reference side effects are **not** ported: no `test.csv` writes, no debug
    prints. Cash-skip events and the equity<0.5 / realized-loss conditions
    become counters in metrics instead of stdout.

## Golden parity fixture (the core acceptance gate)

- `tests/fixtures/turtle/daily_ohlc.csv`: ≥400 rows of real BTC-USDT-SWAP
  daily OHLC (UTC days) exported once from DB canonical candles.
- `tests/fixtures/turtle/expected_default.csv` and `expected_stress.csv`:
  generated **once, offline, in a scratch venv with polars installed**
  (polars is NOT added to project dependencies) by running the reference
  `turtle_trading_system_full` on the fixture with:
  - default set: `(20,55,10,20,4,4,50000.0,0.01, min_position=0.0001, fee=0.003, atr_period=20)`
  - stress set: `(20,55,10,20,4,6,10000.0,0.25, min_position=0.0001, fee=0.003, atr_period=20)`
  Columns pinned: date, equity, money_in_hand, cumulative_profit, s1_units,
  s2_units, s1_position, s2_position, buy_action, sell_action,
  cumulative_win_count, cumulative_loss_count, realized_pnl.
- `tests/unit/test_turtle_backtest.py` asserts the pandas port reproduces the
  expected CSVs (ints/flags exact; floats rtol 1e-9).
- Regeneration steps documented in `docs/GOLDEN_CASES.md` + `docs/RUNBOOK.md`.

## Sweep behavior

- Grid spec: each of the 4 window params is `fixed: <int>` or
  `range: lo~hi[:step]` (reuse the existing token syntax). Optional
  `invest_pct` axis as a percent list/range (e.g. `1~100:1`).
- **invest_pct axis requires all 4 window params fixed** (validation error
  otherwise) — it powers the "拉桿" experiment on a chosen parameter set.
- Caps: ≤5000 valid combos, ≤20000 raw candidates (align with the existing
  sweep constants). Clear 400 errors on violation.
- Per-combo row = reference `index_parameter_result_full.csv` columns
  (win_rate, profit_loss_ratio, expectancy, mdd, final_whole_asset,
  positive_rate, median_asset, mean_asset, s1/s2_return_median/mean,
  s1/s2/overall_max_consec_win/loss, final_win_count, final_loss_count,
  min_equity, min_realized_pnl, final_equity) + `invest_pct` when swept.
- Ranked by `final_equity` for `top_results` (existing panel table renders it).
- Artifacts in `results/turtle_sweeps/<sweep_id>/`:
  - `summary.json` (params, grid, counts, elapsed, artifact names)
  - `rows.csv` (all combos, reference columns)
  - `equity_curves.csv` (long format: invest_pct, date, equity) — only for
    invest_pct-axis sweeps
  - `surface.html` — only when exactly 2 free window params and invest_pct
    fixed (same condition as the reference 3D figure)
- Jobs run through the existing `_sweep_jobs` registry and
  `/sweep/status/{job_id}` endpoints; new
  `GET /sweep/result/{sweep_id}` + `GET /sweep/artifact/{sweep_id}/{name}`
  (allow-listed names only) serve stored results.

## Visualization (user decision: both)

1. **Native heatmaps (dashboard)**: new `Heatmap` SVG component in
   `frontend/charts.js` (no third-party libs), viridis-like scale, hover
   value, click → combo detail. Five small multiples over the 2 free params:
   MDD, Win Rate, Final Equity, Profit/Loss Ratio, Expectancy.
   - Exactly 2 free window params → heatmaps.
   - 1 free param → native line charts (metric vs param).
   - invest_pct axis → line chart `final_equity vs invest_pct` + a slider
     that scrubs the precomputed values, rendering that value's equity curve
     and readouts (final_equity, mdd, min_equity).
2. **Plotly 3D surface artifact**: `surface.html` replicating the reference
   `sweep_params_full.html` layout (2×3 surfaces, 5 metrics), generated from
   a small HTML template embedding the rows JSON and loading
   `<script src="/vendor/plotly.min.js">`. `frontend/vendor/plotly.min.js`
   is vendored (pinned Plotly 2.x, MIT, ~4.6 MB), served by the existing
   static mount, **excluded** from `Makefile` `FRONTEND_JS` / frontend-check
   lists. The dashboard links to the artifact in a new tab.

## Risks

- **Parity drift** pandas vs polars rolling semantics (`min_periods`), float
  summation order → mitigated by the golden fixture with two param sets.
- **Day-boundary mismatch**: DB daily aggregation must be UTC-midnight days to
  match the reference `resample_to_daily`.
- High invest_pct runs mostly hit the cash gate (units skipped); final equity
  vs invest_pct may plateau — that is the honest reference behavior, document
  in the UI hint rather than "fixing".
- `routes_backtest.py` is large; turtle wiring must be additive and must not
  touch replay/daily_winner/rotation paths.
- Vendored plotly adds ~4.6 MB to the repo (user-approved).
- Sweep runtime: ~900-row pure-Python loop per combo ≈ 10–30 ms → 5000 combos
  ≈ 1–3 min; progress updates at least every 2 s.

## Docs impact

- Change Manifest (new research-only PnL/fee/fill accounting surface):
  `docs/change_manifests/2026-07-03-turtle-strategy-runner.md`.
- `docs/FEATURE_MAP.md` new "Turtle Research Backtest" section;
  `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
  `docs/GOLDEN_CASES.md`; `docs/AI_HANDOFF.md` / `docs/CURRENT_STATE.md` /
  `config/workstreams.yaml` at session end.
- No ADR (no existing rule changed; result artifacts follow ADR-0002).

## Open defaults (proceed unless user objects)

- Default symbol BTC-USDT-SWAP; venue = platform primary (canonical DB).
- Sweep caps 5000/20000 as above.
- Turtle metrics tiles show platform-standard total_return / max_drawdown /
  sharpe computed from the daily equity series, plus the turtle metric set.

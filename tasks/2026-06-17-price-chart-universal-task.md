---
status: archived
type: task
owner: claude
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Task (Claude → Codex): Universal price chart + progressive multi-symbol load

> Independent of the multi-venue work (ADR-0007). Open a separate branch.
> Claude wrote this brief; Codex implements. Findings below are leads to verify,
> not a finished diagnosis.

## Task
Make the backtest "Price + Trade Markers" chart render for **every** strategy
(not only MA/EMA/MACD), keep buy/sell markers as before, and load multiple
symbols **progressively** instead of blocking the whole card until all symbols
finish.

## Required behavior
1. **Buy/sell markers as before.** The price chart overlays execution markers
   (buy/sell) for the run, same visual convention as the technical runs have
   today.
2. **Universal price chart.** `daily_winner`, `ohlcv_rotation`, `funding_carry`,
   etc. must show the price+markers chart. (The fast/slow/MACD *indicator
   overlay* lines stay technical-only via `isTechnicalRun` — that gate is
   correct; do not generalize the indicator overlay, only the base price chart.)
3. **Progressive multi-symbol load.** When several symbols are selected, render
   each symbol's price panel as its data arrives. A single pending/missing
   symbol must not freeze the others behind one "Loading price series…" state.

## Findings to verify (save debugging time)
- `frontend/view-backtest.js:946+` "Price + Trade Markers" card is **not** gated
  by `isTechnicalRun`; `isTechnicalRun` (`:828-830`) only gates the indicator
  overlay cards — leave that alone.
- `frontend/view-backtest.js:860-863` `selectedMarketLoading` =
  `effectiveSelectedChartSymbols.some(sym => status unset || "loading")` →
  **any** pending symbol sets `marketLoading=true`, which renders the whole-card
  "Loading price series…" at `:955-956`. This is the all-or-nothing behavior to
  replace with per-symbol panel states (loading / loaded / error / empty).
- `priceChartSymbols` (`:857-859`) requires `filteredPriceSeries` rows for a
  symbol; verify why a non-technical run yields none — check where
  `marketSymbolStatus` and the price-series fetch are wired (the load effect),
  and whether the fetch is skipped for non-technical runs.
- Backend already has a fallback: `routes_backtest.get_price_series` (`:2670`)
  + `_fallback_price_series_from_result` (`:1416`) reconstruct price series from
  `result.json` when `price_series.csv` is absent. New `_run_daily_winner_job`
  (`:735`) and `_run_ohlcv_rotation_job` (`:452`) now write `price_series.csv`;
  **older** `ui_daily_winner_*` / `ui_ohlcv_rotation_*` runs do not — confirm
  the fallback covers them, or scope the fix to runs that have the artifact.

## PERMITTED FILES
- `frontend/view-backtest.js`, `frontend/charts.js` (chart/loading/marker render)
- `frontend/data.js` (per-symbol fetch, if streaming needs it)
- `src/okx_quant/api/routes_backtest.py` (only if the price-series/fallback
  route needs to serve non-technical runs or per-symbol streaming)

## FORBIDDEN (do not touch)
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`
- `backtesting/differential_validation.py` and ct_val provenance gate (owned by
  the ADR-0007 multi-venue branch — see AI_HANDOFF sequencing note)
- existing `results/**` artifacts; `config/risk.yaml`

## SCOPE LIMIT
Fix only the price-chart visibility + progressive load + markers. Do not
refactor unrelated chart/zoom code. Do not change the indicator-overlay gating.

## REQUIRED ON COMPLETION
- List changed files; run `node --check frontend/view-backtest.js`
  (+ `frontend/charts.js`, `frontend/data.js`) and any frontend MIME/API test.
- Update `docs/UI_MAP.md` (chart behavior) and `docs/KNOWN_ISSUES.md`.
- Commit with `AI-Origin: Codex` trailer.

## ACCEPTANCE CRITERIA
- [ ] A `daily_winner` (or `ohlcv_rotation`) run shows the price+markers chart
      with buy/sell markers.
- [ ] Selecting N symbols renders each panel as it loads; one slow/empty symbol
      does not block the rest.
- [ ] A symbol with genuinely no price data shows a per-panel empty/error state,
      not a permanent whole-card "Loading…".
- [ ] MA/EMA/MACD runs still show price chart **and** indicator overlays
      (no regression).

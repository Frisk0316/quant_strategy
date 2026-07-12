---
status: current
type: manual
owner: human
created: 2026-06-25
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Frontend views

`docs/UI_MAP.md` is the maintainer map. This chapter is the user-facing map of
what each dashboard view is for. Dashboard views are inspection surfaces; they
do not by themselves satisfy any deployment gate.

| View | Purpose | Main data/API |
| --- | --- | --- |
| Run Backtest | Configure replay/daily-winner/OHLCV-rotation jobs and inspect available market context | `/api/backtest/run`, `/api/data/coverage`, `/api/data/external-series` |
| Backtest Runs | Review run summaries, metrics, charts, signals, fills, trades, and risk events | `/api/backtest/*` |
| Validation Lab | Run or inspect validation artifacts and source-data checks | validation API endpoints |
| Compare Runs | Compare saved run metrics and artifacts | backtest artifact summaries |
| Metrics Glossary | Read metric definitions used by result cards | static frontend glossary |
| Progress | Read-only workstream milestone panel | `/api/progress` |
| Risk Monitor | Offline/live risk inspection surface; not a live-readiness claim | live/risk API endpoints |
| User Manual | Manifest-driven markdown manual chapters | `/api/manual` |

## Market Data Coverage

The Market Data Coverage card shows OHLCV, funding, and external observation
rows stored in TimescaleDB. The Exchange filter is derived from the row's data
source: external datasets use their provider label, with Binance Vision rows
shown as `binance` and Deribit rows shown as `deribit`.

The export panel can export OHLCV, funding, or external datasets. External export
uses the DB export endpoint after an optional best-effort refresh pre-step.
Only selected yfinance datasets are refreshed on demand. Deribit, Binance Vision
OI, and other DB-only selections export existing rows directly and show
`Using existing DB rows`; they are not reported as skipped.

## Derivatives context

The Run Backtest page includes a Derivatives context card next to Market Data
Coverage. It is display-only and does not write backtest artifacts.

- Dataset dropdown: built from external coverage rows, with Deribit datasets
  ordered first.
- Date range: UTC `Start` / `End` date inputs.
- Data path: `GET /api/data/external-series?dataset_id=...&start=...&end=...`.
- Chart: existing `window.Charts.LineChart`, downsampled by the API above 5,000
  numeric points.

Use this card to visually inspect Deribit DVOL, funding, option-flow, and
option-surface context before research review. Unknown dataset ids return 404
from the API.

## UI rules of thumb

- API shape issues should be traced through the backend route before changing
  frontend defaults.
- Progress is read-only and does not inspect git or DB state.
- Manual chapters are declared in `docs/manual/manual.json`.

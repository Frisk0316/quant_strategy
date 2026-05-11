# ADR-0002: Backtest Result Schema

## Status

Accepted — 2026-05-11

## Context

The frontend (`frontend/view-backtest.js`, `frontend/charts.js`) and API (`src/okx_quant/api/routes_backtest.py`) both consume backtest results. If the result schema changes without coordination, the frontend breaks silently (missing fields render as empty charts, not errors).

The schema is defined implicitly by `backtesting/artifacts.py` column constants (`FILL_COLUMNS`, `TRADE_COLUMNS`, etc.) and the `result.json` top-level structure.

## Decision

The following fields are **frozen** — they may not be removed, renamed, or have their type changed without a matching frontend update and schema version bump:

### `result.json` top-level

```json
{
  "run_id": "string",
  "created_at": "ISO-8601",
  "strategies": ["string"],
  "symbols": ["string"],
  "bar": "string",
  "start": "string",
  "end": "string",
  "metrics": { ... },
  "artifacts": { ... }
}
```

### `metrics` required keys

`total_return`, `sharpe`, `max_drawdown`, `profit_factor`, `order_count`, `fill_rate`, `bankrupt`

### `trades.csv` / `/api/backtest/{run_id}/trades` required columns

`ts`, `datetime`, `inst_id`, `side`, `fill_px`, `fill_sz`, `fee`, `realized_pnl`, `net_realized_pnl`, `size_before`, `size_after`, `equity_after`

### `fills.csv` / `/api/backtest/{run_id}/fills` required columns

`ts`, `datetime`, `inst_id`, `side`, `fill_px`, `fill_sz`, `fee`, `state`, `ct_val`

### `equity_curve.csv` / `/api/backtest/{run_id}/equity` required columns

`ts`, `datetime`, `equity`, `drawdown`, `return`

## Consequences

- Any PR that touches `backtesting/artifacts.py` column constants must be reviewed for schema breakage
- New fields may be added (additive changes are safe)
- Removing or renaming a field requires a coordinated change to `routes_backtest.py` and frontend
- A regression test (`tests/unit/test_backtesting.py`) should assert that a minimal replay produces all required fields

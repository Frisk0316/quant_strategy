---
status: accepted
type: adr
owner: human
created: 2026-05-11
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# ADR-0005: Replay Validation Gates

## Status

Accepted - 2026-05-13

## Context

Historical backtest results are only meaningful if the replay engine correctly models execution, fills, and position accounting. Several failure modes produce plausible-looking but incorrect results:

1. **Terminal position leak** - strategy holds open positions at the end of the replay period. If `liquidate_on_end=False`, unrealized PnL is excluded from the summary, making results look better than they are.
2. **Orphan hedge positions** - pairs trading exit closes the main leg but leaves the hedge leg open, creating phantom risk. This was addressed in PR10B at the strategy signal level; no replay validation gate is needed because the portfolio manager handles linked hedge closes automatically.
3. **Missed funding settlements** - replay period does not span a full 8h settlement window, so funding income is understated.
4. **No fills at all** - order latency plus cancel latency exceeds bar duration, so every order expires unfilled. Equity curve is flat but the run completes without error.

## Implementation Status

Implemented in PR12B and PR13.

- Gate 1 terminal position check is implemented via terminal liquidation and `validation["terminal_positions_closed"]`.
- Gate 2 fill-rate warning is implemented via `validation["gate2_fill_rate_warning"]`.
- Gate 3 data coverage is implemented via `validation["gate3_data_coverage"]` and raises when coverage is below 80%.
- Gate 4 funding coverage warning is implemented via `validation["gate4_funding_coverage_warning"]`.

## Decision

The following validation gates are enforced for replay backtests:

### Gate 1: Terminal Position Check

If `liquidate_on_end=True`, the default for backtesting:

- After the final bar, `ReplayBacktestEngine._liquidate_terminal_positions()` generates terminal liquidation fills for all open positions at the last available mid price.
- `PositionLedger` must show zero positions after terminal liquidation.
- If any position remains non-zero, the run is flagged `bankrupt=True` in metrics.

### Gate 2: Fill Rate Warning

If `fill_rate < 0.05` and `submitted_order_count > 0`, the run logs a warning. Zero-order runs are not flagged.

Example:

```text
WARNING: Gate 2: fill_rate={fill_rate:.1%} - check order_latency_ms and cancel_latency_ms in config/risk.yaml
```

### Gate 3: Minimum Data Coverage

Gate 3 writes coverage to `result.json` under `validation.gate3_data_coverage`.

Coverage is computed only when both `start` and `end` are provided. If either is absent, the gate is skipped with:

```json
{"coverage_pct": 1.0, "note": "no_range_specified"}
```

When a date range is provided, coverage is calculated per symbol as:

```text
actual_bars / expected_bars
```

The overall coverage is the minimum per-symbol coverage. A replay with one symbol at 95% coverage and another at 79% coverage fails at 79%.

If overall coverage is below 80%, the run raises `ValueError` before the replay engine starts.

### Gate 4: Funding Coverage

For `funding_carry` replays, `result.metrics["funding_settlement_count"]` must be greater than zero. If it is zero, a warning is logged: the strategy may have entered but never collected funding.

`funding_settlement_count` aggregates settlements across all symbols in the replay. In mixed-strategy runs, a non-zero count from another SWAP can mask zero FundingCarry settlements. Per-strategy settlement counts are a future enhancement, not part of this ADR.

## Consequences

- `liquidate_on_end=True` is the default for all backtesting runs. Set `False` only when deliberately testing mid-period snapshots.
- Validation results appear in `result.json` under the `"validation"` key.
- The `/api/backtest/{run_id}/walk-forward` and `/cpcv` endpoints expose per-window validation.
- These gates do not guarantee the strategy is profitable; they only verify the simulation mechanics are working.
- Any change to terminal liquidation logic requires the regression tests in `tests/unit/test_backtesting.py` and `tests/integration/test_oracle_correctness.py` to pass.

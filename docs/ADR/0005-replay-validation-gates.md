# ADR-0005: Replay Validation Gates

## Status

Accepted — 2026-05-11

## Context

Historical backtest results are only meaningful if the replay engine correctly models execution, fills, and position accounting. Several failure modes produce plausible-looking but incorrect results:

1. **Terminal position leak** — strategy holds open positions at the end of the replay period. If `liquidate_on_end=False`, unrealized PnL is excluded from the summary, making results look better than they are.
2. **Orphan hedge positions** — pairs trading exit closes the main leg but leaves the hedge leg open, creating phantom risk.
3. **Missed funding settlements** — replay period doesn't span a full 8h settlement window, so funding income is understated.
4. **No fills at all** — order latency + cancel latency exceeds bar duration, so every order expires unfilled. Equity curve is flat but the run completes without error.

## Decision

The following validation gates are enforced in `backtesting/replay.py` and checked by `scripts/run_replay_backtest.py`:

### Gate 1: Terminal position check

If `liquidate_on_end=True` (default for backtesting):
- After the final bar, `ReplayExecutionModel` generates terminal liquidation fills for all open positions at the last available mid price
- `PositionLedger` must show zero positions after terminal liquidation
- If any position remains non-zero, the run is flagged `bankrupt=True` in metrics

### Gate 2: Fill rate warning

If `fill_rate < 0.05` (less than 5% of submitted orders filled), the run logs a warning:
```
WARNING: fill_rate={fill_rate:.1%} — check order_latency_ms and cancel_latency_ms in config/risk.yaml
```

### Gate 3: Minimum data coverage

`data_coverage.json` must show that the replay period is covered by actual candle data. If coverage < 80% of requested bars, the run fails with an explicit error.

### Gate 4: Funding coverage (funding_carry only)

For `FundingCarryStrategy` replays, `funding_log` must contain at least one settlement event. If zero funding rows are present, a warning is logged: strategy may have entered but never collected funding.

## Consequences

- `liquidate_on_end=True` is the default for all backtesting runs. Set `False` only when deliberately testing mid-period snapshots.
- Validation results appear in `result.json` under the `"validation"` key
- The `/api/backtest/{run_id}/walk-forward` and `/cpcv` endpoints expose per-window validation
- These gates do not guarantee the strategy is profitable — they only verify the simulation mechanics are working
- Any change to terminal liquidation logic requires the regression test in `tests/integration/test_replay_engine.py` to pass

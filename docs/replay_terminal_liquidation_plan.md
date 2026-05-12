---
status: proposed
type: design
owner: codex
created: 2026-05-12
last_reviewed: 2026-05-12
expires: none
superseded_by: null
---

# Replay Terminal Liquidation Plan

## Purpose

This document defines PR12B implementation scope for terminal liquidation in the replay backtest engine.

It is a proposed design, not current implementation authority. ADR-0005 remains proposed until the replay validation gates are implemented and tested.

## Problem

Replay backtests can finish while `PositionLedger` still contains open positions. If the run summary relies only on realized PnL and the final equity sample was recorded before the final mark or close, results can look valid while carrying hidden terminal exposure.

This is most dangerous for:

- funding carry, where a perp or spot leg can remain open after the replay window;
- pairs trading, where one leg can close while the hedge leg remains open;
- market making, where resting inventory can remain at the final bar.

ADR-0005 defines the target gate:

- `liquidate_on_end=True` is the default for backtesting;
- open positions are closed at the last available mid price after the final bar;
- `PositionLedger` must be flat after terminal liquidation;
- residual positions or missing prices flag the run as `bankrupt=True`.

## Current Implementation Notes

The existing replay stack already has most required building blocks:

- `ReplayBacktestEngine.run()` owns the final `PositionLedger`, `ReplayRecorder`, and `ReplayExecutionModel`.
- `ReplayExecutionModel.books` stores the latest bid/ask snapshot per instrument.
- `PositionLedger.on_fill()` can close positions, compute realized PnL, update equity, and write trade log rows.
- `ReplayRecorder.record_fill()` and `record_equity()` already write fill and equity artifacts.
- `ReplayBacktestResult` does not yet expose a dedicated validation field.
- `scripts/run_replay_backtest.py` does not yet expose `--liquidate-on-end` / `--no-liquidate-on-end`.

The missing piece is an explicit terminal phase between the feed loop and `recorder.build_result()`.

## PR12B Scope

PR12B should implement only terminal liquidation and the minimal validation surface needed to verify it.

Permitted implementation files should be limited to:

- `backtesting/replay.py`
- `scripts/run_replay_backtest.py`
- `src/okx_quant/core/config.py` if a `BacktestConfig.liquidate_on_end` field is added
- focused tests under `tests/unit/` or `tests/integration/`
- `docs/AI_HANDOFF.md`

PR12B should not change strategy logic, risk limits, config YAML values, frontend code, artifact schema beyond additive fields, or live execution behavior.

## Desired Behavior

### Default Mode

Replay backtests default to:

```text
liquidate_on_end = true
```

At the end of `ReplayBacktestEngine.run()`:

1. Drain the bus after the final historical event.
2. Snapshot all open positions from `PositionLedger.get_all_positions()`.
3. Cancel or ignore any remaining resting replay orders.
4. For each open position, create a synthetic terminal fill:
   - long position: `side="sell"`;
   - short position: `side="buy"`;
   - `fill_sz=abs(position.size)`;
   - `fill_px=last_mid_price(inst_id)`;
   - `strategy=position.strategy or "terminal_liquidation"`;
   - `state="filled"`;
   - metadata includes terminal liquidation markers.
5. Apply the fill through `PositionLedger.on_fill()`.
6. Record the fill in `ReplayRecorder.fill_log`.
7. Record a final equity sample after all terminal fills.
8. Build the result only after the ledger is flat.

### Disabled Mode

When explicitly disabled:

```text
liquidate_on_end = false
```

The engine should not create terminal fills. It should still report terminal open positions in validation data and metrics so the run is visibly a mid-period snapshot, not a fully realized backtest.

## Price Selection

Terminal liquidation must use the last available mid price for each instrument:

```text
mid = (best_bid + best_ask) / 2
```

Source priority:

1. Latest book stored in `ReplayExecutionModel.books[inst_id]`.
2. `Position.last_price` only as an explicit fallback, with validation warning.
3. If neither is available, do not silently close. Flag validation failure and set `metrics["bankrupt"] = True`.

Do not use `SignalPayload.fair_value` for terminal liquidation.

## Fee And Metadata

Terminal fills should be conservative. Use a taker-style fee rate if available; otherwise use a documented constant in replay code.

Recommended metadata:

```python
{
    "action": "terminal_liquidation",
    "liquidate_on_end": True,
    "execution_model": "terminal_liquidation",
    "terminal_price_source": "last_mid",
    "ct_val": ct_val,
    "fee_rate": fee_rate,
}
```

The fill should not be submitted through normal post-only order placement. Terminal liquidation is a replay accounting close, not a maker order simulation.

## Validation Surface

Add an additive validation object to `ReplayBacktestResult` or a result-ready structure emitted by `ReplayRecorder`.

Recommended keys:

```python
{
    "liquidate_on_end": True,
    "terminal_positions_before": {...},
    "terminal_positions_after": {...},
    "terminal_liquidation_fill_count": 0,
    "terminal_liquidation_notional_usd": 0.0,
    "terminal_liquidation_missing_prices": [],
    "terminal_liquidation_price_fallbacks": [],
    "terminal_positions_closed": True,
}
```

Additive metrics should include:

- `bankrupt`
- `terminal_open_position_count`
- `terminal_liquidation_fill_count`
- `terminal_liquidation_notional_usd`

`bankrupt=True` means replay mechanics failed or ended with unresolved exposure. It does not mean the exchange account necessarily went bankrupt.

## CLI Contract

Add explicit replay CLI flags:

```text
--liquidate-on-end
--no-liquidate-on-end
```

Default behavior should preserve ADR-0005:

```text
--liquidate-on-end is true unless explicitly disabled
```

If `BacktestConfig` gains a `liquidate_on_end` field, CLI flags override config for that run.

## Artifact Contract

Any artifact changes must be additive.

Do not remove or rename existing frozen result fields from ADR-0002. If `result.json` gains a new `"validation"` object, existing frontend consumers must continue to work when the key is absent or present.

Terminal liquidation fills should appear in:

- `fills.csv`
- `trades.csv`
- `equity_curve.csv`
- `result.json` metrics and validation fields

## Required Tests For PR12B

Minimum regression coverage:

1. `test_replay_terminal_liquidation_closes_open_swap_position`
   - Open a swap position during replay.
   - End the replay with `liquidate_on_end=True`.
   - Assert final positions are flat.
   - Assert terminal fill exists with `action="terminal_liquidation"`.
   - Assert realized PnL uses `ct_val`.

2. `test_replay_terminal_liquidation_can_be_disabled`
   - Same setup with `liquidate_on_end=False`.
   - Assert no terminal fill exists.
   - Assert validation reports open terminal position.

3. `test_replay_terminal_liquidation_flags_missing_price`
   - Leave a position open without a usable final book or last price.
   - Assert no silent close occurs.
   - Assert `metrics["bankrupt"] is True`.

4. `test_replay_terminal_liquidation_closes_multiple_legs`
   - Use funding carry or pairs-like positions.
   - Assert all legs close and no orphan position remains.

5. CLI smoke test
   - Verify `scripts/run_replay_backtest.py --no-liquidate-on-end` reaches `run_replay_backtest()` with liquidation disabled.

## Non-Goals

PR12B should not implement all ADR-0005 validation gates.

Out of scope:

- fill-rate warning gate;
- minimum data coverage gate;
- funding coverage warning gate;
- frontend display changes;
- position-aware close sizing for strategy exit/stop flows;
- live or demo terminal liquidation behavior;
- changing strategy entry/exit logic.

## Acceptance Criteria

- Replay default closes all terminal open positions.
- Terminal liquidation uses last available mid price.
- Terminal liquidation fills are visible in fill and trade artifacts.
- Result metrics include terminal liquidation counts and `bankrupt`.
- Missing liquidation price does not silently pass.
- `--no-liquidate-on-end` deliberately preserves terminal open positions and reports them.
- Existing unit tests and ruff pass.
- ADR-0005 remains proposed until PR13 implements the rest of the validation gates.

## Implementation Specification Addendum

These notes must be applied before handing PR12B to Codex for implementation.

### Price source correction

Terminal liquidation price comes from the `books` dict inside `ReplayBacktestEngine.run()`, not from `execution_model.books`.

Pass `books` to the terminal phase via argument or closure. This avoids depending on the execution model's internal book cache, which may not represent the same object shape as `OkxBook`.

### SWAP notional formula

`terminal_liquidation_notional_usd` must use contract value for swaps and raw quantity for spot:

```python
terminal_liquidation_notional_usd = (
    sum(abs(pos.size) * ct_val * liquidation_price for SWAP)
    + sum(abs(pos.size) * liquidation_price for spot)
)
```

`ct_val` comes from `self._instrument_specs[inst_id]["ctVal"]` for SWAP instruments.

### List element schemas

`terminal_liquidation_missing_prices` elements:

```python
{"inst_id": str, "reason": str}
```

`terminal_liquidation_price_fallbacks` elements:

```python
{"inst_id": str, "source": str, "price": float}
```

### Bankrupt field in all runs

`bankrupt` must be present in metrics for every run:

```python
bankrupt = (
    len(terminal_liquidation_missing_prices) > 0
    or terminal_positions_after != {}
)
```

When `liquidate_on_end=False`, `bankrupt=False` because no terminal close was attempted.

### Test coverage notes

| Test | Covered gap | Status |
|---|---|---|
| T1: SWAP position closes flat and PnL uses `ct_val` | Gap 1, partially | Must also assert the `terminal_liquidation_notional_usd` formula. |
| T2: disabled mode keeps open position in validation | Gap 4 | Covered by required tests. |
| T3: missing price sets `bankrupt=True` | Gap 4 | Covered by required tests. |
| T4: multi-leg liquidation closes all positions flat | Orphan position risk | Covered by required tests. |
| T5: CLI smoke test | CLI contract | Covered by required tests. |

Additional assertions required in PR12B:

- `terminal_positions_before` and `terminal_positions_after` use stable dict schemas.
- `terminal_liquidation_missing_prices` and `terminal_liquidation_price_fallbacks` use the list element schemas above.
- `metrics["bankrupt"]` exists on every replay result, including runs with no open terminal positions.

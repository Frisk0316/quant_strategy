---
status: proposed
type: design
owner: codex
created: 2026-05-13
last_reviewed: 2026-05-13
expires: none
superseded_by: null
---

# Pairs Position-Aware Close Sizing Plan

## Purpose

Define the implementation scope for making pairs trading exit and stop orders
close the current ledger position size instead of reusing entry signal sizing.

This is a sizing correctness fix. It should not change pairs entry rules,
Kalman/OU parameters, risk limits, or maker-only order routing.

## Current Behavior

`PairsTradingStrategy` emits `SignalPayload` for entry, exit, and stop flows.
`PortfolioManager.on_signal()` converts each signal into one or more
`OrderPayload`s.

For directional signals, PM currently computes a fresh `size_usd` from signal
strength, risk multiplier, volatility targeting or fixed-fractional fallback,
then calls `_compute_order_quantity()`.

That behavior is correct for entries, but wrong for closes:

- exit strength depends on z-score convergence, not open position size;
- stop strength is `1.0`, but still maps through current risk sizing;
- partial fills, manual intervention, terminal liquidation, or prior sizing
  changes can make the current ledger position differ from fresh signal sizing;
- linked hedge close orders need to close their own current ledger leg, not a
  beta-scaled copy of the main close notional.

## Design Decision

Position-aware close sizing belongs in `PortfolioManager`, not in
`PairsTradingStrategy`.

Reason: PM owns `PositionLedger`, instrument specs, current mids, order
quantity rounding, and risk check context. Strategy should continue to describe
intent: entry, exit, stop, side, fair value, and linked hedge metadata.

## Required Behavior

When `sig.metadata["action"]` is `exit` or `stop`:

1. The main leg order size is derived from the current ledger position for
   `sig.inst_id`.
2. A close order is emitted only if the requested side reduces the current
   position:
   - long position (`pos.size > 0`) closes with `sell`;
   - short position (`pos.size < 0`) closes with `buy`.
3. The close quantity equals `abs(pos.size)`, rounded/formatted according to
   the existing instrument `lotSz` formatting rules.
4. `notional_usd` is computed from `abs(pos.size) * price * ctVal`.
5. If there is no current position, PM emits no close order.
6. If side does not reduce the position, PM emits no close order and logs a
   warning.
7. Linked hedge closes use the hedge leg's own current ledger position size.
   Do not multiply the main close size by beta for exit/stop.
8. Entry behavior remains unchanged: entry signals still use risk and signal
   sizing.

## Metadata Contract

Pairs exit/stop signals must include enough metadata for PM to close both legs:

```python
{
    "action": "exit" | "stop",
    "hedge_inst_id": "...",
    "hedge_side": "buy" | "sell",
    "beta": ...,
}
```

Implementation PR should first verify this contract with regression tests.
If current strategy code is missing `hedge_inst_id` or `hedge_side` on exit/stop,
restore that metadata in the same PR before changing PM sizing.

## Implementation Sketch

Add PM helpers:

```python
def _is_close_action(sig: SignalPayload) -> bool:
    return (sig.metadata or {}).get("action") in {"exit", "stop"}

def _is_reducing_side(pos_size: float, side: str) -> bool:
    return (pos_size > 0 and side == "sell") or (pos_size < 0 and side == "buy")

def _position_close_quantity(inst_id: str, side: str, price: float) -> tuple[str, float]:
    pos = self._positions.get_position(inst_id)
    if not _is_reducing_side(pos.size, side):
        return "", 0.0
    ct_val = validate_ct_val(...)
    lot_sz = ...
    qty = abs(pos.size)
    return self._format_size(qty, lot_sz), qty * price * ct_val
```

Then update `_place_directional()`:

- for close actions, use `_position_close_quantity()`;
- for non-close actions, keep `_compute_order_quantity()` unchanged;
- keep existing risk behavior where reducing orders pass `check_notional = 0.0`.

Update `_place_linked_hedges()`:

- if action is `exit` or `stop`, call `_place_directional()` for the hedge leg
  with close-action metadata and let hedge quantity come from that hedge
  position;
- if action is `entry`, keep the current beta-scaled notional behavior.

## Test Plan

Focused unit tests should use synthetic positions and no network or filesystem
I/O.

1. Main close sizes from ledger:
   - open long `ETH-USDT-SWAP` size `3`;
   - emit pairs exit sell signal;
   - assert order `sz == "3"` and not a risk-derived quantity.

2. Short close side:
   - open short `ETH-USDT-SWAP` size `-2`;
   - emit stop buy signal;
   - assert order `sz == "2"`.

3. No position means no close:
   - emit exit signal with no ledger position;
   - assert no `ORDER` event.

4. Wrong-side close is rejected:
   - open long but emit buy exit;
   - assert no `ORDER` event and warning logged.

5. Hedge close sizes from hedge ledger position:
   - main leg size and hedge leg size intentionally differ;
   - emit exit/stop with hedge metadata;
   - assert main and hedge orders use their own ledger sizes.

6. Entry behavior unchanged:
   - emit entry with hedge metadata;
   - assert existing beta-scaled hedge notional path still applies.

7. Existing regression coverage remains:
   - pairs hedge metadata tests;
   - funding carry dual-leg tests;
   - replay terminal liquidation tests.

## Non-Goals

- Do not change pairs entry rules or OU/Kalman parameters.
- Do not change `RiskGuard` limits.
- Do not change `PositionLedger` PnL semantics.
- Do not introduce market orders; orders remain `post_only`.
- Do not solve generic close sizing for all strategies until pairs behavior is
  proven.

## Acceptance Criteria

- Exit/stop orders close current ledger quantities for both pairs legs.
- Entry sizing is unchanged.
- Linked hedge exits/stops close the hedge leg by hedge ledger size, not beta
  notional.
- No order is emitted for absent or non-reducing positions.
- Regression tests cover main leg, hedge leg, no-position, wrong-side, and
  entry unchanged cases.
- `docs/AI_HANDOFF.md` moves this design to complete and lists implementation as
  the next PR.

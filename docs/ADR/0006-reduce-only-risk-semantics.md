# ADR-0006: Reduce-Only Risk Semantics

## Status

Proposed - 2026-05-19, pending Claude re-review and human merge approval

## Context

Long/flat technical strategies need a safe way to close existing exposure after
partial fills. The portfolio manager can mark a close order as `reduce_only`
when the order side reduces the current ledger position. That order should be
treated differently from a new exposure-increasing order, but it must not bypass
all risk controls blindly.

The immediate trigger was a MA/MACD replay bug: partial sell fills could leave
the strategy and ledger out of sync, later creating non-intended exposure and
position-limit blocks. The fix scopes reduce-only close sizing to long/flat
technical exits only. Pairs and funding-carry close sizing remain unchanged
until their separate design work is approved.

## Decision

For this patch:

1. `reduce_only=True` is assigned only by the long/flat technical exit close
   branch in `PortfolioManager`.
2. Reduce-only orders may bypass the fat-finger max-order-notional gate only up
   to the current position notional. A close order larger than the current
   position is blocked.
3. Reduce-only orders may bypass position-limit increase checks because their
   intent is to lower exposure, not add it.
4. Reduce-only orders may pass while the kill switch, hard drawdown stop, or
   daily-loss hard stop is active so the system can close risk.
5. Replay records allowed reduce-only bypasses as risk events with reason
   `allowed_reduce_only_bypass:<reason>` so the behavior is auditable in
   artifacts. Multiple bypass causes are joined with `+`, for example
   `allowed_reduce_only_bypass:kill_switch+position_limit`.
6. Stale quote checks still apply to reduce-only orders.

## Non-Goals

- This ADR does not approve generic position-aware close sizing for all
  strategies.
- This ADR does not implement the P2 pairs close-sizing plan.
- This ADR does not change `config/risk.yaml` thresholds.
- This ADR does not claim MA/MACD are live-ready.

## Consequences

- A correct long/flat exit can close when a stale position is already over a
  position-limit threshold or when a stop state has been triggered.
- A valid close order can flatten an existing position even when price movement
  makes the close notional exceed the single-order entry cap.
- A malformed close order above current position notional is still blocked by
  fat-finger protection.
- Replay artifacts gain an audit trail for allowed reduce-only bypasses in
  `risk_events.csv`.
- Live/shadow execution logs allowed reduce-only bypasses from the shared
  `RiskGuard.check()` path with the same joined reason format.
- Live/shadow promotion still requires the usual gates, including ctVal
  provenance, OOS/WF/CPCV review, explicit human approval, and a shadow-period
  audit sample showing any reduce-only bypass events for reviewer inspection.

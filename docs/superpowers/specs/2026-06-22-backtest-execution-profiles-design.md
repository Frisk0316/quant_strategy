---
status: proposed
type: design
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Backtest Execution Profiles Design

## Problem

Current replay results mix two different questions:

1. Did the strategy make money if its signals became positions?
2. Would the current maker-only execution model actually fill those orders?

For MACD on BTC-USDT-SWAP / Binance / 1H, realistic replay produced 779 orders
but only 13 fill rows because queue allocation, lot/min rounding, cancellation,
and terminal liquidation dominated the run. That is useful execution evidence,
but it is a poor default answer for strategy research.

## Constraints

- Do not weaken live, shadow, demo, or promotion gates.
- Do not edit historical result artifacts.
- Keep strategy code unchanged.
- Preserve the existing realistic maker replay as an execution stress mode.
- `strategy_fill` output is research-only and must remain excluded from
  promotion evidence.
- Avoid a new matching engine. The existing `fill_all_signals` /
  `fill_all_on_submit` path already covers the first useful version.

## User-Facing Choice

The Run Backtest UI and scripts should expose only two user choices:

| Choice | Purpose | Output |
|---|---|---|
| Strategy Fill | Study signal-to-position strategy performance without maker queue/cancel/lot limits blocking fills | One run using `execution_profile = "strategy_fill"` |
| Dual Output | Compare strategy potential against realistic execution friction | Two paired runs: `strategy_fill` and `realistic_execution`, plus a small comparison summary |

No standalone "realistic only" option is needed in the new user-facing control.
It remains available internally because Dual Output uses it.

## Execution Semantics

### `strategy_fill`

Use the existing research-only immediate-fill path:

- Enable full fills on submitted signal orders.
- Set order and cancel latency to zero.
- Set queue fill fraction to 1.0.
- Lift research-only caps that block signal-to-order conversion, as current
  `fill_all_signals` does.
- Fill at the order price / signal fair value used by the current replay path.
- Mark artifacts with `idealized_fill = true` and
  `execution_profile = "strategy_fill"`.

This answers: "If the strategy's signal becomes a position, what happens?"

### `realistic_execution`

Keep the current maker replay:

- Post-only resting orders.
- Queue fill fraction.
- Cancel latency.
- Lot/min rounding.
- Post-only crossing rejection.
- Terminal liquidation behavior.

Mark artifacts with `execution_profile = "realistic_execution"`.

This answers: "How much of the strategy survives this execution model?"

### `dual_output`

Run both profiles using the same strategy, symbols, data window, bar, exchange,
and strategy parameters.

Write:

- `<base_run_id>_strategy_fill`
- `<base_run_id>_realistic_execution`
- `<base_run_id>_execution_comparison.json`

The comparison JSON should stay small:

- `signal_count`
- `submitted_order_count`
- `real_fill_count`
- `submitted_order_fill_count`, excluding terminal liquidation
- `terminal_liquidation_fill_count`
- `fill_rate`
- `total_return`
- `max_drawdown`
- `strategy_minus_realistic_return`
- `strategy_minus_realistic_fill_rate`

## Artifact And Validation Rules

- `strategy_fill` artifacts are research-only upper-bound evidence.
- `realistic_execution` artifacts are execution-model stress evidence, not
  live-readiness evidence by themselves.
- Dual Output comparison is diagnostic evidence, not promotion evidence.
- Promotion review may cite the realistic side only after the normal source,
  validation, WF/CPCV, shadow/demo, and human approval gates pass.
- Existing `fill_all_signals` should be treated as the implementation mechanism,
  but the user-facing name should become `Strategy Fill`.

## API / UI Shape

Smallest useful API field:

```json
{
  "execution_profile": "strategy_fill"
}
```

Allowed values:

- `"strategy_fill"`
- `"dual_output"`

Implementation may keep internal `"realistic_execution"` for paired runs, but
the public picker should only show the two user choices above.

UI copy should be short:

- Strategy Fill: "Evaluate the strategy after signals become fills."
- Dual Output: "Run Strategy Fill and realistic execution side by side."

## Options Considered

### Option A - First-class profiles over existing fill-all path

Rename and expose the existing research control as `strategy_fill`, then add a
dual-run wrapper. This is the recommended path.

Why:

- Smallest diff.
- Fixes the current user confusion.
- Keeps realistic execution intact.
- Avoids inventing a new fill model before shadow/demo calibration data exists.

### Option B - New touch-aware bar fill model

Add a separate engine that fills if OHLC high/low touches an order price.

Why not now:

- Current replay `price_series` is close-derived, not true intrabar book data.
- Bar high/low touch can create optimistic lookahead if not designed carefully.
- Larger blast radius than needed to solve the user's problem.

### Option C - Replace realistic replay default

Make all backtests immediate fill and remove realistic replay from the main path.

Why not:

- Loses useful execution stress evidence.
- Makes it harder to explain shadow/demo gaps later.

## Locate-Before-Edit For Implementation

User-facing behavior:

- Backtest run mode selection and artifact interpretation.

Owning files likely affected:

- `backtesting/research_controls.py`
- `backtesting/replay.py`
- `backtesting/artifacts.py`
- `scripts/run_replay_backtest.py`
- `scripts/run_validation_lab_signal_order_check.py`
- `src/okx_quant/api/routes_backtest.py`
- `frontend/view-config.js`
- `frontend/data.js`
- `docs/UI_MAP.md`
- `docs/DATA_FLOW.md`
- `docs/FEATURE_MAP.md`
- `docs/DOMAIN_RULES.md`
- `docs/INVARIANTS.md`
- `docs/ai_collaboration.md`

Forbidden unless separately approved:

- `src/okx_quant/strategies/`
- Live / shadow / demo mode switches.
- Existing result artifact migration.
- DB schema changes.

Doc Sync impact:

- Implementation will touch backtesting/API/UI and validation semantics.
- A Change Manifest is required because fill and validation semantics affect
  research conclusions.
- ADR-0005 / ADR-0002 review may be needed if artifact schema or gate language
  changes beyond additive metadata.

## Tests

Smallest useful checks:

1. Unit: `strategy_fill` profile sets the same controls as current
   `fill_all_signals` and records `execution_profile = "strategy_fill"`.
2. Unit/integration: `dual_output` creates two result artifacts and one
   comparison JSON.
3. Unit: terminal liquidation is excluded from
   `submitted_order_fill_count`.
4. Frontend static/API test: only two public picker values are accepted.
5. Docs check: metadata, feature-map links, doc-impact advisory.

## Acceptance Criteria

- User can choose Strategy Fill or Dual Output from the backtest entrypoint.
- Strategy Fill produces fills for submitted signal orders without maker queue
  or lot rounding blocking research PnL.
- Dual Output clearly separates strategy performance from execution friction.
- Artifacts explicitly label their execution profile.
- `strategy_fill` / Dual comparison cannot be mistaken for live-readiness or
  promotion evidence.

## Decision

Use Option A.

The first lazy solution that holds is to promote the existing research-only
immediate-fill path into a named execution profile and add a paired-run wrapper.
Do not build a new touch-aware fill model until there is calibrated data or a
specific need that the existing path cannot answer.


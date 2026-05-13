---
status: proposed
type: design
owner: codex
created: 2026-05-13
last_reviewed: 2026-05-13
expires: none
superseded_by: null
---

# Shadow Mode Parity Plan

## Purpose

Define PR14B implementation scope for making shadow mode a reliable SimBroker
primary versus OKX demo mirror comparison.

Shadow mode is a deployment-readiness gate, not a live trading mode. Its job is
to run the production strategy, signal, portfolio, risk, and execution handler
path while using simulated fills for local accounting and OKX demo mirror orders
for calibration.

## Current Behavior

The current codebase already contains most of the intended shadow components:

- `scripts/run_shadow.py` starts the engine with `sim_broker=True`.
- `src/okx_quant/engine.py` routes `cfg.system.mode == "shadow"` to
  `ShadowBroker(primary=SimBroker, mirror=OKXBroker(demo=True))`.
- `ShadowBroker` submits the primary simulated order and asynchronously mirrors
  the same order to OKX demo with a prefixed client order ID.
- `ExecutionHandler.on_fill_ws()` ignores shadow mirror fills for local
  accounting and sends them to `CalibrationLogger`.
- `CalibrationLogger` writes submit, fill, cancel, latency, and slippage events
  under `results/calibration/`.
- `scripts/run_calibration_apply.py` can aggregate calibration files and suggest
  backtest execution parameters.

This means the old handoff claim that shadow mode only instantiates SimBroker is
stale. The remaining issue is narrower: the entrypoint and broker construction
do not yet make the parity contract hard to misuse.

## Gaps

### Gap 1: `run_shadow.py` accepts `mode=demo`

`scripts/run_shadow.py` currently allows both `shadow` and `demo` config modes.
When mode is `demo`, `engine._build_broker()` honors `sim_broker=True` and
returns a plain `SimBroker`, not `ShadowBroker`. In that path no OKX demo mirror
orders are submitted, so the run does not produce a SimBroker versus OKX demo
comparison.

PR14B should require:

```text
config/settings.yaml system.mode == "shadow"
```

for `scripts/run_shadow.py`.

### Gap 2: Shadow primary SimBroker lacks instrument specs

`engine.main()` builds `instrument_specs` for portfolio sizing, but
`_build_broker()` currently constructs `SimBroker(slippage_bps=2.0)` without
passing those specs. `SimBroker.submit()` requires `ctVal` to compute notional
and fees. In shadow mode, this can cause the primary simulated path to reject
otherwise valid orders with a missing `ctVal` error.

PR14B should pass the same `instrument_specs` used by `PortfolioManager` into
the shadow primary `SimBroker`.

### Gap 3: The parity contract is not explicit in tests

Existing tests cover `ShadowBroker` mirroring and shadow demo environment
selection. They do not assert the full engine broker factory contract:

- `mode=shadow` creates `ShadowBroker` even if `sim_broker=True`.
- `mode=demo` with `sim_broker=True` creates a plain `SimBroker`.
- `run_shadow.py` refuses to run unless `mode=shadow`.
- shadow `SimBroker` receives instrument specs.

PR14B should add focused tests for these contracts without touching strategy
logic.

## Desired Shadow Contract

When running `scripts/run_shadow.py`:

1. Config mode must be exactly `shadow`.
2. Market data and private WS should use OKX demo endpoints.
3. Local order accounting should be driven only by the primary `SimBroker`.
4. OKX demo mirror orders should never update `PositionLedger`.
5. Mirror order fills and cancel acknowledgements should be recorded only in
   calibration artifacts.
6. Mirror failures should be logged but must not block the primary simulated
   path.
7. Shadow mode must not submit live OKX orders.

## PR14B Scope

Permitted implementation files should be limited to:

- `scripts/run_shadow.py`
- `src/okx_quant/engine.py`
- `tests/unit/test_execution_flow.py`
- `tests/integration/test_execution_integration.py`, if needed
- `docs/AI_HANDOFF.md`

PR14B should not change strategy logic, risk limits, portfolio sizing behavior,
or live trading behavior.

## Implementation Sketch

1. Tighten `scripts/run_shadow.py`:
   - require `cfg.system.mode == "shadow"`;
   - update comments so they describe the actual `ShadowBroker` path;
   - keep `asyncio.run(main(cfg, sim_broker=True))`; `_build_broker()` checks
     `mode == "shadow"` before the `sim_broker` override, so shadow mode always
     takes precedence.

2. Update `engine._build_broker()`:
   - accept `instrument_specs: dict | None = None`;
   - pass `instrument_specs` into the shadow primary `SimBroker`;
   - keep non-shadow behavior unchanged.

3. Update the call site in `engine.main()`:
   - pass the already-built `instrument_specs` into `_build_broker()`.

4. Add tests:
   - factory returns `ShadowBroker` for `mode=shadow`;
   - factory returns `SimBroker` for `mode=demo, sim_broker=True`;
   - shadow primary can submit an order with configured `ctVal`;
   - `run_shadow.py` rejects `mode=demo`.

## Validation

Minimum PR14B checks:

```bash
pytest tests/unit/test_execution_flow.py -k "shadow"
pytest tests/integration/test_execution_integration.py -k "shadow"
ruff check scripts/run_shadow.py src/okx_quant/engine.py tests/unit/test_execution_flow.py tests/integration/test_execution_integration.py
```

If PR14B only changes unit-covered behavior, full unit tests should still pass
before merge.

## Non-Goals

PR14B should not:

- calibrate `queue_fill_fraction`, latency, or slippage thresholds;
- apply calibration output to `config/risk.yaml`;
- change live or demo order routing;
- change strategy assumptions;
- introduce a new dashboard;
- solve replay execution realism beyond the shadow parity contract.

## Acceptance Criteria

- `scripts/run_shadow.py` refuses `mode=demo`.
- `mode=shadow` always uses `ShadowBroker` with OKX demo mirror orders.
- Shadow primary `SimBroker` receives instrument specs and can compute fees and
  notional metadata.
- Mirror fills remain calibration-only and do not update local accounting.
- Tests document the mode routing contract.
- `docs/AI_HANDOFF.md` moves PR14A to complete and PR14B to next.

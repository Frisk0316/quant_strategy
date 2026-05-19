---
status: current
type: review
owner: codex
created: 2026-05-19
last_reviewed: 2026-05-19
expires: none
superseded_by: null
---

# Claude Code Review Brief: MA/MACD Position and Indicator Fixes

Owner: Codex
Branch/worktree: current workspace
Intent: Prepare all current diffs for Claude Code review.
Do not touch: `research/` files.
Related ADR: `docs/ADR/0006-reduce-only-risk-semantics.md` (proposed, pending
review/merge approval).

## User Intent Update

The user will keep MA/MACD as baseline strategies for research acceptance and
parameter tuning. The goal is to tune parameters toward positive return while
keeping risk within defined bounds. This does not imply live readiness.

## Problem Being Fixed

MA/MACD are long/flat technical strategies. Before this patch, replay maker
orders could partially fill, but the strategy marked itself flat on the first
partial sell fill. Remaining sell fills could then continue after the strategy
believed it was flat, sometimes reversing the ledger short. Later exit signals
could add to that short exposure and trip the position limit, producing long
periods with no trades.

A second issue was found during validation: EMA/MACD were recomputed from a
bounded deque on every bar. This was slower than necessary and, after enough
bars, became a truncated EMA/MACD rather than the full recursive
`ewm(adjust=False)` series emitted in artifacts.

## Diff Inventory

`src/okx_quant/strategies/technical_indicators.py`

- Adds `cancel_existing: True` metadata to long/flat entry and exit signals.
- Keeps `_in_position=True` after partial sell fills until the exit order is
  fully filled or `remaining_sz <= 1e-12`.
- Changes EMA and MACD calculation to incremental recursive state:
  `ema_t = alpha * price_t + (1 - alpha) * ema_{t-1}`.
- MACD now updates fast EMA, slow EMA, MACD line, and signal EMA per bar instead
  of recomputing pandas EWM over a truncated deque.

`src/okx_quant/portfolio/portfolio_manager.py`

- Detects long/flat signal metadata: `mode == "long_flat"` and `action`.
- Skips long/flat exits that would not reduce an actual existing position.
- Skips long/flat entries when an actual long position already exists.
- For long/flat exit orders only, sizes the order from the current ledger
  position, not from a fresh target notional estimate.
- Marks long/flat exit close orders as `reduce_only=True`.
- Non-long/flat reducing orders keep the prior signal-sized behavior and the
  prior risk-check position context. This intentionally leaves pairs/funding
  close sizing unchanged until P2 design work is separately approved.
- Adds `_compute_reduce_order_quantity()` with lot-size rounding tolerance so
  float dust such as `0.45999999999999996` can close as `0.46`.

`src/okx_quant/risk/risk_guard.py`

- Adds `last_block_reason` for specific replay diagnostics.
- Adds `last_bypass_reason` for allowed reduce-only audit diagnostics.
- Keeps the fat-finger max-order-notional gate active for reduce-only orders.
- Allows reduce-only orders through position-limit increase checks.
- Allows reduce-only orders while kill switch or daily/hard-stop state is active,
  so exits can reduce risk.
- Sets explicit block reasons such as `fat_finger`, `position_limit`,
  `stale_quote`, `daily_loss_limit`, and `kill_switch`.

`src/okx_quant/execution/execution_handler.py`

- If an order has `metadata["cancel_existing"]`, cancels existing quotes for the
  same strategy and instrument before submitting the replacement order.

`src/okx_quant/execution/replay_execution.py`

- Rounds partial fill quantities to instrument `lotSz`/`minSz`.
- Allows the final fill to consume the remaining size exactly.
- Allows sub-`minSz` residual dust to be consumed as the final remainder.
- Prevents non-lot dust positions from partial-fill simulation.

`backtesting/replay.py`

- Risk-guard rejections now use `risk_guard.last_block_reason` instead of the
  generic `risk_guard_block`.
- Allowed reduce-only bypasses are recorded to `risk_event_log` with reason
  `allowed_reduce_only_bypass:<reason>` and are exported through
  `risk_events.csv`.

`tests/unit/test_technical_indicator_strategies.py`

- Adds coverage for long/flat partial exits staying in-position until final fill.
- Adds coverage for `cancel_existing` metadata.
- Adds coverage that incremental EMA/MACD match pandas full-series
  `ewm(adjust=False)` after long runs.

`tests/unit/test_execution_flow.py`

- Adds coverage for replacement cancellation before new strategy order submit.
- Adds coverage for long/flat exits sizing from current position and marking
  reduce-only.
- Adds coverage that non-long/flat reducing orders keep legacy signal sizing and
  are not marked reduce-only.
- Adds coverage for reduce quantity float dust rounding.
- Adds coverage for replay partial fills being rounded to lot size.
- Adds coverage for sub-`minSz` replay residual fills.

`tests/unit/test_risk_guard.py`

- Adds coverage that reduce-only closes still respect the fat-finger cap.
- Adds coverage for reduce-only closes bypassing position-limit increase checks
  and kill switch blocking, with `last_bypass_reason`.
- Adds assertion for specific `last_block_reason`.

`tests/integration/test_replay_engine.py`

- Updates expected rejection reason from generic `risk_guard_block` to
  `stale_quote`.
- Updates missing-ctVal test symbols to unknown `FOO/BAR` because current config
  now contains SOL/ADA specs.

## Validation Run

Targeted test suite:

```powershell
& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest `
  tests/unit/test_technical_indicator_strategies.py `
  tests/unit/test_execution_flow.py `
  tests/unit/test_risk_guard.py `
  tests/integration/test_replay_engine.py
```

Result:

- `64 passed, 1 warning`
- Warning: pytest cache could not write `.pytest_cache` due workspace permission.

Replay artifacts:

```powershell
$env:BACKTEST_ARTIFACT_MODE='files'
& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' `
  scripts/run_replay_backtest.py `
  --strategy ma_crossover `
  --symbol BTC-USDT-SWAP `
  --start 2024-01-01 `
  --end 2026-04-30 `
  --bar 1D `
  --save-artifacts `
  --output-dir results `
  --run-id codex_reviewfix_ma_1d_position_limit_files

& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' `
  scripts/run_replay_backtest.py `
  --strategy macd_crossover `
  --symbol BTC-USDT-SWAP `
  --start 2024-01-01 `
  --end 2026-04-30 `
  --bar 1D `
  --save-artifacts `
  --output-dir results `
  --run-id codex_reviewfix_macd_1d_position_limit_files
```

MA 1D replay summary:

- Artifact: `results/codex_reviewfix_ma_1d_position_limit_files`
- Elapsed: about `6.997s`
- Orders: `12`
- Real fills: `71`
- Fill rate: `0.9166666666666666`
- Risk events: `0`
- Rejected orders: `0`
- Negative `size_after`: `0`
- Signal/indicator trigger mismatches: `0`
- Total return: `0.0001921968522926587`
- Max drawdown: `-0.02767902077180736`

MACD 1D replay summary:

- Artifact: `results/codex_reviewfix_macd_1d_position_limit_files`
- Elapsed: about `7.981s`
- Orders: `31`
- Real fills: `52`
- Fill rate: `0.3870967741935484`
- Risk events: `0`
- Rejected orders: `0`
- Negative `size_after`: `0`
- Signal/indicator trigger mismatches: `0`
- Total return: `-0.019890623717632283`
- Max drawdown: `-0.020918196389827837`

## Trigger Verification Method

The artifact-level check joins `signals.csv` to `indicator_series.csv` on
`strategy`, `inst_id`, and `ts`, then compares the signal bar and the previous
indicator bar.

MA/EMA:

- Entry is valid when previous `fast_value <= slow_value` and current
  `fast_value > slow_value`.
- Exit is valid when previous `fast_value >= slow_value` and current
  `fast_value < slow_value`.

MACD:

- Entry is valid when previous `macd <= macd_signal` and current
  `macd > macd_signal`.
- Exit is valid when previous `macd >= macd_signal` and current
  `macd < macd_signal`.

The check also verifies that signal metadata values match the corresponding
indicator row values.

## Review Focus For Claude

1. Confirm that treating MA/MACD as long/flat baseline strategies is acceptable
   for research acceptance and parameter tuning.
2. Review the narrowed reduce-only semantics: fat-finger still blocks, while
   position-limit, kill-switch, and daily/hard-stop bypasses are allowed only
   for reduce-only orders and are recorded in `risk_events`.
3. Review whether replacement-cancel behavior is appropriate for long/flat
   technical strategies. Codex rationale: stale pending orders should not remain
   after a new entry/exit signal, so this clears both sides for the same
   strategy/instrument.
4. Review whether maker/post-only partial-fill assumptions are acceptable for
   this baseline. Partial fills are normal; final fills now clear remaining size.
5. Confirm that incremental EMA/MACD state should be the canonical behavior for
   strategy execution, matching `ewm(adjust=False)` artifacts.
6. Confirm whether funding events should continue to be loaded for all SWAP
   symbols in technical strategy backtests. This remains a possible performance
   optimization, not included in this patch.

## Known Non-Readiness Items

- Do not mark this live-ready.
- Both replay artifacts still have `ct_val_gate_passed=false` because ctVal
  provenance is not fully authoritative under the current gate.
- MA/MACD profitability is not established. The user intends to tune parameters
  toward positive return with bounded risk.
- Log output is still noisy at DEBUG/INFO during replay. This is separate from
  the position-limit fix.
- Live/WebSocket fill paths should be audited before promotion to confirm
  partial-fill metadata carries enough remaining-size state for long/flat
  strategies. This patch is validated through replay artifacts only.

## Suggested Claude Code Review Prompt

```text
Please review the current Codex diff using docs/ai_collaboration.md,
research/strategy_synthesis.md, docs/backtest_live_parity_plan.md, and config/
as truth sources.

Focus on MA/MACD as baseline research-validation strategies, not live-ready
strategies. Review for lookahead, overfit risk, incorrect execution assumptions,
partial-fill handling, reduce-only risk gate behavior, and whether the
signal-to-indicator verification method is sufficient.

Changed files are listed in docs/claude_code_review_ma_macd_position_fix.md.
Please return findings ordered by severity, with file/line references where
possible, plus any research acceptance criteria needed before parameter tuning.
```

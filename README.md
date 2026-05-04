# OKX Quant Strategy

A production-grade quantitative trading system for OKX exchange, targeting $1k–$10k capital. Built on maker-only execution to exploit the OKX VIP0 fee structure. Taker fees make pure taker strategies mathematically unviable at this capital level.

---

## Table of Contents

1. [Strategies](#strategies)
2. [Architecture](#architecture)
3. [Setup](#setup)
4. [Full Backtest Workflow — CLI](#full-backtest-workflow--cli)
5. [Frontend Dashboard](#frontend-dashboard)
6. [Replay Validation](#replay-validation)
7. [Shadow/Demo Calibration](#shadowdemo-calibration)
8. [Live Deployment Gates](#live-deployment-gates)
9. [Trading Engine](#trading-engine)
10. [Configuration Reference](#configuration-reference)
11. [Testing](#testing)
12. [Research Layer](#research-layer)
13. [AI Collaboration](#ai-collaboration)

---

## Strategies

| Strategy | Module | Description |
| -------- | ------ | ----------- |
| AS Market Maker | `strategies/as_market_maker.py` | Avellaneda-Stoikov quotes with VPIN spread multiplier and OBI/OFI alpha skew |
| OBI Market Maker | `strategies/obi_market_maker.py` | Order book imbalance-driven post-only market making |
| Funding Carry | `strategies/funding_carry.py` | Delta-neutral long spot / short perp, earns 8h funding |
| Pairs Trading | `strategies/pairs_trading.py` | Kalman filter hedge ratio + Ornstein-Uhlenbeck spread z-score |

**Key design rules:**

- All orders use `post_only`. Error 51026 (price crossed book) is logged and dropped — never retried as market orders.
- `T_minus_t = 1.0` fixed for AS MM (24/7 market has no expiry horizon).
- VPIN controls spread width only — it is directionless. OBI/OFI drive directional alpha.
- Delta-neutral carry holds long spot + short perp to earn funding without directional exposure.

---

## Architecture

```text
EventBus (asyncio.Queue)
  MARKET → SignalGenerator → SIGNAL → PortfolioManager → ORDER → ExecutionHandler → FILL
                                                                         ↓
                                                             DrawdownTracker + RiskGuard
```

```text
src/okx_quant/
├── core/           config (Pydantic v2), events (dataclasses), bus (asyncio)
├── data/           rest_client, okx_book (SortedDict + CRC32), market_data_handler, feed_store
├── signals/        obi_ofi, vpin, regime (HMM + GARCH + CUSUM)
├── strategies/     as_market_maker, obi_market_maker, funding_carry, pairs_trading
├── portfolio/      sizing (vol-target, quarter-Kelly, fixed-fractional), positions, portfolio_manager
├── risk/           risk_guard, drawdown_tracker, circuit_breaker
├── execution/      broker (OKXBroker / SimBroker / ShadowBroker), execution_handler,
│                   order_manager, replay_execution, rate_limiter
├── monitoring/     calibration_log, metrics (Prometheus), telegram_alert
├── analytics/      performance (Sharpe, MDD, Calmar, Sortino), dsr (DSR/PSR)
├── api/            FastAPI server, routes_backtest, routes_live, state, WebSocket
└── engine.py       main asyncio orchestrator

backtesting/
├── replay.py               Event-driven replay engine (fills market/funding events through full stack)
├── replay_validation.py    AS MM replay walk-forward and CPCV helpers
├── cpcv.py                 Combinatorial Purged Cross-Validation (López de Prado)
├── walk_forward.py         Rolling walk-forward (non-overlapping IS/OOS windows)
├── data_loader.py          Parquet loaders + simple/log return helpers
├── result_utils.py         Normalize strategy outputs, extract returns
└── vectorbt_scanner.py     Fast parameter scanner for initial research
```

---

## Setup

### 1. Install dependencies

```bash
pip install -e ".[dev]"
```

For optional backtesting research tools:

```bash
pip install -e ".[dev,backtest]"
```

### 2. Configure credentials (only needed for live/demo/shadow modes)

```bash
cp .env.example .env
# Edit .env:
#   OKX_API_KEY=...
#   OKX_SECRET=...
#   OKX_PASSPHRASE=...
#   TELEGRAM_TOKEN=...      (optional — for alerts and kill switch)
#   TELEGRAM_CHAT_ID=...    (optional)
```

### 3. Edit config

| File | What to set |
| ---- | ----------- |
| `config/settings.yaml` | `system.mode` (demo/shadow/live), `symbols`, `equity_usd` |
| `config/strategies.yaml` | Per-strategy parameters: `gamma`, `kappa`, `beta_vpin`, etc. |
| `config/risk.yaml` | Hard risk limits and `backtest:` execution parameters |

---

## Full Backtest Workflow — CLI

This is the complete sequence from raw data to a validated result. Run each step in order.

### Step 1 — Download historical data

No API key required. Uses OKX public endpoints.

```bash
python scripts/fetch_okx_data.py \
    --start 2024-01-01 \
    --end   2026-05-01 \
    --bar   1H
```

Downloads:

- `data/ticks/BTC_USDT_SWAP/candles_1H.parquet`
- `data/ticks/ETH_USDT_SWAP/candles_1H.parquet`
- `data/ticks/BTC_USDT_SWAP/funding.parquet`

---

### Step 2 — Bar-proxy backtest (fast, all three strategies)

Runs bar-level proxy returns for AS MM, Funding Carry, and Pairs Trading.
Includes CPCV with N=27 research trials for AS MM overfitting correction.
Takes ~1–2 minutes. Produces 6 PNG charts and a `result.json`.

```bash
python scripts/run_backtest.py
```

Output in `results/backtest_<dates>_<timestamp>/`:

- `result.json` — all metrics, equity curves, trade logs
- `01_market_data.png` through `06_performance_summary.png`

Printed summary example:

```text
AS MM         sharpe=1.42  mdd=-0.08  psr=0.87  dsr=0.71
Funding Carry sharpe=2.11  mdd=-0.03
Pairs Trading sharpe=0.94  mdd=-0.11
```

**Gate:** `dsr >= 0.95` required before proceeding to replay validation.

---

### Step 3 — Replay smoke gate (fast infra check)

Runs the event-driven replay engine (actual fill simulation with fees, slippage, partial fills, cancel latency). Smoke defaults: `n_splits=3, k_test=1`.

```bash
python scripts/run_replay_validation.py \
    --mode   both \
    --symbol BTC-USDT-SWAP \
    --bar    1H \
    --n-splits 3 \
    --k-test   1 \
    --gamma-grid     0.05 0.1 0.2 \
    --kappa-grid     1.0 1.5 \
    --beta-vpin-grid 2.0
```

Output in `results/replay_validation_<timestamp>/result.json`.

This step verifies that:

- Replay engine runs without errors
- Fill/order counts are non-zero
- Walk-forward OOS Sharpe is positive

---

### Step 4 — Single-strategy replay backtest

Run the full event-driven stack for any strategy combination:

```bash
# AS Market Maker only
python scripts/run_replay_backtest.py \
    --strategy as_market_maker \
    --start 2024-01-01 \
    --end   2026-05-01 \
    --bar   1H

# Funding Carry only
python scripts/run_replay_backtest.py \
    --strategy funding_carry \
    --start 2024-01-01 \
    --end   2026-05-01 \
    --bar   1H

# Multiple strategies together
python scripts/run_replay_backtest.py \
    --strategy as_market_maker \
    --strategy funding_carry \
    --start 2024-01-01 \
    --end   2026-05-01
```

Prints orders placed, fill count, Sharpe, MDD, and other metrics.

---

### Step 5 — Full replay CPCV gate (pre-demo requirement)

Full combinatorial purged cross-validation with replay-based returns.
Uses n_splits=6, k_test=2, full 27-combo parameter grid.
Takes ~30–60 minutes depending on data range.

```bash
python scripts/run_replay_validation.py \
    --mode   both \
    --symbol BTC-USDT-SWAP \
    --bar    1H \
    --start  2024-01-01 \
    --end    2026-05-01 \
    --n-splits 6 \
    --k-test   2 \
    --gamma-grid     0.05 0.1 0.2 \
    --kappa-grid     1.0 1.5 2.0 \
    --beta-vpin-grid 1.0 2.0 3.0 \
    --is-days  30 \
    --oos-days  7
```

Printed summary:

```text
Replay CPCV  combos=27 paths=15  DSR=0.961  PSR=0.974
Replay WF    windows=32  mean_oos_sharpe=0.847
```

**Gate:** `DSR >= 0.95` and `mean_oos_sharpe > 0` required before demo trading.
The result JSON includes `backtest_execution` showing the fill model parameters used.

---

### Step 6 — View results in the frontend

Start the engine to launch the API server and dashboard:

```bash
# config/settings.yaml: system.mode = demo
python -m okx_quant.engine
```

Then open `http://localhost:8080` in your browser (see [Frontend Dashboard](#frontend-dashboard) below).

---

## Frontend Dashboard

The web UI is a React SPA served by the FastAPI engine at **`http://localhost:8080`**.

It starts automatically when the engine runs. No separate server command is needed.

### Views

| View | URL path | Description |
| ---- | -------- | ----------- |
| Overview | `/` | Live equity curve, open positions, recent fills |
| Backtest Results | `/results` | All saved runs in `results/`; click to inspect equity curve, trade log, performance stats |
| Walk-Forward | `/walk-forward` | Per-window IS/OOS Sharpe table from the last `run_replay_validation.py` run |
| CPCV | `/cpcv` | CPCV path Sharpes, DSR, PSR for the last validation run |
| Trades | `/trades` | Live trade log with fill_px, fill_sz, fee, strategy |
| Risk | `/risk` | Live: daily loss %, drawdown %, positions per instrument, circuit breaker status |
| Config | `/config` | Read-only view of current `config/` YAML values |

### WebSocket live feed

The dashboard connects to `ws://localhost:8080/api/ws` automatically. Events pushed in real-time:

- `FILL` — every fill with inst_id, side, fill_px, fill_sz, fee, strategy
- `RISK_SNAPSHOT` — equity, drawdown, daily_loss_pct, positions every 2 seconds
- `RISK` — circuit breaker trips and hard stop events

### REST API

The same endpoints the frontend calls are also available for scripting:

```bash
# List all saved backtest runs
curl http://localhost:8080/api/backtest/runs

# Fetch a specific run's full result.json
curl http://localhost:8080/api/backtest/<run_id>

# Live engine status
curl http://localhost:8080/api/live/status

# Current positions
curl http://localhost:8080/api/live/positions

# Recent trades (last 200)
curl http://localhost:8080/api/live/trades?limit=200

# Live risk metrics
curl http://localhost:8080/api/live/risk
```

API docs (Swagger UI): `http://localhost:8080/api/docs`

---

## Replay Validation

The three-layer validation gate before any live capital deployment:

```text
Layer 1  scripts/run_backtest.py           bar-proxy CPCV    N=27 trials   fast (~2 min)
Layer 2  run_replay_validation.py smoke    replay CPCV       n_splits=3    infra check
Layer 3  run_replay_validation.py full     replay CPCV       n_splits=6    pre-demo gate
```

The replay engine (`backtesting/replay.py`) models:

- **Post-only resting orders** with configurable `order_latency_ms`
- **Post-only rejection** when price crosses the book (order dropped, never retried as taker)
- **Partial fills** via `queue_fill_fraction` (fraction of available book size allocated to local orders)
- **Cancel latency** (`cancel_latency_ms`) — orders can fill after cancel is requested
- **Maker fees** from `BacktestConfig.maker_fee_rate`

All three parameters (`order_latency_ms`, `cancel_latency_ms`, `queue_fill_fraction`) are read from `config/risk.yaml` `backtest:` section and calibrated via the shadow/demo calibration workflow below.

### CPCV Python API

```python
from backtesting.cpcv import CPCV

cv = CPCV(n_splits=6, k_test=2, embargo_pct=0.02, purge_size=1)
results = cv.evaluate(df, strategy_fn, periods=365*24, n_trials=27)

print(results["dsr"])               # Deflated Sharpe Ratio (corrected for 27 trials)
print(results["psr"])               # Probabilistic Sharpe Ratio
print(results["overall_oos_sharpe"])
print(results["path_sharpes"])      # per-path OOS Sharpe list
```

### Walk-Forward Python API

```python
from backtesting.walk_forward import WalkForward

wf = WalkForward(is_days=30, oos_days=7)
wf_results = wf.evaluate(df, strategy_fn)
print(wf_results[["window", "is_start", "oos_start", "oos_sharpe"]])
```

---

## Shadow/Demo Calibration

Replay backtest accuracy depends on three parameters that must be measured from real exchange behavior:

| Parameter | Measures | Config key |
| --------- | -------- | ---------- |
| `queue_fill_fraction` | What fraction of available book size our orders actually fill | `backtest.queue_fill_fraction` |
| `order_latency_ms` | Mean time from order submit to first WS fill confirmation | `backtest.order_latency_ms` |
| `cancel_latency_ms` | P95 time from cancel request to WS cancel confirmation | `backtest.cancel_latency_ms` |

### How calibration data is collected

When the engine runs in `demo` or `shadow` mode, a `CalibrationLogger` is automatically started. It writes a JSONL event file per session to `results/calibration/`:

```text
results/calibration/
  calib_20260504T120000.jsonl    ← raw events (submit / fill / cancel)
  summary_20260504T120000.json   ← per-session stats (written on shutdown)
```

Each JSONL line is one of:

- `{"type": "submit", "cl_ord_id": "m_...", "order_px": ..., "submit_ts": ...}`
- `{"type": "fill",   "cl_ord_id": "m_...", "fill_px": ..., "latency_ms": ..., "slippage_bps": ...}`
- `{"type": "cancel_request", ...}` / `{"type": "cancel_ack", "cancel_latency_ms": ...}`

### Step-by-step calibration workflow

**1. Run the engine in demo mode for at least 1–2 weeks:**

```bash
# config/settings.yaml: system.mode = demo
python -m okx_quant.engine
```

**2. Check collected data and preview suggested config:**

```bash
python scripts/run_calibration_apply.py --dir results/calibration
```

Output example:

```text
Loading 14 calibration file(s)...
  calib_20260504T120000.jsonl: 847 events
  ...

=== Calibration Statistics ===
  Submitted orders    : 1240
  Filled orders       : 684
  Fill rate           : 0.5516  → queue_fill_fraction
  Mean order latency  : 312.4 ms  → order_latency_ms
  P95 order latency   : 891.0 ms
  Mean cancel latency : 187.3 ms
  P95 cancel latency  : 543.0 ms  → cancel_latency_ms
  Mean slippage       : 0.31 bps  (informational)
  P95 slippage        : 1.12 bps  (informational)

=== Suggested config/risk.yaml backtest section ===
backtest:
  queue_fill_fraction: 0.5516
  order_latency_ms: 312
  cancel_latency_ms: 543
```

**3. Apply the values to config:**

```bash
python scripts/run_calibration_apply.py --dir results/calibration --apply
```

This writes the suggested values into the `backtest:` section of `config/risk.yaml`.

**4. Re-run full replay CPCV with calibrated parameters** (Step 5 above).

`--min-fills` (default 10) guards against applying with too few data points:

```bash
# Require at least 50 fills before applying
python scripts/run_calibration_apply.py --apply --min-fills 50
```

---

## Live Deployment Gates

**Required before enabling `system.mode: live`:**

| Gate | Requirement |
| ---- | ----------- |
| Bar-proxy CPCV | DSR ≥ 0.95 (N=27 research trials) |
| Replay CPCV (full) | DSR ≥ 0.95 (n_splits=6, k_test=2) with calibrated fill model |
| Demo trading | ≥ 4 weeks, calibration data collected |
| Shadow mode | ≥ 2 weeks, sim PnL tracks demo PnL within tolerance |
| Human approval | Explicit sign-off required — engine will not self-promote |

```bash
# Run live (only after all gates pass)
python scripts/run_live.py
```

**Risk limits (hard-coded, cannot be overridden at runtime):**

| Level | Threshold | Action |
| ----- | --------- | ------ |
| Max order notional | $500 | RiskGuard rejects order |
| Daily loss | 5% | Halt all strategies |
| Soft drawdown | 10% | Size multiplier → 0.5× |
| Hard drawdown | 15% | Close all positions, kill switch |
| Max leverage | 3× | RiskGuard rejects order |

---

## Trading Engine

### Start in each mode

```bash
# Demo: paper trading against live OKX demo environment
# config/settings.yaml: system.mode = demo
python -m okx_quant.engine

# Shadow: SimBroker (primary) + OKXBroker demo (mirror) run in parallel
# config/settings.yaml: system.mode = shadow
python -m okx_quant.engine

# Live: real trading
# config/settings.yaml: system.mode = live
python -m okx_quant.engine

# Or use the mode-specific entry scripts:
python scripts/run_demo.py
python scripts/run_shadow.py
python scripts/run_live.py
```

The engine starts the FastAPI server on port 8080 automatically.

### Telegram kill switch (optional)

If `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env`:

```text
/status   — current mode, equity, drawdown
/kill     — trigger hard stop and halt engine
/reset    — reset daily loss counter
/help     — list commands
```

### Stream live L2 order book to Parquet

For tick-level microstructure data collection:

```bash
python scripts/stream_orderbook.py --symbol BTC-USDT-SWAP
```

---

## Configuration Reference

### `config/settings.yaml`

```yaml
system:
  mode: demo             # demo | shadow | live
  symbols:
    - BTC-USDT-SWAP
    - ETH-USDT-SWAP
  spot_symbols:
    - BTC-USDT
  equity_usd: 5000.0
  log_level: INFO
  json_logs: false
```

### `config/strategies.yaml` (key AS MM params)

```yaml
as_market_maker:
  enabled: true
  gamma: 0.1             # risk-aversion (spread width)
  kappa: 1.5             # order arrival intensity
  beta_vpin: 2.0         # VPIN spread multiplier
  max_pos_contracts: 50
  refresh_interval_ms: 500.0
```

### `config/risk.yaml` (backtest section)

```yaml
risk:
  max_order_notional_usd: 500.0
  max_daily_loss_pct: 0.05
  soft_drawdown_pct: 0.10
  hard_drawdown_pct: 0.15
  max_leverage: 3.0

backtest:
  order_latency_ms: 0       # updated by run_calibration_apply.py
  cancel_latency_ms: 200    # updated by run_calibration_apply.py
  queue_fill_fraction: 0.20 # updated by run_calibration_apply.py
```

---

## Testing

```bash
# Unit tests (no credentials needed)
pytest tests/unit/ -v

# Integration tests (requires .env with demo credentials)
pytest tests/integration/ -v

# Single module
pytest tests/unit/test_strategy_gates.py -v
pytest tests/unit/test_throttles.py -v
```

---

## Research Layer

The `research/` directory tracks quant finance literature and maps it to strategy hypotheses. No imports — pure decision support.

- [research/papers_database.md](research/papers_database.md) — curated paper catalog with evidence quality, data requirements, and crypto applicability ratings
- [research/strategy_synthesis.md](research/strategy_synthesis.md) — synthesized crypto strategies with signal sources, sizing rules, expected edges, and hooks into existing modules
- [research/search_log.md](research/search_log.md) — reproducible search notes for literature refreshes

---

## AI Collaboration

When using Codex and Claude together, follow [docs/ai_collaboration.md](docs/ai_collaboration.md).

**Role split:**

- **Claude** — research, strategy critique, statistical validation review, deployment-risk review
- **Codex** — implementation, tests, bug fixes against the spec Claude produces

**Mandatory gates before any live deployment:**

1. All CPCV gates pass (DSR ≥ 0.95)
2. `research/strategy_synthesis.md` updated with any changed assumptions
3. User explicit approval — neither AI can self-promote to live

---

## Implementation Notes

- **Clock sync**: REST calls sync OKX server time every 5 minutes to avoid error 50102 (>30s drift).
- **Post-only hard rule**: Error 51026 is logged and dropped; never retried as taker. This preserves maker-only execution semantics in both backtest and live.
- **Contract value gate**: `validate_ct_val()` raises `ValueError` if `ctVal > 1`, guarding against fat-finger notional errors. Adjust allowlist when expanding beyond BTC/ETH.
- **WS reconnect**: `CircuitBreaker` tracks reconnect count; halts strategies if threshold exceeded within the rolling window.
- **OKX book CRC32**: `OkxBook` stores raw string tuples for exact CRC32 validation. Sequence gaps or checksum mismatches raise `RuntimeError` → reconnect.
- **Feed storage**: Tick data written to Parquet by default; TimescaleDB backend available via `storage.backend: timescaledb` in `settings.yaml`.
- **Pairs trading**: Kalman filter updates hedge ratio online each tick. OU half-life must be < 48h for entry. `max_hedge_uncertainty: 10.0` prevents entry when Kalman variance is high.

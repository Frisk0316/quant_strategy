---
status: current
type: architecture
owner: human
created: 2026-05-11
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Architecture

System architecture reference for `quant_strategy`. Updated from source read on 2026-05-11.

---

## Document Semantics

This document uses three status labels:

- **Current implementation** — behavior verified in the current source code.
- **Target architecture** — intended behavior that may not be fully implemented yet.
- **Known gap** — documented mismatch between target design and current implementation.

Codex must not treat **Target architecture** or **Known gap** sections as implemented behavior. If a section carries one of those labels, open an issue before writing code that depends on it.

---

### Known gaps in this document

| Area | Status | Reference |
| --- | --- | --- |
| Shadow mode (ShadowBroker vs OKX demo) | Known gap | `AI_HANDOFF.md` bug #1; PR12 |
| Replay validation gates (terminal liquidation, fill rate, coverage) | Target architecture | ADR-0005; PR10–11 |
| Deployment stages (enforced by policy, not code) | Target architecture | `docs/ai_collaboration.md` |

---

## System Layers

```
┌─────────────────────────────────────────────────────┐
│                   Market Data                        │
│   WebSocket (OKX public/private/business channels)  │
└──────────────────────────┬──────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  EventBus   │  async queue + handler routing
                    └──────┬──────┘
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐   ┌──────────────┐  ┌──────────────┐
    │ Strategy │   │  Execution   │  │  RiskGuard   │
    │  Layer   │   │    Layer     │  │    Layer     │
    └────┬─────┘   └──────┬───────┘  └──────┬───────┘
         │ SignalPayload   │ FillPayload      │ RiskPayload
         ▼                ▼                  ▼
    ┌──────────────────────────────────────────────┐
    │             Portfolio Layer                   │
    │    PortfolioManager + PositionLedger          │
    └──────────────────────┬───────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌───────────┐ ┌──────────┐ ┌──────────────┐
       │  API      │ │  Data    │ │  Backtesting │
       │  Layer    │ │  Layer   │ │  Layer       │
       └───────────┘ └──────────┘ └──────────────┘
```

---

## Event Flow

Every component communicates through typed events on the `EventBus`. No direct imports between trading layers.

```
MARKET → Strategy.on_market() → SignalPayload
SignalPayload → PortfolioManager.on_signal() → OrderPayload
OrderPayload → RiskGuard.check() → [pass / block]
OrderPayload → ExecutionHandler.on_order() → FillPayload
FillPayload → PositionLedger.on_fill() → updated Position + trade_log
FillPayload → DrawdownTracker.update() → equity curve
```

**Event types** (`src/okx_quant/core/events.py`):

| EvtType | Payload | Direction |
|---|---|---|
| `MARKET` | `MarketPayload` (L2 book / trade tick / funding rate) | WS → Strategies |
| `SIGNAL` | `SignalPayload` (strategy, inst_id, side, strength, fair_value, target_bid/ask) | Strategy → Portfolio |
| `ORDER` | `OrderPayload` (cl_ord_id, inst_id, side, sz, px, td_mode, strategy) | Portfolio → Execution |
| `FILL` | `FillPayload` (fill_px, fill_sz, fee, state, metadata) | Execution → Portfolio/Strategies |
| `RISK` | `RiskPayload` (level, reason, triggered_at) | RiskGuard → Engine |
| `FUNDING` | embedded in `MarketPayload` | WS → PositionLedger |

RISK events are always delivered first (priority queue). All other events are FIFO.

---

## Strategy Layer

**Location:** `src/okx_quant/strategies/`

All strategies implement the abstract base `Strategy` (`base.py`):

```python
async def on_market(event: Event, book: OkxBook) -> Optional[SignalPayload]
async def on_fill(event: Event) -> None
```

Control methods called only by RiskGuard: `halt()`, `soft_stop()`, `resume()`.

| Strategy | File | Signal Logic |
|---|---|---|
| `FundingCarryStrategy` | `funding_carry.py` | Long spot + short perp (delta-neutral carry). Entry: `APR > min_threshold AND basis_z < max`. Exit: APR negative or 8h rebalance. |
| `PairsTradingStrategy` | `pairs_trading.py` | BTC-ETH spread. Entry `\|z\| > 2.0`, exit `\|z\| < 0.3`, stop `\|z\| > 4.0`. Kalman filter dynamic hedge ratio. OU parameters recalibrated every 100 bars. |
| Technical crossover strategies | `technical_indicators.py` | Long/flat MA, EMA, and MACD crossover baselines. |
| External-feature baselines | `external_features.py` | Research-only Fear & Greed and CME daily gap baselines. |

---

## Signal Layer

**Location:** `src/okx_quant/signals/`

Pure functions — no state, no side effects.

- `regime.py`: HMM / GARCH / CUSUM style regime helpers used by research hooks.
- Historical microstructure helpers may exist for archived research, but
  order-book market-making strategies are not active strategy modules.

---

## Portfolio Layer

**Location:** `src/okx_quant/portfolio/`

### PositionLedger (`positions.py`)

Single source of truth for all holdings and P&L. Never bypassed.

**`Position` fields:** `inst_id`, `size` (signed: + long / − short), `avg_entry`, `ct_val`, `realized_pnl`, `last_price`, `strategy`

**Key methods:**
- `on_fill(inst_id, side, fill_px, fill_sz, fee, ...)` — Updates `size`, `avg_entry`, `realized_pnl`, appends to `_trade_log`
- `apply_cashflow(amount, ...)` — Funding settlements (non-trade cashflows)
- `get_equity()` → `cash_equity + Σ unrealized_pnl`
- `save_snapshot() / load_snapshot()` — Redis crash recovery

**P&L accounting:**
- SWAP: `unrealized_pnl = size × ct_val × (last_price − avg_entry)`
- SPOT: `unrealized_pnl = size × (last_price − avg_entry)`
- `notional = abs(size) × last_price × ct_val`

`ct_val` for `BTC-USDT-SWAP` = 0.01 (each contract = 0.01 BTC). Missing this factor = 100× error.

### PortfolioManager (`portfolio_manager.py`)

Converts `SignalPayload → OrderPayload`. Applies RiskGuard multiplier.

Sizing chain (in order):
1. Signal strength multiplier (from `SignalPayload.strength`)
2. RiskGuard per-strategy multiplier `[0, 1]`
3. Vol-targeted notional: `equity × (target_vol / realized_vol)`
4. Cap to `max_order_notional_usd`

For paired-quote signals: emits both bid and ask orders simultaneously with distinct `cl_ord_id`.
For pairs trading: calls `_place_linked_hedges()` to emit hedge leg order.

### Sizing (`sizing.py`)

| Function | Formula |
|---|---|
| `vol_target_size` | `equity × (target_vol / realized_vol)` |
| `fixed_fractional` | `equity × risk_pct / stop_distance_pct` |
| `quarter_kelly` | `0.25 × (mu / sigma²) × equity`, clipped |

---

## Execution Layer

**Location:** `src/okx_quant/execution/`

### ExecutionHandler (`execution_handler.py`)

Orchestrates the order lifecycle:
1. Receives `ORDER` event
2. Stale quote check: `|price − mid| / mid > stale_quote_pct` → reject
3. Submits via `OrderManager`
4. Awaits fill from WebSocket private channel (5s timeout)
5. Emits `FILL` event

Post-only rejections (OKX error 51026) are logged and **never retried as market orders**.

### OrderManager (`order_manager.py`)

Tracks in-flight orders:
- `_pending: dict[cl_ord_id → OrderPayload]`
- `_quotes: dict["strategy:inst_id" → {"buy": [...], "sell": [...]}]`
- `cancel_all_quotes(strategy, inst_id, side)` — batch cancel, max 20 per OKX limit

### Broker Abstraction (`broker.py`)

| Broker | Used when | Fill behavior |
|---|---|---|
| `OKXBroker` | live / demo | Post-only via OKX REST; fill arrives via WS private channel |
| `SimBroker` | backtest / shadow primary | Immediate simulated fill at `price ± slippage` with configurable `fill_probability` |
| `ShadowBroker` | shadow mode | Wraps SimBroker (primary) + OKXBroker (mirror). Mirror fires async; primary fill returned immediately. Mirror fills feed `CalibrationLogger`. |

### ReplayExecutionModel (`replay_execution.py`)

Deterministic L1 replay for backtesting:
- Models resting order queue with `order_latency_ms` before activation
- `cancel_latency_ms = 200ms` before cancel takes effect
- `queue_fill_fraction = 0.20` — fraction of book available to fill (calibrated from demo data)
- Post-only check: buy ≥ ask_px or sell ≤ bid_px → reject

---

## Risk Layer

**Location:** `src/okx_quant/risk/`

### RiskGuard (`risk_guard.py`)

Every `OrderPayload` must pass `check()`. No bypass path exists.

Checks in order (first failure blocks):

| Check | Condition | Action |
|---|---|---|
| Kill switch | `kill == True` | Block |
| Equity | `equity ≤ 0` | Block |
| Fat-finger | `notional_usd > max_order_notional_usd` (default 500) | Block |
| Position size | `current_notional + order > max_pos_pct_equity × equity` (default 30%) | Block |
| Stale quote | `\|price − mid\| / mid > stale_quote_pct` (default 2%) | Block |
| Daily loss | `daily_pnl% < −max_daily_loss_pct` (default 5%) | Block + `kill=True` |
| Soft drawdown | `drawdown% ≤ −soft_drawdown_pct` (default 10%) | All multipliers × 0.5 |
| Hard drawdown | `drawdown% ≤ −hard_drawdown_pct` (default 15%) | `kill=True`, multipliers = 0 |

Resets require explicit operator call; `hard_stop_cooldown_hours = 48`.

### DrawdownTracker (`drawdown_tracker.py`)

Updates on every fill. Tracks `_peak_equity` (high-water mark), `_day_start_equity` (UTC midnight reset).

### CircuitBreaker (`circuit_breaker.py`)

Infrastructure-level guard (not market conditions):
- WS reconnect circuit: > 3 reconnects within 60s → trip
- REST error rate circuit: > 5% error rate over last 100 calls → trip

Once tripped, stays tripped until manual `reset()`.

---

## Data Layer

**Location:** `src/okx_quant/data/`, `sql/`

### OkxBook (`data/okx_book.py`)

Live L2 order book with CRC32 checksum validation over top-25 interleaved levels. Raises `RuntimeError` on sequence gap or checksum mismatch → triggers WS resubscribe.

### Data Loader (`data/data_loader.py`)

```python
load_candles(inst_id, bar, backend, dsn, start, end) → DataFrame
# backends: "parquet" | "postgres" | "market"

load_funding(inst_id, backend, dsn) → DataFrame
```

### TimescaleDB Schema

- `market_klines` — raw OHLCV from exchanges (Binance primary, Bybit validation)
- `canonical_candles` — deduplicated, validated, derived-bar candles (1m base → 5m/15m/1H)
- `funding_rates` — OKX perpetual funding settlement rates
- `backtest_runs` — one row per replay backtest run (summary stats)
- `backtest_artifacts` — JSONB payloads for all artifact types per run

---

## Backtesting Layer

**Location:** `backtesting/`

### Replay Engine (`replay.py`)

Per-bar event loop using the **same strategy/portfolio/execution/risk components** as live trading:

```
For each market bar:
  1. Emit MarketPayload → EventBus
  2. Strategy.on_market() → SignalPayload
  3. PortfolioManager.on_signal() → OrderPayload
  4. RiskGuard.check() → pass or record risk event
  5. ReplayExecutionModel.on_market() → FillPayload (deterministic)
  6. PositionLedger.on_fill() → Position update + trade_log entry
  7. DrawdownTracker.update(equity)
  8. Append to ReplayRecorder
End → build_result() → ReplayBacktestResult
```

### ReplayBacktestResult

```python
equity_curve: pd.Series      # Portfolio value indexed by ts
metrics: dict                # total_return, sharpe, max_drawdown, profit_factor, ...
order_log: pd.DataFrame
fill_log: pd.DataFrame
trade_log: pd.DataFrame      # Aggregated position deltas
funding_log: pd.DataFrame
signal_log: list[dict]
risk_event_log: list[dict]
rejected_log: list[dict]
cancel_log: list[dict]
```

### Artifact Writer (`backtesting/artifacts.py`)

`save_backtest_artifacts()` writes results to DB or files based on `_artifact_mode()`:

| `BACKTEST_ARTIFACT_MODE` | `DATABASE_URL` set? | Behavior |
|---|---|---|
| not set | yes | DB only |
| not set | no | files only (`results/<run_id>/`) |
| `files` | either | files only |
| `db` | yes | DB only |
| `db` | no | falls back to files (with warning) |
| `both` | yes | files + DB |

DB-backed runs also maintain `backtest_artifact_rows`, a derived read index for
large list artifacts. It is rebuilt from existing artifacts and is not a trading
source of truth.

### Walk-Forward (`walk_forward.py`)

Sliding 30-day IS / 7-day OOS windows, step = 7 days. Returns per-window OOS Sharpe.

### CPCV (`cpcv.py`)

López de Prado combinatorial purged CV: `n_splits=6`, `k_test=2` → C(6,2)=15 combinations → 5 non-overlapping OOS paths. Applies embargo (2%) and purge (1 sample) to prevent label leakage. Computes PSR and DSR.

---

## API Layer

**Location:** `src/okx_quant/api/`

FastAPI server on port 8080. Mounts frontend SPA at `/`.

### Route Map

| Prefix | Router | Purpose |
|---|---|---|
| `/api/live/*` | `routes_live.py` | Live engine status, risk metrics, positions, recent fills |
| `/api/backtest/*` | `routes_backtest.py` | Backtest runs CRUD, all time-series artifacts |
| `/api/config/*` | `routes_config.py` | Config inspection |
| `/api/data/*` | `routes_data.py` | Instrument list, data coverage, backfill trigger |
| `/api/ws` | `server.py` | WebSocket live broadcast |

### Key Backtest Endpoints

```
GET  /api/backtest/runs              → run list (summary stats)
POST /api/backtest/run               → start run (returns job_id)
GET  /api/backtest/{run_id}          → full result.json
GET  /api/backtest/{run_id}/equity   → equity curve time series
GET  /api/backtest/{run_id}/trades   → trade log
GET  /api/backtest/{run_id}/fills    → fill log
GET  /api/backtest/{run_id}/funding  → funding cashflow log
GET  /api/backtest/{run_id}/signals  → signal history
```

### EngineState (`state.py`)

Bridge between engine and HTTP/WS. Holds live references to `PositionLedger`, `RiskGuard`, `DrawdownTracker`. Maintains `_recent_trades: deque[500]` and broadcasts fill/risk events to all connected WS clients.

---

## Configuration Layer

**Location:** `config/`

| File | Controls |
|---|---|
| `settings.yaml` | System mode (demo/shadow/live), symbols, storage backend, OKX endpoints, market data ingestion |
| `strategies.yaml` | All strategy parameters (thresholds, sizing, timing) |
| `risk.yaml` | All risk limits (fat-finger, position size, drawdown thresholds, circuit breaker settings, backtest fill model params) |

**Canon:** `config/` files override chat/session memory. Strategy assumption changes must update `research/strategy_synthesis.md` before touching `config/` or implementation.

---

## Engine Orchestration

**Location:** `src/okx_quant/engine.py`

Startup sequence:
1. Load config → REST clock sync → fetch instrument specs (`ct_val` per symbol)
2. Build: `EventBus`, `PositionLedger`, `RiskGuard`, `CircuitBreaker`, `EngineState`
3. Build strategies (enabled from `strategies.yaml`)
4. Register all handlers to EventBus by event type
5. Start background tasks: `dispatch_loop`, public/private WS, `feed_store.flush_loop`, clock sync, daily reset, API server, Telegram bot
6. Await SIGTERM/SIGINT → graceful shutdown

---

## Deployment Stages

No strategy may skip a stage (hard rule in `docs/ai_collaboration.md`):

| Stage | Duration | Mode | Broker |
|---|---|---|---|
| Historical backtest | — | replay | ReplayExecutionModel |
| Walk-forward / CPCV | — | replay | ReplayExecutionModel |
| Demo | ≥ 4 weeks | demo | SimBroker |
| Shadow | ≥ 2 weeks | shadow | ShadowBroker (sim primary + OKX mirror) |
| Half-size live | — | live | OKXBroker (50% allocation) |
| Full-size live | — | live | OKXBroker |

# OKX Quant Strategy

A production-grade quantitative trading system targeting OKX exchange, designed for $1k–$10k capital. Built around maker-only strategies to exploit OKX VIP0 fee structure (taker fees make pure taker strategies mathematically unviable).

## Core Design Principles

- **Maker-only execution**: All orders use `post_only`. Error 51026 (price crossed book) is logged and dropped — never retried as market orders.
- **Delta-neutral carry**: Long spot + short perpetual earns funding without directional exposure.
- **Ergodic Avellaneda-Stoikov**: `T_minus_t=1.0` fixed (24/7 market has no expiry horizon).
- **VPIN controls spread width only** — it is directionless. OBI/OFI drive directional alpha.

## Strategies

| Strategy | Module | Description |
|----------|--------|-------------|
| AS Market Maker | `strategies/as_market_maker.py` | Avellaneda-Stoikov quotes with VPIN spread multiplier and OBI/OFI alpha skew |
| OBI Market Maker | `strategies/obi_market_maker.py` | Order book imbalance-driven market making |
| Funding Carry | `strategies/funding_carry.py` | Delta-neutral long spot / short perp, earns 8h funding |
| Pairs Trading | `strategies/pairs_trading.py` | Kalman filter hedge ratio + Ornstein-Uhlenbeck spread z-score |

## Architecture

```
EventBus (asyncio.Queue)
  MARKET → SignalGenerator → SIGNAL → PortfolioManager → ORDER → ExecutionHandler → FILL
                                                                          ↓
                                                              DrawdownTracker + RiskGuard
```

```
src/okx_quant/
├── core/           config (Pydantic v2), events (dataclasses), bus (asyncio)
├── data/           rest_client, okx_book (SortedDict + CRC32), market_data_handler, feed_store
├── signals/        obi_ofi, vpin, regime (HMM + GARCH + CUSUM)
├── strategies/     as_market_maker, obi_market_maker, funding_carry, pairs_trading
├── stocks/         TW/US minute-bar backtesting and stock order routing
├── portfolio/      sizing (vol-target, quarter-Kelly, fixed-fractional)
├── risk/           risk_guard, drawdown_tracker, circuit_breaker
├── execution/      broker (OKXBroker / SimBroker), execution_handler
└── engine.py       main asyncio orchestrator

backtesting/
├── cpcv.py         Combinatorial Purged Cross-Validation (N=6, k=2, embargo=2%)
├── walk_forward.py Rolling walk-forward validation (non-overlapping IS/OOS)
├── data_loader.py  Parquet/Tardis loaders + simple/log return helpers
└── vectorbt_scanner.py Fast parameter research before higher-fidelity validation
```

## Risk Limits

| Level | Threshold | Action |
|-------|-----------|--------|
| Daily loss | 5% | Halt all trading |
| Soft stop | 10% drawdown | Size multiplier → 0.5 |
| Hard stop | 15% drawdown | Close all, kill switch |
| Max order notional | $500 | RiskGuard rejects order |

## Setup

### 1. Install dependencies

```bash
pip install -e ".[dev]"
```

If you want the optional backtesting research tools as well:

```bash
pip install -e ".[dev,backtest]"
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your OKX API key, secret, passphrase
```

`.env` fields:
```
OKX_API_KEY=...
OKX_SECRET_KEY=...
OKX_PASSPHRASE=...
OKX_IS_DEMO=true        # set false for live
TELEGRAM_TOKEN=...      # optional
TELEGRAM_CHAT_ID=...    # optional
```

### 3. Edit config

- [config/settings.yaml](config/settings.yaml) — mode (`demo`/`shadow`/`live`), symbols, equity
- [config/strategies.yaml](config/strategies.yaml) — per-strategy parameters (gamma, kappa, etc.)
- [config/risk.yaml](config/risk.yaml) — hard risk limits

### 4. Run

```bash
# Demo mode (paper trading against live OKX demo)
python -m okx_quant.engine

# Shadow mode (compute signals, log orders, no execution)
# Set mode: shadow in config/settings.yaml
python -m okx_quant.engine
```

## Run The Whole Project

This repo has two common workflows:

1. Research / backtesting workflow
2. Trading engine workflow

### A. Research / Backtesting

1. Install the project

```bash
pip install -e ".[dev]"
```

2. Download historical market data into `data/ticks/`

```bash
python scripts/fetch_okx_data.py
```

This writes parquet files such as:

- `data/ticks/BTC_USDT_SWAP/candles_1H.parquet`
- `data/ticks/ETH_USDT_SWAP/candles_1H.parquet`
- `data/ticks/BTC_USDT_SWAP/funding.parquet`

3. Run the backtest report

```bash
python scripts/run_backtest.py
```

This script loads the parquet data, runs the strategy examples, performs walk-forward validation for funding carry, and writes figures into `results/`.

4. Run a TW/US stock minute-bar backtest

```bash
python scripts/run_stock_backtest.py --market US --symbol AAPL --data data/stocks/AAPL_1m.csv
python scripts/run_stock_backtest.py --market TW --symbol 2330 --data data/stocks/2330_1m.csv
```

The stock subsystem accepts CSV/parquet OHLCV minute bars, filters regular sessions
(`09:00–13:30` Taipei for TW, `09:30–16:00` New York for US), executes signals on
the next bar open, and models market-specific lot sizes, fees, tax, and slippage.

5. Run unit tests

```bash
pytest tests/unit -v
```

6. Run integration tests if you have demo credentials configured

```bash
pytest tests/integration -v
```

### B. Trading Engine

1. Install the project

```bash
pip install -e ".[dev]"
```

2. Configure `.env`

```bash
cp .env.example .env
```

3. Choose a mode in [config/settings.yaml](config/settings.yaml)

- `demo`: paper trading against OKX demo
- `shadow`: compute signals and simulate order flow without sending exchange orders
- `live`: real trading, only after validation

4. Start the engine

```bash
python -m okx_quant.engine
```

Before enabling `live`, the intended promotion path is:

1. Historical backtest
2. CPCV / walk-forward validation
3. Demo run
4. Shadow run
5. Live deployment

## Backtesting

The backtesting utilities are intentionally split into three layers:

- `backtesting/data_loader.py`: loads candles / funding parquet files and computes either `simple` or `log` returns
- `backtesting/walk_forward.py`: rolling validation using non-overlapping half-open windows, so the IS/OOS boundary timestamp is never shared
- `backtesting/cpcv.py`: combinatorial purged cross-validation with purge + embargo applied per test block, plus path-level OOS aggregation

The current CPCV implementation is designed to be safer than a naive combinatorial split:

- Test groups are selected combinatorially from `n_splits`
- Purging is applied immediately before each test block
- Embargo is applied immediately after each test block
- OOS metrics are reported from complete OOS paths when path construction is available, instead of naively concatenating overlapping OOS fragments

Requires Deflated Sharpe Ratio (DSR) ≥ 0.95 before promoting to live.

```python
from backtesting.cpcv import CPCV

cv = CPCV(n_splits=6, k_test=2, embargo_pct=0.02, purge_size=1)
results = cv.evaluate(df, strategy_fn)

print(results["dsr"])
print(results["psr"])
print(results["overall_oos_sharpe"])
print(results["path_sharpes"])
```

`strategy_fn` must accept `(train_data, test_data)` and return either:

- a `pd.Series` aligned to `test_data.index`, or
- a vector with the same length as `test_data`

Example:

```python
import pandas as pd

def strategy_fn(train_data: pd.DataFrame, test_data: pd.DataFrame) -> pd.Series:
    threshold = train_data["signal"].mean()
    positions = (test_data["signal"] > threshold).astype(float)
    return test_data["close"].pct_change().fillna(0.0) * positions.shift(1).fillna(0.0)
```

### Walk-Forward Example

```python
from backtesting.walk_forward import WalkForward

wf = WalkForward(is_days=14, oos_days=7)
wf_results = wf.evaluate(df, strategy_fn)
print(wf_results[["window", "is_start", "oos_start", "oos_sharpe"]])
```

## TW/US Stock Minute System

The stock module is separate from the OKX crypto event path because equities use
different sessions, lot sizes, fees, taxes, and broker APIs.

- `okx_quant.stocks.data.load_minute_bars`: load CSV/parquet minute OHLCV and filter regular sessions.
- `okx_quant.stocks.backtest.MinuteBarBacktester`: next-bar-open execution for target-weight strategies.
- `okx_quant.stocks.broker.StockOrderRouter`: validated order entry for paper or REST broker gateways.
- `config/stocks.yaml`: starter TW/US symbols, lot sizes, max order notional, and broker mode.

The built-in `MovingAverageCrossStrategy` is a smoke-test example. Production
stock strategies can subclass `StockStrategy` and return `TargetSignal` objects.

### Return Helpers

```python
from backtesting.data_loader import compute_returns

simple_r = compute_returns(candles, method="simple")
log_r = compute_returns(candles, method="log")
```

## Testing

```bash
pytest tests/unit/ -v          # 72 unit tests
pytest tests/integration/ -v   # requires .env with demo credentials
```

## OKX WebSocket Book

`OkxBook` stores `(price_str, size_str)` tuples as raw strings to preserve exact server values for CRC32 checksum validation. Floating-point conversion happens only at consumption time (`to_array()`). Sequence gaps or checksum mismatches raise `RuntimeError` triggering reconnect.

## Key Implementation Notes

- **Clock sync**: REST calls sync OKX server time every 5 minutes to avoid error 50102 (timestamp expired).
- **WS reconnect**: CircuitBreaker tracks reconnect count; halts if threshold exceeded within window.
- **Feed storage**: Tick data written to Parquet by default; TimescaleDB backend available via config.
- **Pairs trading**: Kalman filter updates hedge ratio online each tick; OU half-life must be < 48h for entry.

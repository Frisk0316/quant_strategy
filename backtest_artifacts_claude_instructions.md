# Claude 任務文件：補完 Backtest Result Artifacts、CSV Export 與 Frontend API

## 0. 任務背景

目前專案是一套 crypto 回測系統，資料層已經接上 PostgreSQL / TimescaleDB，並且已經開始使用 multi-exchange canonical schema。

目前已知狀態：

1. Binance BTCUSDT 1m OHLCV 已寫入 `market_klines`。
2. Binance BTCUSDT 已 canonicalize 到 legacy `canonical_candles`，以 `inst_id = BTC-USDT-SWAP` 提供給目前 backtest loader 使用。
3. `load_candles(... backend="postgres")` 已確認能從 DB 讀出 1m OHLCV，例如 2024-01-01 單日 1440 rows。
4. replay backtest 已確認能跑出 `n_periods`，表示 DB → loader → replay feed 是通的。
5. Pairs trading 在 BTC / ETH 兩腿資料完整時，應可產生 orders / fills。
6. Funding rate 目前主要寫在 `market_funding_rates`，並透過 SQL mirror 到 legacy `funding_rates`。
7. 目前 `scripts/run_replay_backtest.py` 主要只印 summary，尚未正式輸出完整 artifacts 給前端與 CSV 分析使用。
8. 前端目前仍大量依賴 mock data，缺乏正式 backtest artifacts API。
9. 回測交易紀錄目前不足以完整回答「在哪裡買、在哪裡賣、這筆交易盈虧多少、fee / funding 影響多少」。

本任務目標是補完 **回測結果輸出層**，使每一次 backtest 都可以產生一致、可讀、可檢查、可供前端使用的結果資料。

---

## 1. 最終目標

完成後，每次執行 replay backtest 時，系統應能產生：

```text
results/<run_id>/
  result.json
  config.json
  metrics.json

  orders.csv
  fills.csv
  trades.csv
  positions.csv
  equity_curve.csv
  returns.csv
  drawdown.csv
  funding.csv
  signals.csv
  risk_events.csv
  rejected_orders.csv
  cancel_log.csv
  execution_markers.csv
  data_coverage.json
```

這些 artifacts 要支援三種用途：

1. **前端 Dashboard / API 使用**
2. **CSV / JSON 檔案人工檢查**
3. **後續交易視覺化與 PnL attribution 分析**

即使某些資料為空，例如沒有 trades，也必須輸出空 CSV 並保留正確 header。

---

## 2. 請先檢查目前 repository

請先閱讀以下檔案，確認目前結構後再修改：

```text
scripts/run_replay_backtest.py
backtesting/replay.py
backtesting/data_loader.py
src/okx_quant/portfolio/positions.py
src/okx_quant/portfolio/portfolio_manager.py
src/okx_quant/execution/replay_execution.py
src/okx_quant/risk/risk_guard.py
src/okx_quant/analytics/performance.py
src/okx_quant/api/routes_backtest.py
frontend/view-results.jsx
frontend/view-trades.jsx
config/settings.yaml
config/strategies.yaml
config/risk.yaml
```

不要覆蓋既有功能。請以最小侵入方式加入 artifacts export。

---

## 3. 新增檔案：`backtesting/artifacts.py`

請新增：

```text
backtesting/artifacts.py
```

負責：

1. 建立 `run_id`
2. 建立 `results/<run_id>/`
3. 輸出 JSON / CSV
4. 補齊空 CSV header
5. 整理 metrics
6. 整理 execution markers
7. 整理 data coverage
8. 將所有 artifacts 路徑寫入 `result.json`

建議核心函數：

```python
def save_backtest_artifacts(
    result,
    cfg,
    args,
    output_dir: str = "results",
    run_id: str | None = None,
) -> Path:
    ...
```

也可以拆成：

```python
build_run_id(...)
write_json(...)
write_csv(...)
normalize_orders(...)
normalize_fills(...)
normalize_trades(...)
build_execution_markers(...)
build_data_coverage(...)
```

---

## 4. `run_id` 命名規則

若使用者沒有傳入 `--run-id`，請自動產生：

```text
replay_<strategy_names>_<start>_<end>_<bar>_<timestamp>
```

範例：

```text
replay_pairs_trading_20240101_20240108_1m_20260506_170000
```

請避免使用 Windows 不合法路徑字元，例如 `:`。

---

## 5. `scripts/run_replay_backtest.py` CLI 要新增參數

目前 CLI 主要只印 summary。請新增：

```bash
--save-artifacts
--output-dir results
--run-id optional
--artifact-format csv
```

範例：

```bash
python scripts/run_replay_backtest.py \
  --strategy pairs_trading \
  --start 2024-01-01 \
  --end 2024-01-08 \
  --bar 1m \
  --save-artifacts \
  --output-dir results
```

成功後應印出：

```text
Saved backtest artifacts to results/<run_id>
```

如果未指定 `--save-artifacts`，可以維持原本只印 summary 的行為。

---

## 6. `result.json` 格式

`result.json` 是前端讀取單次回測結果的入口。請輸出如下格式：

```json
{
  "run_id": "replay_pairs_trading_20240101_20240108_1m_20260506_170000",
  "created_at": "2026-05-06T17:00:00Z",
  "mode": "replay_backtest",
  "strategies": ["pairs_trading"],
  "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
  "bar": "1m",
  "start": "2024-01-01T00:00:00Z",
  "end": "2024-01-08T00:00:00Z",
  "backend": "postgres",
  "data_source": {
    "ohlcv_layer": "canonical_candles",
    "funding_layer": "funding_rates",
    "primary_exchange": "binance"
  },
  "metrics": {
    "n_periods": 10080,
    "total_return": 0.01,
    "sharpe": 1.2,
    "sortino": 1.5,
    "max_drawdown": -0.03,
    "calmar": 0.4,
    "profit_factor": 1.3,
    "win_rate": 0.52,
    "order_count": 10,
    "fill_count": 8,
    "real_fill_count": 8,
    "fill_rate": 0.8,
    "total_fees": 12.3,
    "fill_notional_usd": 50000,
    "funding_cashflow": -3.2,
    "funding_settlement_count": 3,
    "psr": 0.7,
    "dsr": 0.6,
    "bankrupt": false,
    "min_equity": 4950,
    "last_equity": 5050
  },
  "artifacts": {
    "config": "config.json",
    "metrics": "metrics.json",
    "orders": "orders.csv",
    "fills": "fills.csv",
    "trades": "trades.csv",
    "positions": "positions.csv",
    "equity_curve": "equity_curve.csv",
    "returns": "returns.csv",
    "drawdown": "drawdown.csv",
    "funding": "funding.csv",
    "signals": "signals.csv",
    "risk_events": "risk_events.csv",
    "rejected_orders": "rejected_orders.csv",
    "cancel_log": "cancel_log.csv",
    "execution_markers": "execution_markers.csv",
    "data_coverage": "data_coverage.json"
  }
}
```

---

## 7. `metrics.json` 要求

請將 `result.metrics` 輸出到：

```text
metrics.json
```

但請修正以下問題。

### 7.1 `fill_count` 不應包含 pending fill

目前 replay execution 可能會在 submit order 時回傳 `state = pending` 的 `FillPayload`。這類資料不應該被算進真實成交數。

請新增以下 metrics：

```text
submitted_order_count
pending_fill_event_count
real_fill_count
partial_fill_count
filled_count
cancelled_count
rejected_order_count
```

真實 fill 定義：

```python
fill_sz > 0 and state in {"filled", "partially_filled"}
```

`fill_rate` 應改成：

```python
real_fill_count / submitted_order_count
```

若 `submitted_order_count = 0`，`fill_rate = 0`。

請保證：

```text
fill_rate <= 1
```

不要出現 `fill_rate = 5.0` 這類結果。

---

## 8. `orders.csv` 欄位

請確保 `orders.csv` 至少有以下欄位：

```text
ts
datetime
strategy
inst_id
side
ord_type
px
sz
notional_usd
td_mode
cl_ord_id
state
reason
metadata
```

要求：

1. `ts` 保留原始 timestamp。
2. `datetime` 使用 ISO 8601 UTC。
3. `metadata` 請序列化成 JSON string。
4. 若目前 order log 沒有欄位，請在 export 時補 `NULL` / 空值。
5. 如果沒有 orders，也要輸出空 CSV header。

---

## 9. `fills.csv` 欄位

請確保 `fills.csv` 至少有：

```text
ts
datetime
strategy
inst_id
side
fill_px
fill_sz
fee
fee_ccy
state
cl_ord_id
ord_id
notional_usd
fee_rate
ct_val
remaining_sz
execution_model
metadata
```

要求：

1. `pending` fill 可以保留在 `fills.csv`，但不要算進 `real_fill_count`。
2. `fill_sz = 0` 不應影響 PnL。
3. `notional_usd` 優先從 metadata 取。
4. 若 metadata 沒有 `notional_usd`，用：

```python
fill_px * fill_sz * ct_val
```

計算。
5. `metadata` 請輸出 JSON string。
6. 若沒有 fills，也要輸出空 CSV header。

---

## 10. `trades.csv` 欄位：最重要

目前 `PositionLedger.on_fill()` 的 trade log 不足以回答：

```text
哪裡買？
哪裡賣？
這筆交易賺賠多少？
fee 吃掉多少？
倉位前後如何變化？
```

請補完 trade lifecycle logging。每一筆真實成交都要記錄：

```text
ts
datetime
strategy
inst_id
side
fill_px
fill_sz
fee
fee_ccy

size_before
size_after
avg_entry_before
avg_entry_after
position_notional_before
position_notional_after

realized_pnl
net_realized_pnl
unrealized_pnl_after
cash_before
cash_after
equity_after

is_opening
is_reducing
is_closing
is_reversing

metadata
```

### 10.1 PnL 計算要求

請確認：

```text
realized_pnl = 平倉部分產生的毛 PnL
net_realized_pnl = realized_pnl - fee
```

若只是加倉：

```text
realized_pnl = 0
net_realized_pnl = -fee
```

若是減倉或平倉，必須計算 realized PnL。

若是反手，請拆解或正確處理：

1. 先平掉原倉位並計算 realized PnL。
2. 剩餘數量成為新方向倉位。
3. trade log 要能看出是 reversing。

---

## 11. `positions.csv` 欄位

請輸出 position snapshot。

最低要求：每次真實 fill 後輸出一筆。

理想要求：每個 market event 後輸出一筆，方便前端畫 position curve。

至少包含：

```text
ts
datetime
strategy
inst_id
size
avg_entry
mark_price
notional
unrealized_pnl
realized_pnl
net_realized_pnl
cash
equity
leverage
```

若一開始不想輸出每分鐘 position，也可以先只輸出 fill 後 snapshot，但欄位需保留。

---

## 12. `equity_curve.csv` 欄位

目前 equity curve 只是 series。請改成表格輸出：

```text
ts
datetime
equity
cash
realized_pnl
unrealized_pnl
funding_pnl
fee_paid
drawdown
return
```

如果某些欄位目前沒有資料，先填 0 或 NaN，但 header 必須保留。

---

## 13. `returns.csv` 欄位

請輸出：

```text
ts
datetime
return
log_return
```

如果 equity <= 0，`log_return` 應為 NaN，不要讓程式噴 warning。

---

## 14. `drawdown.csv` 欄位

請輸出：

```text
ts
datetime
equity
running_max_equity
drawdown
drawdown_pct
```

---

## 15. `funding.csv` 欄位

請輸出所有 funding event 與 funding payment。

至少包含：

```text
ts
datetime
inst_id
strategy
funding_rate
funding_rate_pct
funding_interval_hours
mark_price
position_size
position_notional
funding_fee
cash_before
cash_after
equity_after
source
```

### 15.1 Funding loader 目前已知問題

目前 funding ingestion 寫入的是：

```text
market_funding_rates
```

並且可透過 SQL mirror 到 legacy：

```text
funding_rates
```

但 `load_funding(... backend="postgres")` 可能仍讀不到資料。

請做以下其中一種修法。

#### 短期修法

修改 `backtesting/data_loader.py` 的 `_load_funding_pg()`，讓它直接查 legacy `funding_rates`：

```sql
SELECT
    ts,
    funding_rate AS rate,
    realized_rate,
    next_funding_ts AS "nextFundingTime",
    funding_interval_hours,
    mark_price,
    source
FROM funding_rates
WHERE inst_id = $1
  AND ts >= $2
  AND ts < $3
ORDER BY ts;
```

#### 長期修法

新增：

```python
load_funding(... backend="market", exchange="binance")
```

直接查：

```text
market_instruments + market_funding_rates
```

---

## 16. `signals.csv` 欄位

請記錄每次 strategy 產生的 signal，即使後續沒有變成 order。

至少包含：

```text
ts
datetime
strategy
inst_id
side
strength
fair_value
target_bid
target_ask
metadata
```

這很重要。若回測沒有交易，前端可以判斷原因是：

```text
沒有 market data
沒有 signal
有 signal 但 risk blocked
有 order 但沒有 fill
```

請在 replay recorder 或 event bus 流程中加入 signal logging。

---

## 17. `risk_events.csv` 欄位

目前 terminal 會出現：

```text
Order blocked: position limit
```

但沒有結構化輸出。請讓 RiskGuard 在擋單時輸出 risk event。

至少包含：

```text
ts
datetime
strategy
inst_id
side
px
sz
notional_usd
reason
current_position
position_limit
current_equity
metadata
```

常見 reason：

```text
position_limit
max_order_notional
max_leverage
daily_loss_limit
drawdown_limit
stale_quote
```

如果短期不方便改 RiskGuard，可先讓 PortfolioManager 在 risk check failed 時記錄一筆 risk event。

---

## 18. `rejected_orders.csv` 欄位

ReplayExecutionModel 有 post-only reject 邏輯，請輸出 rejected orders。

至少包含：

```text
ts
datetime
strategy
inst_id
side
px
sz
cl_ord_id
reason
best_bid
best_ask
metadata
```

常見 reason：

```text
post_only_cross
invalid_price
invalid_size
risk_blocked
```

---

## 19. `cancel_log.csv` 欄位

請輸出 replay execution 的 cancel log。

欄位：

```text
ts
datetime
inst_id
cl_ord_id
state
effective_ts
reason
```

---

## 20. `execution_markers.csv` 欄位

這是給前端 K 線買賣點視覺化用。

請從真實 fills 生成：

```text
ts
datetime
inst_id
strategy
side
price
qty
fee
net_realized_pnl
position_after
marker_position
marker_shape
marker_text
```

規則：

```text
buy  → marker_position = belowBar, marker_shape = arrowUp
sell → marker_position = aboveBar, marker_shape = arrowDown
```

`marker_text` 範例：

```text
BUY 0.01 @ 42350.4 | PnL: 12.3
SELL 0.01 @ 44100.1 | PnL: -3.2
```

---

## 21. `data_coverage.json`

請輸出這次 backtest 實際使用到的資料範圍。

格式：

```json
{
  "candles": [
    {
      "inst_id": "BTC-USDT-SWAP",
      "bar": "1m",
      "first_ts": "2024-01-01T00:00:00Z",
      "last_ts": "2024-01-08T00:00:00Z",
      "row_count": 10080,
      "source_primary": "binance"
    },
    {
      "inst_id": "ETH-USDT-SWAP",
      "bar": "1m",
      "first_ts": "2024-01-01T00:00:00Z",
      "last_ts": "2024-01-08T00:00:00Z",
      "row_count": 10080,
      "source_primary": "binance"
    }
  ],
  "funding": [
    {
      "inst_id": "BTC-USDT-SWAP",
      "first_ts": "2024-01-01T00:00:00Z",
      "last_ts": "2024-01-08T00:00:00Z",
      "row_count": 21,
      "source": "binance"
    }
  ]
}
```

這可以幫前端顯示：

```text
這次回測用了哪些資料？
資料是否完整？
BTC / ETH 是否時間對齊？
funding 是否有載入？
```

---

## 22. `config.json`

請輸出本次使用的 config，包括：

```text
system config
strategy params
risk params
backtest params
storage params
CLI args
```

但不要輸出：

```text
API key
secret
passphrase
telegram token
任何敏感資訊
```

---

## 23. FastAPI routes 要補完

請檢查並補完：

```text
src/okx_quant/api/routes_backtest.py
```

至少支援：

```text
GET /api/backtest/runs
GET /api/backtest/{run_id}
GET /api/backtest/{run_id}/metrics
GET /api/backtest/{run_id}/equity
GET /api/backtest/{run_id}/orders
GET /api/backtest/{run_id}/fills
GET /api/backtest/{run_id}/trades
GET /api/backtest/{run_id}/positions
GET /api/backtest/{run_id}/funding
GET /api/backtest/{run_id}/signals
GET /api/backtest/{run_id}/risk-events
GET /api/backtest/{run_id}/rejected-orders
GET /api/backtest/{run_id}/cancel-log
GET /api/backtest/{run_id}/execution-markers
GET /api/backtest/{run_id}/data-coverage
```

API 可以先讀：

```text
results/<run_id>/*.csv
results/<run_id>/result.json
```

不需要馬上 DB 化。

---

## 24. 前端需要呈現的內容

請讓前端逐步支援以下資料。

### 24.1 Backtest Runs

欄位：

```text
run_id
strategy
symbols
start
end
bar
total_return
sharpe
max_drawdown
order_count
real_fill_count
created_at
```

### 24.2 Backtest Detail

顯示：

```text
metrics cards
equity curve
drawdown curve
returns distribution
orders table
fills table
trades table
funding table
risk events table
```

### 24.3 Execution Chart

需要：

```text
candles
execution_markers
position series
PnL per trade
```

若 candle API 尚未完成，可以先只顯示 fills / trades table，之後再做 K 線圖。

---

## 25. Performance metrics 防呆

請修：

```text
src/okx_quant/analytics/performance.py
```

目前如果 equity <= 0，程式可能執行：

```python
np.log(eq[-1])
```

導致 warning。

請改成：

```python
if final_equity <= 0:
    cagr = np.nan
    calmar = np.nan
    bankrupt = True
else:
    bankrupt = False
```

metrics 裡要加入：

```text
bankrupt
min_equity
last_equity
```

若 equity 序列中任何點 <= 0，也應將 `bankrupt = True`。

---

## 26. Funding 不應只限制在 funding_carry

目前 replay feed 可能只在 `funding_carry` strategy 啟用時才載入 funding events。

請調整邏輯：

1. 所有 perpetual strategies 都應可計入 funding cost。
2. 如果本次回測 symbols 包含 `*-USDT-SWAP`，應嘗試載入對應 funding events。
3. 沒有 funding data 時，請 warning，但不要讓 backtest crash。
4. `funding.csv` 要能看出是否有載入 funding。

---

## 27. 空資料輸出規則

即使資料為空，也要輸出 CSV header。

建議定義固定 schema：

```python
ORDER_COLUMNS = [...]
FILL_COLUMNS = [...]
TRADE_COLUMNS = [...]
POSITION_COLUMNS = [...]
EQUITY_COLUMNS = [...]
RETURN_COLUMNS = [...]
DRAWDOWN_COLUMNS = [...]
FUNDING_COLUMNS = [...]
SIGNAL_COLUMNS = [...]
RISK_EVENT_COLUMNS = [...]
REJECTED_ORDER_COLUMNS = [...]
CANCEL_LOG_COLUMNS = [...]
EXECUTION_MARKER_COLUMNS = [...]
```

寫 CSV 時：

```python
df = ensure_columns(df, COLUMNS)
df.to_csv(path, index=False)
```

---

## 28. 時間欄位規則

所有 CSV 都應同時保留：

```text
ts
datetime
```

其中：

```text
ts = 原始 timestamp，通常是 ms 或 DB timestamp
datetime = ISO 8601 UTC 字串
```

若 `ts` 是毫秒 timestamp，請轉換成：

```python
pd.to_datetime(ts, unit="ms", utc=True)
```

若 `ts` 已經是 datetime，請轉成 UTC ISO string。

---

## 29. Metadata 輸出規則

凡是 `metadata` 欄位：

1. 如果是 dict，輸出 JSON string。
2. 如果是空，輸出 `{}`。
3. 不要輸出 Python repr，例如 `{'a': 1}`。
4. 請用 `json.dumps(..., ensure_ascii=False)`。

---

## 30. Acceptance Criteria

完成後，以下測試必須通過。

### 30.1 可以輸出完整 artifacts

執行：

```bash
python scripts/run_replay_backtest.py \
  --strategy pairs_trading \
  --start 2024-01-01 \
  --end 2024-01-08 \
  --bar 1m \
  --save-artifacts
```

應產生：

```text
results/<run_id>/result.json
results/<run_id>/metrics.json
results/<run_id>/config.json
results/<run_id>/orders.csv
results/<run_id>/fills.csv
results/<run_id>/trades.csv
results/<run_id>/positions.csv
results/<run_id>/equity_curve.csv
results/<run_id>/returns.csv
results/<run_id>/drawdown.csv
results/<run_id>/funding.csv
results/<run_id>/signals.csv
results/<run_id>/risk_events.csv
results/<run_id>/rejected_orders.csv
results/<run_id>/cancel_log.csv
results/<run_id>/execution_markers.csv
results/<run_id>/data_coverage.json
```

### 30.2 空資料也要有 header

即使沒有 trades，也要產生：

```text
trades.csv
```

且有正確欄位 header。

### 30.3 fill_count 正確

`pending` 不應該算進 `real_fill_count`。

### 30.4 fill_rate 不可大於 1

`fill_rate` 應為：

```python
real_fill_count / submitted_order_count
```

### 30.5 前端 API 可讀

至少以下 API 要可回傳 JSON：

```text
GET /api/backtest/runs
GET /api/backtest/{run_id}
GET /api/backtest/{run_id}/fills
GET /api/backtest/{run_id}/equity
GET /api/backtest/{run_id}/trades
```

### 30.6 result.json 可作為前端入口

前端應可只靠 `result.json` 找到所有 artifact 檔案。

### 30.7 performance 不應噴 log warning

如果 equity <= 0，metrics 要標記 bankrupt，而不是讓 `np.log()` 噴 warning。

---

## 31. 不要做的事

請不要：

1. 不要把 API keys / secrets 寫進任何 artifact。
2. 不要讓 `fill_rate > 1`。
3. 不要把 pending fill 當成真實成交。
4. 不要只印 terminal summary，不存檔。
5. 不要只輸出圖表，不輸出原始表格資料。
6. 不要因為某些 DataFrame 為空就不輸出 CSV。
7. 不要在 equity <= 0 時直接用 log 計算 CAGR。
8. 不要破壞目前 `run_replay_backtest.py` 原本可以只印 summary 的行為。
9. 不要把 artifacts 直接寫進 repository root，請統一寫入 `results/<run_id>/`。
10. 不要把 funding 限定只有 funding_carry 才能使用；perpetual strategies 也應能計入 funding cost。

---

## 32. 建議實作順序

請依照以下順序實作：

1. 新增 `backtesting/artifacts.py`
2. 實作固定 CSV schemas
3. 實作 `save_backtest_artifacts(result, cfg, args, output_dir, run_id)`
4. 修改 `scripts/run_replay_backtest.py`，新增 `--save-artifacts`
5. 先輸出：
   - `result.json`
   - `metrics.json`
   - `config.json`
   - `orders.csv`
   - `fills.csv`
   - `equity_curve.csv`
   - `returns.csv`
6. 再補：
   - `trades.csv`
   - `positions.csv`
   - `drawdown.csv`
7. 補：
   - `funding.csv`
   - `signals.csv`
   - `risk_events.csv`
   - `rejected_orders.csv`
   - `cancel_log.csv`
   - `execution_markers.csv`
   - `data_coverage.json`
8. 修 metrics：
   - `real_fill_count`
   - `pending_fill_event_count`
   - `fill_rate`
   - `bankrupt`
   - `min_equity`
   - `last_equity`
9. 修 funding loader
10. 補 FastAPI artifact routes
11. 更新前端讀取 API
12. 更新 README，說明如何跑 backtest、查看 artifacts、提供給前端

---

## 33. 最低可用版本

如果時間有限，請至少先完成：

```text
result.json
metrics.json
config.json
orders.csv
fills.csv
trades.csv
equity_curve.csv
returns.csv
drawdown.csv
data_coverage.json
```

這些完成後，前端至少可以做：

```text
Backtest Runs
Backtest Detail
Equity Curve
Orders / Fills / Trades Table
Data Coverage Check
```

之後再補：

```text
positions.csv
funding.csv
signals.csv
risk_events.csv
rejected_orders.csv
cancel_log.csv
execution_markers.csv
```

# 回測系統擬真化改善企劃書

## 1. 執行摘要

本專案目前已經具備不錯的研究骨架：有 `WalkForward`、`CPCV`、`DSR/PSR` 等統計驗證工具，也有 live engine、strategy、portfolio、broker abstraction 等可重用模組。但「回測結果」與「實盤行為」之間仍有明顯斷層，核心原因不是資料真假，而是回測主流程尚未走同一套事件驅動下單、撮合、回報、記帳路徑。

目前最主要的落差是：

1. `scripts/run_backtest.py` 以手寫 bar-level 近似公式回測三個策略，而不是重放歷史事件後讓策略真正送單、排隊、成交、更新庫存與權益。
2. `SimBroker` 仍是「固定滑價 + 固定成交機率 + 立即成交」模型，無法模擬 post-only rejection、queue position、partial fill、cancel/replace 與延遲。
3. Funding carry 與 pairs strategy 都是多腿策略，但現況的 signal / execution / accounting 還是單腿思維，離實盤最遠。
4. 目前的 validation 是建立在簡化報酬序列上，而不是建立在「訂單事件與成交事件產生的報酬」上。

因此，本企劃書的建議不是繼續微調 bar-level 公式，而是把回測系統升級為「歷史事件重放 + 同碼策略 + 可校準的模擬撮合 + 可驗證的記帳引擎」，並以 shadow / demo 的真實差異反向校準模擬器。

## 2. 現況診斷

| 面向 | 目前實作 | 與實盤的落差 | 相關程式 |
| --- | --- | --- | --- |
| 回測主流程 | 三個策略都在 `scripts/run_backtest.py` 以獨立迴圈與近似公式計算報酬 | 沒有經過 `Strategy -> Signal -> Portfolio -> Order -> Fill -> PositionLedger` 的真實鏈路 | `scripts/run_backtest.py` |
| AS 做市回測 | 用 `high/low` 推 mid，用 `fill_prob = spread_AS / spread_mkt` 估成交，庫存變化由 bar 報酬方向推回去 | 沒有掛單存續時間、排隊順位、被動成交次序、撤單、部分成交、成交先後 | `scripts/run_backtest.py:147-200` |
| Funding carry 回測 | 只看 funding rate，APR 過門檻就進場，APR < 0 就出場 | 沒有 spot 腿、basis、hedge drift、兩腿不同手續費、settlement 時點、借貸成本 | `scripts/run_backtest.py:264-277` |
| Pairs 回測 | 只用單一報酬流模擬 spread 收斂 | 沒有雙腿聯動送單、不同腿成交不同步、beta 對沖殘差、 legging risk | `scripts/run_backtest.py:375-390` |
| 高保真框架 | 標示要用 Nautilus，但目前只是 skeleton | 還沒進入真正可執行的 L2 / queue-aware backtest | `backtesting/nautilus_backtest.py:28-78` |
| 模擬撮合 | `SimBroker` 立即以目標價加減固定滑價成交，且用固定機率判斷成交 | 沒有訂單簿上下文、post-only rejection、partial fill、latency、book walk、cancel latency | `src/okx_quant/execution/broker.py:145-201` |
| shadow mode | 註解宣稱同時跑 SimBroker 與 demo OKX | 實際上 engine 在 shadow 只選 `SimBroker`，沒有做真實對照 | `scripts/run_shadow.py:2-27`, `src/okx_quant/engine.py:156-164` |
| 統計驗證 | CPCV / WF 設計方向正確 | `strategy_fn` 仍可直接回傳報酬序列，無法約束一定要走下單與成交流程 | `backtesting/cpcv.py:178-260`, `backtesting/walk_forward.py` |

## 3. 目前已知 blocker

這些問題即使先不重構整個回測框架，也應列為 P0，因為會直接扭曲模擬結果或讓 live/backtest 行為失真。

### P0-1. Shadow mode 的描述與實作不一致

`scripts/run_shadow.py` 註解寫的是「SimBroker 與 OKX demo 並行比對」，但實際上 `engine.py` 在 `shadow` 模式只建立 `SimBroker`。這會讓 shadow 無法達成「模擬 vs demo 成交品質校準」的目的。

### P0-2. `SimBroker` 沒有完整 fill event 回寫設計

目前 `ExecutionHandler.on_order()` 假設 fill 會由 WebSocket 回來，但 `SimBroker.submit()` 雖然直接產生 `FillPayload`，流程中並沒有對應的模擬 fill event emission。若未來要用同一套 engine 跑 backtest / replay，這條路徑必須補齊。

### P0-3. `PositionLedger` 對 reversal position 的成本基礎不正確

當部位由多翻空或空翻多時，現有 `on_fill()` 只計算平倉 PnL，但沒有把剩餘反向部位的 `avg_entry` 重設為新的開倉價格。這會污染 unrealized PnL，讓任何高頻翻向策略的 equity curve 失真。

相關位置：`src/okx_quant/portfolio/positions.py:141-156`

### P0-4. `PortfolioManager.update_return()` 寫回的是固定 0

目前回填 return 的邏輯是 `(fill.fill_px / fill.fill_px - 1)`，結果永遠是 0，代表任何依賴近期波動做 sizing 的行為都不會正常運作。若未來回測改走同碼 portfolio，這會直接扭曲 sizing。

相關位置：`src/okx_quant/portfolio/portfolio_manager.py:159-172`

## 4. 改善目標

本企劃建議把「盡可能模擬實盤」明確定義為以下五個目標：

1. 同一套 strategy code 可同時跑歷史重放、shadow、demo、live。
2. 回測報酬來自成交事件與權益變化，不來自手寫報酬公式。
3. 模擬撮合要能表達 maker/taker、post-only rejection、部分成交、撤單、延遲與資金費結算。
4. 多腿策略要能以 basket / linked-order 方式回測，而不是單腿近似。
5. validation gate 要建立在 replay 產生的 trade log / fill log / equity curve 之上，再做 walk-forward、CPCV、DSR、PSR。

## 5. 建議目標架構

### 5.1 單一事件驅動 Replay Kernel

新增一個歷史重放層，將 `data/ticks` 或 parquet 歷史資料轉成和 live 相同的 event stream：

1. `HistoricalEventFeed`
2. `ReplayClock`
3. `ReplayExecutionVenue`
4. `FundingSettlementEngine`
5. `BacktestRecorder`

這一層的責任是：

1. 依歷史時間順序送出 `MARKET` / `FUNDING` 事件。
2. 讓現有 `Strategy`、`PortfolioManager`、`ExecutionHandler` 直接接事件。
3. 在模擬撮合器裡決定 fill、partial fill、cancel、fee、latency。
4. 將交易日誌、部位、權益、風控事件完整落盤。

### 5.2 優先採用「同碼 replay」而不是繼續擴寫 `run_backtest.py`

`scripts/run_backtest.py` 適合當研究報表腳本，但不應繼續承擔「高擬真回測」責任。建議把它降級為：

1. 報表產生器
2. 參數掃描入口
3. 呼叫正式 backtest engine 的 wrapper

真正的回測邏輯應搬到 `backtesting/engine.py` 或類似模組，直接重用現有 live 元件。

### 5.3 Nautilus 的定位

建議分兩段：

1. 短中期：先在現有專案內完成 replay engine，讓大部分策略先實現同碼與正確記帳。
2. 中長期：對 `ASMarketMaker` 與任何 order-book-driven 策略，接入 Nautilus 或等價的 L2/L3 撮合框架，專門處理 queue priority、book walk 與微結構回測。

原因是目前 `backtesting/nautilus_backtest.py` 還只是 skeleton，若直接全量切過去，專案風險高、交付時間長。

## 6. 分策略改善方案

### 6.1 AS Market Maker

目標：從 bar proxy 升級為真實掛單回測。

必做項目：

1. 使用歷史 order book / trade tick 重建 decision-time 的 best bid/ask 與深度。
2. 訂單建立後必須「掛在簿上」，直到成交、撤單或改價。
3. 模擬 post-only rejection，若價格穿價則 reject，而不是偷轉 taker。
4. 模擬 queue position 與 partial fill。
5. 模擬 quote refresh latency、cancel latency 與 market data latency。
6. 將 maker fee / rebate、inventory carry、mark-to-mid 與 fill-to-fill PnL 分開記錄。

建議指標：

1. Quote fill rate
2. Quote lifetime
3. Realized spread
4. Inventory half-life
5. Adverse selection after fill
6. Cancel-to-fill ratio

### 6.2 Funding Carry

目標：從單一 funding 序列升級為 delta-neutral 雙腿投組模擬。

必做項目：

1. 同時模擬 spot 腿與 perp 腿。
2. 計入兩腿各自 fee schedule。
3. 在 funding settlement 時點實際入帳 funding cashflow。
4. 計入 basis 變化與對沖殘差。
5. 加入 rebalance drift 邏輯，而不是只看時間。
6. 依 OKX 合約規格處理最小下單量、lot size 與 contract value。

建議指標：

1. Funding PnL
2. Basis PnL
3. Hedge drift
4. Rebalance turnover
5. Net carry after fees

### 6.3 Pairs Trading

目標：從 spread 報酬近似升級為雙腿 linked execution。

必做項目：

1. 支援 basket order / linked order。
2. 允許兩腿不同時成交，並記錄 legging risk。
3. 對 beta 對沖數量做 contract rounding。
4. 將進出場條件建在實際可成交價格，而非純 mid/spread。
5. 記錄 entry slippage、hedge slippage、residual beta exposure。

建議指標：

1. Spread convergence PnL
2. Hedge slippage
3. Residual delta exposure
4. Time-to-hedge
5. Legging loss

## 7. 驗證層改善

### 7.1 保留 CPCV / Walk-Forward，但輸入改為 replay 結果

`CPCV` 與 `WalkForward` 的方向是對的，尤其 `CPCV` 已經有 per-test-block purge/embargo 與 path-level aggregation。這部分應保留，但 `strategy_fn` 不該再直接吐一條報酬序列，而應該：

1. 接收 train / test 資料切片
2. 在 train slice 做參數校準
3. 在 test slice 啟動 replay engine
4. 由 replay engine 回傳 trade log、fill log、equity curve、returns

這樣 CPCV 衡量的才是「可執行策略」的 OOS 表現，而不是「理論報酬函數」的 OOS 表現。

### 7.2 新增 execution-quality validation

除了 Sharpe / DSR / PSR，建議加上：

1. Fill rate 誤差：backtest vs shadow/demo
2. Slippage 誤差：backtest vs shadow/demo
3. Signal-to-fill latency 分布誤差
4. Inventory / exposure 分布誤差
5. Per-trade PnL 分布的 KS test

## 8. 實作路線圖

### Phase 0：修 blocker，讓同碼回測有基礎

預估 3-5 天。

交付：

1. 修正 shadow mode，支援真正的 Sim vs demo 對照。
2. 補上模擬 fill event 回寫流程。
3. 修正 `PositionLedger` reversal accounting。
4. 修正 `PortfolioManager.update_return()`。
5. 為以上項目補 unit tests。

### Phase 1：建立歷史事件重放回測核心

預估 1-2 週。

交付：

1. `HistoricalEventFeed`
2. `ReplayClock`
3. `BacktestRunner`
4. `BacktestRecorder`
5. 可讓現有 `ASMarketMaker` / `PairsTradingStrategy` / `FundingCarryStrategy` 跑在 replay bus 上

### Phase 2：模擬撮合器升級

預估 1-2 週。

交付：

1. queue-aware maker fill model
2. partial fill / cancel / amend
3. latency model
4. fee / funding / settlement model
5. 可校準參數檔，來源為 shadow / demo 統計

### Phase 3：多腿策略回測能力

預估 1-2 週。

交付：

1. basket / linked order abstraction
2. funding carry 雙腿回測
3. pairs 雙腿對沖回測
4. legging risk 指標報表

### Phase 4：正式 validation pipeline

預估 1 週。

交付：

1. replay-based walk-forward
2. replay-based CPCV
3. promotion gate report
4. backtest vs shadow calibration dashboard

## 9. 驗收標準

建議把「可升級到實盤前一階段」的條件寫死：

1. 所有策略回測都必須產出 fill log、order log、equity curve、fees、funding cashflow。
2. AS 做市策略至少在一段 L2 歷史資料上跑過 queue-aware replay。
3. Funding carry 與 pairs 一律以雙腿成交紀錄驗證，不接受單腿近似。
4. CPCV / walk-forward 的 OOS 結果來自 replay，而非手寫 return proxy。
5. shadow / demo 對照中，fill rate、slippage、latency 的誤差落在預設門檻內。

## 10. 優先順序建議

若要以投資報酬率排序，我建議：

1. 先修 Phase 0 blocker。
2. 再做 Phase 1 replay kernel。
3. 優先把 ASMarketMaker 搬到高擬真回測。
4. 接著補 funding carry 的雙腿與 funding settlement。
5. 最後補 pairs 的 linked execution 與 Nautilus 深化。

原因很直接：目前做市策略對 execution realism 最敏感，funding carry 對記帳與 cashflow 最敏感，pairs 則對多腿 execution 最敏感。三者共通底盤先完成，後續擴充成本最低。

## 11. 結論

目前專案最大的優勢，不是已有多少策略，而是已經具備 live engine、strategy abstraction、portfolio 與統計驗證工具。離「盡可能模擬實盤」差的，不是再多一個指標，而是少了一個把歷史資料轉成真實事件並走完整交易鏈路的 replay execution layer。

最務實的方向是：

1. 停止擴寫 `scripts/run_backtest.py` 這類手工近似回測。
2. 先在現有架構內完成同碼 replay backtest。
3. 用 shadow / demo 校準模擬撮合器。
4. 再把最依賴微結構的策略接上 Nautilus 級別的 L2 回測。

這樣做，回測結果才會真正接近未來上線時會看到的成交品質、庫存風險與權益曲線。

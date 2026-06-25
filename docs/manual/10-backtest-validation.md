# 回測與驗證 gate

這章解釋：為什麼一個「回測很漂亮」的策略**還不能**上線。本專案把過擬合當成頭號敵
人，所以在回測與上線之間放了一串 gate。這章講每個 gate 的**意義與理由**；精確門檻與
硬規則以 `docs/ai_collaboration.md` 為準（連結在最後）。

## 為什麼需要 gate

歷史回測只證明「這組參數在過去這段資料上看起來賺錢」。在大量嘗試下，純靠運氣也能挑
出漂亮曲線。gate 的目的是把「真 edge」和「過擬合的幻覺」分開。

## 各 gate 的意義

| Gate | 在防什麼 | 為什麼重要 |
|---|---|---|
| **Replay 引擎** | 用事件驅動 replay（含 maker 費、滑價、部分成交、取消延遲）取代理想化撮合 | 理想化成交會高估 edge；replay 逼近真實執行 |
| **Walk-forward** | 非重疊 IS/OOS 視窗滾動 | 證明參數不是只 fit 單一區間 |
| **CPCV** | Combinatorial Purged Cross-Validation（López de Prado） | 多路徑 OOS + purge/embargo，擋 train/test 洩漏 |
| **DSR / PSR** | Deflated / Probabilistic Sharpe Ratio | 依「嘗試次數」對 Sharpe 打折，懲罰大海撈針 |
| **honest `n_trials`** | DSR 必須餵入**誠實**的嘗試次數（按假設家族累計，非單次 grid 數） | 低報 `n_trials` 會灌水 DSR，讓假 edge 過關 |
| **idealized-fill 排除** | `fill_all_signals` / `strategy_fill` 等理想化成交產物 | 這類產物是 capacity/敏感度工具，**不得**當 edge 證據 |
| **differential validation** | 用外部 reference 引擎（vectorbt/backtrader）重核訊號邏輯 | 抓「實作把策略做歪」的 bug |
| **ct_val provenance** | SWAP 的合約乘數必須來自權威來源（DB/交易所結構性恆等） | ct_val 是 PnL/notional/funding/margin 的線性乘子，錯了 PnL 偏差可達 10–1000 倍 |

> **核心觀念（honest `n_trials`）**：在誠實計數下，沒有真 edge 的想法期望通過數 ≈ 0；
> 有真 edge 的想法期望嘗試 ≈ 1/(真 edge 基率)。真正的槓桿是**先驗品質**，不是試更多
> 次。把重試假裝成「新家族」來繞過計數，就是降標準。

## 「驗證通過」不等於「可上線」

即使 CPCV/DSR 過了，仍要經過 replay/shadow、demo、人類批准等**部署 gate**（見「部署
階段 gate」章）。本手冊與引擎都**不會**自動把策略推上線——上線是使用者的決定。

## 真值來源 / 延伸閱讀

- 回測正確性 Gate、部署 Gate、ct_val 來源檢查、differential validation 的精確條文：
  `docs/ai_collaboration.md`。
- DSR/PSR 的程式介面與門檻：`README.md`（Replay Validation 段落）、`analytics/dsr.py`。
- 不變量與失敗模式：`docs/INVARIANTS.md`、`docs/FAILURE_MODES.md`。

> 本章只解釋「為什麼」。任何數字門檻（例如 DSR/PSR ≥ 0.95）與硬規則以
> `docs/ai_collaboration.md` 為準。

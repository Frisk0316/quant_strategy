# 策略與其參數

這章逐一說明**目前啟用（`enabled: true`）**的策略：它的經濟想法，以及每個參數的意義
與設計理由。**真值來源一律是 `config/strategies.yaml`**——本章不寫死數字當權威，數字
請以該 config 為準。

> 其他策略（`pairs_trading`、`xs_momentum`、`s5_residual_meanrev`、`s6_ts_momentum`、
> `s7_basis_meanrev`、`fear_greed_sentiment`、`cme_gap_fill`）目前 `enabled: false`，
> 屬於研究/未驗證候選，不在本章「啟用」範圍。策略假設請見
> `research/strategy_synthesis.md`。

## funding_carry — 資金費套利（delta-neutral）

**想法**：同時持有現貨多單 + 永續空單，賺 8 小時 funding，不吃方向風險。

| 參數 | 意義 | 設計理由 | 真值來源 |
|---|---|---|---|
| `perp_symbol` / `spot_symbol` | 永續 / 現貨標的 | carry 需要對應的現貨腿 | `config/strategies.yaml` |
| `min_apr_threshold` | 進場最低年化 funding | 低於門檻時 funding 不足以覆蓋成本/風險 | 同上 |
| `rebalance_drift_threshold` | 現貨/永續名目偏移多少才再平衡 | 保持 delta-neutral，但避免過度交易吃成本 | 同上 |
| `max_abs_basis_z` | basis z-score 過極端就擋進場 | basis 已偏離時進場，回歸風險高 | 同上 |
| `max_crowding` | 擁擠度 proxy 上限 | 擁擠交易反轉風險高 | 同上 |
| `funding_check_interval_secs` | funding 輪詢秒數 | WS 更新間用 REST 補抓 funding | 同上 |

## ma_crossover / ema_crossover — 均線交叉（long/flat 基準）

**想法**：快線上穿慢線做多、下穿轉平。屬技術指標基準線，也是 differential validation
的參考策略。

| 參數 | 意義 | 設計理由 | 真值來源 |
|---|---|---|---|
| `symbols` | 適用標的 | 指定在哪些 perp 上跑 | `config/strategies.yaml` |
| `fast_window` / `slow_window`（MA） | 快/慢均線視窗（bar 數） | 快慢差決定訊號靈敏度與雜訊 | 同上 |
| `fast_span` / `slow_span`（EMA） | 快/慢 EMA 跨度 | EMA 對近期價格加權，較 MA 靈敏 | 同上 |
| `indicator_db_warmup` | 指標是否用 DB 暖機 | 預設 false，讓指標 artifact 對齊策略冷啟動語義 | 同上 |

## macd_crossover — MACD 交叉

**想法**：MACD 線與 signal 線交叉作為進出場。

| 參數 | 意義 | 設計理由 | 真值來源 |
|---|---|---|---|
| `fast_span` / `slow_span` | MACD 的快/慢 EMA 跨度 | 兩者差形成 MACD 線 | `config/strategies.yaml` |
| `signal_span` | signal 線 EMA 跨度 | MACD 與 signal 交叉產生進出訊號 | 同上 |
| `indicator_db_warmup` | 指標是否用 DB 暖機 | 同上：對齊 marker/strategy parity | 同上 |

## 共通參數

| 參數 | 意義 |
|---|---|
| `enabled` | 是否啟用此策略 |
| `td_mode` | OKX 交易模式（如 `cross`） |

## 真值來源 / 延伸閱讀

- 參數實際值：`config/strategies.yaml`（唯一真值來源）。
- 策略假設與研究理由：`research/strategy_synthesis.md`。
- 新策略接入規範（後端/前端/contract 四點）：`docs/ai_collaboration.md`、
  `docs/FEATURE_MAP.md`。

> 改策略假設要先更新研究/設計文件再實作；不要只憑本手冊或聊天記憶改參數語義。

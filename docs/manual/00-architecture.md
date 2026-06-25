# 系統架構總覽

這一章幫你建立全局心智圖：資料怎麼進來、訊號怎麼變成下單、風控在哪一層把關。
看完這章，後面每一章的參數你都能對到「它在哪個環節、為什麼存在」。

## 事件流（從市場到成交）

整個交易引擎是事件驅動的（`asyncio.Queue` 當 EventBus）：

```text
MARKET → SignalGenerator → SIGNAL → PortfolioManager → ORDER → ExecutionHandler → FILL
                                                                      │
                                                          DrawdownTracker + RiskGuard
```

- **SignalGenerator**：把市場資料（K 線、funding、外部特徵）轉成「想做多/做空/平倉」
  的 signal。策略邏輯住在這裡。
- **PortfolioManager**：把 signal 變成實際下單數量（sizing：vol-target、quarter-Kelly、
  fixed-fractional），並維護持倉狀態。
- **ExecutionHandler**：把 order 送進 broker（live 是 OKX、回測是 SimBroker/replay、
  shadow 是兩者並行）。所有單預設 `post_only`（maker-only）。
- **RiskGuard / DrawdownTracker**：在下單前後檢查名目、槓桿、回撤、日內虧損，必要時
  擋單或啟動 kill switch。

> **設計理由（maker-only / post-only）**：本專案目標資本 $1k–$10k，吃 OKX VIP0 費率。
> taker 費率會讓純 taker 策略在這個資本級別數學上不可行，所以預設只掛 maker 單；
> 價格穿價的 post-only 被拒（error 51026）會被記錄並丟棄，**絕不**改用市價單追。

## 模組地圖（`src/okx_quant/`）

| 模組 | 職責 |
|---|---|
| `core/` | config（Pydantic v2）、events（dataclass）、bus（asyncio） |
| `data/` | REST client、order book、market data handler、candle store（TimescaleDB） |
| `signals/` | regime（HMM/GARCH/CUSUM）、technical / external-feature 訊號輔助 |
| `strategies/` | funding_carry、pairs_trading、technical_indicators、external_features… |
| `portfolio/` | sizing、positions、portfolio_manager |
| `risk/` | risk_guard、drawdown_tracker、circuit_breaker |
| `execution/` | broker（OKX / Sim / Shadow）、execution_handler、order_manager、replay |
| `analytics/` | performance（Sharpe/MDD/…）、dsr（DSR/PSR） |
| `api/` | FastAPI server、routes_backtest / live / config / data、WebSocket |
| `backtesting/`（repo 根） | replay 引擎、CPCV、walk-forward、differential validation |

## 資料層（兩套並行、由 canonical 橋接）

| 層 | 舊系統（OKX-only） | 新系統（多交易所） |
|---|---|---|
| K 線儲存 | `raw_candles` | `market_klines` |
| 策略可讀 | `canonical_candles` ← 回測讀這裡 | 由 `canonicalize.py` 提升 |
| Funding | `funding_rates` | `market_funding_rates` |

> **為什麼有兩套**：OKX 資料同時鏡寫兩套以維持向後相容；Binance/Bybit 只落在新的
> `market_*`，必須先 `canonicalize.py` 提升到 `canonical_candles` 回測才讀得到。
> 多交易所/point-in-time universe 的設計理由見 `docs/DATA_FLOW.md`。

## 真值來源 / 延伸閱讀

- 完整架構與 CLI 流程：`README.md`（Architecture / Full Backtest Workflow 段落）。
- 檔案所有權與功能對應：`docs/FEATURE_MAP.md`。
- 資料流與 ingestion：`docs/DATA_FLOW.md`。

> 本手冊是「為什麼這樣設計」的入口；任何規則細節以上述 source docs 與 `config/`
> 為準。若手冊與它們衝突，以 source docs 為準。

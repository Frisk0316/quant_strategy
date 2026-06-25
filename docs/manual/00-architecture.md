# 系統架構

本專案是事件驅動的量化交易與回測系統。使用者操作主要走 dashboard/API；研究、驗證與部署判斷則以 repo 內文件與 artifacts 為準。

## 核心流程

```text
Market data -> SignalGenerator -> PortfolioManager -> ExecutionHandler -> FILL
                                                    -> RiskGuard / DrawdownTracker
```

| 模組 | 職責 |
| --- | --- |
| `core/` | 設定、事件、事件匯流排 |
| `data/` | exchange client、order book、market data、candle store |
| `signals/` | regime、technical、external-feature signal helpers |
| `strategies/` | 策略實作與 signal 產生 |
| `portfolio/` | sizing、positions、portfolio manager |
| `risk/` | risk guard、drawdown tracker、circuit breaker |
| `execution/` | broker、order manager、replay/shadow/live execution |
| `analytics/` | performance metrics、DSR/PSR helpers |
| `api/` | FastAPI routes for dashboard and offline tools |
| `backtesting/` | replay、walk-forward、CPCV、differential validation |

## 重要界線

- Dashboard 是操作與檢視面，不是部署核准。
- `research/` 是 Claude ownership；Codex 不應任意修改。
- `config/`、risk、deployment gate 的變更需要明確批准。
- 任何策略是否可 demo/shadow/live，必須回到 `docs/ai_collaboration.md` 的 Gate。

---
status: current
type: manual
owner: human
created: 2026-06-25
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# 策略與參數

策略 runtime 參數主要在 `config/strategies.yaml`。`enabled: true` 只代表系統會載入或允許使用該策略，不代表它通過部署 Gate。

## 目前常見策略

| 策略 | 用途 | 狀態提醒 |
| --- | --- | --- |
| `funding_carry` | spot/perp delta-neutral carry | 需要 funding、basis、crowding 與 execution evidence |
| `pairs_trading` | ETH/BTC 類 pairs spread | 目前 disabled；不能當成已驗證 |
| `ma_crossover` | moving-average crossover baseline | active baseline；需 differential validation |
| `ema_crossover` | EMA crossover baseline | active baseline；需 differential validation |
| `macd_crossover` | MACD signal baseline | active baseline；需 differential validation |
| `xs_momentum` | cross-sectional momentum research | disabled；research-tier until coverage and validation pass |
| `s5_residual_meanrev` | residual mean-reversion research candidate | disabled；Stage 3 caveated |
| `s6_ts_momentum` | time-series momentum research candidate | disabled；statistical pass is not promotion pass |
| `s7_basis_meanrev` | basis mean-reversion research candidate | disabled；currently refuted/non-passing |
| external-feature strategies | Fear & Greed、CME gap 等外部資料策略 | external data freshness and missingness matter |

## 參數閱讀規則

- 策略假設來源是 `research/strategy_synthesis.md` 或使用者明確指示。
- `indicator_db_warmup` 影響圖表/indicator artifact 連續性，不應默默改變策略 signal 語意。
- Disabled strategy 的參數只能當成配置草稿，不是部署或績效結論。
- 改策略行為時，通常需要測試、validation artifact、handoff，以及 Claude review。

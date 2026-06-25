# 風控限制

這章說明 RiskGuard / DrawdownTracker 在每筆下單前後檢查的限制：每個限制**在防什麼**、
**為什麼設成這種等級**。**真值來源是 `config/risk.yaml`**；本章不寫死數字當權威，請以
該 config 為準。

> 設計脈絡：目標資本 $1k–$10k。風控偏保守，寧可少做也不要一次爆掉。部分硬上限在程式
> 內，無法在 runtime 被覆蓋（見 `README.md` Live Deployment Gates）。

## 下單與部位限制

| 參數 | 意義 | 設計理由 | 真值來源 |
|---|---|---|---|
| `max_order_notional_usd` | 單筆下單名目上限 | fat-finger 防呆：限制單筆暴露，擋下單數量打錯 | `config/risk.yaml` → `risk.max_order_notional_usd` |
| `max_pos_pct_equity` | 單一標的部位佔總權益上限 | 避免單一標的集中度過高 | 同上 |
| `max_leverage` | 最大槓桿（部位名目/權益） | 控制爆倉風險與保證金壓力 | 同上 |
| `stale_quote_pct` | 下單價偏離最新 mid 超過此值就拒 | 擋過期報價/異常價下單 | 同上 |

## 回撤與日內虧損

| 參數 | 意義 | 設計理由 | 真值來源 |
|---|---|---|---|
| `max_daily_loss_pct` | 日內虧損達此比例 → 當日停止所有交易 | 把單日最大傷害封頂 | `config/risk.yaml` |
| `soft_drawdown_pct` | 軟回撤：所有策略 size 乘數減半 | 回撤初期先降風險，不直接全停 | 同上 |
| `hard_drawdown_pct` | 硬回撤：平掉所有部位 + 冷卻期 | 觸及深回撤時保本、強制冷靜 | 同上 |
| `hard_stop_cooldown_hours` | 硬停後到可手動重置的冷卻時數 | 防止剛爆完就情緒性重啟 | 同上 |

## 斷路器（circuit breakers）

| 參數 | 意義 |
|---|---|
| `ws_reconnect_circuit_threshold` / `ws_reconnect_window_secs` | 滾動視窗內 WS 重連次數超過門檻 → 觸發斷路 |
| `rest_error_rate_circuit_threshold` / `rest_error_rate_window` | REST 錯誤率超標 → 觸發斷路 |

> **設計理由（斷路器）**：連線/REST 異常常是市場或基礎設施出狀況的前兆。寧可暫停，也
> 不要在資料/連線不穩時繼續送單。

## 真值來源 / 延伸閱讀

- 風控參數實際值：`config/risk.yaml`（唯一真值來源）。
- 硬上限與部署 gate（max order notional、daily loss、drawdown、leverage、kill
  switch）：`README.md`（Live Deployment Gates）。
- 業務規則（sizing / 風控語義）：`docs/DOMAIN_RULES.md`、`docs/INVARIANTS.md`。

> 改風控限制屬業務規則變更：要更新 `docs/DOMAIN_RULES.md` 並走 Change Manifest，且
> 部署相關 gate 的變更需使用者明確批准。

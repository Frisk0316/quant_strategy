# 風控限制

風控設定主要在 `config/risk.yaml`。這些限制保護實盤、demo、shadow 與 replay 設定，不應為了讓回測更漂亮而任意放寬。

## 交易與曝險限制

| 參數 | 說明 |
| --- | --- |
| `max_order_notional_usd` | 單筆訂單名目金額上限，避免 fat-finger |
| `max_pos_pct_equity` | 單一商品最大倉位佔 equity 比例 |
| `max_leverage` | 最大槓桿 |
| `stale_quote_pct` | 訂單價格相對最新 mid 的允許偏離 |

## 停損與 circuit breaker

| 參數 | 說明 |
| --- | --- |
| `max_daily_loss_pct` | 當日虧損超過門檻時停止交易 |
| `soft_drawdown_pct` | soft drawdown 後降低策略 sizing |
| `hard_drawdown_pct` | hard drawdown 後關閉倉位並進入 cooldown |
| `hard_stop_cooldown_hours` | hard stop 後允許人工 reset 前的等待時間 |
| `ws_reconnect_circuit_threshold` / `ws_reconnect_window_secs` | WebSocket reconnect circuit breaker |
| `rest_error_rate_circuit_threshold` / `rest_error_rate_window` | REST error-rate circuit breaker |

## 回測特殊項

- `backtest.fill_all_signals` 是 research-only idealized mode。
- idealized fill 可以用來看容量或 execution sensitivity，但不可滿足 deployment gate。
- 改風控或 sizing rule 時，需檢查 `docs/DOMAIN_RULES.md`、`docs/INVARIANTS.md`，必要時補 Change Manifest。

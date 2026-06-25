# 設定檔對照

`config/` 是 runtime 設定來源之一。任何會改變 live、shadow、demo、risk、sizing、execution gate 的設定，都需要明確使用者批准。

| 檔案 | 主要內容 | 注意事項 |
| --- | --- | --- |
| `config/settings.yaml` | system mode、symbols、storage backend、Timescale DSN、primary exchange、market data instruments、clock sync | `storage.primary_exchange` 會影響 backtest data source；live deployment to exchange X 需要對應 evidence |
| `config/strategies.yaml` | funding carry、pairs、MA/EMA/MACD、XS/S5/S6/S7、external feature strategies | `enabled: false` 的策略不可視為已部署；研究策略仍需 gate |
| `config/risk.yaml` | max order notional、position/equity cap、leverage、daily loss、drawdown、circuit breaker、backtest execution controls | `fill_all_signals` 是 research-only idealized mode |
| `config/universe.yaml` | research universe rules，例如 top-N、ADV、warmup、rebalance、deny-list | point-in-time universe evidence 仍需 coverage/validation |
| `config/instrument_specs.yaml` | local instrument spec fallback | DB-backed or explicit authoritative `ct_val` provenance is required for promotion evidence |

## 實務規則

- 修改 config 前，先確認 owning docs: `docs/FEATURE_MAP.md`、`docs/DATA_FLOW.md`、`docs/DOMAIN_RULES.md`。
- 改 business rule 時需依 Doc Sync Harness 補 Change Manifest。
- 不要把 local fallback config 說成 exchange-authoritative evidence。
- 不要把 disabled strategy 的參數解讀成已驗證或可部署。

---
status: current
type: manual
owner: human
created: 2026-06-25
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# 回測與驗證 Gate

回測結果要能被引用，必須有可追溯 artifact，並清楚標示驗證狀態。單次漂亮績效不是 edge evidence。

## 常見 Gate

| Gate | 說明 |
| --- | --- |
| Replay backtest | 使用 replay engine 產生 price、equity、fills、result artifacts |
| Walk-forward | 依時間切 train/test，檢查 OOS 表現 |
| CPCV | Combinatorial Purged Cross-Validation，用 purge/embargo 降低 leakage |
| DSR / PSR | 檢查 Sharpe 是否仍能承受多次嘗試與統計不確定性 |
| honest `n_trials` | 人工調參、grid sweep、未保留 artifact 的嘗試都要算入 |
| differential validation | 用 reference engine 交叉檢查 signal logic |
| source data validation | 檢查 artifact 資料來源、DB parity、funding/external observations |
| `ct_val` provenance | SWAP 回測必須知道 contract value 來源是否 authoritative |

## 不可當作 promotion evidence

- `validation_status: in_sample`
- `validation_status: naive_backtest`
- `fill_all_signals: true`
- `idealized_fill: true`
- `execution_profile: strategy_fill`
- `execution_profile: dual_output`
- 任何 skip 的 validation check

## 使用者檢查順序

1. 看 `result.json` 的 `validation_status`、`validation`、`execution_profile`。
2. 看 Validation Lab 或 validation artifact 的 pass/fail/skip。
3. 看 `docs/AI_HANDOFF.md` 與 `docs/CURRENT_STATE.md` 是否仍列阻擋項。
4. 若要往 demo/shadow/live，回到 `docs/ai_collaboration.md` 的部署 Gate。

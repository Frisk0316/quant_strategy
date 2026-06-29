# 部署 Gate

部署 Gate 的主來源是 `docs/ai_collaboration.md`。本專案不得只因為某次回測績效漂亮，就宣稱策略可以 demo、shadow 或 live。

## 基本順序

| Stage | 必要條件 |
| --- | --- |
| Historical backtest | 必須有可追溯 artifact；`in_sample` 或 `naive_backtest` 不可當作 edge 或 promotion evidence |
| Walk-forward / CPCV | 必須通過 train/test leakage 檢查；CPCV 需要誠實回報 `n_trials`，且 DSR/PSR gate 需達標 |
| Idealized fill exclusion | `fill_all_signals`、`idealized_fill`、`strategy_fill`、`dual_output` 不可滿足部署 Gate |
| Differential validation | active/declared strategy 需依 contract 產出 portable validation evidence |
| Replay / shadow | 需有人類核准 replay/shadow 條件，並檢查 order、fill、fee、funding、equity artifacts |
| OKX demo | 需人類核准 demo，並確認風控、監控與 rollback |
| Live | 需人類明確核准；必須保留 kill switch 與 rollback path |

## 不可跳過的限制

- 不可用 chat memory 改變策略假設；策略假設來源是 `research/strategy_synthesis.md` 或使用者明確指示。
- 不可把 idealized execution artifact 當成 live readiness。
- 不可在沒有所有 gate 與人類核准時宣稱 live ready。
- 不可變更 live、shadow、demo 或 deployment gate，除非使用者明確批准。

## 使用者核對方式

- 先看 artifact 的 `validation_status`、`validation`、`execution_profile`。
- 再看 Validation Lab 的 pass/fail/skip；skip 不是 pass。
- 最後回到 `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`、`docs/KNOWN_ISSUES.md` 確認是否仍有阻擋項。

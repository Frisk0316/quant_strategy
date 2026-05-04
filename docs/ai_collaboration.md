# Codex 與 Claude 協作手冊

本文件定義本專案同時使用 Codex 與 Claude 時的分工、交接、驗證與部署規範。目標是提高研究與實作速度，同時避免檔案互相覆蓋、策略假設漂移、回測結果不可重現，或把未驗證策略推上 demo/live。

## 核心原則

1. **單一真相來源**：策略假設、驗證門檻與部署條件必須落在 repo 內的文件，不以聊天紀錄為準。
2. **研究與實作分流**：Claude 優先做研究推理、策略審查與風險檢查；Codex 優先做程式修改、測試、回測流程與部署檢查。
3. **小步交付**：每次只改一個明確範圍，完成後留下可審查的 diff、測試指令與結論。
4. **不直接 live**：任何策略即使回測漂亮，也必須經過成本模型、walk-forward/CPCV、demo/shadow 與風控 gate。
5. **保護使用者變更**：任何 AI 都不得重置、覆蓋或刪除不屬於自己本輪工作的變更。

## 角色分工

| 角色 | 主要責任 | 建議輸出 | 避免事項 |
| --- | --- | --- | --- |
| Claude | 文獻整理、策略假設、統計與風險審查、lookahead/overfit 檢查、部署前第二審 | strategy spec、review notes、risk memo、問題清單 | 直接改動核心交易程式、同時修改多個實作模組 |
| Codex | 程式實作、測試、回測腳本、config 檢查、部署 checklist、修 bug | code diff、test result、implementation notes、PR/commit 摘要 | 根據聊天記憶擅自改策略假設、跳過測試後宣稱可部署 |
| 使用者 | 決定策略優先級、資金風險、是否進入 demo/shadow/live | 明確批准、資金上限、部署窗口 | 同時要求兩個 AI 修改同一檔案同一段邏輯 |

## 單一真相來源

| 資訊類型 | 權威檔案 |
| --- | --- |
| 策略假設與研究理由 | `research/strategy_synthesis.md` 或 `research/strategy_synthesis_zh.md` |
| 回測與實盤一致性改善 | `docs/backtest_live_parity_plan.md` |
| AI 協作規範 | `docs/ai_collaboration.md` |
| 專案執行方式與部署階段 | `README.md` |
| 策略參數 | `config/strategies.yaml` |
| 風控限制 | `config/risk.yaml` |
| 交易模式與環境 | `config/settings.yaml` |

如果聊天內容與 repo 文件衝突，以 repo 文件為準。若要改變策略假設，先更新研究或設計文件，再實作。

## 建議工作流

### 1. 研究到實作

1. Claude 先把策略整理成可測試假設：
   - signal definition
   - entry/exit rule
   - sizing rule
   - execution assumption
   - risk stop
   - validation path
2. Codex 將假設轉為任務清單與實作 diff。
3. Codex 跑單元測試、回測或最小可重現檢查。
4. Claude 審查 Codex 的 diff 與回測結果，特別檢查：
   - lookahead bias
   - survivorship/data leakage
   - fee/slippage/missed-fill 模型
   - overfit risk
   - strategy spec 是否被實作歪掉
5. 使用者決定是否進入 demo/shadow。

### 2. Bugfix 到部署

1. Codex 先重現 bug 或定位不一致行為。
2. Codex 實作最小修補，補測試。
3. Claude 做風險審查，確認修補沒有改變策略語義或風控假設。
4. Codex 跑部署前檢查。
5. 使用者批准後才能切換到更高風險模式。

## 檔案所有權與避免衝突

同一時間只讓一個 AI 修改同一個 ownership area。

| Area | 建議主責 | 路徑 |
| --- | --- | --- |
| Research/spec | Claude | `research/` |
| Backtesting engine/report | Codex | `backtesting/`, `scripts/run_backtest.py`, `scripts/run_replay_backtest.py` |
| Strategy implementation | Codex | `src/okx_quant/strategies/`, `src/okx_quant/signals/` |
| Risk and sizing | Codex with Claude review | `src/okx_quant/risk/`, `src/okx_quant/portfolio/` |
| Deployment/config | Codex with user approval | `config/`, `scripts/run_live.py`, `scripts/run_shadow.py`, `docker/` |
| Collaboration docs | Either, but one editor at a time | `docs/ai_collaboration.md`, `AGENTS.md`, `CLAUDE.md` |

如果 Claude 與 Codex 都需要改同一區域，先由一方完成並提交/交接，另一方再接手。

## Git 與 Worktree 建議

最穩定的協作方式是把 Claude 與 Codex 放在不同 branch 或 worktree。

```bash
git checkout -b codex/implementation-task
git worktree add ../quant_strategy_claude claude/research-task
```

建議命名：

| 用途 | Branch pattern |
| --- | --- |
| Claude 研究整理 | `claude/research-*` |
| Claude 審查筆記 | `claude/review-*` |
| Codex 實作 | `codex/impl-*` |
| Codex 修 bug | `codex/fix-*` |
| 部署準備 | `codex/deploy-*` |

每次交接前都應提供：

```text
Owner:
Branch/worktree:
Changed files:
Intent:
Tests/checks run:
Known risks:
Next recommended action:
Do not touch:
```

## 交接模板

### Claude 交給 Codex

```text
Task:
Strategy/spec source:
Required behavior:
Files likely affected:
Validation required:
Risk concerns:
Acceptance criteria:
```

### Codex 交給 Claude

```text
Implementation summary:
Diff scope:
Assumptions made:
Tests/checks run:
Backtest/result artifacts:
Questions for review:
Deployment readiness:
```

## 回測正確性 Gate

策略進入 demo/shadow 前，至少要確認：

1. 資料時間區間、時區與 symbol 對齊。
2. 沒有用未來資料產生當下 signal。
3. OKX maker/taker fee、spread、slippage、missed fill 或 maker-only 約束有被納入。
4. Walk-forward 或 CPCV 沒有 train/test leakage。
5. DSR/PSR 或等價的過擬合檢查有被記錄。
6. Trade log、fill log、equity curve 可以重現。
7. 策略參數來自文件或 config，不是隱藏在 notebook/chat 裡。

## 部署 Gate

任何 live 之前必須完成以下階段：

1. Historical backtest
2. Walk-forward 或 CPCV
3. Replay 或 shadow 檢查
4. OKX demo
5. 小資金 live
6. 才能擴大資金

部署前檢查：

| Check | Requirement |
| --- | --- |
| Mode | `config/settings.yaml` 明確顯示目標模式，且使用者已批准 |
| Secrets | `.env`、API key、passphrase 沒有被 commit |
| Risk | `config/risk.yaml` 有 max notional、drawdown、kill switch |
| Execution | live 預設 maker-only；taker 只允許明確風險出場 |
| Observability | logs、metrics、Telegram alert 或等價告警可用 |
| Rollback | 有回到 shadow/demo 或停止 engine 的明確步驟 |

## AI 提示詞範本

### 給 Claude

```text
請根據 repo 內的 docs/ai_collaboration.md 與 research/strategy_synthesis.md 審查這個策略或 diff。
請優先檢查策略假設、資料洩漏、lookahead bias、過度擬合、成本模型與 live 風險。
不要直接修改核心交易程式；請輸出可交給 Codex 實作的具體問題清單與 acceptance criteria。
```

### 給 Codex

```text
請根據 docs/ai_collaboration.md、research/strategy_synthesis.md 與相關 config 實作這個任務。
請先檢查工作區是否有既有變更，只修改本任務需要的檔案。
完成後請列出 changed files、測試指令、結果、假設與部署風險。
未通過回測/測試/風控 gate 前，不要宣稱可 live。
```

## 衝突處理

如果兩個 AI 產出衝突：

1. 保留兩邊 diff，不要重置工作區。
2. 以 `research/strategy_synthesis.md`、`docs/backtest_live_parity_plan.md`、config 與測試結果作為裁決依據。
3. 若是策略假設衝突，先讓 Claude 審查並更新 spec。
4. 若是程式行為衝突，讓 Codex 補測試後用測試結果裁決。
5. 使用者決定是否採納高風險變更。

## 最小完成定義

一個 AI 任務完成時，至少應留下：

1. 明確 changed files。
2. 實作或研究摘要。
3. 已跑的測試/回測指令與結果。
4. 沒跑測試時的原因。
5. 剩餘風險或下一步。


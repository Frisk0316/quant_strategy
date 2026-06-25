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
4. Walk-forward 或 CPCV 沒有 train/test leakage；每筆 backtest artifact 必須附帶 `validation_status`，判定規則見 [`research/strategy_synthesis.md#validation-status-convention`](../research/strategy_synthesis.md#validation-status-convention)。
5. DSR/PSR 或等價的過擬合檢查有被記錄；promotion 需 DSR >= 0.95、PSR >= 0.95，且 `n_trials` 誠實申報。
6. Trade log、fill log、equity curve 可以重現。
7. 策略參數來自文件或 config，不是隱藏在 notebook/chat 裡。

## 部署 Gate

任何 live 之前必須完成以下階段：

| Stage | Requirement |
| --- | --- |
| Historical backtest | 必須有可重現 artifact 與 `validation_status`；`in_sample` 或 `naive_backtest` 不得勾選此 gate、不得引用為 edge evidence、不得作為 promotion 依據。 |
| Walk-forward 或 CPCV | 必須由 `validation_status: walk_forward` 或 `validation_status: cpcv` artifact 滿足；不得有 train/test leakage。CPCV 必須誠實申報 `n_trials`，且 DSR >= 0.95、PSR >= 0.95。 |
| Idealized fill 排除 | 任何 `result.validation.fill_all_signals == true`（或同義的 `result.validation.idealized_fill == true`、`execution_profile == "strategy_fill"`、`execution_profile == "dual_output"`）的 artifact，不論 `validation_status` 為何，皆 **不得勾選任何 Deployment Gate stage**、不得引用為 edge evidence、不得作為 promotion 依據。`fill_all_signals` / `strategy_fill` 是 research-only 的 capacity / execution sensitivity 工具，`dual_output` 是診斷比較摘要，禁止當作 live readiness 證據；理由與排除清單見 `research/strategy_synthesis.md#validation-status-convention`。 |
| Differential validation | 每個 active/declared 策略都必須在 `backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS` 宣告至少一條可攜到外部 reference engine 的驗證路徑；已由 user 顯式退役且不再出現在 UI/API/contract 的策略，不屬於 promotion scope。技術指標策略（`ma_crossover`、`ema_crossover`、`macd_crossover`）目前已實作 vectorbt / backtrader signal-logic reference：在 `results/<run_id>/validation/<validation_id>/validation_result.json` 中，至少有一個 reference engine（vectorbt 或 backtrader）回報 `engines.<engine>.comparison.signal_logic.status == "PASS"` 且 `engines.<engine>.comparison.signal_logic.actionable_mismatch_count == 0`。Scope 限定 **signal-logic only**：indicator/signal 方向與時序差異列入；PnL、equity、metric mismatches 為 advisory，不阻擋本 gate。Advisory scope（`trade_execution` / `pnl_semantics` / `metrics`）mismatch 不自動 FAIL Differential validation gate，但 reviewer 可在 promotion ADR 引用非零 `actionable_mismatch_counts` 作為拒絕或暫緩理由；advisory 表示「不自動 gate fail」，不是「可忽略」。非技術策略不得再以永久 `not applicable` 結案；vectorbt/backtrader 的 artifact signal replay 只能證明外部引擎可重播 artifact signals 與 OHLCV 時間軸，`reference_role: advisory`，不得讓 `portable_validation_gate` 通過。若完整 reference adapter 尚未實作，`portable_validation_gate.passed` 必須為 `false`，並以 `adapter_required_engines` 或 `blocked_reason: only_advisory_reference_replay_completed` 標示 blocking gap；promotion ADR 必須把它列為 blocking gap 或由使用者顯式批准並更新本 gate 條文。**無 override**：FAIL 為硬性阻擋，不接受 reviewer attestation 推翻；如需排除須由 user 顯式批准並更新本 gate 條文。**追溯適用**：適用於所有 active/declared 現存與未來策略 artifact；現存 artifact 若未跑 differential validation、未產出必要欄位，或 `portable_validation_gate.passed != true`，不得作為 promotion evidence。本 gate 與「Idealized fill 排除」、下節「ct_val 來源檢查」皆為獨立必過項目，互不取代。 |
| Replay 或 shadow 檢查 | 必須使用同碼 replay 或 shadow 對照，並保留 fill log、order log、equity curve、fees、funding cashflow。 |
| OKX demo | 需要使用者批准，且 demo 期間風控、告警、rollback 可驗證。 |
| 小資金 live | 需要使用者再次批准，使用明確資金上限與 kill switch。 |
| 擴大資金 | 只能在前述階段均通過、Claude/使用者複核後進行。 |

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

### Deployment gate：ct_val 來源檢查

### Differential validation：資料來源與結論輸出

`backtesting/differential_validation.py` 必須在每次 validation artifact 中輸出 `source_data_validation` 與 `validation_conclusion`。
`source_data_validation` 至少檢查 artifact 層級的 `price_series.csv` OHLCV 結構、必要 artifact 是否存在、funding artifact 是否存在（策略需要時）、funding cashflow 公式、external-feature observations（策略需要時）、以及 `ct_val` provenance 欄位。
若未設定 `DIFF_VALIDATION_ENABLE_DB_PARITY=1` 與 DSN，`checks.db_parity.status`、需要 funding 的 `checks.funding_db_parity.status`、以及需要外部資料的 `checks.external_observations_db_parity.status` 必須明確為 `SKIP`，不得宣稱 DB parity 已通過；目前 `price_series.csv` 的 DB parity 以 timestamped close 對 canonical close 證明同源，artifact OHLCV 結構另由 artifact-level check 檢查，funding rates 與 external_observations 則各自由對應 DB parity 檢查。
`validation_conclusion.status == "ADVISORY_ONLY"` 表示外部引擎已能重播/匯出 advisory evidence，但仍不是 promotion evidence。

任何 SWAP backtest 在進入 live / shadow / demo gate 前，**必須通過 ct_val provenance gate**：

- 來源：`result.validation.ct_val_sources` 與 `result.validation.ct_val_all_authoritative`（自 2026-05 起由 `backtesting.replay._attach_ct_val_provenance()` 寫入 result.json）。
- Venue tag: `result.validation.exchange` and each `ct_val_sources[<symbol>].exchange`
  must identify the run's execution venue. A PASS attests the `ct_val` for that
  symbol on that venue, not just for the canonical symbol name.
- **Authoritative sources**：`db`（從 `venue_instrument_specs(exchange, symbol)` 查得，驗證過的權威值）、`config_override`（呼叫端顯式傳入 instrument_specs）、`spot_unit`（USDT 現貨對的恆等 1.0）、`exchange_base_unit`（Binance/Bybit 一般 USDT-M perp 的結構性 base-unit 合約恆等 1.0；`1000...` 乘數合約不適用，必須走 DB spec）。
- **Non-authoritative sources**：`registry`（讀自 `config/instrument_specs.yaml`，OKX-only bundled fallback）、`hardcoded_btc_eth`（離線情境下的 0.01 兜底）。
- Gate 規則：
  - **PASS** ⇔ `ct_val_all_authoritative == true` 且 provenance 的 `exchange` 與本次 run 的 execution venue 一致（即所有 swap symbol 的 ct_val 都來自 `db`、`config_override` 或適用的 `exchange_base_unit`，且不是錯用其他 venue 的規格）。
  - **FAIL** 時必須拒絕該回測進入 live/shadow/demo gate；如要 override 必須在 PR 描述顯式說明每個 non-authoritative symbol 的核對方式，並由 human reviewer 顯式 approve。

理由：ct_val 是 PnL / notional / funding / margin / liquidation 公式的線性乘子。非權威來源（即使 0.01 對 BTC/ETH 是真實值）在交易所改規格時會 silently drift，造成 backtest 與真實環境 PnL 偏差 10–1000 倍。CLAUDE.md hard rule 已要求 ct_val 一定要在公式裡，這條 gate 進一步要求它必須是「verified upstream」的值。

## 衝突處理

如果兩個 AI 產出衝突：

1. 保留兩邊 diff，不要重置工作區。
2. 以 `research/strategy_synthesis.md`、`docs/backtest_live_parity_plan.md`、config 與測試結果作為裁決依據。
3. 若是策略假設衝突，先讓 Claude 審查並更新 spec。
4. 若是程式行為衝突，讓 Codex 補測試後用測試結果裁決。
5. 使用者決定是否採納高風險變更。

## 新策略接入規範

撰寫新的策略時，必須同時完成下列三個接入點，才算完成：

1. **後端 `routes_backtest.py`**：在 `allowed` 集合加入策略名稱，實作對應的 `_run_<strategy>_job` 函式，確保 `result.json` 符合 ADR-0002 schema（必含 `run_id`、`created_at`、`strategies`、`symbols`、`bar`、`start`、`end`、`metrics`、`artifacts`，metrics 必含 `total_return`、`sharpe`、`max_drawdown`、`order_count`、`fill_rate`、`bankrupt`）。
2. **前端 `data.js`**：在 `STRATEGIES` 陣列加入策略描述物件（含 `id`, `name`, `tag`, `desc`）。
3. **前端 `view-config.js`**：加入對應的 UI 控制項（universe、bar、參數欄位等），並在 `StrategyParams` 加入說明文字。
4. **Reference portability contract**：在 `backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS` 宣告此策略可由哪些 reference engine 驗證、目前狀態是 `implemented`、`adapter_required` 或 `not_targeted`、需要哪些 artifact，以及限制。新增策略若缺此 contract，單元測試必須失敗，且不得進入 review 或 demo/shadow 流程。

不符合上述四點的策略，視為未完成，不得進入 review 或 demo/shadow 流程。

### 驗證專用策略

標示 `tag: "Validation"` 的策略設計目的為煙霧測試與系統驗證，**不具備 demo/shadow/live 資格**，亦不得通過部署 Gate。若需將驗證結果用於策略研究，必須在 `research/strategy_synthesis.md` 說明其限制。

目前已知的驗證專用策略：

| 策略 | 目的 | 已知偏差（intentional，禁止「修正」） |
| --- | --- | --- |
| `daily_winner` | 驗證 DB 每日聚合、交易生成、metrics 與前端 artifact 串接 | 不得用於 live trading；顯示用成本來自合併 `cost_rate`（fee+slip 不分開），不可視為純手續費 PnL；validation 必須顯式指定 `wf`/`cpcv`/`both`，`validation=none` 不自動生成 WF/CPCV；trades 欄位非 ADR-0002 fills schema；1D 資料僅支援 Postgres（無 parquet fallback） |

## Human Review Overview

當 AI 產生的計畫或治理工作一次牽涉多份 source docs 時，agent 必須在
`docs/human_overviews/` 新增或更新一份 Human Review Overview。

這份 overview 是給人類看的決策與審核入口，必須列出 source docs、風險等級、需要
人類拍板的決策點、不能只看摘要的必讀章節、AI 尚未驗證的 unknowns，以及測試 /
doc impact / schema 驗證狀態。

overview **不取代 source docs**。若兩者衝突，以 source docs 為準，且 overview 必須
把衝突講出來。何時必須建立、責任分工與優先順序的完整規則見
[`AI_OUTPUT_CONTRACT.md`](AI_OUTPUT_CONTRACT.md)；總索引見
[`review_index.md`](review_index.md)；格式檢查為
`python scripts/docs/check_human_overview.py`。

## 最小完成定義

一個 AI 任務完成時，至少應留下：

1. 明確 changed files。
2. 實作或研究摘要。
3. 已跑的測試/回測指令與結果。
4. 沒跑測試時的原因。
5. 剩餘風險或下一步。


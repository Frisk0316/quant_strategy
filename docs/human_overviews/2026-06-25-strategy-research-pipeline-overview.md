---
status: deprecated
type: human_review_overview
owner: human
created: 2026-06-25
last_reviewed: 2026-07-12
topic: "Strategy Research Pipeline Stage 1"
source_docs:
  - docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md
  - docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md
  - docs/superpowers/pipeline/driver.md
  - docs/superpowers/pipeline/stage1-hypothesis.md
  - docs/superpowers/pipeline/stage2-feasibility.md
  - docs/superpowers/pipeline/stage3-implement-backtest.md
  - docs/superpowers/pipeline/shortlist-template.md
  - docs/change_manifests/2026-06-25-family-cumulative-n-trials.md
decision_required: true
risk_level: medium
human_must_read:
  - docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md
  - docs/ai_collaboration.md
  - docs/change_manifests/2026-06-25-family-cumulative-n-trials.md
superseded_by: docs/human_overviews/2026-07-12-project-diagnosis-overview.md
expires: none
---

# Human Review Overview: Strategy Research Pipeline Stage 1

> Superseded on 2026-07-12. The first full cycle and later checkpoints have run;
> current evidence and pending human decisions are in the project diagnosis overview.

## 1. 這次在做什麼？

建立一條「按一次就跑到短名單」的策略研究管線（Stage 1）。使用者啟動一個預先登記
的批次（第一批 = `[S7, S5, S6]`，來自 `strategy_synthesis.md` 未實作 backlog），由
一個 Claude session 當 driver，對每個候選依序跑：文獻→假設 → 可行性檢查 →
實作+回測，中間不用人逐步下 prompt。跑完停在**一個** Claude 證據審查關卡，再產出
一份短名單交使用者決定是否發布。重點是省 prompt，不是放寬標準。

## 2. 為什麼要做？

原本「找文獻 → 評估 → 進回測系統 → 正式回測篩 gate → 發布」每一步都要使用者手動
下 prompt 叫 Claude/Codex 接手，太人工。這次把這條鏈接成有界自動化，但刻意只做
Stage 1（單 session、現有 backlog、一個檢查點、手動啟動），把更難的背景平行化與
排程留到後續階段。

## 3. 本次產生 / 修改了哪些文件？

| 文件 | 用途 | 必讀程度 | 備註 |
|---|---|---|---|
| docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md | 設計 spec + 8 條 locked 決策 + n_trials 政策 | 必讀 | status 仍 `draft`，等使用者複審 |
| docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md | 實作計畫（Task 1 程式 + Task 2–4 文件） | 建議讀 | Task 1 是唯一 trading-core 改動 |
| docs/superpowers/pipeline/driver.md | driver 啟動程序與停止條件 | 建議讀 | runbook |
| docs/superpowers/pipeline/stage1-hypothesis.md | 研究 subagent 任務模板 | 可略讀 | 機器/agent 用 |
| docs/superpowers/pipeline/stage2-feasibility.md | 可行性 subagent 任務模板 | 可略讀 | 機器/agent 用 |
| docs/superpowers/pipeline/stage3-implement-backtest.md | Codex 實作+回測 subagent 模板 | 可略讀 | 機器/agent 用 |
| docs/superpowers/pipeline/shortlist-template.md | 每批短名單格式 | 可略讀 | 證據彙整格式 |
| docs/change_manifests/2026-06-25-family-cumulative-n-trials.md | n_trials 改成 family 累計的 change manifest | 必讀 | 直接影響 overfit gate |

> 註：S5/S6/S7 的策略實作與 backtest 檔案（`src/okx_quant/strategies/s5..s7`、
> `backtesting/s5..s7_*`）目前是 working tree 內的 untracked 改動，屬於 pipeline
> 第一批的 Stage 3 產物，**本 overview 未審查、未驗證它們**（見 §7）。

## 4. 這次真正的決策點

| 決策 | 預設選擇 | 為什麼 | 是否需要人類批准 |
|---|---|---|---|
| 批准 Stage 1 管線設計 | 等待（spec 仍 draft） | spec 自述等使用者複審後才轉實作計畫 | yes |
| 啟動第一批 `[S7, S5, S6]` 跑 pipeline | 尚未啟動 | 跑了才會有任何 gate 證據；啟動需填 `runtime_cap`（無靜默預設） | yes |
| 通過候選是否「發布」成 `enabled:false` | pending | 發布權只在使用者；不自動上線 | yes |

## 5. 主要風險

| 風險 | 為什麼重要 | 對應防線 | 是否已機器檢查 |
|---|---|---|---|
| `n_trials` 被低報 → DSR 灌水 | overfit gate 失效、假 edge 進短名單（S11 就是這樣壞的） | family 累計 n_trials（plan Task 1）+ invariant + 守門測試 | 部分：測試已寫，但本 session 未執行 |
| 把重試 relabel 成新 family 繞過 K / deflation | 變相降標準 | 檢查點① Claude 判定 + driver hard rule | 否（人為判定，尚未沉澱成自動 invariant） |
| 把「機器已建好」誤讀成「策略已驗證」 | 幻覺、誤導發布決定 | 本 overview §7 明列 unverified；發布定義限 `enabled:false` | N/A |
| 跑 pipeline 的 compute 成本失控 | 預算超支、批次跑不完 | `runtime_cap` 啟動時必填，超過則乾淨中止 | 否 |

## 6. 不能只看摘要的地方

這批改動碰到 overfit gate 的核心會計（`n_trials` → DSR/PSR），屬於不能只看摘要的
類別。高風險審查時，人類必須打開：

- **`docs/superpowers/specs/...-design.md` 第 2 段**（family ledger + trial-count
  協定 + 停止條件）與 **`docs/change_manifests/2026-06-25-family-cumulative-n-trials.md`**
  ——確認 n_trials 是從帳上算出來、不是程式常數。
- **`docs/ai_collaboration.md` 的回測/部署 Gate 條文**——這條 pipeline 重用既有
  DSR≥0.95 / PSR≥0.95、idealized-fill 排除、differential validation、ct_val
  provenance gate；要確認它**重用**而非**改動**這些 gate。
- 任何「某候選通過了」的宣稱——必須打開該批 `results/<batch_id>/` 證據 artifact 與
  `HYPOTHESIS_LEDGER.md` / `EXPERIMENT_REGISTRY.md`，不能只信短名單摘要。

## 7. AI 尚未驗證 / 不確定的地方

- **本 session 尚未執行此 pipeline。沒有任何策略通過 gate，也沒有任何 edge 宣稱。**
- S5/S6/S7 的 Stage 3 實作（working tree untracked 檔案）本 overview **未審查**，
  無法保證 leak-free、n_trials 誠實、或 differential/ct_val gate 狀態。
- 計畫 Task 1（`scan_xs_momentum` 加 `prior_family_n_trials`、餵 family 累計值進
  CPCV）是否已 land 並通過 `tests/unit/test_xs_momentum_backtest.py`，本 session
  未跑、未確認。
- 兩段式回測（parquet 預篩 → DB CPCV）的實際 compute 成本未知。
- 「試幾次才會過」沒有固定答案；spec 明說期望多數候選被 refute，那是 gate 在運作，
  不是失敗。

## 8. 測試與檢查狀態

| 檢查 | 狀態 | 指令 / 證據 |
|---|---|---|
| unit tests | not run | 本 overview 任務未改 trading-core；pipeline 自身的 `tests/unit/test_xs_momentum_backtest.py` 由 Codex 在實作時負責 |
| doc impact | pass | `python scripts/docs/check_doc_impact.py`（本 overview 批次無 impact-matrix 觸發） |
| schema validation | not run | lifecycle metadata（`check_doc_metadata.py`）僅 advisory，非本任務範圍 |
| human overview check | pass | `python scripts/docs/check_human_overview.py` |

## 9. 對現有系統的影響

- **策略邏輯**：無。pipeline 不改任何已啟用策略；S5/S6/S7 仍是待跑、待審的 backlog
  候選。
- **回測**：間接。計畫 Task 1 改 `scan_xs_momentum` 的 `n_trials` 來源為 family
  累計——這是把計數**誠實化、變嚴格**，不是放寬。
- **資料**：無。
- **execution**：無。
- **risk**：無。
- **live / demo / shadow gate**：無。spec 明文「不改任何 deployment/demo/shadow/live
  gate」；發布權在使用者。
- **UI / API**：無。發布定義限 `enabled:false` 已驗證候選，未上線。
- **文件與 handoff**：是。`docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md` 已登記此
  pipeline；`research/strategy_synthesis.md` 指向第一批順序 `[S7, S5, S6]`。

## 10. 下一步

- **人類**：複審 spec（仍 draft）；決定是否啟動第一批 `[S7, S5, S6]`（需給
  `runtime_cap`）；之後對通過候選做發布決定。
- **Claude**：擔任 driver session；在檢查點① 用 `REVIEW_QUESTIONS.md` /
  `CRITIQUE_PROTOCOL.md` + `ai_collaboration.md` gate 條文審證據；產短名單；審查
  S5/S6/S7 Stage 3 diff 的 leak / n_trials 誠實性。
- **Codex**：實作計畫 Task 1（family 累計 n_trials）並跑
  `tests/unit/test_xs_momentum_backtest.py`；按 stage3 模板實作候選並產 gate 證據
  artifact。
- **何時停止 / 升級給人類**：family 撞重試上限 K（預設 2）、撞 `runtime_cap`、或出現
  任何需要放寬 gate 才能過的情況——一律停止並升級，不得自行放寬。

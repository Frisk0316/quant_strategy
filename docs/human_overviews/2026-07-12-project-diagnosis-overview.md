---
status: current
type: human_review_overview
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
topic: "Whole-project diagnosis and follow-up ordering"
source_docs:
  - tasks/2026-07-12-project-diagnosis-followup-tasks.md
  - docs/CURRENT_STATE.md
  - docs/AI_HANDOFF.md
  - docs/KNOWN_ISSUES.md
  - config/workstreams.yaml
  - docs/FAILURE_MODES.md
  - docs/INVARIANTS.md
  - tasks/2026-07-12-claude-p0-review.md
  - docs/change_manifests/2026-07-12-artifact-id-containment.md
  - docs/change_manifests/2026-07-12-ct-val-validation-contract.md
  - docs/change_manifests/2026-07-12-venue-fail-closed.md
decision_required: false
risk_level: high
human_must_read:
  - tasks/2026-07-12-project-diagnosis-followup-tasks.md
  - docs/ai_collaboration.md
  - docs/ADR/0003-position-pnl-accounting.md
  - docs/ADR/0007-multi-venue-instrument-specs.md
  - docs/change_manifests/2026-07-12-artifact-id-containment.md
  - docs/change_manifests/2026-07-12-ct-val-validation-contract.md
  - docs/change_manifests/2026-07-12-venue-fail-closed.md
superseded_by: null
expires: none
---

# Human Review Overview: Whole-project diagnosis and P0 closure

## 1. 這次在做什麼？

以協作文件、accepted ADR、Feature/Data/UI maps、目前 Git 狀態與可執行檢查為依據，
盤點專案完成/進行/blocked 狀態；立即修復低風險且可重現的 UI、測試與治理 harness
問題；把涉及 money path、資料 provenance、受保護 differential validation 或 Git
integration 的問題整理成有明確 ownership、scope 與驗收的後續任務。

後續 Claude review 與使用者決策已完成；Codex 已依批准範圍實作 P0.1-P0.3，並同步
H-012 SHELVE/no-retry 與 H-013 Stage-1 sign-off。沒有修改 research 或既有 results。

## 2. 為什麼要做？

原本 `CURRENT_STATE`/`AI_HANDOFF`/Progress 仍描述已提交的工作為 uncommitted，推薦的
standalone server 又缺 Manual router。基線同時有一個 unit 與一個 integration 紅燈，
`docs-impact --strict` 在 Git 失敗時還會假裝「沒有變更」。這些問題會讓人類與下一個
AI session 依錯誤狀態工作。

## 3. 本次產生 / 修改了哪些文件？

| 類別 | 來源 / 產出 | 用途 |
|---|---|---|
| 後續任務 | `tasks/2026-07-12-project-diagnosis-followup-tasks.md` | P0→P2 順序、permitted files、驗收 |
| 當前真相 | `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `config/workstreams.yaml` | clean-start/目前 diff、完成/blocked/next |
| Durable gaps | `docs/KNOWN_ISSUES.md`, `docs/FAILURE_MODES.md`, `docs/INVARIANTS.md` | 新發現的路徑、venue、ct_val 與 routing bug class |
| 導航/操作 | `FEATURE_MAP`, `UI_MAP`, `DATA_FLOW`, `RUNBOOK` | Manual/Progress owning path 與驗證方式 |
| P0 實作依據 | `tasks/2026-07-12-claude-p0-review.md` + 三份 Change Manifest | 批准契約、diff scope、測試與回滾證據 |
| 本 overview | 本檔 + `docs/review_index.md` | 人類審核入口 |

## 4. 這次真正的決策點

| 決策 | 已記錄結果 | 為什麼 | 狀態 |
|---|---|---|---|
| P0.1 artifact ID | 完整 API/library/CLI reject + containment | 防止 root escape 與 wrong-artifact truncation | 已實作；待獨立 diff review |
| P0.2 `ct_val` | finite、`>0`、`<=1e7`；provenance 分開由 R1.4/I16 管 | 支援合法 multiplier 並拒絕 NaN/corruption | 已實作；公式未變 |
| P0.3 venue | omitted/blank→config primary；explicit unknown→400 | 禁止靜默換 venue | 已實作 |
| P0.4 長分支 | Option B：先合併 5 個 main-only commits，再單一例外 PR | 96 ahead / 5 behind 需要可審計整合 | 已批准；未執行 |
| H-012 | SHELVE、no retry；E-037 不可作 promotion evidence | 統計弱且 hygiene 發現 F36 cost lag | 已記錄 |
| H-013/E-038 | Stage-1 approved；E-038 reserved-only | registry 不建立零試驗 double truth | 已記錄；Stage-2 未跑 |

## 5. 主要風險

| 風險 | 現況 | 防線 |
|---|---|---|
| 任意 artifact path | 已修；只接受 safe component 且 resolved-root contained | F30/I32 + API/library/CLI regression |
| `ct_val` NaN/合法 multiplier | 已修 numeric domain；provenance 規則未放寬 | F32/I34 + Manifest/ADR/money-path tests |
| venue typo讀錯資料 | 已修；queue 前 400 | F31/I33 + run/sweep request tests |
| E-037 turnover cost timing | runner 仍有 F36；策略已 shelved | 舊 artifact 不改；重用前另案修復並新建 experiment |
| repo 文件透過 UI 過度曝露 | 已修 | 只在 loopback standalone 開啟 workstream 明列、repo-contained `.md`；engine/non-loopback 不提供 file route |
| 狀態/測試假綠 | 已修主要根因 | synchronized state + fail-closed doc impact |
| 誤宣稱可部署 | 仍禁止 | collaboration gates + explicit human approval |

## 6. 不能只看摘要的地方

- `tasks/2026-07-12-project-diagnosis-followup-tasks.md` 的 P0.1–P0.4：這些是實際
  scope/acceptance，不可只依本 overview 執行。
- ADR-0003、ADR-0007 與 ct-val Manifest：numeric domain 已改為 `(0,1e7]`；
  promotion-grade provenance 仍由 R1.4/I16 管，不能把 numeric acceptance 當 authority。
- `docs/ai_collaboration.md` 的 Differential validation、ct_val provenance、promotion
  gates：任何研究結果都仍未取得 live/demo/shadow 資格。

## 7. AI 尚未驗證 / 不確定的地方

- P0.1/P0.2/P0.3 已本機實作與 targeted 驗證；尚未 commit/push/integrate，仍建議
  Claude 對完整 diff 做獨立 review。
- 沒有重跑或修改任何策略 experiment/result artifact。
- P0.4 Option B 已批准，但 5 個 main-only commits 尚未合併，也未跑 integration-commit
  的 `verify-full`。
- README/歷史 overview/archive、A11 validator、lab target 與新 tasks lifecycle enforcement
  仍屬 P1；ADR-0001/0006 的人類決策已記錄，不再是 open decision。
- 目前 Demo key 無效；本輪 browser smoke 使用 standalone server，不證明 engine mode。

## 8. 測試與檢查狀態

基線：full unit `661 passed, 1 failed`；integration `37 passed, 1 failed`。兩個紅燈已定位
為 Turtle 固定輸入的多餘單位猜測與 stale ADR-0007 測試。修復後 full unit
`666 passed`、integration `38 passed`；Ruff、12 個 Node syntax、docs/config、backtest
smoke、temporary 8081 API smoke 與 Manual/Progress browser flow 均通過。user-owned 8080
已由使用者決定棄用且未被本輪停止。

P0 最終驗證：targeted `306 passed, 1 skipped`、full unit `768 passed, 1 skipped`、
integration `38 passed`；full Ruff、docs metadata/links/overview、docs-impact strict、
config、backtest smoke 與 12 個 frontend syntax 均通過。Skip 是 Windows 無 symlink
權限；API smoke 因未設定 running server 明確 SKIP。可選 `validate-data` 因本機 legacy
parquet fixture 不存在而 advisory FAIL，不是 P0 行為失敗。完整記錄見 session handoff。

## 9. 對現有系統的影響

- 策略、signal、risk、execution、PnL、fee、funding、gate：無變更。Portfolio 僅修改
  shared `ct_val` numeric validator；所有 sizing/PnL caller 公式不變。
- DB schema、existing results：無變更。
- API/UI：新增 loopback-standalone-only 的 read-only Progress allow-list file route；
  engine/non-loopback 不提供 file route；standalone server 補 Manual route；Manual response
  不再顯示 lifecycle frontmatter。
- Harness：Git inspect failure 不再被 `docs-impact` 當成 clean；A9/A10 executable rules
  補齊，A11 明確保留給 dedicated ledger validator。
- API/artifacts：不安全 ID 改為明確拒絕；未知 venue 改為 400；omitted/blank venue
  解析為 config primary。這是 intentional fail-closed contract change。
- Docs/Progress：改為目前 commit/workstream 真相。

## 10. 下一步

1. 另開 Git task 執行已批准的 P0.4 Option B，並在 integration commit 跑
   `verify-full`；本輪不自動 merge/commit/push。
2. 完成 P1 governance/docs 與已批准的 liquidation unattended-mode task。
3. H-013/E-038 只另開 Stage-2 probe；Stage 3 尚未授權。
4. 最後補小型 browser/noise coverage；Demo key 仍由使用者建立。

任何需要放寬 gate、修改 protected money path、切 live/shadow/demo、或寫 existing results
的步驟都必須停止並另取明確批准。

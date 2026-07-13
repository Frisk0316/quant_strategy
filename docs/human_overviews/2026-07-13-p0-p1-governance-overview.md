---
status: current
type: human_review_overview
owner: human
created: 2026-07-13
last_reviewed: 2026-07-13
topic: "P0.4 integration, P1 governance, and the post-merge PR #9 follow-up"
source_docs:
  - tasks/2026-07-12-p04-integration-handoff.md
  - tasks/2026-07-12-p1-governance-docs-handoff.md
  - docs/change_manifests/2026-07-12-ct-val-validation-contract.md
  - docs/RUNBOOK.md
  - docs/DOC_IMPACT_MATRIX.md
  - tasks/2026-07-13-pr9-followup-fixes-session-handoff.md
decision_required: true
risk_level: high
human_must_read:
  - docs/change_manifests/2026-07-12-ct-val-validation-contract.md
  - docs/RUNBOOK.md
  - tasks/2026-07-13-pr9-followup-fixes-session-handoff.md
superseded_by: null
expires: none
---

# Human Review Overview: P0.4 整合 + P1 治理批次（含 Codex 審核修正）

## 1. 這次在做什麼？

把已審核通過的 P0 加固正式 commit 並以單一 integration-exception PR（#9）送
回 main；同時完成 P1.1 治理工具（lab 測試分離目標、A11 ledger 驗證器、tasks/
lifecycle 強制、overview 覆蓋人工步驟）與 P1.2 文件清理（README 瘦身、歷史
文件歸檔、CHANGELOG 補歷史）。Codex 審核後回報一個 money-path blocker 與多個
文件/工具漏洞，第一輪修補處理了共用 `ct_val` 驗證、RUNBOOK gate 條文、handoff
生命週期、A11 驗證器與 tasks checker。其後複審發現的 DB/registry/caller-spec
provenance、failed-fill atomicity、ledger parser 與 template 豁免漏洞均已修復並完成
全量驗證；follow-up PR 尚未建立。

## 2. 為什麼要做？

分支長期偏離 main（審計時 96 commits ahead），且審計發現信任邊界與治理帳本
缺口。若不整合並把治理檢查機器化，後續研究決策會建立在不可信的基線上。

## 3. 本次產生 / 修改了哪些文件？

- 程式：`src/okx_quant/portfolio/positions.py`（ct_val 驗證封閉）、
  `backtesting/replay.py`（provenance 前驗證）、
  `scripts/docs/check_ledger_consistency.py`（新增後強化）、
  `scripts/docs/check_doc_metadata.py`（tasks/ 強制＋凍結名單）、`Makefile`。
- 測試：`tests/unit/test_position_pnl_accounting.py`、`test_backtesting.py`、
  `test_ledger_consistency.py`（14）、`test_doc_metadata_tasks.py`（8）。
- 文件：`README.md`（897→101）、`docs/RUNBOOK.md`（操作細節集中＋gate 修正）、
  `docs/DOMAIN_RULES.md` R1.5、`docs/INVARIANTS.md` I34、ct_val Change
  Manifest 附錄、`docs/DOC_IMPACT_MATRIX.md` A11、CHANGELOG、狀態文件，
  以及 90+ 份歷史 tasks/ 文件的 lifecycle 歸檔。

## 4. 這次真正的決策點

1. PR #9 已由 PR head `00c7a51` 合併到 `main` 的 `b378e16`。五個後續修補
   commits 不在 PR #9，必須另開 follow-up PR；人類決策點改為審核該 follow-up。
2. K_limit 驗證器現在硬性要求 `== 2`；未來若要放寬 retry 政策，必須先改
   `docs/EXPERIMENT_REGISTRY.md` 條文與驗證器，屬 user 決策。
3. 歷史 tasks/ 文件全部標 `archived` —— 若有任何一份你認為仍是現行授權文件，
   請指出，我們改回。

## 5. 主要風險

- money-path 變更：`ct_val` 非法值現在會 raise 而非靜默通過/fallback。任何
  依賴舊行為的呼叫端會開始報錯 —— 全套 841 unit passed / 1 skipped ＋
  38 integration 綠燈，
  但線上/腳本呼叫端若餵髒值會 fail loud（這是設計目的）。
- RUNBOOK gate 條文改為指向 `docs/ai_collaboration.md`，刪除了 bar-proxy
  gate 與過時 `ctVal > 1` 說法；若有人依 README/RUNBOOK 舊條文操作，行為會
  不同（舊條文本來就是錯的）。
- 沒有任何 strategy/risk/execution 行為、部署 gate 或既有 result artifact
  被修改。

## 6. 不能只看摘要的地方

- `docs/change_manifests/2026-07-12-ct-val-validation-contract.md` 附錄 ——
  兩個封閉點的確切語義（缺值 fallback vs 明確值必驗）。
- `docs/RUNBOOK.md` 的 Live Deployment Gates 與 Replay gate 段 —— 確認新
  措辭沒有弱化任何 gate。

## 7. AI 尚未驗證 / 不確定的地方

- validate-data 在本機因薄 parquet 鏡像無法通過（環境限制，非程式問題）。
- api-smoke 需要運行中的伺服器，本批以 SKIP 回報。
- A11 驗證器不檢查 artifact 檔案存在性（誠實限制，已寫進輸出與矩陣）。

## 8. 測試與檢查狀態

Follow-up 最終驗證：unit 841 passed / 1 skipped（既有 Windows symlink 權限）；
integration 38；lab 18；Ruff、docs metadata/links/ledger、Human Overview、config
check、backtest smoke 全部通過；`DOC_IMPACT_BASE=00c7a51` strict 檢查 131 個變更
檔案通過。API smoke 未啟動 server，未作 live/deployment readiness 聲明。

## 9. 對現有系統的影響

回測/研究計算結果不變（合法 `ct_val` 走相同公式）；非法輸入從靜默錯誤變成
立即失敗。治理檢查從人工變成 `make docs-check`/`make verify` 的硬性項目。
README 不再是第二真相源。

## 10. 下一步

從 `codex/pipeline-batch1-stage3` 為五個 post-merge commits 加上本輪已驗證修補另開
follow-up PR，由人類審核與合併。之後：OKX liquidation unattended mode（Codex）、
E-038 Stage-2（獨立任務）、user 建立 OKX Demo key。

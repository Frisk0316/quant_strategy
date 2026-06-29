# 策略研究管線

策略研究管線（Strategy Research Pipeline）把「找文獻 → 評估可行性 → 做進回測系統 → 正式回測篩 Gate → 發布」接成有界自動化：使用者啟動一個預先登記的批次，按一次就跑到「通過 Gate 的短名單」，中間不用逐步下 prompt。重點是省人工，不是放寬標準。設計來源是 `docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md`（目前 `status: draft`）。

## 流程

```
使用者啟動批次 {candidates, runtime_cap, data_tier}
   │  ← 整批先寫進 ledger，過不過都算數
   ▼
driver（一個 Claude session），對每個候選依序派 subagent：
   ├─ Stage 1 文獻→假設   [研究 subagent]  → HYPOTHESIS_LEDGER (H-xxx)
   ├─ Stage 2 可行性檢查  [研究 subagent]  → 不過就 skip（記原因）
   ├─ Stage 3 實作+回測   [Codex subagent] → leak 回歸測試 + 兩段式回測
   ▼
  檢查點① Claude 證據審查   ← 唯一的自動化內人為關卡
   ▼  通過→短名單；沒過→ledger 記 refuted/shelved
  檢查點② 使用者決定發布   ← 發布只有使用者能按
```

## 各階段

| 階段 | 負責 | 產出 |
| --- | --- | --- |
| Stage 1 文獻→假設 | 研究 subagent | `HYPOTHESIS_LEDGER` 假設（含 family、可測 spec、grid、validation path） |
| Stage 2 可行性 | 研究 subagent | 資料可得性、相關性上限、成本後 edge 嗅探；FAIL 就 skip 並記原因 |
| Stage 3 實作+回測 | Codex subagent | trading-core 實作 + leak 回歸測試 + Gate 證據 artifact |
| 檢查點① | Claude | 用 `REVIEW_QUESTIONS.md` / `CRITIQUE_PROTOCOL.md` + 部署 Gate 條文審證據 |
| 檢查點② / 發布 | 使用者 | 通過者接進系統成 `enabled: false` 已驗證候選 |

## 關鍵規則

- **編排**：單 session + `subagent-driven-development` skill；不是新框架、不是 cron。
- **n_trials 按假設家族(family)累計**：family 的 `n_trials` = 該 family 歷來所有批次的 grid 組合數 + 重試次數總和，餵進 CPCV 算 DSR。防「跨 batch 拆小」「同 family 微調重試」兩種灌水。這是把計數變嚴格，不是放寬。
- **重試上限 K（預設 2）**：同一經濟機制重試 K 次仍不過 → shelve 並升級給使用者；不會無限調參。
- **兩段式回測**：parquet research-tier 預篩 → DB venue-scoped CPCV 正式。
- **發布定義**：通過者只接成 `enabled: false` 已驗證候選 + ledger 標 supported；**不自動上線、不碰任何 demo/shadow/live Gate**。真正 promote 仍走現有獨立、全門控、使用者批准的部署流程（見「部署 Gate」章）。
- **記錄載體**：長期真相寫 `HYPOTHESIS_LEDGER.md` + `EXPERIMENT_REGISTRY.md`；`results/<batch_id>/` 的 JSON 與短名單是可丟的 scratch，檢查點時對帳同步回 ledger。

## 目前狀態

- Stage 1 machinery（driver/templates、family 累計 `n_trials`、invariant I23）已建好；完整的自動 driver 編排尚未跑過。
- 第一批候選順序 `[S7, S5, S6]` 的 Stage 3 回測已單獨跑出 refit artifacts，**全部未通過 Gate**：S6 `statistical_gate_passed:false`、S7 `shelved_pending_research_review`、S5 為資料-universe artifact（非支持也非反駁）。
- 目前**沒有任何候選通過 Gate**，無 promotion / live / demo / shadow。S5/S6/S7 在「策略與參數」章仍列為 disabled 研究候選。

## 分階段路線圖

- **Stage 1**（現在）：單 session、現有 backlog、一個檢查點、手動啟動。
- **Stage 2 解鎖**：把檢查點① 的 leak / n_trials / DSR 不變量檢查沉澱成自動 invariant/測試後，才開背景平行 agent。
- **Stage 3 解鎖**：Stage 2 穩定 + 排程 cron/loop 自動執行 family 預算與停止條件 + 文獻搜索 ingestion 加品質過濾。

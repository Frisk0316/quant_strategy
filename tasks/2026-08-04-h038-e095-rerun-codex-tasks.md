---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# H-038 / E-095 rerun — Codex task

**使用者裁決 2026-08-04：E-094 是 contract error，F-S5 回到 K 1/2，授權重跑一次。**
依據：`tasks/2026-08-04-h038-wsc-claude-review.md` BLOCKER 1。E-094 的
`member_day_coverage == 1.0` 是無出處的 inline literal，比唯一前例
(`backtesting/taker_flow_probe.py` 的 0.95) 和 I11 (≥0.80) 都嚴，導致所有下游
檢定 NOT_EVALUATED、n_obs=0。E-095 修正這個 admissibility precondition 後重跑。

契約沿用 `tasks/2026-08-04-h038-residual-meanrev-stage2-codex-tasks.md` 全部條款
（PERMITTED/FORBIDDEN、breadth 實算、四項檢定、frozen params、無網格、無 Stage 3），
以下只列 **delta**：

## Delta 與 E-094 的差異

1. `backtesting/s5_residual_meanrev_probe.py`：把 1.0 literal 改成具名常數
   `MIN_MEMBER_DAY_COVERAGE = 0.95`，並在 artifact 中新增 provenance 欄位，
   內容指明來源：taker_flow_probe 前例 0.95、I11 ≥0.80、2026-08-04 使用者裁決。
   **只許改這個門檻與 provenance 輸出，其餘探針邏輯逐行不變。**
2. Frozen params 不變（E-014 SHA-bound：`BTC+ETH`, lookback 14, top_n 10,
   z_enter 1.5, z_exit 0.0），仍無網格搜尋。
3. Artifact 寫到新目錄 `results/h038_stage2_e095/`（E-094 的
   `results/h038_stage2_20260804/` 不可變，保留為紀錄）。
4. Registry 新增 E-095 列；H-038/K 行已由 Claude 預先更新為 1/2。
   **E-095 跑完後 K 記回 2/2 terminal，無論結果**——這次門檻有出處,
   資料若仍 FAIL 或統計 FAIL 就是家族的最終答案，不得再有 E-096。
5. `n_trials` 起始值仍為 registry-cumulative 72（E-094 未消耗 grid trials）。
6. 測試：更新 `tests/unit/test_s5_residual_meanrev_probe.py` —— 門檻常數與
   provenance 欄位各一個斷言;0.99994 coverage 現在必須 PASS data gate 進入
   distinctness。

## ACCEPTANCE CRITERIA（binary，在原任務清單之上追加）

- [ ] probe diff 只含門檻常數、provenance 輸出、對應測試
- [ ] artifact 含 provenance 欄位且 coverage 0.999942 通過 data gate
- [ ] E-094 目錄位元組不變
- [ ] ledger 記 E-095 結果並將 K 收回 2/2 terminal

## 預期

data gate 這次會過(0.999942 > 0.95),機制第一次真正被測量。power FAIL 機率仍高
(n_trials=72)——那是可接受的終局。**接近門檻也不得調整成本、breadth 或視窗。**

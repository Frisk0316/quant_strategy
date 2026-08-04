---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# H-038 F-S5-RESIDUAL-MEANREV Stage-2 probe — Codex tasks

**使用者授權 2026-08-04：「跑」。** 這是 F-S5 家族的最後一次迭代，K 將由 1/2 用到
**2/2**。無論結果為何，跑完之後這個家族永久關閉，不得再有重跑、retune 或第三次迭代。

Contract: `docs/HYPOTHESIS_LEDGER.md` H-038 列（family `F-S5-RESIDUAL-MEANREV`，
起始 `n_trials = 72`）＋ `docs/superpowers/specs/2026-07-29-literature-slate-h032-h037.md`
的迭代資格稽核表。正當性以 E-014 的記載為準：失敗原因是
"a data-universe artifact, not strategy refutation or support" —— 卡的是資料，
不是機制，而資料已在 ADR-0014 / ADR-0015 / 重建 PIT membership 之後修復。

## 最重要的一條（兩天前才踩到）

E-092 / E-093 剛推翻了 H-045 / H-046 —— 它們機械上報 Stage-2 PASS，是因為
**推定 breadth = 2 而沒有實際依據**，違反 ADR-0013；改回 breadth = 1 之後 MDS 高於
plausible Sharpe，正確判定是 power FAIL。

H-038 是橫斷面書，breadth > 1 在原理上站得住腳，**但必須從實際的 PIT universe 算出來，
不得沿用預設值、不得寫死、不得從標的總數推定**。具體要求：

- breadth = 樣本期間內**同時持有的名目平均數**，由實際成交/持倉序列計算，
  不是 universe 大小、不是網格假設。
- 計算方式、輸入序列、以及得到的數值必須寫進 artifact，並在 ledger 註記中複述。
- 如果 breadth 算不出來（持倉序列缺失、universe 重建失敗），**fail closed**：
  以 breadth = 1 判定，或直接判 data FAIL。不得推定。

## Task: 執行 H-038 / E-094 Stage-2 四項檢定

Task: 在修復後的資料宇宙上重跑 S5 殘差均值回歸書，跑完 ADR-0013 的四項 Stage-2
檢定，寫出 SHA-bound 不可變 artifact，並如實更新兩本 ledger。

### PERMITTED FILES

- `backtesting/s5_residual_meanrev_probe.py`（新增；Stage-2 探針，模式比照
  `backtesting/moneyness_vol_probe.py`）
- `backtesting/pipeline_stage2_registry.py`（僅新增 H-038 的註冊列）
- `tests/unit/test_s5_residual_meanrev_probe.py`（新增）
- `docs/HYPOTHESIS_LEDGER.md`、`docs/EXPERIMENT_REGISTRY.md`（結果列）
- `results/h038_stage2_20260804/`（新增 artifact）
- `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`、`config/workstreams.yaml`（收尾）

### FORBIDDEN

- `src/okx_quant/strategies/s5_residual_meanrev.py` —— **既有策略實作不得修改**。
  這是迭代的重點：換資料，不換機制。改了機制就不再是 H-038。
- `src/okx_quant/signals/`、`risk/`、`portfolio/`、`execution/`、`config/risk.yaml`
- 任何既有的 `results/**` artifact（只新增）
- 任何參數網格搜尋、任何 Stage 3

SCOPE LIMIT: 只做 Stage 2。Stage 3 需要另外的明確授權。

### 必要行為

1. **資料**：ADR-0014 source-aware canonical candles ＋ ADR-0015 economic-asset
   aliases ＋ 重建後的 PIT membership。任何缺口 fail closed，不得以鄰近標的替代。
2. **四項檢定**（依序，任一 FAIL 即停止，不繼續往下）：
   - data：universe 覆蓋率、member-day 完整性，逐筆對帳並記錄實際數字
   - distinctness：對 E-014 以及家族內既有參考序列的相關性
   - cost：net-of-cost，成本假設要與最近幾次探針一致並在 artifact 中明列
   - power：`min_detectable_sharpe(breadth=<實算>, n_obs=<實際>,
     n_trials=<registry-cumulative，起始 72>, periods_per_year=<實際>)`
3. **Artifact**：`results/h038_stage2_20260804/stage2_feasibility.json`，含四項
   檢定的輸入與輸出、breadth 推導、SHA-256。寫入後不可變。
4. **Ledger**：H-038 列更新為實際 outcome；E-094 新增至 registry。
   **K 記為 2/2，family status 記為 terminal**，無論通過與否。

### REQUIRED ON COMPLETION

- `git diff --stat`
- 貼出：`python -m pytest tests/unit/test_s5_residual_meanrev_probe.py -v` 尾段
- 貼出：實際 artifact 的完整 JSON 與其 SHA-256
- 貼出：`python scripts/docs/check_ledger_consistency.py` 結果
- `ruff check` 新增檔案
- **明確回報 breadth 的實算值與推導方式**

### ACCEPTANCE CRITERIA（binary）

- [ ] `src/okx_quant/strategies/s5_residual_meanrev.py` 的 diff 為空
- [ ] breadth 由實際持倉序列算出，artifact 中有推導；未推定、未寫死
- [ ] 四項檢定各有記錄的輸入數字，不是布林值
- [ ] power 檢定使用 registry-cumulative `n_trials`，起始值 72
- [ ] artifact 有 SHA-256 且未修改任何既有 `results/**` 檔案
- [ ] 兩本 ledger 記錄 K 2/2 與 terminal 狀態
- [ ] 無網格搜尋、無 Stage 3、無 promotion 或 deployment 宣稱
- [ ] diff 只含 PERMITTED FILES

REPORT: 變更檔案、測試輸出尾段、artifact JSON + SHA、breadth 推導、
做過的假設、任何 UNCONFIRMED 或跳過的項目。

## 預期

power FAIL 的機率高 —— `n_trials = 72` 的 DSR 門檻極嚴，而最近 7 個候選全部死在
這一關。那是可接受的結果：K 的用途就是用一次預先登記的檢定把家族收掉，
而不是讓它無限期懸著。**不得因為快要過關就調整成本假設、breadth 或視窗。**

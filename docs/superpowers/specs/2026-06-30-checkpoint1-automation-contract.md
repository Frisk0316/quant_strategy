---
status: draft
type: design
owner: human
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# 檢查點① 自動化契約 — 可自動 vs 必須人審 + invariant / 測試契約

> 對應 [strategy-research-pipeline-design.md](2026-06-25-strategy-research-pipeline-design.md)
> 的 **Stage 2 解鎖條件**:「把檢查點① 的 leak / n_trials / DSR 不變量檢查沉澱成自動
> invariant/測試(不再每次需 Claude)→ 才開背景平行 agent」。
> 本文件把那 9 項檢查切成「機械可判定」與「必須人審」兩半,給前者定 invariant +
> 測試契約 + 一支 aggregator checker(讓 Codex 實作),後者明確保留為人為關卡。
> `status: draft` = 等使用者複審後才交 Codex。本文件不改任何 demo/shadow/live gate。

## 1. 目的與 scope

- **目的**:讓 Stage 3 回測證據出來後,「機械可判定的部分」由一支 checker 一次跑完
  並產出機器可讀結果,Claude/人只需審「剩下需要判斷的部分」。這是把人從
  *per-candidate 每項都看* 降到 *per-candidate 只看判斷項*,並解鎖背景平行(編排 B)。
- **scope**:新增一支 checker 腳本 + 一條 invariant + 一個對帳檔。**不碰** trading-core、
  回測引擎演算法、deployment/demo/shadow/live gate。promotion gate 門檻**不放鬆**。
- **核心區分原則**:能化約成 `==` / boolean / 不變量比較的 → 沉澱成 assert;凡涉及
  「誠不誠實 / 新不新穎 / 真不真實」的判斷 → 留給人。**自動項通過是必要非充分**:
  它只代表「沒有明顯硬傷」,不代表「可進短名單」。

## 2. 對照表:檢查點① 9 項 → 機械可判定 vs 人審剩餘

來源 = [strategy-research-pipeline-design.md](2026-06-25-strategy-research-pipeline-design.md)
第 4 段檢查點① 的 9 項;欄位來源 = [stage3-implement-backtest.md](../pipeline/stage3-implement-backtest.md)
的 `summary.json` gate-evidence schema。

| # | 檢查點① 項目 | 機械可判定部分(→ checker assert) | 既有保證 / 工具 | 必須人審的剩餘判斷 |
|---|---|---|---|---|
| 1 | n_trials 誠實 | `family_cumulative_n_trials == EXPERIMENT_REGISTRY 該 family 累計總和`,且 CPCV 實際吃的就是這個值 | I13、I23、`EXPERIMENT_REGISTRY.md` | 「這次 attempt 算重試還是新 family」屬判斷(見 #9),checker 只能核對數字一致,不能判斷歸屬正確 |
| 2 | leak-free | `leak_test_passed == true` 且該 leak 回歸測試**存在**於 test suite 並在 CI 綠燈 | I8、I24、`test_xs_momentum_backtest.py::test_daily_close_target_is_not_traded_on_same_day` 模式 | **spot-check lag 邏輯**:測試本身是否真的擋到該策略的 leak 形態(測試可能寫歪、覆蓋不到)——人看 |
| 3 | DSR 不變量 | `DSR <= PSR(0)` 且 DSR 由修正後 harness 算;可由 `recheck_dsr.py` 從保留的 path returns 重算複核 | I21、I25、`scripts/recheck_dsr.py` | 無(純不變量)。但若 artifact 沒保留 raw returns → checker 標 `dsr_not_recomputable`,升級人看 |
| 4 | idealized-fill 排除 | `idealized_fill == false` | I14、I17 | 無(純 flag) |
| 5 | differential validation | `portable_validation_gate == true`,**或** 誠實標 `blocked_reason` / `adapter_required_engines`(欄位存在且非空) | I16 鄰接、`differential_validation.py`、`ai_collaboration.md` gate | 「blocked 的理由誠不誠實」(是真缺 adapter,還是該做沒做)——人看 |
| 6 | ct_val provenance | `ct_val_all_authoritative == true` 且 provenance `exchange` == run venue | I16、`replay._attach_ct_val_provenance` | 無(純 flag + venue 字串比對) |
| 7 | 門檻 | `dsr >= 0.95` **且** `psr >= 0.95` | gate schema | 無(純比較) |
| 8 | 裁決 supported/refuted | — | — | **整項人審**:即使 7 項全綠,是否進短名單仍是 Claude 證據裁決(成本真實性、樣本代表性、機制可信度) |
| 9 | 重試 vs 新 family 判定 | checker 可**標示** family_id 是否為本批新出現、K 計數現值 | K 上限、family 規則 | **整項人審**:用 relabel 把重試偽裝成新 family 來繞過 K,只有人能判 |

**淨結果**:#3、#4、#6、#7 可完全自動;#1、#2、#5 的「對帳/存在性/欄位」可自動,但各留一塊判斷;#8、#9 整項保留人審。

## 3. 新增最小機制(ponytail:鏡像既有 Stage 2 checker,不造新框架)

> `// ponytail: mirror scripts/run_pipeline_stage2_check.py + backtesting/pipeline_feasibility.py 的既有模式,只多一支 aggregator + 一個對帳`

1. **`scripts/run_pipeline_checkpoint1_check.py`** — 吃一個候選的 `summary.json` +
   `docs/EXPERIMENT_REGISTRY.md`,跑 #1–#7 的機械子集,輸出
   `results/<batch_id>/<candidate>/checkpoint1_auto.json`:

   ```text
   schema_version, batch_id, candidate_id, family_id,
   checks: [ {name, status(PASS|FAIL|NEEDS_HUMAN), reason}, ... ]
       # n_trials_reconcile, leak_test_present_and_green, dsr_le_psr,
       # idealized_fill_excluded, portable_gate_or_honest_block,
       # ct_val_authoritative_and_venue_match, dsr_psr_threshold
   checkpoint1_auto_status: PASS | FAIL | NEEDS_HUMAN
   human_review_items: [ leak_lag_spotcheck, diff_block_reason_honest,
                         verdict, retry_vs_new_family ]   # 永遠列出,提醒人看
   ```

   - 任一機械 check FAIL → `checkpoint1_auto_status = FAIL`(直接擋,不必勞煩人)。
   - 機械全過但有 `dsr_not_recomputable` 之類 → `NEEDS_HUMAN`。
   - **`human_review_items` 永遠非空**:把 #2/#5/#8/#9 顯式列出,杜絕「自動綠燈 = 可發布」誤讀。

2. **對帳**:checker 讀 `EXPERIMENT_REGISTRY.md` 算 family 累計,與 `summary.json` 的
   `family_cumulative_n_trials` 對帳;不一致即 #1 FAIL。根治「寫死 8 / 跨 batch 拆小」。

3. **新增不變量 I26**(`docs/INVARIANTS.md`,接在 I25 後):

   > **I26** — 任何 Stage 3 候選 summary 在進入檢查點① 人審前,必須先由
   > `run_pipeline_checkpoint1_check.py` 產出 `checkpoint1_auto.json` 且
   > `checkpoint1_auto_status != FAIL`;且其 `family_cumulative_n_trials` 必須與
   > `EXPERIMENT_REGISTRY.md` 該 family 累計總和**逐一對帳相等**。
   > `checkpoint1_auto_status == PASS` 為**必要非充分**:不取代 `human_review_items`
   > 的人為裁決,亦不得作為 promotion/publish 依據。
   > 守護:`R6.3 / R7.4`;測試:`tests/unit/test_pipeline_checkpoint1_check.py`。

> **與 from-0 ingestion 的銜接(2026-06-30 使用者決策)**:該管線**採用**跨輪知識回饋,
> 故 I26 的 family 累計對帳**必須涵蓋「回饋偏置而生且碰 Pass-A」的 trial**。只要 ingestion
> 端誠實把這些登記進 `EXPERIMENT_REGISTRY`,checker 對帳的 family 總和即已含它們——這條
> 銜接是該決策能安全打開的前提。見
> [stage3-idea-ingestion-design §4.7 / §8](2026-06-30-stage3-idea-ingestion-design.md)。

## 4. Codex 任務(交付用)

```text
Task: 實作檢查點① aggregator checker + I26,把機械子集從 Claude 每次審降級為自動 gate
Strategy/spec source: 本文件 + 2026-06-25-strategy-research-pipeline-design.md §4
Required behavior:
  - 新增 scripts/run_pipeline_checkpoint1_check.py:讀 summary.json + EXPERIMENT_REGISTRY,
    跑 §2 機械子集(#1 對帳 / #2 存在+綠 / #3 DSR≤PSR / #4 idealized_fill / #5 欄位 /
    #6 ct_val+venue / #7 門檻),輸出 checkpoint1_auto.json(schema 見 §3)。
  - human_review_items 永遠輸出 [leak_lag_spotcheck, diff_block_reason_honest, verdict,
    retry_vs_new_family]。
  - 在 docs/INVARIANTS.md 新增 I26(文字見 §3.3)。

PERMITTED FILES (only edit these):
- scripts/run_pipeline_checkpoint1_check.py            (新增)
- backtesting/pipeline_checkpoint1.py                  (新增,純函式,給 checker import;鏡像 pipeline_feasibility.py)
- tests/unit/test_pipeline_checkpoint1_check.py        (新增)
- docs/INVARIANTS.md                                   (僅加 I26 一列)
- docs/superpowers/pipeline/stage3-implement-backtest.md (僅加「Stage 3 結束需跑 checkpoint1 checker」一句)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ , signals/ , risk/ , portfolio/ , execution/
- backtesting/cpcv.py , walk_forward.py , differential_validation.py , replay.py  (只讀它們的輸出,不改演算法)
- analytics/dsr.py
- config/risk.yaml , config/settings.yaml , 任何 deployment/demo/shadow/live gate
- 既有 results/** artifact(不得回寫/遷移)

SCOPE LIMIT:
只新增「讀 artifact + 對帳 + 標記」的純檢查層。不改任何回測/統計演算法、不改門檻、
不重算既有 artifact。checker 是 advisory aggregator,FAIL 只擋「進人審」,不改 promotion gate。

REQUIRED ON COMPLETION:
- List changed files
- Run: pytest tests/unit/test_pipeline_checkpoint1_check.py + make docs-check
- 若改動觸及 DOC_IMPACT_MATRIX 業務規則列 → 補 Change Manifest(本任務僅加檢查層+I26,
  預期不觸 PnL/fee/funding/sizing/fills/gates 規則語義,但 I26 是新不變量 → 在 PR 說明對帳)
- Commit with AI-Origin: Codex trailer

ACCEPTANCE CRITERIA:
- [ ] checkpoint1_auto.json 對一個既有 batch-2 候選(如 c2_funding_carry)能正確產出,
      且 n_trials 對帳數字與 EXPERIMENT_REGISTRY 一致。
- [ ] 故意把 summary 的 family_cumulative_n_trials 改錯 → checker 回 FAIL(對帳測試)。
- [ ] idealized_fill=true / dsr>psr / dsr<0.95 任一 → checker 回 FAIL。
- [ ] human_review_items 永遠非空,且 README/輸出明示「auto PASS ≠ 可發布」。
- [ ] I26 入 INVARIANTS.md,測試守護存在並通過。
```

## 5. 為什麼剩下那幾項不能自動(留給人的護欄,不是工程不成熟)

- **#2 lag spot-check**:leak 回歸測試「存在且綠」可自動,但「測試是否真覆蓋這個策略的
  leak 形態」需要看實作——XS momentum 2026-06-24 的 day-D 用當日收盤 leak,當時別的
  測試是綠的,是人看 lag 邏輯才抓到,而且那份 leaked artifact 還自帶
  `promotion_gate_passed:true`。
- **#5 blocked 理由誠實**:欄位存在可自動,但「該做 adapter 卻標 blocked」是規避,需人判。
- **#8 裁決 / 成本真實性**:C2 funding-carry 重算成本後實現年化波動 0.247% < 2% 自檢紅線
  ——所有 gate flag 都可能過,但「這個 hedge 模型太平靜、不可信」只有人會起疑。
- **#9 retry vs 新 family**:用 relabel 把重試偽裝成新 family 繞過 K = 降標準,純判斷。

這四項是**過擬合最佳化器**最會鑽的縫;把它們留給人,正是本管線把 overfitting 風險
壓住的設計,不是暫態。對應 Stage 3 全自動時,它們升級為「per-batch / per-policy 稽核」
而非消失(見 [stage3-idea-ingestion-design](2026-06-30-stage3-idea-ingestion-design.md))。

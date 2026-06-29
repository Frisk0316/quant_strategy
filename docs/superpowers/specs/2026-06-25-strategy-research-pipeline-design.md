---
status: draft
type: design
owner: human
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# 策略研究管線 Stage 1 — 設計 spec

> brainstorming 已完成(第 1–4 段與使用者逐段確認;第 5 段重用清單、路線圖、
> 預設值由 Claude 補完)。`status: draft` 表示等待使用者複審;複審通過後轉
> writing-plans 產實作計畫。本管線不改任何 demo/shadow/live gate。

## 問題 / 動機

目前「找文獻 → 評估 → 做進回測系統 → 正式回測篩 gate → 發布」每一步都要使用者
手動下 prompt 叫 Claude/Codex 接手,太人工。目標:讓這條鏈在使用者**不逐步下
prompt** 的情況下,按一次就跑到「通過 gate 的短名單」。

使用者理想流程:1) 找文獻 2) 評估可行性 3) 做進回測系統 4) 正式回測篩 gate
5) 發布。

**前置共識:**
- 這是全專案 overfitting 風險最高的活動;gate(DSR ≥ 0.95、PSR ≥ 0.95、honest
  n_trials、leak-free、differential validation、ct_val provenance)**不可為了讓
  策略過而放鬆**。
- 「試幾次才會過」無固定答案:誠實計數下沒有真 edge 的想法期望通過數 ≈ 0;有真
  edge 的想法期望嘗試 ≈ 1/(真 edge 基率)。真正槓桿是**先驗品質**,不是試更多次。
- 角色:Claude 做研究/spec/審查;Codex 實作 trading-core;使用者決定發布。

## 已定決策 (locked)

| # | 決策 | 選擇 |
|---|------|------|
| 1 | 核心目標 | 兩者都要但**分階段**:先做「省 prompt 的有界自動化」,站穩後逐步加大發掘規模,每加大一次先把更多 review 判斷沉澱成自動 invariant。 |
| 2 | 第一階段候選來源 | **先用現有 backlog**(`research/strategy_synthesis.md` 未實作候選 S5/S6/S7…)。 |
| 3 | 檢查點數量 | **一個**:1→3 自動跑(含強制 leak 回歸測試),回測證據出來後 Claude 做證據審查,再進短名單;發布是使用者的第二關。 |
| 4 | n_trials 累計政策 | **按假設家族(family)累計**;不同 family 互不 deflate。 |
| 5 | 編排機制 | **A — 單 session subagent 管線**(用既有 `subagent-driven-development`)。 |
| 6 | Stage 3 回測 | **兩段式**:parquet research-tier 預篩 → DB venue-scoped CPCV 正式。 |
| 7 | 「發布」定義 | **接 UI 成 `enabled:false` 已驗證候選** + ledger 標 supported;不自動上線、不碰 deployment gate。 |
| 8 | 長期記錄存放 | **重用現有永久 ledger**(`HYPOTHESIS_LEDGER` + `EXPERIMENT_REGISTRY`)當 single source of truth;每批 JSON 狀態 + 短名單為 `results/<batch_id>/` 可丟 scratch,對帳同步回 ledger。 |

## 第 1 段:架構與流程

使用者啟動一個「預先登記的批次」(例 候選 = [S7, S5, S6]),driver(Claude
session)按候選依序派 subagent 跑完 1→3,每個候選回測證據出來後停在 Claude 證據
審查,最後把通過者整理成短名單交使用者決定發布。

```text
使用者: 啟動批次  {candidates:[S7,S5,S6], family_budget:..., data_tier:...}
      │   ← 先把整批寫進 ledger,不管過不過都算數
      ▼
 driver(Claude session) ── 對每個候選依序:
   ├─ stage 1  文獻→假設        [subagent: 研究]   → 寫 HYPOTHESIS_LEDGER (H-xxx)
   ├─ stage 2  可行性自動檢查    [subagent: 研究]   → 不過就 skip(記原因)
   ├─ stage 3  實作 + 回測       [subagent: Codex]  → leak 回歸測試 + honest n_trials
   │                                                  → gate 證據 artifact
   ▼
 ┌─ 檢查點① Claude 證據審查 ─┐   ← 唯一的自動化內人為關卡
 │  leak-free? n_trials 誠實? │
 │  DSR≥0.95 & PSR≥0.95?      │
 └────────────┬───────────────┘
              ▼   通過 → 短名單 (+ ledger supported);沒過 → ledger refuted/shelved(記 n_trials)
 ┌─ 檢查點② 使用者 ──────────┐   ← 發布只有使用者能按
 │  看短名單,決定是否接 UI    │
 └─────────────────────────────┘
```

- driver = 這個 session,按一次跑到短名單,中間不用下 prompt。
- 兩個人為關卡:① Claude 審回測證據,② 使用者決定發布;1→3 之間無人值守。
- ledger 是骨幹:批次開始整批登記,每候選不管過不過都把 n_trials 記進它的 family。

## 第 2 段:family ledger + trial-count 協定 + 停止條件

**① 批次預先登記**:啟動時 driver 先把整批寫進帳(候選、各候選計畫 grid、各自
family),才開始跑。先承諾再看結果;事後不能把沒過的 trial 拿掉。

**② family 歸屬 + 累計**:每候選對應一個經濟機制 family;family 的 `n_trials` =
該 family 歷來所有 batch 的(grid 組合數 + 重試次數)總和;不同 family 互不
deflate;算 DSR 餵進 CPCV 的是 family 累計值,不是這次 run 的 grid 數。→ 同時擋
掉跨 batch 拆小、同 family 微調重試兩種作弊。

**③ honest n_trials 強制**:Stage 3 必須從 ledger 讀 family 累計值傳進 CPCV;檢查
點① 核對「傳進去的 == ledger family 累計」。根治「寫死 8」——n_trials 是帳上算出
來的,不是程式常數。

**④ 停止條件**:(a) 批次候選跑完;(b) 撞 runtime/compute 上限;(c) **family 重試
上限 K**——某 family 重試 K 次仍不過 → 停止重試該 family,升級給使用者。每次重試
只墊高它自己門檻;這不是降標準,是誠實地把該 family shelve。

**重試 vs 新 family(K 的判定基準)**:一次 attempt 內掃 grid(多個參數組合)是
正常搜索,不算重試,全數計入 family n_trials。**重試** = 整個 attempt 失敗後,對
**同一經濟機制**調旋鈕/修 bug 再從頭跑(吃同 family 額度,計入 K)。**新 family**
= 真的不同的經濟機制(全新 n_trials 預算,K 歸零)。把重試假裝成新 family 來繞過
K 就是降標準,由檢查點① Claude 判定守住。

**⑤ 記錄載體(不建新 DB)**:**長期真相(family 累計 n_trials / 假設 / 裁決)寫進
永久的 `HYPOTHESIS_LEDGER.md`(family)+ `EXPERIMENT_REGISTRY.md`(每 run trial)**
——這是 single source of truth,不放在會被清理的 `results/` 裡。機器迴圈用一個 JSON
批次狀態檔(`results/<batch_id>/`,單次可丟 scratch)當共享 trial 計數本,檢查點時
對帳同步回兩個永久 markdown ledger;scratch 即使被清,長期真相仍在 ledger。
`// ponytail: 永久真相用既有 markdown ledger,JSON 只是單次 scratch,不上 DB`

**已知張力(接受)**:按 family 累計 ⇒ family 每重試一次門檻更高;停止條件 (c) 是
操作答案——不會永遠調,要嘛早過,要嘛 shelve。

## 第 3 段:每階段契約

**Stage 1 — 文獻→假設(研究 subagent)**
- 輸入:backlog 候選 id + `strategy_synthesis.md` 對應段落。
- 產出:`HYPOTHESIS_LEDGER` 假設(H-xxx),含 經濟機制(→ family id)、可測
  signal/entry/exit/sizing/execution/risk spec、計畫 grid、資料需求、validation
  path、預先登記的 family n_trials 預算。
- 自動通過:spec 欄位齊全 + family 已指定 + grid 已宣告。(第一階段是把 backlog
  條目展開成完整可測 spec,不是文獻搜索。)

**Stage 2 — 可行性自動檢查(研究 subagent)** ← 花實作成本前先擋:
- (a) **資料可得性**:該 universe/區間所需序列在 DB/parquet 是否齊;缺 → skip。
- (b) **相關性上限**:便宜 proxy——signal 跟現有 enabled 策略是否經濟上夠不同
  (例 S7 必須是獨立回歸 timing 層,不是 funding_carry 換標籤);太近 → skip/flag。
- (c) **成本後 edge 嗅探**:便宜預估(sample window 上原始 signal 是否以合理幅度
  超過 maker+slippage),非回測,只是「值不值得實作」味道測試。
- 產出:PASS → 進 stage 3;FAIL → skip,ledger 記原因(沒掃 grid 算 0 trials)。

**Stage 3 — 實作 + 回測(Codex subagent)**
- Codex 按 stage-1 spec 實作 trading-core,**強制帶 leak 回歸測試**。
- 強制 artifact/測試:leak 回歸測試、宣告 differential validation contract
  (`REFERENCE_VALIDATION_CONTRACTS`)、不得用 idealized-fill 當證據、ct_val
  provenance。
- 回測兩段式:
  - **Pass A 便宜預篩**:parquet research-tier 粗 grid WF → 砍明顯輸家(不算
    promotion 證據,但 trial 計入 family)。
  - **Pass B 正式**:存活者 → DB venue-scoped CPCV,餵 family 累計 n_trials →
    DSR/PSR。
- 產出 gate 證據 artifact(機器可讀,給檢查點① 自動核對):

```text
candidate_id, family_id, batch_id,
grid_size_this_run, family_cumulative_n_trials,
wf_oos_sharpe, cpcv_oos_sharpe, dsr, psr,
leak_test_passed(bool), portable_validation_gate(bool),
idealized_fill(bool), ct_val_all_authoritative(bool),
promotion_gate_passed(bool), status
```

## 第 4 段:兩個人為關卡 + 短名單 + 發布

**檢查點① — Claude 證據審查**(抓 S11 那種 leak 的地方;直接重用
`docs/REVIEW_QUESTIONS.md` / `CRITIQUE_PROTOCOL.md` + `ai_collaboration.md` gate
條文,不另造 checklist):
1. **n_trials 誠實**:傳進去 == ledger family 累計(不是寫死)。
2. **leak-free**:leak 回歸測試存在且通過 + spot-check lag 邏輯。
3. **DSR 不變量**:DSR ≤ PSR(0) 成立、由修正後 harness 算。
4. **idealized-fill 排除**:`idealized_fill==false`。
5. **differential validation**:`portable_validation_gate` 通過或誠實標 blocked。
6. **ct_val provenance**:全 authoritative 且 venue 一致。
7. **門檻**:DSR ≥ 0.95 **且** PSR ≥ 0.95。
8. **裁決**:supported → 進短名單;否則 refuted/shelved 記原因,n_trials 照記進
   family。
9. **重試/新 family 判定**:確認這個 attempt 是重試(同機制,吃 K)還是新 family
   (新機制,K 歸零),防止用 relabel 繞過重試上限。

**短名單 artifact**(每批一個 markdown,放 `results/<batch_id>/`):每個通過候選
列 H-id、family、證據 artifact 路徑、DSR/PSR/n_trials、Claude 裁決註記、「下一步:
需使用者發布決定」。沒過的列附錄(含原因 + 累計 trial),讓使用者一眼看到整批
搜索強度。

**發布(step 5)**:通過者接進系統成 `enabled:false` 已驗證候選 + ledger 標
supported + 更新 `strategy_synthesis.md` 狀態。**不自動上線、不碰
demo/shadow/live gate**;真正 promote 仍是現有獨立、全門控、使用者批准的部署流程。

## 第 5 段:重用 vs 新增清單 (ponytail)

**重用(零或極小改動):**
- 編排:`superpowers:subagent-driven-development` skill。
- 記錄:`HYPOTHESIS_LEDGER.md`、`EXPERIMENT_REGISTRY.md`。
- 回測/統計:`backtesting/walk_forward.py`、`backtesting/cpcv.py`、
  `analytics/dsr.py`(已修)、`backtesting/differential_validation.py`、ct_val
  provenance(`backtesting/replay._attach_ct_val_provenance`)。
- 審查:`REVIEW_QUESTIONS.md` / `CRITIQUE_PROTOCOL.md` / `INVARIANTS.md`;
  `scripts/recheck_dsr.py`(DSR 不變量 sanity,可當檢查點① 的自動 sanity)。
- 策略骨架:`backtesting/xs_momentum_backtest.py` 模式(新策略 mirror)。

**新增(最小):**
- 一個 JSON 批次狀態檔(單次 scratch,非真相 of record),放 `results/<batch_id>/`;
  對帳同步回永久 ledger。
- driver 啟動程序:一個記錄好的 prompt 模板 + subagent-driven skill,**不是新框架**。
- gate 證據 summary schema:擴充既有 `summary.json`,非全新格式。
- 每階段 subagent 任務模板(`tasks/` 下 markdown)。
- 一個短名單 artifact 格式(markdown)。
- 跨切要求(Codex 區):Stage 3 呼叫 CPCV 時 **n_trials 從 ledger 讀 family 累計**
  傳入(修掉寫死)。

## 分階段路線圖

- **Stage 1(本 spec)**:單 session、backlog、一個檢查點、手動啟動。
- **Stage 2 解鎖條件**:把檢查點① 的 leak / n_trials / DSR 不變量檢查**沉澱成自動
  invariant/測試**(不再每次需 Claude)→ 才開背景平行 agent(編排 B)。
- **Stage 3 解鎖條件**:Stage 2 穩定 + 排程 cron/loop 自動執行 family 預算與停止
  條件 + 文獻搜索 ingestion 加品質過濾(編排 C)。

## 批次參數預設 (可調)

- **第一批候選順序 = [S7, S5, S6]**(S7 先驗最高、過擬合風險最低)。
- **family 重試上限 K = 2**(原始嘗試 + 2 次重試,再 shelve 並升級)。
- **data tier = 兩段式**(parquet 預篩 → DB CPCV)。
- **runtime/compute 上限**:啟動時必填參數,**無靜默預設**;超過則批次乾淨中止。

## 角色 / scope

- 本文件為設計/治理文件,Claude 可寫。trading-core(`strategies/`、`signals/`、
  `risk/`、`portfolio/`、`execution/`)、回測引擎、config 由 Codex 實作。
- 本管線只產出「通過既有 gate 的短名單」,**不改任何 deployment/demo/shadow/live
  gate**,發布權在使用者。

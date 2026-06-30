---
status: draft
type: design
owner: human
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# 發想器本體（idea generator front-end）設計 spec

> 對應 [stage3-idea-ingestion-design.md](2026-06-30-stage3-idea-ingestion-design.md)
> 的「從 0 發想」前段。本檔把**發想器本體**定清楚:它是**自動版 Stage 1**——取代
> 人工 backlog,自己產出候選假設,輸出**剛好是現有
> [stage1-hypothesis.md](../pipeline/stage1-hypothesis.md) 契約**的 `HYPOTHESIS_LEDGER`
> 草稿,所以**下游 Stage 2 / Stage 3 / checkpoint① 完全不動**。
> `status: draft`。不碰任何 deployment/demo/shadow/live gate。
>
> **可實作邊界(誠實)**:**B(taxonomy 枚舉)半邊現在就能做**(taxonomy 已在);
> **A(文獻 ingestion)半邊卡在 corpus 來源決策**(§7),本檔只定其介面契約,不發明來源。

## 1. 它接在哪

```text
[現況] 人工 backlog ─┐
                     ▼
[本檔] 發想器本體 = 自動 Stage 1 ──► HYPOTHESIS_LEDGER 草稿(stage1 契約)
                     │                       │
   B taxonomy 枚舉 ──┤                       ▼
   A 文獻 ingestion ─┘             [既有] Stage 2 可行性 ─► Stage 3 回測 ─► checkpoint①
                                          (全部不改)
```

發想器**只替換 Stage 1 的輸入來源**(從人工 backlog → 自動枚舉/文獻),輸出契約與下游一字不改。

## 2. 架構（資料流）

```text
taxonomy §2  ┐
ledger       ┼─► (機器) gap 枚舉 + 過濾 + 排序 ──► 每個 eligible gap
data-avail   ┘                                        │
                                                      ▼
                                   (LLM 研究 subagent) 草擬 stage1 假設
                                   ── 只吃 機制+文獻+taxonomy;資料防火牆 ──
                                                      │
                                                      ▼
                          §7 family-minting checker (ASSIGN/MINT/SKIP/NEEDS_HUMAN)
                                                      │
                                                      ▼
                          prior-plausibility gate(ex-ante 淨成本後 edge + 非 refuted 換皮 + 參數簡約)
                                                      │
                                                      ▼
                              ≤15 cap + 先驗排序 ──► 批次預先登記(寫 ledger + JSON batch)
                                                      │
                                                      ▼
                                          交既有 Stage 2(不改)
```

**機器 vs LLM 分工**:
- **機器(Codex 碼)**:gap 枚舉/過濾/排序、§7 與 prior-gate 串接、≤15 cap、批次預先登記。**確定性**。
- **LLM(研究 subagent,Claude 角色)**:把一個 eligible gap 草擬成完整 stage1 假設(機制已知,
  創造的是可測 signal/entry/exit/sizing/exec/risk/universe + grid + 資料需求 + validation path +
  n_trials 預算)。重用 [stage1-hypothesis.md](../pipeline/stage1-hypothesis.md) 模板 + §5 防火牆附則。

## 3. B 半邊:taxonomy 枚舉（unblocked,完整 spec）

**gap 來源**:走 [mechanism-taxonomy.md §2](2026-06-30-mechanism-taxonomy.md) 目錄,對每個 family
判斷「有沒有還沒測、且值得測的格」。

**過濾(便宜先砍,省 LLM 與 compute)**:
- 砍掉 `occupied` 且 `refuted/shelved` 且**未宣告新機制轉折**的(H-002/006/007/008)。
- 砍掉 `data-blocked`——**重用既有 Stage 2 `pipeline_feasibility.py` 的 data-availability 探針**
  (OI / 清算 / on-chain / options 直接出局,別等 LLM 草擬完才在 Stage 2 死)。
- 保留池 = 資料可行的 frontier(`F-FUNDING-XS-DISPERSION`、`F-XVENUE-LEADLAG`)+
  資料允許的 untested-documented(`F-VOL-REGIME` overlay;`F-OFI-MAKER-SKEW`/`F-VPIN-MM` 若有
  L1/trade tape;`F-CME-GAP` 若有 CME 日線)+ `inconclusive` family 的**真新變體**。

**排序(先驗品質,取 top ≤15)**:資料可行 > 部分可行;低 crowding > 高 crowding;非近期 refuted;
**參數越少越優先**(AlphaAgent 借鏡:少自由度 = 小 grid = 低 family n_trials 負擔)。

> 誠實預期:**現有資料下,B 枚舉只會吐出個位數可行候選**(主要是那 2 個 frontier + vol-regime
> overlay),不是硬湊 15 個。這正是「先驗空間很窄」的研究訊號,不是 bug;≤15 cap 綽綽有餘。

## 4. A 半邊:文獻 ingestion = **自動化既有 crypto-alpha-lab**（corpus 已定）

**重大重用**:`research/crypto-alpha-lab/` 已是「論文→評分→alpha 候選」的半手動骨架(Phase 1:
intake/scoring 模板 + pydantic schemas + tests + **預留的 `pipeline/` 與 `adapters/` 模組**;
README「Next Stage」第 1-4 點正是 ingestion/scoring/exporter/validation)。A 半邊 = **把它的手動
流程自動化,不另造**。lab `pipeline/` 註明「Reserved for future paper-to-alpha workflow
orchestration」——就是這裡。

- **corpus 落腳**:`research/crypto-alpha-lab/papers/`(已存在;research/ 為 Claude 區,lab 專為此設)。
- **來源(使用者定,免費優先)**:arXiv `q-fin`(主)+ SSRN(免費摘要/多數免費 PDF)+ RePEc/IDEAS、
  NBER 免費、央行 working paper、OpenReview、Semantic Scholar。付費期刊(Journal of Finance / RFS /
  JFE)只走其**免費 preprint**(作者 PDF / SSRN),不抓付費全文。
- **cadence(使用者定)**:**每週一次 + 個人手動補**。沿用 lab 既有 dated 慣例:每週新增
  `papers/search_log_<date>.md` + `papers/screen_<date>.json`(已有 `*_2026-05-26` 範本);手動投稿
  直接丟 `papers/`。
- **流程(自動化 lab pipeline/)**:
  1. 抓 arXiv/免費來源 → LLM 產 `PaperScoring` 記錄(schema 已在 `schemas/paper_scoring.py`:
     evidence/crypto/data/fit/cost/novelty + leakage/overfit 罰分 + `priority_score()`)。
  2. `priority_score() >= 3.8` → 升級為 `AlphaCandidate`(schema 已在 `schemas/alpha_candidate.py`)。
  3. **adapter(lab 已預留 `adapters/`)** 把 `AlphaCandidate` → 父 pipeline 的 stage1 草稿
     (HYPOTHESIS_LEDGER proposed + family);`alpha_category`(momentum/mean_reversion/microstructure/
     carry/stat_arb/volatility/alternative_data/risk_filter/execution)→ taxonomy family 對映。
  4. 與 B 半邊匯流:§7 family-minting → prior-gate → ≤15 cap → 批次預先登記 → 父 Stage 2。
- **評分 ↔ 父 gate 對映(互補,不重造)**:lab `PaperScoring`(便宜、論文級、實作前)= ingestion §4.5
  prior-plausibility gate 的操作化(`priority_score>=3.8` = eligible);父 **Stage 2**
  (data-availability/distinctness/cost-after-edge)、**§7**、**checkpoint①** 是實作後的權威硬 gate。
  lab 分數是前置粗篩,父 gate 是後置硬篩——兩層互補,**不得用 lab 分數取代父 gate**。
- **資料防火牆(硬規則)**:抽取/評分/草擬只看**論文 + 機制 + taxonomy + ledger 元資料**,**絕不餵
  OOS 區段價格或 fold 邊界**。
- **frontier 回寫**:A 產出的新機制鑄 family 前,須回寫 `research/strategy_synthesis.md`(Claude 審)
  ——lab README/AGENTS 也明訂 lab **不**自行改 synthesis.md,故回寫是一個獨立 Claude-審步驟。

## 5. 守則（沿用決策,發想器必須遵守）

1. **批次預先登記**:發想器產出的整批候選(含 A 與 B、含跨輪回饋衍生)**在跑任何 Pass-A 前**
   先寫進 ledger + JSON batch。先承諾再看結果,事後不能抽掉沒過的。
2. **≤15 候選/輪**(決策 3):cap 在排序後套用;超出乾淨中止。
3. **資料防火牆**(§4):發想器輸入永不含 OOS 價格/fold 邊界。
4. **prior-plausibility gate**(ingestion §4.5):每張草稿須帶 ex-ante 淨成本後 edge 理由 +
   非已 refuted family 換皮(§7 判)+ 參數簡約。
5. **跨輪回饋入帳**(決策 4 / ingestion §4.7):回饋偏置而生的候選**標記 feedback-spawned**,
   且只要碰 Pass-A 就**計入 family n_trials**;回饋只准影響「下一個試什麼」的優先序,不准繞過入帳。
6. **§7 為唯一鑄造判定**:family 歸屬一律走 family-minting checker;Stage 2 的 distinctness 留作
   確認層,不在本任務重構。

## 6. Codex 任務（B 半邊可實作碼）

```text
Task: 實作發想器 B 半邊的確定性碼(gap 枚舉 + 過濾 + 排序 + 批次預先登記),串 §7 與 Stage 2 探針
Strategy/spec source: 本檔 §3/§5 + mechanism-taxonomy.md + stage1-hypothesis.md 契約
Required behavior:
  - 新增 backtesting/pipeline_idea_generator.py:
    enumerate_gaps(taxonomy, ledger, data_availability_probe) -> [eligible_gap]
      過濾規則見 §3(砍 refuted-無轉折 / data-blocked;保留 feasible frontier + untested-documented)
    rank_and_cap(gaps, cap=15) -> [candidate]  # 先驗排序見 §3,deterministic
    register_batch(candidates, batch_id) -> 寫 ledger 草稿 + results/<batch_id>/idea_batch.json
      (預先登記:跑 Pass-A 前完成)
  - 串接(import,不改其行為):pipeline_feasibility.py(data-availability 探針)、
    pipeline_family_minting.py(§7,每個草稿 ASSIGN/MINT)、pipeline_checkpoint1.py(ledger 解析)。
  - 新增 scripts/run_pipeline_idea_generator.py(CLI):產 eligible gap 清單 + 寫批次預先登記。
  - LLM 草擬步驟**不在本任務**(研究 subagent 用 stage1 模板做);本任務在草稿不存在時輸出
    gap 清單 + draft_status=pending_llm,草稿回填後再跑 §7/prior-gate/register。

idea_batch.json schema:
  schema_version, batch_id, generated_at, source(B_taxonomy|A_literature|feedback),
  cap_applied(15), n_eligible_before_cap,
  candidates: [ {provisional_candidate_id, family_id_or_NEW, mechanism, data_feasible(bool),
                 prior_rank, planned_grid_size, draft_status(pending_llm|drafted),
                 family_minting_decision, feedback_spawned(bool)} ],
  skipped: [ {family_id, reason(refuted_no_twist|data_blocked|cap_overflow)} ]

PERMITTED FILES (only edit these):
- backtesting/pipeline_idea_generator.py             (新增)
- scripts/run_pipeline_idea_generator.py             (新增)
- tests/unit/test_pipeline_idea_generator.py         (新增)
- docs/superpowers/pipeline/stage1-hypothesis.md     (僅加「autonomous mode + 資料防火牆」附則一節)
- docs/change_manifests/2026-06-30-idea-generator-frontend.md  (新增,R6.3/R7.4 doc-impact)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ , signals/ , risk/ , portfolio/ , execution/
- backtesting/cpcv.py , walk_forward.py , differential_validation.py , replay.py , pipeline_feasibility.py 行為
- pipeline_family_minting.py / pipeline_checkpoint1.py 的決策行為(只 import)
- HYPOTHESIS_LEDGER.md / EXPERIMENT_REGISTRY.md 的裁決或 n_trials 值(草稿只 append proposed,不改既有值)
- research/strategy_synthesis.md(frontier 回寫是另一個 Claude-審步驟)
- 任何 deployment/demo/shadow/live gate;既有 results/** artifact

SCOPE LIMIT:
只做確定性的「枚舉→過濾→排序→cap→預先登記」+ 串既有探針/§7。不做 LLM 草擬、不抓文獻、
不碰 A 半邊 corpus、不改門檻以外統計。cap 與排序權重為 config 常數,標 ponytail ceiling。

REQUIRED ON COMPLETION:
- List changed files
- Run: pytest tests/unit/test_pipeline_idea_generator.py + make docs-check
- 補 change manifest(枚舉/預先登記是治理流程變更,鏡像 checkpoint①/family-minting manifest)
- Commit with AI-Origin: Codex trailer

ACCEPTANCE CRITERIA:
- [ ] enumerate_gaps 砍掉 refuted-無轉折(H-002/006/007/008)與 data-blocked(OI/清算/on-chain/options),
      理由寫進 skipped[]。
- [ ] 現有資料狀態下,F-FUNDING-XS-DISPERSION 與 F-XVENUE-LEADLAG 出現在 eligible(feasible frontier)。
- [ ] n_eligible > 15 時套 cap 並 deterministic 排序;skipped 標 cap_overflow。
- [ ] register_batch 在「跑任何 Pass-A 前」寫出 idea_batch.json + ledger proposed 草稿。
- [ ] feedback_spawned 候選被標記並保證進預先登記(決策 4 入帳前提)。
- [ ] 每個 drafted 候選經 §7 family-minting 決定後才登記。
```

## 6b. 任務（A 半邊 = 自動化 crypto-alpha-lab，corpus 已定）

實作 lab 的 `pipeline/` + `adapters/`,把論文→評分→候選自動化,產出**父 stage1 草稿**與 B 半邊匯流。
**碼大多落在 lab 內**(遵 lab AGENTS「只在 research/crypto-alpha-lab/ 內」),只在父端加最小 merge hook。

```text
Task: 自動化 crypto-alpha-lab 的 paper→score→candidate→adapter 流程(每週批次)
Strategy/spec source: 本檔 §4 + crypto-alpha-lab README「Next Stage」+ 既有 schemas/rubric
Required behavior:
  - 在 lab pipeline/ 實作:
    fetch_papers(sources, date_window) -> [raw_paper]   # arXiv q-fin 主 + 免費來源,keyless
    score_papers(raw_papers) -> [PaperScoring]           # LLM 研究 subagent,重用既有 schema+rubric
    promote(scored, threshold=3.8) -> [AlphaCandidate]   # priority_score()>=3.8;重用既有 schema
  - 在 lab adapters/ 實作:
    to_parent_stage1_draft(AlphaCandidate) -> dict        # 產 HYPOTHESIS_LEDGER proposed 草稿
      alpha_category -> taxonomy family 對映;附 §7 用的代表 signal 描述
  - 每週寫 papers/search_log_<date>.md + papers/screen_<date>.json(沿用既有 dated 範本)。
  - 父端最小 hook:backtesting/pipeline_idea_generator.py 的 register_batch 接受 A-half 草稿,
    與 B-half 候選同批預先登記(走同一 §7→prior-gate→cap→register)。
  - 資料防火牆:LLM 輸入只含論文+機制+taxonomy+ledger 元資料;在 prompt 組裝處 assert 不含
    OOS 價格序列/fold 邊界。

PERMITTED FILES (only edit these):
- research/crypto-alpha-lab/src/crypto_alpha_lab/pipeline/   (實作 fetch/score/promote)
- research/crypto-alpha-lab/src/crypto_alpha_lab/adapters/   (實作 AlphaCandidate→父 stage1 草稿)
- research/crypto-alpha-lab/papers/                          (每週 dated 產物)
- research/crypto-alpha-lab/tests/                           (測試)
- backtesting/pipeline_idea_generator.py                     (僅加「接受 A-half 草稿」的 merge hook)
- docs/change_manifests/2026-06-30-idea-generator-a-half.md  (新增)

FORBIDDEN (do not touch):
- 既有 lab schemas(paper_scoring.py / alpha_candidate.py)的欄位/行為(只 consume,不改)
- 父 trading-core / gates / cpcv / dsr / differential / pipeline_feasibility / pipeline_family_minting 行為
- research/strategy_synthesis.md 值(frontier 回寫是獨立 Claude-審步驟)
- live trading、交易所 API client、secrets、付費期刊全文抓取(lab AGENTS 硬規則)
- 把 OOS 價格/fold 邊界餵進 LLM(防火牆)

SCOPE LIMIT:
只做「抓免費文獻 → LLM 評分(重用 rubric)→ 過門檻 → 轉父 stage1 草稿」。fetcher 限 keyless 免費
來源(arXiv/OpenReview/Semantic Scholar API;SSRN/RePEc 走免費 metadata,不繞付費牆)。不改任何
父 gate、不啟用策略。LLM 評分/草擬屬研究 subagent(Claude 角色);fetcher/adapter 屬 Codex。

REQUIRED ON COMPLETION:
- List changed files
- Run: (lab) python -m pytest;(父)pytest tests/unit/test_pipeline_idea_generator.py;make docs-check
- 補 change manifest
- Commit with AI-Origin: Codex trailer

ACCEPTANCE CRITERIA:
- [ ] fetch_papers 以 keyless 公開 API 抓 arXiv q-fin 指定日期窗,無 secrets。
- [ ] score_papers 產合法 PaperScoring;priority_score()>=3.8 過濾正確(重用既有 schema)。
- [ ] AlphaCandidate→adapter→父 stage1 草稿,alpha_category→family 對映正確。
- [ ] 每週 dated search_log + screen json 寫出(沿用 2026-05-26 範本格式)。
- [ ] 防火牆:LLM prompt 組裝不含 OOS 價格/fold(assert 測試)。
- [ ] A-half 草稿與 B-half 同批預先登記,共走 §7→prior-gate→cap。
```

## 7. 已定:corpus 決策（2026-06-30 使用者）

- **來源**:arXiv `q-fin` 為主;免費學術優先——SSRN、RePEc/IDEAS、NBER 免費、央行 WP、OpenReview、
  Semantic Scholar;付費期刊只走免費 preprint。
- **落腳**:`research/crypto-alpha-lab/papers/`(**重用既有 lab**,不另建)。
- **cadence**:每週一次 + 個人手動補;沿用 lab dated `search_log_<date>.md` + `screen_<date>.json`。
- A 半邊已從介面契約升級為完整 spec(§4 + §6b)。無剩餘待決策。

## 8. 重用 vs 新增 / scope

**重用**:stage1-hypothesis 模板、Stage 2 data-availability 探針、§7 family-minting checker、
checkpoint① ledger 解析、批次預先登記機制、永久 ledger、cron/loop + subagent skill。
**新增(最小)**:一支確定性 enumerator/ranker/registrar(§6)+ 一段 autonomous-mode 草擬附則 +
(A 待解)文獻抽取。`// ponytail: 發想器 = 自動 Stage 1,只替換輸入來源,下游一律重用`

- 本檔為設計/治理文件,Claude 可寫。確定性碼屬 Codex;LLM 草擬屬研究 subagent。
- 發想器**只產草稿與短名單候選**,不啟用策略、不碰 deployment/demo/shadow/live gate;發布權在使用者。

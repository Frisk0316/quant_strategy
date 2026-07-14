---
status: archived
type: task
owner: claude
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Pipeline 自動發想改善任務 P1–P8

Author: Claude（2026-07-03 pipeline 審核）。Implementer: Codex。

審核結論（依據 `results/idea_batch_20260702_literature_001/`、
`results/idea_batch_20260701_taxonomy_002/`、`docs/HYPOTHESIS_LEDGER.md`）：
防守面（n_trials/K/DSR/PSR/checkpoint①）已足，**不再加閘門**；瓶頸全在入口側
——資料解鎖、文獻前端精度、跨輪回饋落地。統計功效背景見
`docs/superpowers/specs/2026-07-03-statistical-power-gates.md`。

**使用者已定決策（2026-07-03）**：
1. LLM 摘要級評分：**不開 API**，改用 Claude Code / Codex 對話式（session）評分
   （落在 P2(d)）。
2. OI 歷史：**不買付費資料**，改用公開可下載來源（落在 P8，Binance Vision）。
3. 統計功效文件：Claude 撰寫（已完成，見上）。

**優先序**：P1 ≈ P2 ≈ P8（入口解鎖）> P3（小而立即）> P4 > P6 > P5 ≈ P7。
P1–P3 完成前**不要**把 orchestrator 接上排程自動化。

**全部任務共同 FORBIDDEN（不重複列在各任務）**：
- `src/okx_quant/strategies/`、`signals/`、`risk/`、`portfolio/`、`execution/`
- `config/risk.yaml`、任何 live/demo/shadow/deployment gate
- `docs/HYPOTHESIS_LEDGER.md`、`docs/EXPERIMENT_REGISTRY.md`（durable ledger 只讀）
- `research/strategy_synthesis.md` 及其他 research 真相文件
- 既有 `results/**` artifacts（含 `idea_batch_20260701_taxonomy_002/`、
  `idea_batch_20260702_literature_001/`、`pipeline_batch2_20260625/`）
- Stage-2/checkpoint①/DSR/PSR 門檻值（禁止為了湊 PASS 調閾值）

**全部任務共同 REQUIRED ON COMPLETION**：
- 列出變更檔案；跑指定測試命令；`make docs-impact`（data-provenance 類變更附
  Change Manifest）；更新 `docs/AI_HANDOFF.md` / `docs/CURRENT_STATE.md` /
  `config/workstreams.yaml`；依 AGENTS.md 格式回報；commit 時帶
  `AI-Origin: Codex` trailer。

---

## P1 — top-30 universe funding 史回補 + F-FUNDING-XS-DISPERSION Stage-2 重探測

Task: 把 point-in-time top-30 USDT-perp universe 全體成員的 Binance 8H funding
史回補到 2024-01-01 → 現在，然後對 F-FUNDING-XS-DISPERSION 重跑 Stage-2
data-availability 探測（寫進**新** output root，不碰 taxonomy_002 既有 artifact）。

Strategy/spec source: `docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md`
F-FUNDING-XS-DISPERSION 列；E-028 探測結果（合格 8 標的、5 過覆蓋、每日 ready
廣度 0/10）。

Required behavior:
1. 以 `scripts/build_universe_membership.py` 的 point-in-time 成員全集（歷史上任
   一時點入選過 top-30 的 symbol 聯集）為回補清單。
2. 用 Binance keyless `GET /fapi/v1/fundingRate`（分頁，全史可得）回補每個
   symbol 的 funding 到 `funding_rates`（DB + parquet 同寫，沿用既有
   `scripts/market_data/backfill_funding.py` / `download_binance_data.py` 路徑；
   缺功能才擴充，不重造）。`source` 欄如實記 binance。
3. 產出 per-symbol 覆蓋報告：rows、first/last ts、缺口數、stale 區間。
4. 用 `scripts/run_pipeline_stage2_data_probe.py --output-root
   results/stage2_reprobe_20260703_funding/` 重跑 funding dispersion 探測。
   門檻（min breadth 10 等）**一字不改**；誠實 PASS 或 FAIL 都是合格產出。

PERMITTED FILES:
- `scripts/market_data/backfill_funding.py`（如需擴充）
- `scripts/download_binance_data.py`（僅 funding 路徑修補，如需）
- 新增 `scripts/market_data/backfill_universe_funding.py`（僅當上兩者確實不敷用）
- `tests/unit/test_backfill_universe_funding.py`（新）
- `results/stage2_reprobe_20260703_funding/`（新 artifact）

SCOPE LIMIT: 只回補 funding 與重跑探測。不動探測邏輯、不動 universe 建構邏輯、
不開 Stage-3、不寫 ledger。

REQUIRED: `pytest tests/unit/test_pipeline_stage2_data_probe.py
tests/unit/test_backfill_universe_funding.py -q`；真實回補需 DB 環境，無 DB 時
如實回報 blocked。

ACCEPTANCE CRITERIA:
- [ ] 覆蓋報告存在且列出 universe 全體成員的 funding 覆蓋。
- [ ] `results/stage2_reprobe_20260703_funding/**/stage2_feasibility.json` 存在，
      門檻與 E-028 相同。
- [ ] `results/idea_batch_20260701_taxonomy_002/**` 與
      `git diff --stat` 均無變更（byte-identical）。
- [ ] 探測結果（PASS 或 FAIL）與 per-symbol 覆蓋一致、可對帳。

---

## P2 — 文獻前端精度包（摘要抓取 + 誠實計分 + session 評分交接）

Task: 把文獻前端從「標題關鍵字打分」升級為「摘要級、可稽核、由 Claude/Codex
session 完成最終評分」的三段式：keyword 預篩 → review bundle → session 評分。

Strategy/spec source: `docs/superpowers/specs/2026-06-30-stage3-idea-ingestion-design.md`
§3（來源 A）、§4.5；`scripts/literature_keyword_scorer.py` 現況
（`scoring_method=mechanical_keyword_placeholder`）；使用者決策 2026-07-03：
**不用 API**，LLM 評分 = Claude Code / Codex 對話 session 人機評分。

Required behavior:
1. **摘要抓取**：`fetch_papers` 層（`research/crypto-alpha-lab/src/
   crypto_alpha_lab/pipeline/paper_ingestion.py`——先例：本檔 2026-06-30 即由
   Codex 實作，屬 lab 管線程式碼，非 research 真相文件）補上 abstract 欄位：
   arXiv Atom feed 的 summary、Crossref JATS abstract（有就取）、Semantic
   Scholar Graph API `fields=abstract`。全部 keyless。
2. **retry/backoff/快取**：對 429/timeout 做指數退避（尊重 `Retry-After`），
   加 on-disk 快取（`data/literature_cache/`，gitignored），重跑不重抓。
3. **誠實子分數**：`literature_keyword_scorer.py` 移除「關鍵字命中即寫死
   data_availability=4 / implementation_fit=4」的假先驗；無 abstract 的論文
   notes 標 `metadata_only=true` 且子分數取保守下限。**無 abstract 的論文
   不得進 selected candidates**（driver 層強制）。
4. **可稽核 search log**：每 source × query 記錄查詢字串、HTTP 狀態/例外、
   抓到篇數、快取命中、retry 次數（取代現在的一行 log）。
5. **session 評分交接（取代 API LLM）**：
   - scorer 產 `review_bundle.json`：keyword 預篩 top-N（N 可設，預設 15）的
     paper_id/title/abstract/venue/year/url。**資料防火牆**：bundle 內不得含
     任何市場序列、fold 邊界、回測結果（沿用 `build_scoring_prompt` fail-closed
     檢查）。
   - Claude/Codex 在對話 session 中讀 bundle、逐篇寫 `scores_llm.json`
     （`PaperScoring` schema，`scoring_method=llm_session_claude` 或
     `llm_session_codex`，附 `reviewed_by` + 日期）。此檔由 session 手寫，
     **不是**本任務要自動生成的。
   - `run_pipeline_literature_ideas.py` 經既有 `--scores` 吃 session 分數；
     `idea_batch.json` 每個 candidate 記錄 scoring_method 來源鏈
     （prefilter=mechanical, final=llm_session_*）。scoring_method 仍為
     placeholder 的分數**不得**單獨支持 selected。

PERMITTED FILES:
- `scripts/literature_keyword_scorer.py`
- `scripts/run_pipeline_literature_ideas.py`
- `research/crypto-alpha-lab/src/crypto_alpha_lab/pipeline/paper_ingestion.py`
  （僅 fetch/abstract/快取層）
- `tests/unit/test_literature_keyword_scorer.py`、
  `tests/unit/test_pipeline_literature_ideas.py`、
  `research/crypto-alpha-lab/tests/test_pipeline_adapters.py`
- `.gitignore`（加 `data/literature_cache/`）

SCOPE LIMIT: 不改 `PaperScoring` schema 本體、不改 promote/cap 規則（≤15 不變）、
不跑真實批次（真實批次由 Claude/human 觸發）。

REQUIRED: `pytest tests/unit/test_literature_keyword_scorer.py
tests/unit/test_pipeline_literature_ideas.py -q` 及 lab suite
`pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider`。

ACCEPTANCE CRITERIA:
- [ ] arXiv/Crossref/S2 fetch 帶 abstract（可得時），429/timeout 有退避與快取，
      單元測試覆蓋（mock opener，不打真網路）。
- [ ] 無 abstract 論文：`metadata_only=true`、保守子分數、**無法**成為 selected
      （測試證明）。
- [ ] `review_bundle.json` 產出且防火牆測試證明含市場序列/fold 欄位時 fail-closed。
- [ ] driver 拒絕以 placeholder 分數單獨 select（測試證明）；接受
      `llm_session_*` 分數並在 `idea_batch.json` 記錄來源鏈。
- [ ] search log 含 query/狀態/篇數/快取/retry 各欄。

---

## P3 — 文獻路徑 prior-plausibility gate（refuted family 換皮偵測）

Task: 在文獻 driver 的 family 映射之後加一道機械 gate：候選映到
refuted/shelved family 且無 twist 證據 → 強制 skip（reason
`refuted_family_no_twist`），不得進 candidates、不得消耗 Stage-1 人審。

Strategy/spec source: ingestion spec §4.5（prior plausibility gate）；實證教訓
= `alpha-doi-10-2139-ssrn-6609698`（機械映到已 refuted 的 F-FUNDING-CARRY、
2026-07-02 Stage-1 SKIP，見
`results/idea_batch_20260702_literature_001/hypothesis_ledger_draft.md`）。

Required behavior:
1. 重用 `backtesting/pipeline_idea_generator.py` 既有的 I28 verdict 來源機制
   （讀 `docs/HYPOTHESIS_LEDGER.md` Status，唯讀），不另造 parser。
2. 判定規則：`family_id_or_NEW` 命中 refuted/shelved family 時，除非分數記錄帶
   非空 `twist_evidence` 欄（僅 `llm_session_*` 評分可填；mechanical 分數
   永遠視為無 twist），一律 skip 為 `refuted_family_no_twist`。
3. skip 記入 `idea_batch.json` 的 `skipped`（帶 reason），漏斗可稽核。

PERMITTED FILES:
- `scripts/run_pipeline_literature_ideas.py`
- `backtesting/pipeline_idea_generator.py`（僅抽出可共用的 verdict 讀取 helper，
  不改 taxonomy 路徑行為）
- `tests/unit/test_pipeline_literature_ideas.py`

SCOPE LIMIT: 只加 gate 與測試。不重跑歷史批次、不改 taxonomy 路徑既有 skip 邏輯。

REQUIRED: `pytest tests/unit/test_pipeline_literature_ideas.py
tests/unit/test_pipeline_idea_generator.py -q`。

ACCEPTANCE CRITERIA:
- [ ] 回歸測試：以 ssrn-6609698 為 fixture（title/keyword 映到 F-FUNDING-CARRY、
      mechanical 分數），driver 輸出 skip reason `refuted_family_no_twist`。
- [ ] 帶非空 `twist_evidence` 的 `llm_session_*` 分數可通過 gate（測試證明）。
- [ ] taxonomy 路徑既有測試全綠（行為未變）。

---

## P4 — 跨輪知識回饋落地（locked 決策 4）

Task: 實作跨輪回饋的機械半部：家族裁決/失敗原因 tags → 發想器排序偏置 →
`feedback_spawned` 誠實入帳。判斷半部（tags 內容）由 Claude 維護。

Strategy/spec source: ingestion spec §4.7 + §8 決策 4（**硬條件**：回饋只准影響
排序，凡回饋衍生且碰 Pass-A 的候選一律計入 family n_trials，I26 對帳涵蓋）。

Required behavior:
1. 新設 `config/pipeline_feedback_tags.yaml`（schema + 初始內容如下，Codex 照抄；
   之後內容由 Claude/human 維護）：
   ```yaml
   # 跨輪回饋 tags。內容 owner: Claude/human。機器只消費、不自動改寫。
   # reason tags: cost_kill | calm_hedge_artifact | breadth_fail |
   #              crowded_decay | harness_artifact | data_gap
   families:
     F-XS-MOMENTUM:        {verdict: refuted_shelved, reasons: [crowded_decay], guidance: avoid}
     F-S7-BASIS-MEANREV:   {verdict: shelved,          reasons: [cost_kill],     guidance: avoid}
     F-PAIRS-OU:           {verdict: refuted,          reasons: [cost_kill, crowded_decay], guidance: avoid}
     F-S5-RESIDUAL-MEANREV: {verdict: inconclusive,    reasons: [data_gap],      guidance: needs_data}
     F-S6-TS-MOMENTUM:     {verdict: inconclusive,     reasons: [crowded_decay], guidance: retry_with_twist}
     F-FUNDING-CARRY:      {verdict: refuted_shelved,  reasons: [calm_hedge_artifact, cost_kill], guidance: avoid}
     F-SENTIMENT:          {verdict: refuted,          reasons: [crowded_decay], guidance: avoid}
     F-FUNDING-XS-DISPERSION: {verdict: proposed,      reasons: [breadth_fail],  guidance: needs_data}
     F-XVENUE-LEADLAG:     {verdict: proposed,         reasons: [data_gap],      guidance: needs_data}
   ```
2. `backtesting/pipeline_idea_generator.py` 載入 tags（檔缺 = 無偏置，不失敗）：
   `guidance: avoid` 降排序、`needs_data` 在資料探測仍 FAIL 時降排序、
   `retry_with_twist` 不加分（僅不降）。**只動 rank，不動資格判定**——
   refuted-no-twist/overlay/data-blocked 的既有 skip 規則優先於 tags。
3. 排序受 tags 影響的候選在 `idea_batch.json` 標 `feedback_spawned=true`
   （欄位已存在），並原樣傳進 orchestrator 預登記 state。
4. 測試證明 `feedback_spawned=true` 候選走到 Pass-A 時被 checkpoint① 的
   n_trials 對帳計入（I26 覆蓋回饋衍生 trial）。

PERMITTED FILES:
- `config/pipeline_feedback_tags.yaml`（新）
- `backtesting/pipeline_idea_generator.py`、`scripts/run_pipeline_idea_generator.py`
- `backtesting/pipeline_orchestrator.py`（僅 `feedback_spawned` 傳遞，如需）
- `tests/unit/test_pipeline_idea_generator.py`、
  `tests/unit/test_pipeline_orchestrator.py`、
  `tests/unit/test_pipeline_checkpoint1_check.py`（僅加案例）

SCOPE LIMIT: tags 只影響排序。不得因 tags 讓任何候選繞過 cap、探測、distinctness
或入帳。不自動改寫 YAML。

REQUIRED: `pytest tests/unit/test_pipeline_idea_generator.py
tests/unit/test_pipeline_orchestrator.py tests/unit/test_pipeline_checkpoint1_check.py -q`；
本任務屬 pipeline 治理規則 → 附 Change Manifest 並補 `docs/INVARIANTS.md`
一條（回饋只動排序、必入帳）。

ACCEPTANCE CRITERIA:
- [ ] tags 檔存在且 loader 對缺檔/壞 schema fail-safe（缺=無偏置，壞=報錯拒跑）。
- [ ] 測試：同一輸入，有/無 tags 只改變順序與 `feedback_spawned` 標記，
      不改變 selected 集合資格規則。
- [ ] 測試：`feedback_spawned=true` 且進 Pass-A 的候選計入 family n_trials 對帳。
- [ ] 新 invariant 落 `docs/INVARIANTS.md` + Change Manifest。

---

## P5 — 清算資料前向累積（keyless）

Task: 沿用 OI/DVOL 既有 external adapter 模式，新增 keyless 清算資料前向累積，
為未來 F-LIQUIDATION-CASCADE 的 Stage-2 探測鋪資料。**只登記 dataset，不建
family、不跑探測/回測。**

Strategy/spec source: mechanism-taxonomy F-LIQUIDATION-CASCADE 列（blocked，無
清算 feed）；`scripts/market_data/ingest_external.py` +
`src/okx_quant/data/external_clients/binance_oi.py` 既有模式。

Required behavior:
1. 優先 REST 可輪詢 keyless 來源（候選：OKX `GET /api/v5/public/
   liquidation-orders`）。先驗證真實可得性與保留窗，如實記錄。
2. 若 REST 不可行、僅剩 WebSocket（如 Binance `forceOrder`）：**不建 daemon**，
   在任務回報中如實記 gap 並停——常駐收集器是另一個需使用者決策的部署題。
3. 新 dataset（如 `liq_okx_btc`、`liq_okx_eth`）走 `ingest_external.py` dispatch；
   `fail_on_empty_fetch` 維持 fail-closed；`--dry-run` 可驗 config/adapter。
4. 明確記錄：前向累積起點、來源保留窗、單位/欄位語義。

PERMITTED FILES:
- `src/okx_quant/data/external_clients/`（新 module 一支）
- `scripts/market_data/ingest_external.py`（dispatch 註冊）
- `tests/unit/`（對應新測試一支）

SCOPE LIMIT: 資料層 only。不更新 taxonomy data status（那是 Claude 覆蓋觀察到
真實 coverage 後的審查決定）。

REQUIRED: `pytest tests/unit/test_ingest_external*.py -q`（含新 adapter 測試）；
data-provenance Change Manifest。

ACCEPTANCE CRITERIA:
- [ ] `--dry-run` 驗證新 dataset config/dispatch 不需網路/DB。
- [ ] 空抓 raise、checkpoint 不前進（fail-closed 測試）。
- [ ] 真實可得性/保留窗如實寫進任務回報與 dataset 註記。

---

## P6 — 資料事件重探測（orchestrator `--reprobe`）

Task: orchestrator 加 advisory 重探測模式：對 latest status 為 `stage2_fail` 的
候選重跑同一 family Stage-2 探測，結果有變才 append 新狀態（append-only 不變），
並輸出 `reprobe_advisory.json` 摘要變化。

Strategy/spec source: `docs/superpowers/specs/2026-07-01-pipeline-orchestration-driver-design.md`
（I29 append-only）；實需 = OKX 1m 回補完成後 F-XVENUE-LEADLAG、P1 完成後
F-FUNDING-XS-DISPERSION 都需要有紀律的重判定路徑。

Required behavior:
1. `scripts/run_pipeline_orchestrator.py --reprobe`：只選 latest status =
   `stage2_fail` 的候選，用 state 內已記錄的 hypothesis_id（不需新 mapping 輸入），
   重跑該 family 的 Stage2Probe。
2. 結果與上次相同 → state **byte-identical**（沿用既有 idempotency 語義）；
   結果改變 → append 新 status entry（如 `stage2_fail -> stage2_pass_on_reprobe`
   或帶新 metrics 的 `stage2_fail`），舊 entry 一字不動。
3. 每次 reprobe 寫 `reprobe_advisory.json`：哪些候選重測、指標前後值、是否改判。
   改判 ≠ 自動晉級：進 Stage-3 仍走既有人審/checkpoint 流程。

PERMITTED FILES:
- `backtesting/pipeline_orchestrator.py`、`scripts/run_pipeline_orchestrator.py`
- `tests/unit/test_pipeline_orchestrator.py`

SCOPE LIMIT: 不動 Stage2Probe 本體、不動門檻、不自動觸發 Stage-3。

REQUIRED: `pytest tests/unit/test_pipeline_orchestrator.py -q`。

ACCEPTANCE CRITERIA:
- [ ] 無變化 reprobe → state byte-identical（測試證明）。
- [ ] 有變化 reprobe → 僅 append，`status_history` 舊項不變（測試證明）。
- [ ] `reprobe_advisory.json` 含前後指標與改判清單。
- [ ] `--reprobe` 不需要 `--hypothesis-ids`（讀 state），對缺 hypothesis_id 的
      state fail-closed。

---

## P7 — 批次漏斗指標 sidecar

Task: 讓「發想效率」可量測：各 driver 每批寫 `funnel_metrics.json`，外加一支
彙總 CLI 印跨批漏斗表。Advisory only。

Strategy/spec source: 2026-07-03 審核發現——目前每批「抓幾篇→過門檻幾個→
Stage-1/2/3 各過幾個」無機器可讀記錄，效率無法追蹤。

Required behavior:
1. `run_pipeline_literature_ideas.py`、`run_pipeline_idea_generator.py`、
   orchestrator 各在 batch 目錄寫 `funnel_metrics.json`：
   `{fetched, scored, above_threshold, selected, skipped: {reason: count},
   stage2_pass, stage2_fail, stage3_*}`（各 driver 填自己知道的階段，其餘省略）。
2. 新 CLI `scripts/run_pipeline_funnel_report.py`：掃 `results/idea_batch_*/`
   彙總成一張表（stdout + markdown 檔皆可），唯讀。

PERMITTED FILES:
- `scripts/run_pipeline_literature_ideas.py`、
  `scripts/run_pipeline_idea_generator.py`、
  `backtesting/pipeline_orchestrator.py`
- `scripts/run_pipeline_funnel_report.py`（新）
- 對應 `tests/unit/` 測試

SCOPE LIMIT: 純觀測。不改任何選擇/跳過邏輯；報表唯讀不回寫。

REQUIRED: `pytest tests/unit/test_pipeline_literature_ideas.py
tests/unit/test_pipeline_idea_generator.py tests/unit/test_pipeline_orchestrator.py -q`
＋新報表測試。

ACCEPTANCE CRITERIA:
- [ ] 三個 driver 各產 `funnel_metrics.json` 且計數與 `idea_batch.json`/
      state 對得上（測試證明）。
- [ ] 彙總 CLI 對既有歷史批次目錄（無 metrics 檔）不炸，標 `n/a`。

---

## P8 — 公開 OI 歷史（Binance Vision metrics；取代付費方案）

Task: 從 Binance Vision 公開 dump（`https://data.binance.vision/data/futures/
um/daily/metrics/<SYMBOL>/`，每日 zip CSV，含 5m `sum_open_interest` /
`sum_open_interest_value`，歷史約回到 2021-12）批量下載並 ingest 到
`external_observations`，解 F-OI-POSITIONING 的歷史資料封鎖。
**使用者決策 2026-07-03：不買付費 OI。**

Strategy/spec source: mechanism-taxonomy F-OI-POSITIONING 列；
`src/okx_quant/data/external_clients/binance_oi.py`（REST ~30 天窗）已有單位
慣例 `USDT_notional`。

Required behavior:
1. **Step 0（fail-closed 驗證）**：先對 BTCUSDT 抓一日檔驗證可得性與 schema
   （欄位名、時區、單位）。若 metrics dump 不存在或 schema 不符，**如實回報並
   停**——不得靜默退回 REST 30 天窗充當歷史。
2. 批量下載器（新 script）：symbol × 日期範圍 → 下載 zip → 解析 CSV →
   寫 `external_observations`，dataset 如 `oi_binance_hist_btc` /
   `oi_binance_hist_eth`（先 BTC/ETH，universe 擴展另議）。單位與既有
   `oi_binance_*` 一致（`USDT_notional`，取 `sum_open_interest_value`），
   provenance 註記 `binance_vision_metrics`（與 REST 來源可區分）。
3. 冪等：重跑同日不重複寫入（upsert 或 checkpoint）。
4. 產 per-symbol 覆蓋報告（first/last ts、rows、缺日清單）。

PERMITTED FILES:
- `scripts/market_data/download_binance_vision_metrics.py`（新）
- `src/okx_quant/data/external_clients/`（如需 thin parser module）
- `scripts/market_data/ingest_external.py`（dispatch 註冊，如走此路徑）
- 對應 `tests/unit/` 測試（本地 fixture zip/CSV，不打真網路）

SCOPE LIMIT: 資料層 only。不建 family/探測/回測；taxonomy data status 更新留給
Claude 審查。BTC/ETH 先行。

REQUIRED: 新測試 + `pytest tests/unit -k binance_vision -q`；data-provenance
Change Manifest；真實下載需網路/DB，環境缺就如實回報。

ACCEPTANCE CRITERIA:
- [ ] Step 0 驗證結果（可得/不可得、schema）如實寫進回報。
- [ ] fixture 測試證明解析、單位換算、冪等寫入正確。
- [ ] （環境允許時）BTC/ETH 2024-01-01→今 覆蓋報告存在，缺日如實列出。
- [ ] REST 30 天路徑與 Vision 歷史路徑 provenance 可區分，未互相污染。

---

## P9 — universe membership builder 改吃 canonical DB（2026-07-03 實資料驗收時新診斷）

Task: 修 `scripts/build_universe_membership.py` 的資料來源缺陷：它只讀本地
`data/ticks/*/candles_1m.parquet`（薄鏡像），導致 `eligible` 是「當天磁碟剛好
有哪些 parquet」的假象。改為（或新增）從 canonical DB 計算每日美元成交量，
重建共用的 `data/universe/universe_membership.parquet`。

Strategy/spec source: 2026-07-03 Claude 實資料驗收診斷。實測證據：
- 現行 membership:每日 eligible 中位數 **2**(BTC/ETH 僅 61 天 eligible、
  MEME 卻 657 天——經濟上不可能);這是 E-028 `universe=8`、H-004 S5
  「no grid activity」的共同根因。
- DB 重建診斷(`data/universe/universe_membership_db_20260703.parquet`,
  scratch 產出):探測窗內每日 eligible 中位數 **29**、868/898 天廣度 ≥10。
- 對照探測 artifact:`results/stage2_reprobe_20260703_funding/`(現行
  membership:good 7/10、min_daily 1、median 2.0 FAIL)vs
  `results/stage2_reprobe_20260703_funding_dbuniverse/`(DB universe:
  good 28/10 ✓、median 27 ✓、僅 min=2 因 warmup 窗緣 FAIL)。

Required behavior:
1. `build_universe_membership.py` 新增 DB 路徑:從 `canonical_candles`
   (`bar='1m'`,`source_primary='binance'`)以 `sum(vol_quote)` 聚合每日
   美元成交量;資格邏輯(`build_membership()`)**一字不改**。保留 parquet
   路徑作為無 DB fallback,輸出需標注 `source`(db/parquet)。
2. 排除覆蓋不足的日(建議 `bar_count >= 1000`/日才算 active,防半日資料)。
3. 重建共用 `data/universe/universe_membership.parquet`(gitignored 本地檔),
   輸出前後 eligible/day 統計對照。
4. 重跑 `run_pipeline_stage2_data_probe.py --candidate funding` 進
   `results/stage2_reprobe_<date>_funding_rebuilt/`,誠實記錄 PASS/FAIL。
5. warmup 窗緣已於 2026-07-03 經使用者批准並由 Claude 實作:廣度 min 只評估
   `START+30d` 之後(`FundingThresholds.breadth_warmup_days`,manifest
   `docs/change_manifests/2026-07-03-stage2-breadth-warmup.md`)。P9 **不需**
   再動窗口;門檻值仍一字不改。DB-universe 診斷 + 新窗口的預覽 =
   `data_availability=PASS`(good 28/10、min 24/10,
   `results/stage2_reprobe_20260703b_funding_warmupwin_dbuniverse/`),
   所以 P9 重建 membership 後預期正式 PASS。

PERMITTED FILES:
- `scripts/build_universe_membership.py`
- `tests/unit/`(builder 的 DB-source 單元測試,mock conn)
- `results/stage2_reprobe_*_funding_rebuilt/`(新 artifact)

SCOPE LIMIT: 不動 Stage-2 門檻、探測窗、資格公式。不動既有 reprobe artifacts。

REQUIRED: 新測試 + `pytest tests/unit -k universe -q`;真實重建需 DB。

ACCEPTANCE CRITERIA:
- [ ] DB 路徑與 parquet 路徑用同一 `build_membership()`(測試證明)。
- [ ] 重建後 membership 在 2024-02→2026-06 的每日 eligible 中位數 ≥ 20。
- [ ] 重跑探測 artifact 存在;門檻/窗未改;PASS 或 FAIL 誠實記錄。
- [ ] 舊 membership 檔的差異對照(前後 eligible/day)寫入任務回報。

---

## 交付順序建議

1. **第一波（並行）**：P1（funding 回補）、P8（OI 歷史）、P2（文獻精度包）。
2. **第二波**：P3（小）、P6（等 P1/OKX 回補有東西可重測時最有價值）。
3. **第三波**：P4、P5、P7。
4. 全部落地後，才討論把 orchestrator 接上排程（cron/loop）——在那之前自動化
   只會更快地把低精度候選送進人審。

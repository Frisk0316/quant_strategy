---
status: draft
type: design
owner: human
created: 2026-07-01
last_reviewed: 2026-07-01
expires: none
superseded_by: null
---

# Pipeline 編排 driver 設計(把 §6 的一句話展開成可交付任務)

> 對應 [stage3-idea-ingestion-design.md §6](2026-06-30-stage3-idea-ingestion-design.md#6-編排roadmap-編排-c)
> 「cron/loop driver 觸發 → 自動發想一批 → 預先登記 → 對每候選跑 Stage 2→3 →
> checkpoint① auto checker 擋機械硬傷 → 把 NEEDS_HUMAN / auto-PASS 的彙整成短名單 →
> 人只審判斷項 + 發布」。這份 spec 把那句話展開成可驗收的設計 + Codex 任務。
>
> **優先級**:使用者 2026-07-01 指定這塊優先於其他候選/資料蒐集工作,因為這是目前
> pipeline 唯一「真正未實作的機械件」——B/A 半發想、Stage 2 可行性、checkpoint①、
> family-minting 全部已存在,只是沒有一個東西把它們串起來自動跑。
>
> **2026-07-01 第二版(Claude 審閱後加固)**:第一版把「要做什麼」講清楚了,但把
> 「怎麼做」留了幾個會讓 Codex 卡住或做出不安全預設的空隙——確切的登記表 Callable
> 簽章、`idea_batch.json` 候選缺 `hypothesis_id`/`candidate_dir` 欄位、既有 3 個
> Stage-3 runner 是寫死路徑的 0-參數函式(直接登記會有「幫錯的 batch 覆寫舊
> results」的地雷)、文獻批次任務 B 的 `--source` 二次抓取與 `--scores` 對不上
> `paper_id` 的競態風險。本版把這些逐一定案,§1.2/§1.3/§1.5 改寫、新增 §1.6/§1.7,
> Task A/B 的 Required Behavior、Permitted Files、Acceptance Criteria 同步更新。
> §0/§2/§3(除已標註處)語義不變。

## 0. 先講清楚一個關鍵限制(否則這份 spec 會過度承諾)

現況盤點發現:**Stage 2 資料探測與 Stage 3 回測都不是通用的**。

- `scripts/run_pipeline_stage2_data_probe.py` 目前**寫死給 taxonomy_002 的兩個候選**
  (`probe_funding` / `probe_xvenue`),module-level 常數 `BATCH_ID`/`START`/`END_EXCLUSIVE`
  也是寫死的。它確實已經用一個 `CANDIDATES: dict[str, CandidateSpec]` 的登記表模式——
  這是可以擴展的起點,但目前只登記了 2 個 family。
- Stage 3(`docs/superpowers/pipeline/stage3-implement-backtest.md`)明文寫
  「Role: Codex, trading-core implementation」——每個新 family 的回測邏輯目前都是
  Codex 手刻的獨立模組(`c1_pairs_ou`/`c2_funding_carry`/`c3_sentiment_backtest.py` 等),
  不是一個吃參數就能跑任意機制的通用引擎。

**結論**:「cron 觸發後從發想到短名單全自動跑完」對於*還沒有人寫過 Stage2/3 程式碼的新
family* 是不誠實的承諾——那等於要 driver 自己生程式碼,是完全不同量級、風險也高得多的
能力,**本 spec 不做這個**。

**本 spec 實際做的**:把「發想→逐候選跑 Stage2→(有 Stage3 就跑)→checkpoint①→彙整短名單」
這條**狀態機 + 排程/對帳**自動化,Stage2 探測函式與 Stage3 回測函式維持**依 family_id
查表的可插拔登記**。已經有程式碼的 family(目前 2 個)可以真的一路自動跑到短名單;
還沒有程式碼的 family,driver 誠實停在 `awaiting_stage2_implementation` /
`awaiting_stage3_implementation`,列進短名單提醒人補實作,**不會靜默跳過、不會捏造結果**。

這仍然是真實的自動化收益:現在每批要人工依序呼叫 4-5 支腳本、手寫 `shortlist.md`;
之後對「已有程式碼」的 family 是一個指令到底,對「還沒有程式碼」的 family 也不會被漏審。

## 1. 設計

### 1.1 狀態機

每個候選在一個批次內走以下狀態(單向,不可逆向刪除,對應 ingestion §4.4「批次預先登記」
延伸到自動候選):

```text
idea_registered
  → awaiting_stage2_implementation (family 沒有登記 Stage2 探測函式,停)
  → stage2_fail (探測跑了,data_availability FAIL 或 distinctness/cost_after_edge 缺席
                 導致 stage2_status FAIL,停)
  → stage2_pass
    → awaiting_stage3_implementation (family 沒有登記 Stage3 回測函式,停)
    → stage3_done
      → checkpoint1_pass | checkpoint1_fail | checkpoint1_needs_human
```

沒有新增 `awaiting_family_minting` 這類額外狀態(第一版審閱時考慮過,見 §1.6 的理由)——
family 未定案的候選一律自然落在 `awaiting_stage2_implementation`,原因與「沒人寫探測函式」
完全一致:**這個 family_id 在 `STAGE2_PROBES` 裡查不到**,不需要為此另開一條分支。

### 1.2 批次狀態檔(新增,延伸既有批次預先登記機制)

`results/<batch_id>/orchestrator_state.json`:

```json
{
  "schema_version": 1,
  "batch_id": "idea_batch_20260701_taxonomy_002",
  "created_at": "2026-07-01T00:00:00+00:00",
  "source": "taxonomy",
  "max_runtime_seconds": 600,
  "candidates": [
    {
      "candidate_id": "B-f-funding-xs-dispersion",
      "candidate_dir": "f_funding_xs_dispersion",
      "family_id": "F-FUNDING-XS-DISPERSION",
      "hypothesis_id": "H-009",
      "status": "stage2_fail",
      "status_history": [
        {"status": "idea_registered", "at": "2026-07-01T00:00:00+00:00"},
        {"status": "stage2_fail", "at": "2026-07-01T00:00:05+00:00"}
      ],
      "stage2_feasibility_path": "results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/stage2_feasibility.json",
      "summary_path": null,
      "checkpoint1_auto_path": null
    }
  ]
}
```

- `source` ∈ `{"taxonomy", "literature", "mixed"}`,直接抄 `idea_batch.json` 的 `source`
  欄位(已由 `pipeline_idea_generator.register_batch` 產生,不必重算)。
- `max_runtime_seconds` 必填,無預設(見 §1.7)。
- **append-only**:候選一旦預先登記(driver 開跑前先把整批候選連同 `idea_registered`
  狀態寫進這個檔),之後只能**往前推進 `status_history`**,不能刪除候選或覆蓋既有紀錄。
  對應新 invariant I29(見下)。
- **重跑同一 `batch_id` 是冪等的**:CLI 每次執行先嘗試讀取既有
  `results/<batch_id>/orchestrator_state.json`;若存在,就地載入,只對仍處於非終態
  (`idea_registered`/`stage2_pass`/`stage3_done` ——正常情況下單次執行內就會把每個候選推
  進到終態,所以第二次執行通常是純粹的重放/no-op)的候選繼續推進;已經是終態
  (`stage2_fail`/`awaiting_stage2_implementation`/`awaiting_stage3_implementation`/
  `checkpoint1_pass`/`checkpoint1_fail`/`checkpoint1_needs_human`)的候選**一律跳過**,
  不重新呼叫任何探測/回測函式。若檔案不存在,才呼叫 `pre_register_batch` 建立初始狀態。
- 這個檔本身不是永久 ledger,是 batch 對帳用的 sidecar,跟現有 `idea_batch.json` /
  `hypothesis_ledger_draft.md` 同一個等級——**不寫入 `docs/HYPOTHESIS_LEDGER.md` /
  `docs/EXPERIMENT_REGISTRY.md`**,那兩個檔仍然只由 Claude/人審後手動/半手動 append。

### 1.3 Stage2/Stage3 可插拔登記表

把 `run_pipeline_stage2_data_probe.py` 現有的 `CANDIDATES` dict 模式抽成可匯入的登記表
(對現有兩個 family 的探測邏輯**零行為變更**,純粹讓 orchestrator 可以查表呼叫)。

**Stage2 移動範圍**:`CandidateSpec`、`FundingThresholds`、`VenueThresholds`、`CANDIDATES`、
`build_stage2_result`、`build_fail_closed_result`、`build_funding_data_check`、
`build_xvenue_data_check`、`load_point_in_time_universe`、`_connect`、
`_fetch_funding_timestamps`、`_summarize_funding`、`probe_funding`、`_fetch_venue_coverage`、
`probe_xvenue`,以及它們用到的小工具函式(`_utc`/`_iso_dt`/`_jsonable`/`_expected_1m_rows`/
`_expected_8h_rows`/`_safe_ratio`/`_quantiles`/`_spec`)**整段搬到**
`backtesting/pipeline_stage2_registry.py`,函式體逐字不變。
`BATCH_ID`/`START`/`END_EXCLUSIVE`/`DSN`/`UNIVERSE_PATH`/`FUNDING_SOURCE`/`VENUES`/
`XVENUE_SYMBOLS`/`FUNDING_MIN_*`/`XVENUE_MIN_*` 這些**CLI 專屬預設值留在**
`scripts/run_pipeline_stage2_data_probe.py`(它是 taxonomy_002 這一支 CLI 的預設,不是
orchestrator 的通用設定)。`run_pipeline_stage2_data_probe.py` 改為
`from backtesting.pipeline_stage2_registry import (...)` 逐一具名匯入,`main()`/
`run_data_probe()`/`_candidate_list()`/`_print_summary()` 留在原地不動,CLI 行為不變。

在 `backtesting/pipeline_stage2_registry.py` 新增 orchestrator 要查的表,**key 是
family_id**(不是舊的 `"funding"`/`"xvenue"` candidate key),並用一層薄 adapter 統一
signature,因為 `probe_funding` 需要 `universe_path`、`probe_xvenue` 不需要:

```python
Stage2Context = Mapping[str, Any]  # 至少含 "start", "end"(datetime), "universe_path"(Path)
Stage2Probe = Callable[[Any, Stage2Context], Awaitable[FeasibilityResult]]

async def _run_funding_probe(conn: Any, ctx: Stage2Context) -> FeasibilityResult:
    return await probe_funding(
        conn, universe_path=ctx["universe_path"], start=ctx["start"], end=ctx["end"],
        thresholds=FundingThresholds(),
    )

async def _run_xvenue_probe(conn: Any, ctx: Stage2Context) -> FeasibilityResult:
    return await probe_xvenue(conn, start=ctx["start"], end=ctx["end"], thresholds=VenueThresholds())

STAGE2_PROBES: dict[str, Stage2Probe] = {
    "F-FUNDING-XS-DISPERSION": _run_funding_probe,
    "F-XVENUE-LEADLAG": _run_xvenue_probe,
}
```

**Stage3 登記表要處理一個真實地雷**:`scripts/run_pipeline_batch2_checkpoint.py::run_c1()` /
`run_c2()` / `run_c3()` 是**0 參數函式**,內部寫死
`BATCH_ID = "pipeline_batch2_20260625"` 與 `OUT = Path("results") / BATCH_ID`。如果登記表
直接把它們當成「吃任意 batch 的 Stage3 runner」呼叫,orchestrator 對一個*新*
`batch_id` 呼叫 `F-PAIRS-OU` 時,會**悄悄把 summary.json 寫進舊的
`results/pipeline_batch2_20260625/c1_pairs_ou/` 目錄**,而不是這次批次自己的目錄——這是
一個會靜默污染既有 artifact 的 bug,必須在登記表這層擋掉。做法:登記表 adapter 檢查
context 的 `batch_id`,只有等於這 3 個函式寫死的 `pipeline_batch2_20260625` 才放行,否則
丟出明確例外(不是回傳假結果,不是靜默略過):

```python
Stage3Context = Mapping[str, Any]  # batch_id, candidate_id, candidate_dir, hypothesis_id,
                                    # family_id, output_root, dsn, start, end
Stage3Runner = Callable[[Stage3Context], dict[str, Any]]

_LEGACY_BATCH_ID = "pipeline_batch2_20260625"

def _legacy_runner(fn: Callable[[], dict[str, Any]], family_id: str) -> Stage3Runner:
    def _run(ctx: Stage3Context) -> dict[str, Any]:
        if ctx["batch_id"] != _LEGACY_BATCH_ID:
            raise RuntimeError(
                f"{family_id} Stage3 runner is a refuted-batch demo entry scoped to "
                f"batch_id={_LEGACY_BATCH_ID!r}; refusing to run for "
                f"batch_id={ctx['batch_id']!r} to avoid overwriting the old batch2 "
                "results directory"
            )
        return fn()
    return _run

STAGE3_RUNNERS: dict[str, Stage3Runner] = {
    "F-PAIRS-OU": _legacy_runner(run_c1, "F-PAIRS-OU"),
    "F-FUNDING-CARRY": _legacy_runner(run_c2, "F-FUNDING-CARRY"),
    "F-SENTIMENT": _legacy_runner(run_c3, "F-SENTIMENT"),
}
```

這 3 個 family 已經 refuted,`pipeline_idea_generator.enumerate_gaps` 早就把
`refuted_no_twist` 的 family 排除在 `idea_batch.json` 之外(見既有 I28),所以正常批次
**不會**經由 orchestrator 真的呼叫到這 3 個 legacy runner——登記它們純粹是讓
`STAGE3_RUNNERS` 有非空示範,而上面的 batch_id 守門是「萬一有人手動塞一個
family_id 對到這三者」時的安全網,不是預期路徑。`F-FUNDING-XS-DISPERSION` /
`F-XVENUE-LEADLAG` 目前沒有 Stage3 runner,**不得**臨時生一個湊數,留在 registry 外,
orchestrator 會正確停在 `awaiting_stage3_implementation`。

`pipeline_stage3_registry.py` 從 `scripts/run_pipeline_batch2_checkpoint.py` **只 import**
`run_c1`/`run_c2`/`run_c3`,不修改該檔任何一行(它不在本任務 PERMITTED FILES 內)。

### 1.4 停止條件(沿用已鎖決策,不新增)

- 批次跑完(所有候選到終態)。
- 撞候選數上限(≤15,idea_generator 已控管,orchestrator 只做存在性檢查,不重複收斂邏輯)。
- 撞 `max_runtime_seconds`(**CLI 必填,無靜默預設**——沒填就是 argparse 直接報錯,對應
  ingestion §4.6「runtime 上限仍須啟動時填,無靜默預設」)。超時檢查點設在**兩個候選之間**
  (每推進完一個候選就檢查一次累積耗時),不做候選內部(例如 Stage2 DB 查詢中途)的搶佔;
  已經開始推進的候選一定會跑完自己的 Stage2/3/checkpoint1,下一個候選才會被超時擋下,
  該候選維持在它被擋下前的最後狀態(通常是 `idea_registered`,未被推進)。
- family 撞 K 上限(family-minting checker 已回報 `at_k_limit`,orchestrator 只讀不判斷)。

### 1.5 彙整短名單(自動產生,取代現在手寫的 `shortlist.md`)

跑完批次後,從 `orchestrator_state.json` 產出 `results/<batch_id>/shortlist.md`,單一表格
(不分「通過」/「未通過」兩張表——orchestrator 的終態種類比 promotion 的 pass/fail 更多,
分兩表會把 `awaiting_*` 硬塞進某一邊,不誠實):

```markdown
# Batch `<batch_id>` Orchestrator Shortlist

- Generated by: `scripts/run_pipeline_orchestrator.py`
- Candidates: <n>

| Candidate | Family | Hypothesis | Final status | Checkpoint1 auto status | Human review items |
|---|---|---|---|---|---|
| B-f-funding-xs-dispersion | F-FUNDING-XS-DISPERSION | H-009 | stage2_fail | n/a | n/a |
| B-f-xvenue-leadlag | F-XVENUE-LEADLAG | H-010 | stage2_fail | n/a | n/a |
```

規則:

- 每個候選一行,欄位 = candidate_id、family_id、hypothesis_id、最終 `status`、
  `checkpoint1_auto_status`(只有終態是 `checkpoint1_*` 時才有值,否則 `n/a`)、
  固定的 `human_review_items`(來自 `Checkpoint1Result.human_review_items`,只有終態是
  `checkpoint1_*` 時才有值)。
- `awaiting_stage2_implementation` / `awaiting_stage3_implementation` 的候選**一樣列出**,
  `Human review items` 欄位寫死文字 `待 Codex 補 Stage2 探測函式` /
  `待 Codex 補 Stage3 回測 runner`,不得省略、不得留白。
- `family_id` 顯示 `orchestrator_state.json` 裡記的值,**即使該值是字面上的 `"NEW"`**
  (見 §1.6 第 3 點)——短名單就是要讓人看到「這個候選連 family 都還沒真的分派」。

### 1.6 候選欄位解析規則(從 `idea_batch.json` 到 `orchestrator_state.json` 候選)

`idea_batch.json` 的 `candidates[]`(見
`backtesting/pipeline_idea_generator.py::register_batch`)**不包含** `candidate_dir` 或
`hypothesis_id` 欄位——這是既有格式的事實,不是本 spec 的疏漏,`pre_register_batch` 必須
從既有欄位機械推導,推不出來的就是硬性失敗,不得捏造:

1. **`candidate_id`**:直接取候選的 `provisional_candidate_id`(已存在,例如
   `"B-f-funding-xs-dispersion"`)。
2. **`candidate_dir`**:確定性推導,規則 = 去掉開頭的 `"B-"` 或 `"A-"` 來源前綴,再把
   `-` 換成 `_`:

   ```python
   def derive_candidate_dir(provisional_candidate_id: str) -> str:
       slug = provisional_candidate_id
       for prefix in ("B-", "A-"):
           if slug.startswith(prefix):
               slug = slug[len(prefix):]
               break
       return slug.replace("-", "_")
   ```

   驗證:`"B-f-funding-xs-dispersion"` → `"f_funding_xs_dispersion"`;
   `"B-f-xvenue-leadlag"` → `"f_xvenue_leadlag"`——與既有
   `results/idea_batch_20260701_taxonomy_002/{f_funding_xs_dispersion,f_xvenue_leadlag}/`
   目錄名完全吻合,必須寫測試鎖住這個推導規則。
3. **`family_id`**:取 `candidate.get("family_id") or candidate.get("family_id_or_NEW")`。
   若該值為空字串、`None`,或字面上等於 `"NEW"`(A-half 文獻候選在
   `family_minting_decision == "MINT"` 或分類對不到既有 family 時會是這個值,見
   `research/crypto-alpha-lab/src/crypto_alpha_lab/adapters/parent_stage1.py`),
   **不特別分岔處理**——原樣把這個值(含字面 `"NEW"`)寫進
   `orchestrator_state.json` 的 `family_id` 欄位。因為 `STAGE2_PROBES`/`STAGE3_RUNNERS`
   本來就不會有 `"NEW"` 這個 key,候選自然落在 `awaiting_stage2_implementation`,短名單
   照樣把它列出來提醒人去做 family-minting 判斷——不需要為這個情境另建一條狀態分支
   (見 §1.1 的說明)。**必須有一條測試**:給一個 `family_id_or_NEW == "NEW"` 的假候選,
   確認 orchestrator 不炸、最終落在 `awaiting_stage2_implementation`、`family_id` 欄位
   如實顯示 `"NEW"`。
4. **`hypothesis_id`**:`idea_batch.json` 完全沒有這個欄位——指派 H-XXX 編號是 Claude/人
   在 Stage-1 審查時做的事(現況:taxonomy_002 的 H-009/H-010 是 Codex 手動對應寫死在
   `CANDIDATES` dict 裡,不是從 `idea_batch.json` 算出來的)。`pre_register_batch` 新增
   **必填**參數 `hypothesis_ids: Mapping[str, str]`(candidate_id → hypothesis_id),CLI
   對應 **必填** `--hypothesis-ids <path to json>` 參數,格式:

   ```json
   {"B-f-funding-xs-dispersion": "H-009", "B-f-xvenue-leadlag": "H-010"}
   ```

   若 `idea_batch.json` 裡任何一個候選的 `candidate_id` 不在這個映射裡,
   `pre_register_batch` **必須丟出 `ValueError`,整批註冊失敗**(不寫任何檔案、不部分
   註冊)——這個映射檔就是 Claude/人完成 Stage-1 審查、確認候選值得往下跑的憑證,跟
   `--max-runtime-seconds` 一樣走「必填、無靜默預設」的原則。

### 1.7 狀態推進邏輯(`advance_candidate` 逐狀態規則)

```text
狀態 idea_registered:
  probe = STAGE2_PROBES.get(candidate.family_id)
  若 probe 為 None → 狀態變 awaiting_stage2_implementation(終態,停)
  否則:
    result = await probe(conn, context)          # FeasibilityResult
    寫 results/<batch_id>/<candidate_dir>/stage2_feasibility.json
      (內容 = pipeline_feasibility.result_to_dict(result),沿用既有函式)
    stage2_status = pipeline_feasibility.evaluate_stage2_result(result)
    若 stage2_status == "FAIL" → 狀態變 stage2_fail(終態,停)
    否則 → 狀態變 stage2_pass

狀態 stage2_pass:
  runner = STAGE3_RUNNERS.get(candidate.family_id)
  若 runner 為 None → 狀態變 awaiting_stage3_implementation(終態,停)
  否則:
    summary = runner(context)   # dict;runner 自己負責把 summary.json 寫到它認定的路徑
    → 狀態變 stage3_done,記錄 summary_path

狀態 stage3_done:
  registry_text = Path("docs/EXPERIMENT_REGISTRY.md").read_text(encoding="utf-8")  # 只讀一次
  ckpt_result = pipeline_checkpoint1.evaluate_summary(summary, registry_text, summary_path)
  ckpt_status = pipeline_checkpoint1.evaluate_checkpoint1_result(ckpt_result)
  寫 results/<batch_id>/<candidate_dir>/checkpoint1_auto.json
    (內容 = pipeline_checkpoint1.result_to_dict(ckpt_result),沿用既有函式)
  → 狀態變 checkpoint1_pass | checkpoint1_fail | checkpoint1_needs_human
    (對應 ckpt_status == PASS | FAIL | NEEDS_HUMAN;終態,停)
```

全程**只呼叫既有函式**(`pipeline_feasibility.result_to_dict`/`evaluate_stage2_result`、
`pipeline_checkpoint1.evaluate_summary`/`evaluate_checkpoint1_result`/`result_to_dict`),
orchestrator 本身不重新實作任何判定邏輯——這點是既有草稿就定下的 SCOPE LIMIT,第二版只是
把「怎麼呼叫」寫得更具體。

## 2. 仍然不會被自動化的部分(照 §5 原則,升級成批級稽核,不是待辦)

- 幫新 family 寫 Stage2 探測 / Stage3 回測程式碼——永遠是 Codex 的實作任務,orchestrator
  只負責排程與對帳,不生程式碼。
- family 是否要 mint / assign / skip(family-minting 的 `MINT`/`NEEDS_HUMAN`/
  `SKIP_RECOMMENDED` 判斷本身)、checkpoint① #8 裁決、#9 重試 vs 新 family——永遠人審。
- idea-source corpus 批准、family-minting 稽核頻率、成本真實性判斷、發布——永遠人審。

## 3. Codex 任務 A(交付用):實作 orchestrator

```text
Task: 實作 pipeline 編排 driver,把「發想→逐候選 Stage2→(有 Stage3 就跑)→checkpoint①→
      短名單」串成一個狀態機驅動的 CLI,Stage2/3 維持依 family_id 查表的可插拔登記
Strategy/spec source: 本文件(2026-07-01 第二版,§1.1-§1.7)+
                       2026-06-30-stage3-idea-ingestion-design.md §4.4/§4.6/§6

Required behavior:
  - 新增 backtesting/pipeline_orchestrator.py(純函式優先,鏡像 pipeline_checkpoint1.py/
    pipeline_feasibility.py 的既有模式:dataclass 或 dict 皆可,但 I/O 集中在
    `run_orchestrator`,狀態推進邏輯保持可單元測試),精確函式簽章:

    def pre_register_batch(
        idea_batch: Mapping[str, Any],
        *,
        hypothesis_ids: Mapping[str, str],
        batch_id: str,
        max_runtime_seconds: int,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        """依 §1.2/§1.6 規則把 idea_batch['candidates'] 轉成初始 orchestrator_state
        payload(全部 idea_registered)。寫入前檢查候選數 <=15(沿用 idea_generator
        既有上限,只做存在性檢查,不重算排序);任何候選的 candidate_id 不在
        hypothesis_ids 裡就 raise ValueError,不寫任何檔案。"""

    async def advance_candidate(
        candidate: MutableMapping[str, Any],
        *,
        conn: Any,
        context: Mapping[str, Any],   # batch_id, candidate_dir, output_root, start, end,
                                      # universe_path, dsn
        stage2_probes: Mapping[str, Stage2Probe],
        stage3_runners: Mapping[str, Stage3Runner],
        registry_text: str,
    ) -> None:
        """依 §1.7 就地推進單一候選到下一個終態或停等狀態,append-only 寫
        status_history。候選已在終態時直接 return,不重跑。"""

    def render_shortlist(state: Mapping[str, Any]) -> str:
        """依 §1.5 格式回傳 shortlist.md 內容(markdown字串)。"""

    async def run_orchestrator(
        *,
        idea_batch_path: Path,
        hypothesis_ids_path: Path,
        batch_id: str,
        max_runtime_seconds: int,
        output_root: Path,
        dsn: str,
        universe_path: Path,
        start: str,
        end_exclusive: str,
    ) -> Path:
        """CLI 用的頂層入口:載入或建立 orchestrator_state.json,依 §1.4 停止條件
        推進所有未到終態的候選,寫回 state 檔 + shortlist.md,回傳批次輸出目錄。"""

  - 新增 backtesting/pipeline_stage2_registry.py:依 §1.3 把
    scripts/run_pipeline_stage2_data_probe.py 現有邏輯整段搬過來,新增 keyed-by-family_id
    的 STAGE2_PROBES dict(見 §1.3 程式碼)。對既有兩個候選**輸出必須逐位元組相同**
    (regression,不是重寫探測邏輯)。run_pipeline_stage2_data_probe.py 改為 import 這個
    登記表,CLI 行為不變。
  - 新增 backtesting/pipeline_stage3_registry.py:依 §1.3 只 import(不修改)
    scripts/run_pipeline_batch2_checkpoint.py 的 run_c1/run_c2/run_c3,用
    `_legacy_runner` adapter 包一層 batch_id 守門(見 §1.3 程式碼),登記
    F-PAIRS-OU / F-FUNDING-CARRY / F-SENTIMENT。F-FUNDING-XS-DISPERSION /
    F-XVENUE-LEADLAG 目前沒有 Stage3 runner,**不得**臨時生一個湊數,留在 registry 外。
  - 新增 scripts/run_pipeline_orchestrator.py(CLI):
    參數 `--batch-id`(必填)、`--idea-batch-path`(必填,既有 idea_batch.json 路徑——
    **不支援** `taxonomy`/`literature` 關鍵字模式,那是各自既有 CLI
    `run_pipeline_idea_generator.py` / `run_pipeline_literature_ideas.py` 的職責,
    orchestrator 只消費它們的輸出)、`--hypothesis-ids`(必填,見 §1.6 第 4 點)、
    `--max-runtime-seconds`(**required=True,不給預設值**)、`--output-root`(預設
    `results`)、`--dsn`(預設沿用既有 DSN 常數)、`--universe-path`(預設
    `data/universe/universe_membership.parquet`)、`--start`(預設 `2024-01-01`)、
    `--end-exclusive`(預設 `2026-06-17`)。跑完寫 orchestrator_state.json + shortlist.md。
  - 在 docs/INVARIANTS.md 新增 I29(文字見下)。

I29(接 I28 後):
  「pipeline 編排 driver 的批次狀態檔(orchestrator_state.json)必須在開跑前完成候選
   預先登記,之後的狀態變更只能 append 到 status_history、不得刪除或覆蓋既有候選；
   預先登記時每個候選的 hypothesis_id 必須來自呼叫端明確提供的映射,缺一個就整批註冊
   失敗,不得留空或臨時生成。沒有登記 Stage2 探測函式或 Stage3 回測函式的 family
   (含 family_id 字面為 "NEW" 的候選)必須停在 awaiting_stage2_implementation /
   awaiting_stage3_implementation 並列入短名單,不得靜默跳過或以其他 family 的結果代替。
   針對寫死輸出路徑的既有 Stage3 runner,登記表必須以 batch_id 守門,拒絕在非其原生
   batch 下執行,以免覆寫既有 artifact。driver 不得寫入 docs/HYPOTHESIS_LEDGER.md 或
   docs/EXPERIMENT_REGISTRY.md。
   守護:R6.3 / R7.4;測試:tests/unit/test_pipeline_orchestrator.py」

PERMITTED FILES (only edit these):
- backtesting/pipeline_orchestrator.py           (新增)
- backtesting/pipeline_stage2_registry.py        (新增)
- backtesting/pipeline_stage3_registry.py        (新增)
- scripts/run_pipeline_orchestrator.py           (新增)
- scripts/run_pipeline_stage2_data_probe.py      (僅允許「改為 import 新登記表」的最小重構,
                                                   輸出/CLI 行為不得改變)
- tests/unit/test_pipeline_orchestrator.py       (新增)
- tests/unit/test_pipeline_stage2_registry.py    (新增)
- tests/unit/test_pipeline_stage3_registry.py    (新增)
- docs/INVARIANTS.md                             (僅加 I29)
- docs/superpowers/pipeline/stage3-implement-backtest.md
  (僅加一句:新 Stage3 runner 要進 orchestrator 自動排程,需在
   backtesting/pipeline_stage3_registry.py 登記)
- docs/change_manifests/2026-07-01-pipeline-orchestrator.md  (新增,鏡像
  checkpoint①/family-minting manifest 的 R6.3/R7.4 doc-impact 審查;trigger area
  A5 backtesting + A9 validation/gates,同
  docs/change_manifests/2026-06-30-checkpoint1-automation.md 的引用方式)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ , signals/ , risk/ , portfolio/ , execution/
- backtesting/cpcv.py , walk_forward.py , differential_validation.py , replay.py
  (只讀既有輸出,不改回測/統計演算法)
- backtesting/c1_pairs_ou*.py, c2_funding_carry*.py, c3_sentiment_backtest.py
  (只 import/呼叫既有函式,不改其回測邏輯/輸出)
- scripts/run_pipeline_batch2_checkpoint.py(只 import run_c1/run_c2/run_c3,不修改此檔
  任何一行,包括其寫死的 BATCH_ID/OUT 路徑)
- backtesting/pipeline_idea_generator.py、backtesting/pipeline_family_minting.py
  (只呼叫既有函式/讀既有輸出,不改候選上限、排序、family-minting 判定邏輯)
- analytics/dsr.py ; config/risk.yaml ; config/settings.yaml
- 任何 deployment/demo/shadow/live gate
- HYPOTHESIS_LEDGER.md / EXPERIMENT_REGISTRY.md(只讀,orchestrator 不得寫入)
- 既有 results/** artifact(不得回寫/遷移;含 results/idea_batch_20260701_taxonomy_002/**
  的既有 stage2_feasibility.json 與 results/pipeline_batch2_20260625/** 底下所有既有
  summary.json/stage2_feasibility.json——regression 測試用複製/新路徑比對,不覆蓋原檔)

SCOPE LIMIT:
只做「狀態機 + 查表呼叫 + 對帳 + 彙整短名單」的排程層。不新增任何 family 的 Stage2 探測
邏輯或 Stage3 回測邏輯(F-FUNDING-XS-DISPERSION / F-XVENUE-LEADLAG 目前仍然
awaiting_stage3_implementation,這是預期行為,不是任務的缺陷)。不改 idea_generator 的
候選上限/排序邏輯,不改 checkpoint①/family-minting 的判定邏輯,只呼叫既有 CLI/函式。
不實作 `--idea-batch-source taxonomy|literature` 這種替呼叫端跑發想器的模式——orchestrator
只消費既有 idea_batch.json 檔案路徑。

REQUIRED ON COMPLETION:
- List changed files
- Run: pytest tests/unit/test_pipeline_orchestrator.py tests/unit/test_pipeline_stage2_registry.py
  tests/unit/test_pipeline_stage3_registry.py tests/unit/test_pipeline_checkpoint1_check.py
  tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py
  + make docs-check
- 對照重構前後跑一次 scripts/run_pipeline_stage2_data_probe.py --candidate all,確認兩個
  既有 stage2_feasibility.json 輸出不變(diff 為空)
- 補 change manifest(新增 I29 = pipeline 治理規則變更,鏡像 2026-06-30-checkpoint1-automation.md
  的審查流程)
- 更新 docs/AI_HANDOFF.md / docs/CURRENT_STATE.md / config/workstreams.yaml(「Strategy
  research pipeline — full-auto roadmap」workstream 的 `ingestion_impl` 里程碑進度與
  `state`/`next` 文字)
- Commit with AI-Origin: Codex trailer

ACCEPTANCE CRITERIA:
- [ ] 對 idea_batch_20260701_taxonomy_002 的既有兩個候選跑 orchestrator,產出的
      stage2_feasibility.json 與現有手跑版本逐位元組相同。
- [ ] 兩個候選最終都停在 stage2_fail(因為現有資料仍然探測 FAIL,且 data_availability
      即使 PASS 也會因為 distinctness/cost_after_edge 缺席而 stage2_status FAIL——見
      docs/AI_HANDOFF.md 2026-07-01 taxonomy_002 段落),shortlist.md 正確標示。
- [ ] 給一個沒有登記 Stage2 探測函式的假 family_id → 狀態停在
      awaiting_stage2_implementation,出現在 shortlist.md,不拋例外、不靜默消失。
- [ ] 給一個 family_id_or_NEW == "NEW" 的假候選(模擬未 mint 的文獻候選) →
      不拋例外,狀態停在 awaiting_stage2_implementation,shortlist.md 的 family 欄位
      如實顯示 "NEW"。
- [ ] 給一個 Stage2 PASS 但沒有 Stage3 runner 的假 family_id(可用測試替身模擬 PASS)→
      停在 awaiting_stage3_implementation。
- [ ] 對同一個 batch_id 跑兩次 orchestrator,第二次不能刪除或覆蓋第一次已終態的候選
      (append-only 測試),且第二次不重新呼叫任何探測/回測函式(用呼叫計數 mock 驗證)。
- [ ] `derive_candidate_dir` 對 "B-f-funding-xs-dispersion" / "B-f-xvenue-leadlag" 分別
      推導出 "f_funding_xs_dispersion" / "f_xvenue_leadlag"(與既有目錄名逐字相符)。
- [ ] `idea_batch.json` 候選的 `candidate_id` 缺一個對應的 hypothesis_id →
      `pre_register_batch` 拋 ValueError,且 orchestrator_state.json 不被寫入
      (檢查檔案不存在或內容不變)。
- [ ] 用假 context 呼叫 STAGE3_RUNNERS["F-PAIRS-OU"]、batch_id 給一個非
      "pipeline_batch2_20260625" 的值 → 拋 RuntimeError,不寫入任何 summary.json。
- [ ] CLI 不給 --max-runtime-seconds 時直接報錯,不使用任何預設值跑下去。
- [ ] orchestrator 執行過程中對 docs/HYPOTHESIS_LEDGER.md / docs/EXPERIMENT_REGISTRY.md
      沒有任何寫入(測試以 mtime 或 mock 驗證)。
- [ ] I29 入 INVARIANTS.md,測試守護存在並通過。
```

## 4. Codex 任務 B(交付用,依附任務 A 但可獨立驗收):真的跑一次文獻批次

> 背景:A 半文獻發想程式(`scripts/run_pipeline_literature_ideas.py`)2026-07-01 已完成,
> 但 `results/` 底下**還沒有任何 `weekly_screen*` 產出**——程式碼存在不等於流程被驗證過。
> 這個任務只是「真的按一次按鈕」,不改動任何發想/評分邏輯。
>
> **2026-07-01 第二版修正**:原版要求「用 `--source` 抓一次,另外做一支評分器產出
> `--scores`」——這兩步若各自獨立呼叫 `fetch_papers`,兩次網路抓取的 `paper_id` 集合可能
> 不一致(公開 API 隨時間變化、排序不保證穩定),導致 `--scores` 對不上主 CLI 內部重新抓到
> 的論文,執行時直接因為「missing score for paper_id」報錯。修正:評分器**只抓一次**,把
> 抓到的原始論文存成快照,main CLI 呼叫時吃這個快照(`--papers`),不要再用 `--source`
> 二次抓取。

```text
Task: 執行一次真實文獻發想批次,產出可供 Claude Stage-1 審查的草稿
Strategy/spec source: docs/change_manifests/2026-07-01-literature-idea-driver.md +
                       scripts/run_pipeline_literature_ideas.py 既有 CLI

Required behavior:
  - 新增 scripts/literature_keyword_scorer.py,一支獨立小 CLI/函式庫,職責是:
    1. 呼叫既有 `crypto_alpha_lab.pipeline.fetch_papers(sources, date_window)`(**只呼叫
       一次**,不重複抓),選一組合理的查詢詞,圍繞現有 taxonomy 機制空間,例如
       `funding rate arbitrage` / `cross-sectional cryptocurrency momentum` /
       `cross-exchange lead-lag crypto` / `basis trading crypto perpetual`。
    2. 把抓到的原始論文 metadata 寫成快照 JSON(`--papers-out <path>`,結構與
       `fetch_papers` 回傳的 list[dict] 逐項相同,可直接被
       `run_pipeline_literature_ideas.py --papers` 吃)。
    3. 對每篇論文,用**機械式、確定性**的關鍵字比對(論文 `title` 對
       `docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md` 的機制關鍵字算重疊),
       輸出符合 `crypto_alpha_lab.schemas.PaperScoring` schema 的紀錄(`paper_id`/
       `title`/`authors`/`year` 照抄原始論文欄位;`alpha_category`/`expected_horizon`
       由關鍵字命中對應到 `PaperScoring` 允許的 9 個/4 個列舉值,命不中就用最保守值;
       8 個 0-5 分欄位由關鍵字命中數的簡單、確定性映射給出,例如
       `min(5, keyword_hits)`),寫成 `--scores-out <path>`(結構 =
       `{"paper_id": {...PaperScoring 欄位...}, ...}`,符合
       `run_pipeline_literature_ideas.py::_score_map` 能吃的格式)。
    4. 每筆輸出的 `notes` 欄位必須含 `scoring_method=mechanical_keyword_placeholder`
       字樣,並在函式/CLI 的 docstring 與任務報告明確標注——這**不是**真正的
       新穎性/品質判斷,只是讓管線能真的跑到底;真正的論文品質判斷仍然是 Claude/人在
       Stage-1 審查時做。因為 keyless 抓取只給得到論文標題(無摘要),這個機械評分器
       對機制分類/品質判斷本來就是粗略的,不是精細判斷的替代品。
  - 用步驟 2 產出的快照呼叫既有主 CLI:
    `python scripts/run_pipeline_literature_ideas.py --papers <papers-out 快照>
     --scores <scores-out 檔案> --batch-id <真實日期>_literature_001 ...`
    **不要**在這一步再傳 `--source`(那會觸發二次網路抓取,見上方修正說明)。
  - 跑出的批次維持既有 gate:全部候選 `draft_status="pending_llm"`(A-half 目前 code
    路徑實際寫的是 `draft_status="drafted"`——若與既有 CLI 行為不一致,以
    `run_pipeline_literature_ideas.py` 現有程式碼的實際輸出為準,不要為了湊這行文字去改
    既有邏輯)、`allow_live_trading=false`;不跑 Stage 2/3;不 append 任何東西到
    docs/HYPOTHESIS_LEDGER.md / docs/EXPERIMENT_REGISTRY.md。

PERMITTED FILES (only edit these):
- scripts/literature_keyword_scorer.py     (新增)
- tests/unit/test_literature_keyword_scorer.py  (新增)
- results/idea_batch_<真實日期>_literature_001/**   (新產出的批次資料夾,非既有 artifact;
  含 papers 快照,可放在同一批次目錄下,例如 `raw_papers_snapshot.json`)

FORBIDDEN (do not touch):
- research/crypto-alpha-lab/ 既有發想/評分/防火牆邏輯(只呼叫,不改行為)
- scripts/run_pipeline_literature_ideas.py(只呼叫既有 CLI 參數,不新增/修改參數)
- docs/HYPOTHESIS_LEDGER.md / docs/EXPERIMENT_REGISTRY.md
- 任何既有 results/** artifact
- Stage 2/3、checkpoint①、trading-core、gates

SCOPE LIMIT:
只是「補一個機械式評分器 + 一次性論文快照工具,讓既有 CLI 能不靠人工打分跑完一次」+
「真的執行一次」。不改 paper_ingestion.py / adapters 的評分/防火牆邏輯,不放寬
pending_llm / allow_live_trading 預設值,不修改 run_pipeline_literature_ideas.py 的 CLI
介面。

REQUIRED ON COMPLETION:
- List changed files
- Run: pytest tests/unit/test_literature_keyword_scorer.py + 既有 lab 測試套件
- 在完成報告中列出:用了哪些查詢詞、抓到幾篇論文、幾篇過 threshold 進 A-half draft、
  batch_id、產出路徑
- Commit with AI-Origin: Codex trailer

ACCEPTANCE CRITERIA:
- [ ] results/ 下出現真實的 weekly_screen/search_log_*.md 與 screen_*.json。
- [ ] 產出 idea_batch.json,候選(若有)`allow_live_trading=false`,`draft_status` 與
      `run_pipeline_literature_ideas.py` 既有程式碼實際產出的值一致。
- [ ] scores 輸出中每筆都標 scoring_method="mechanical_keyword_placeholder"。
- [ ] 主 CLI 呼叫使用 `--papers` 快照,未傳 `--source`,快照裡的 paper_id 與
      `--scores` 裡的 paper_id 集合完全一致(不會有 missing score 例外)。
- [ ] 沒有任何 docs/HYPOTHESIS_LEDGER.md / docs/EXPERIMENT_REGISTRY.md 寫入。
- [ ] 完成報告明確交棒給 Claude 做 Stage-1 審查,不自行升級任何候選。
```

## 5. scope / role

- 本檔為設計/治理文件,Claude 可寫,不啟用任何策略、不碰 deployment/demo/shadow/live gate。
- 任務 A/B 的實際程式碼屬 Codex 實作範圍。
- `// ponytail: orchestrator 只是一個查表狀態機 + markdown 彙整,不引入 workflow engine
  (Airflow/Prefect 之類),批次量級(<=15 候選)不需要`
- `// ponytail: family 未定案的候選不另開 awaiting_family_minting 狀態,沿用
  awaiting_stage2_implementation 的「查表查不到」語意就夠誠實,不需要為單一 edge case
  多養一條狀態分支`

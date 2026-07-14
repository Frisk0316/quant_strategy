---
status: archived
type: task
owner: human
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# 專案維護改善任務 M1–M5(非 pipeline 範圍)

來源:2026-07-03 Claude 全專案審核(排除進行中的 pipeline 自動化改善計畫 P1–P8,
見 `tasks/2026-07-03-pipeline-improvement-tasks.md`)。

每個任務獨立可交付;建議順序:M1 → M2 → M3/M4(可平行)→ M5(待 user 決策)。
所有任務共通禁區:`src/okx_quant/strategies/`、`src/okx_quant/signals/`、
`src/okx_quant/risk/`、`src/okx_quant/portfolio/`、`src/okx_quant/execution/`、
`config/risk.yaml`、`research/`(內容檔)、`results/**` 既有 artifact、
`docs/HYPOTHESIS_LEDGER.md`、`docs/EXPERIMENT_REGISTRY.md`、任何部署 gate。

---

## M1 — CI 與本地驗證一致性修復

Task: 讓 CI 覆蓋與 `make verify` 宣稱的範圍一致,消除四個已確認的漂移。
Strategy/spec source: 本檔;`docs/KNOWN_ISSUES.md`(Harness 節,lab 套件兩步規則)。
Required behavior:

1. **CI ruff 範圍**:`.github/workflows/ci.yml` 目前跑 `ruff check src tests`,
   但 `make lint` 跑 `src/ tests/ backtesting/ scripts/`。近期新代碼多在
   `backtesting/`、`scripts/`,CI 完全沒 lint。改 CI 為
   `ruff check src tests backtesting scripts`。先在本地跑一次;若 backtesting/
   scripts 有 fatal-class(E9/F63/F7/F82)違規,小修即可修,非小修則回報停止。
2. **crypto-alpha-lab 套件進 CI**:`docs/KNOWN_ISSUES.md` 明言 CI 必須把 parent
   與 lab 套件分兩步跑,但 `ci.yml` 沒有 lab 步驟(16 個測試從未在 CI 跑過)。
   新增步驟:`pip install -e research/crypto-alpha-lab` 後
   `python -m pytest research/crypto-alpha-lab/tests -p no:cacheprovider`。
   只改 `ci.yml`,不動 `research/` 內任何檔案。
3. **根層測試檔**:CI 與 `make test-unit` 都只跑 `tests/unit/`;
   `tests/test_daily_winner_backtest.py` 與 `tests/test_ohlcv_rotation.py` 從未
   在 CI 執行。先本地無 DB 跑這兩檔:通過則加入 CI pytest 呼叫;若需 DB/資料,
   不強塞 CI,改在 `docs/KNOWN_ISSUES.md` 記錄明確排除原因。
4. **frontend-check 清單漂移**:`Makefile` 的 `frontend-check` 手動列檔,漏了
   實際被 `index.html` 載入的 `frontend/view-manual.js` 與
   `frontend/tweaks-panel.js`。改為對 `frontend/*.js` 逐檔 `node --check` 的
   迴圈(或至少補上兩檔),使清單不再能漂移。

PERMITTED FILES (only edit these):
- .github/workflows/ci.yml
- Makefile(僅 frontend-check 目標)
- docs/KNOWN_ISSUES.md(僅第 3 點的排除記錄)
- backtesting/、scripts/ 內僅限修 fatal-class lint 違規的最小 diff

FORBIDDEN (do not touch):
- 共通禁區(見檔頭);research/crypto-alpha-lab/ 內任何檔案
- pyproject.toml 的 ruff select 規則(擴大 lint 規則是另一個任務)

SCOPE LIMIT:
只修一致性,不擴大 lint 規則、不加新 CI job 種類、不動 integration 測試
(需 DB,維持 local-only)。

REQUIRED ON COMPLETION:
- List changed files
- Run: `ruff check src tests backtesting scripts`、`make frontend-check`、
  `pytest tests/unit -q`、`cd research/crypto-alpha-lab && python -m pytest -q`
- 更新 docs/RUNBOOK.md 若驗證指令說明有變
- Commit with AI-Origin: Codex trailer when committing is requested

ACCEPTANCE CRITERIA:
- [ ] CI 的 ruff 步驟涵蓋 backtesting/ 與 scripts/ 且綠燈
- [ ] CI 有獨立 lab 測試步驟且綠燈(不修改 research/ 內檔案)
- [ ] 兩個根層測試檔:進 CI 或在 KNOWN_ISSUES 有明確排除記錄(二擇一,不得沉默)
- [ ] `frontend/*.js` 每一檔都被 frontend-check 檢查(含 view-manual、tweaks-panel)

---

## M2 — 治理文件減肥與過期狀態修正(docs-only)

Task: 執行 KNOWN_ISSUES 已列的 handoff 歷史遷移,並修正三處已確認過期的狀態文件。
Strategy/spec source: `docs/DOC_LIFECYCLE.md`、`docs/COMPRESSION_RULES.md`、
`docs/CURRENT_STATE.md` 自身的 "How to update" 規則。
Required behavior:

1. `docs/AI_HANDOFF.md` 現為 1,138 行(約 5 萬 token,每個 session 都要讀,
   直接吃掉 context budget);`docs/CHANGELOG_AI.md` 僅 174 行。把 2026-06-25
   以前(含批次一/二歷史、XS momentum 逐日記錄)的 session 條目無損遷移到
   `docs/CHANGELOG_AI.md`,AI_HANDOFF 只留現行狀態、do-not-touch、最近兩週條目
   與 next actions。目標 ≤ 400 行。遷移是搬移不是改寫:規則/決策/數值逐字保留。
2. `docs/CURRENT_STATE.md` 現為 573 行,違反自身 "keep this short / overwrite,
   do not append" 規則,且含過期事實(如 `Current branch:
   codex/xs-momentum-universe-scaffold`)。重寫為一屏快照(目標 ≤ 150 行),
   歷史細節移到 CHANGELOG_AI,耐久缺口移到 KNOWN_ISSUES。
3. `docs/KNOWN_ISSUES.md`:「older Markdown files do not yet include lifecycle
   metadata」條目已過期(`check_doc_metadata.py` 現在 0 warnings),標記已解決;
   順檢其餘條目是否仍準確。
4. `STATUS.md` 分支看板停在 2026-06-25:對照 `git branch -a` 現況更新各列
   (現行分支是 `codex/pipeline-batch1-stage3`,看板沒有這列;
   `fix-pairs-hedge-close-metadata` 與 `fix/pairs-hedge-close-metadata` 疑似重複)。
   只更新看板文字;**實際刪分支是 user 手動決定,不得執行**。

PERMITTED FILES (only edit these):
- docs/AI_HANDOFF.md、docs/CHANGELOG_AI.md、docs/CURRENT_STATE.md、
  docs/KNOWN_ISSUES.md、STATUS.md、config/workstreams.yaml(若里程碑狀態連動)

FORBIDDEN (do not touch):
- 共通禁區;docs/DOMAIN_RULES.md、docs/INVARIANTS.md(本任務無業務規則變更)

SCOPE LIMIT:
純搬移與過期修正;不改寫任何規則、決策、數值語意。**前置條件:先確認
2026-07-03 pipeline session 對 AI_HANDOFF/CURRENT_STATE/workstreams.yaml 的
未提交修改已 commit,否則不得開工(避免覆蓋)。**

REQUIRED ON COMPLETION:
- List changed files
- Run: `make docs-check`(check_doc_metadata + feature-map links)
- Commit with AI-Origin: Codex trailer when committing is requested

ACCEPTANCE CRITERIA:
- [ ] AI_HANDOFF.md ≤ 400 行且保留:現行目標、do-not-touch、最近兩週條目、next
- [ ] 被遷移條目在 CHANGELOG_AI.md 逐字可找到(抽查 3 條:批次一關閉、C2 realism、DSR 修復)
- [ ] CURRENT_STATE.md ≤ 150 行、無過期分支/日期陳述
- [ ] STATUS.md 每一列的 State 與 git 現況一致;無新增刪分支動作
- [ ] `make docs-check` 通過

---

## M3 — backtest-smoke 冷凍 fixture(補 KNOWN_ISSUES 既有承諾)

Task: `make backtest-smoke` 目前只驗 entrypoint 可 import/啟動;KNOWN_ISSUES
明言「加 tiny frozen no-DB fixture 前不得視為 replay 執行覆蓋」。補上該 fixture,
讓 smoke 真正跑通一條最小 replay 路徑。
Strategy/spec source: `docs/KNOWN_ISSUES.md`(Harness 節);參考既有
`tests/fixtures/engine_consistency/` 的冷凍 fixture 模式與
`scripts/run_engine_consistency_smoke.py`。
Required behavior:

- 新增小型冷凍 OHLCV fixture(數百根 bar 即可)與一個最小 replay smoke:
  用一個現有已啟用的技術指標策略(如 MA crossover),產出 artifact 到暫存目錄,
  斷言 result/metrics/fills artifact 結構存在且非空。
- 無 DB、無網路;目標 60 秒內跑完。
- **風險預警**:venue-scoped candle 讀取會拒絕 parquet fallback(I19 相關)。
  若最小 no-DB replay 無法在不弱化 venue-scoping/I19 的前提下實現,停止並回報
  邊界,**不得放寬任何 venue-scoping 或資料來源規則**。

PERMITTED FILES (only edit these):
- scripts/smoke/backtest_smoke.py
- tests/fixtures/backtest_smoke/**(新增)
- Makefile(僅 backtest-smoke 目標,如需參數)
- docs/KNOWN_ISSUES.md、docs/RUNBOOK.md(狀態更新)

FORBIDDEN (do not touch):
- 共通禁區;backtesting/replay.py、backtesting/data_loader.py 的行為
  (smoke 只能呼叫,不能為了讓 smoke 過而改引擎)

SCOPE LIMIT:
只做 smoke 覆蓋;不做 WF/CPCV、不寫 results/、不當作 promotion 證據。

REQUIRED ON COMPLETION:
- List changed files
- Run: `make backtest-smoke`(貼執行時間與輸出摘要)、`pytest tests/unit -q`
- Commit with AI-Origin: Codex trailer when committing is requested

ACCEPTANCE CRITERIA:
- [ ] `make backtest-smoke` 在無 DB 環境實際執行 replay 並驗證 artifact 結構
- [ ] 人為弄壞 replay 一處(本地暫時改動後還原)可使 smoke 失敗 — 證明有偵測力
- [ ] 執行時間 ≤ 60s;無網路/DB 依賴
- [ ] 未修改任何引擎行為檔案

---

## M4 — monitoring 模組最小單元測試

Task: `src/okx_quant/monitoring/`(telegram_alert、metrics、calibration_log)
被 `engine.py` 引用但 tests/ 全無覆蓋;FEATURE_MAP 自承「no dedicated monitoring
test is mapped here yet」。補最小單元測試。
Strategy/spec source: 本檔;`docs/FEATURE_MAP.md` Telegram/Monitoring 節。
Required behavior:

- 新增 `tests/unit/test_monitoring.py`:
  - TelegramMonitor:mock 傳輸層,驗證訊息格式化與錯誤路徑不拋出未捕捉例外;
    斷言測試中無真實網路呼叫。
  - metrics:計數器/量表更新後可讀回正確值。
  - calibration_log:寫入→讀回 roundtrip。
- 更新 FEATURE_MAP.md 該節的 Tests 列。

PERMITTED FILES (only edit these):
- tests/unit/test_monitoring.py(新增)
- docs/FEATURE_MAP.md(僅 Telegram/Monitoring 節 Tests 列)

FORBIDDEN (do not touch):
- 共通禁區;src/okx_quant/monitoring/**(發現 bug 先回報,不順手改)

SCOPE LIMIT:
只加測試。測試若揭露 monitoring 實作 bug,記入 docs/KNOWN_ISSUES.md 並回報,
不在本任務修。

REQUIRED ON COMPLETION:
- List changed files
- Run: `pytest tests/unit/test_monitoring.py -v`、`pytest tests/unit -q`
- Commit with AI-Origin: Codex trailer when committing is requested

ACCEPTANCE CRITERIA:
- [ ] 三個 monitoring 模組各至少一個行為斷言測試
- [ ] 測試無網路/DB 依賴
- [ ] monitoring 原始碼零修改

---

## M5 — stocks 模組處置(先等 user 決策)

Task: `src/okx_quant/stocks/`(5 檔,分鐘級股票回測引擎)+
`scripts/run_stock_backtest.py` + `tests/unit/test_stock_system.py` 完全不在
`docs/FEATURE_MAP.md`、AGENTS.md 檔案所有權表、或任何 docs 中 — 是孤兒功能,
違反本 repo「locate-before-edit / 每個功能有 owning files 映射」原則。
Strategy/spec source: 本檔;`docs/FEATURE_MAP.md` 格式。

**user 決策點(二擇一)**:
- **選項 A(預設,docs-only)**:保留模組,在 FEATURE_MAP.md 補一節
  (行為、owning files、tests、do-not-touch:與加密交易核心無關、不接 UI/API、
  不參與任何 gate),並在模組 `__init__.py` docstring 標註 research-only 狀態。
- **選項 B**:user 確認已棄用 → 刪除模組 + script + test,並在
  CHANGELOG_AI.md 記錄。

PERMITTED FILES (only edit these):
- 選項 A:docs/FEATURE_MAP.md、src/okx_quant/stocks/__init__.py(僅 docstring)
- 選項 B:src/okx_quant/stocks/**、scripts/run_stock_backtest.py、
  tests/unit/test_stock_system.py、docs/CHANGELOG_AI.md

FORBIDDEN (do not touch):
- 共通禁區;選項 A 下不得改任何 stocks 行為代碼

SCOPE LIMIT:
未取得 user 明示選項前,只能做選項 A。

REQUIRED ON COMPLETION:
- List changed files
- Run: `make docs-check`;選項 B 另跑 `pytest tests/unit -q` 確認無殘留引用
- Commit with AI-Origin: Codex trailer when committing is requested

ACCEPTANCE CRITERIA:
- [ ] stocks 不再是無主功能:FEATURE_MAP 有節(A)或模組已移除且無殘留引用(B)
- [ ] `make docs-check` 通過(feature-map links 檢查含新節連結)

---

## M2-R1 — 補齊 M2 遺漏的逐字歷史遷移(2026-07-03 Claude 審核後新增)

Task: M2(commit `0191c1d`)完成了瘦身但**沒有**完成遷移:AI_HANDOFF 刪除的
2026-06-24 → 2026-07-01 session 歷史(DSR 修復、XS 洩漏事件、批次一關閉、
C2 realism 再定價、pipeline 全自動 roadmap 各條)未逐字進入
`docs/CHANGELOG_AI.md`(該檔條目從 06-23 直接跳到 07-02),抽查數值
(C2 DSR 0.0041、WF -1.5093)在 CHANGELOG 找不到。歷史目前只存在 git
(`git show 0191c1d^:docs/AI_HANDOFF.md`),違反 M2 驗收條件 2。
Strategy/spec source: 本檔 M2;`docs/COMPRESSION_RULES.md`(規則/決策/數值無損)。
Required behavior:

1. 以 `git show 0191c1d^:docs/AI_HANDOFF.md` 為來源,把被刪除的各 dated session
   條目**逐字**(允許僅加日期標題與最小格式調整)搬入 `docs/CHANGELOG_AI.md`,
   按日期倒序插入既有條目之間;同時刪除或改寫檔尾 "Pending Migration" 段落
   (本任務即該 dedicated cleanup task)。
2. 恢復 M2 從 `docs/KNOWN_ISSUES.md` 刪掉但仍有效的兩條操作性警語(可併入
   既有條目):(a) EXPERIMENT_REGISTRY 的 Family K-budget 表是人工維護的
   checkpoint①#9 狀態,過期值仍需人工覆核(I27 只記了不可混淆,沒記人工維護
   staleness);(b) registry 新列應明寫 family-cumulative n_trials,否則
   `family_registry_from_text()` 回退為歷史 max-row 解讀。
3. 順手修正已過期的 handoff 陳述:AI_HANDOFF/CURRENT_STATE 中「P1–P8 為
   working tree 髒檔、勿掃入」的警告已被 `dfc7af8`(P1–P8 已單獨提交)取代。

PERMITTED FILES (only edit these):
- docs/CHANGELOG_AI.md、docs/KNOWN_ISSUES.md、docs/AI_HANDOFF.md、
  docs/CURRENT_STATE.md

FORBIDDEN (do not touch):
- 共通禁區;不得改動任何規則/決策/數值語意 — 只搬移與除舊

REQUIRED ON COMPLETION:
- Run: `python scripts/docs/check_doc_metadata.py` 與
  `python scripts/docs/check_feature_map_links.py`
- Commit with AI-Origin: Codex trailer when committing is requested

ACCEPTANCE CRITERIA:
- [ ] CHANGELOG_AI 含 2026-06-24→07-01 各條;抽查三條逐字可找到:批次一關閉
      (含「do not tune S5/S6/S7 to chase the gate」語意)、C2 realism
      (DSR 0.0041、WF OOS Sharpe -1.5093、n_trials=48)、DSR 修復
      (`DSR <= PSR(0)` 不變量與兩個 untrusted artifact 名)
- [ ] KNOWN_ISSUES 恢復上述兩條操作性警語
- [ ] AI_HANDOFF 仍 ≤ 400 行;docs 檢查通過
- [ ] 無「dirty pipeline worktree」過期警告殘留

---

## 觀察但暫不排任務(記錄理由)

- **ruff 規則擴大**:pyproject 註解自承「先清 lint debt 再擴大」。等 M1 讓 CI
  範圍一致後,再視 debt 量決定是否值得;現在擴大會產生大量無關 diff。
- **瀏覽器級前端互動測試**(KNOWN_ISSUES 既列):需引入 Playwright 等新依賴,
  維護成本高;view-backtest.js(1,914 行)雖大但近期無回歸事故。建議暫緩,
  等 chart 回歸真的發生再投資。
- **integration 測試進 CI**:需 TimescaleDB + 種子資料,維持 local-only
  (`make verify-full`)是誠實的現狀,不硬塞。
- **分支清理**:8+ 條 stale/已合併分支(見 STATUS.md)刪除屬 user 手動決定;
  M2 只更新看板。
- **frontend 大檔重構**(view-backtest.js/view-config.js 各 ~1.9k 行):
  無測試護欄前重構風險大於收益;若 M-系列後仍想做,先補測試再談。

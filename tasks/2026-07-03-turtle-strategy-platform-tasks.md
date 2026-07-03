---
status: current
type: task
owner: claude
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# 海龜策略平台整合任務 T1–T5

Author: Claude（2026-07-03 規劃）。Implementer: Codex。
設計規格（必讀）：`docs/superpowers/specs/2026-07-03-turtle-platform-design.md`。
策略真相來源：`new_startegy_海龜/trading_target_func.py`（`turtle_trading_system_full`
long 版）與 `new_startegy_海龜/sweep_params_interactive_full_函式說明文件.docx`。
**Parity 是驗收標準：不准「順手改良」參考實作的交易語意**（怪癖保留清單見 spec
§Semantics contract）。

**使用者已定決策（2026-07-03）**：
1. Sweep 視覺化「兩者都要」：儀表板原生 SVG heatmap ＋ 每次 sweep 產出參考檔
   同款的 plotly 3D surface 獨立 HTML（vendored plotly.min.js）。
2. `invest_pct` 拉桿可拉到 100%（實務建議 ≤25%，以 UI hint 呈現，不做硬限制）。
3. 單次回測 UI 預設值 = 使用者範例呼叫
   `turtle_trading_system_full(daily_df,20,55,10,20,4,4,50000.0,0.01,min_position=0.0001,fee=0.003,atr_period=20)`。

**優先序**：T1（核心移植＋golden fixture）> T2（單次回測 API）> T3（sweep API）
> T4（前端）> T5（docs）。T1 未過 parity 測試前，不得開始 T2–T4。

**全部任務共同 FORBIDDEN（不重複列在各任務）**：
- `src/okx_quant/strategies/`、`signals/`、`risk/`、`portfolio/`、`execution/`
- `config/risk.yaml`、`config/strategies.yaml`、`config/settings.yaml`、
  `config/universe.yaml`、任何 live/demo/shadow/deployment gate
- `backtesting/replay.py`、`backtesting/parameter_sweep.py`、
  `backtesting/daily_winner_backtest.py`、`backtesting/artifacts.py`、
  `backtesting/differential_validation.py`
- `new_startegy_海龜/`（唯讀參考；不得修改）
- `research/`、`docs/HYPOTHESIS_LEDGER.md`、`docs/EXPERIMENT_REGISTRY.md`
- 既有 `results/**` artifacts（turtle sweep 寫進**新的** `results/turtle_sweeps/`）
- 不得把 polars / plotly 加進 `pyproject.toml`（fixture 用一次性 scratch venv 產生）

**全部任務共同 REQUIRED ON COMPLETION**：
- 列出變更檔案；跑各任務指定測試＋`pytest tests/unit -q` 迴歸；
  `python scripts/docs/check_doc_metadata.py`、
  `python scripts/docs/check_feature_map_links.py`（docs 變更時）；
  `python scripts/docs/check_doc_impact.py`（T5 manifest）；
  更新 `docs/AI_HANDOFF.md` / `docs/CURRENT_STATE.md` / `config/workstreams.yaml`；
  依 AGENTS.md 格式回報；commit 時帶 `AI-Origin: Codex` trailer。
- 本 repo 工作樹現有 **M2-R1 未 commit docs**（另一工作流所有）：不得覆蓋、
  不得一起 commit。

---

## T1 — turtle_trading_system_full 忠實移植 + golden parity fixture

Task: 在 `backtesting/turtle_backtest.py` 用 pandas/numpy（現有依賴）忠實移植
參考實作的 long 版核心與指標，並以 golden fixture 鎖定 parity。

Required behavior:
1. 移植 `calc_atr`、`calc_unit_size`、`turtle_trading_system_full`（S1/S2 雙系統、
   加碼、2×ATR 停損、S1 skip-after-win、現金閘 `cost < money_in_hand`、
   S1 先於 S2 評估）。逐日輸出欄位與參考一致（spec 列出的 pinned columns 必備）。
2. 移植指標：`_calc_trade_pnl` 配對、`calc_win_rate_full`、
   `calc_profit_loss_ratio_full`、`calc_expectancy_full`、
   `calc_mdd(filter_zero=True)`、`calc_whole_asset_stats`、
   `get_outcomes_single` / `get_outcomes_overall_v2`、`max_consecutive`。
3. rolling 語意對齊 polars：`rolling(N, min_periods=N)` 後 `shift(1)`（入場/出場
   極值）；ATR 為 rolling mean **不 shift**（參考行為，保留）。
4. **不移植**參考的副作用：無 `test.csv`、無 debug print；現金不足跳過次數等
   改記進 metrics 計數器。`initial_fund` 參數捨棄（docx §9 記載未使用）。
5. 產生 fixtures：`tests/fixtures/turtle/daily_ohlc.csv`（≥400 天真實
   BTC-USDT-SWAP UTC 日線，從 DB canonical 匯出一次）＋
   `expected_default.csv` / `expected_stress.csv`（**一次性 scratch venv 裝 polars
   跑參考程式產生**；param set 見 spec；產生步驟寫進 PR 描述與 T5 docs）。
6. `TurtleParams` 驗證：window 參數正整數、`0 < invest_pct <= 1`、
   `min_position > 0`、`0 <= fee < 1`、unit limits ≥1。

PERMITTED FILES:
- `backtesting/turtle_backtest.py`（新）
- `tests/unit/test_turtle_backtest.py`（新）
- `tests/fixtures/turtle/`（新）

SCOPE LIMIT: 純函式庫層。不碰 API、前端、replay、sweep 既有程式。

REQUIRED: `pytest tests/unit/test_turtle_backtest.py -q`；
`ruff check backtesting/turtle_backtest.py tests/unit/test_turtle_backtest.py`。

ACCEPTANCE CRITERIA:
- [ ] parity 測試：兩組 param set 對 expected CSV 全欄位吻合（int/flag 精確、
      float rtol 1e-9）。
- [ ] 無 lookahead 回歸測試：構造「當日 high 等於含當日的 rolling max、但小於
      shift(1) 極值」的日線，斷言不進場（證明用的是前 N 日、不含當日）。
- [ ] 現金閘測試：構造 cost ≥ money_in_hand 的情境，斷言跳過且計數器 +1。
- [ ] S1 skip-after-win 測試：獲利平倉後下一次 S1 突破被跳過一次。
- [ ] 單次回測（2 年日線）在一般開發機 < 1 秒。
- [ ] 模組無任何檔案寫入副作用。

---

## T2 — 單次回測 API（daily_winner 模式）

Task: 在 `src/okx_quant/api/routes_backtest.py` 把 `turtle` 接進單次回測
job 流程，產出標準 ADR-0002 run artifacts，讓既有結果頁直接渲染。

Required behavior:
1. `turtle` 加入 run 請求的策略 allow-list；請求分流到新的
   `_run_turtle_job`（BackgroundTasks，模式同 `_run_daily_winner_job`）。
2. 資料：沿用 daily_winner 的 Postgres 日線聚合路徑（UTC 日界），單一 symbol
   （預設 BTC-USDT-SWAP）、日期區間、venue 由請求帶入；bar 固定 1D（請求帶
   其他 bar 回 400）；DB 不可用時回明確錯誤（不做 parquet fallback——本地
   mirror 太薄）。
3. artifacts 寫進標準 run 目錄：`result.json`（strategies=["turtle"]、平台標準
   metrics 由日 equity 序列計算＋turtle 指標 namespace）、`price_series.csv`、
   `indicator_series.csv`（ATR、enter/leave 線、S1/S2 停損線）、`trades.csv`
   （ts、system s1|s2、action entry|pyramid|exit、reason、price=close、size、
   fee_paid、units_after、cash_after）、`equity.csv`（日 equity）。
4. 參數 schema 驗證失敗回 400；job 狀態/取消沿用既有 run job 端點。

PERMITTED FILES:
- `src/okx_quant/api/routes_backtest.py`（僅新增 turtle 分支與 helpers）
- `backtesting/turtle_backtest.py`（如需補 result 轉換 helper）
- `tests/unit/test_routes_backtest_turtle.py`（新）
- `tests/unit/test_turtle_backtest.py`（如需擴充）

SCOPE LIMIT: 不動 replay/rotation/daily_winner 既有路徑；不改既有端點 schema。

REQUIRED: `pytest tests/unit/test_routes_backtest_turtle.py tests/unit/test_turtle_backtest.py -q`。

ACCEPTANCE CRITERIA:
- [ ] 以小型 fixture 日線跑完 job：run 目錄含上述全部 artifacts，
      `GET /{run_id}` / `/equity` / `/metrics` 正常回應。
- [ ] result.json 含 turtle 指標（win_rate、profit_loss_ratio、expectancy、
      mdd、final_whole_asset、final_equity、min_equity、min_realized_pnl、
      max consec 系列、cash-skip 計數）。
- [ ] 非法參數（invest_pct>1、負 window 等）回 400。
- [ ] 期末不強制平倉；final equity 含未平倉市值（與參考一致）。

---

## T3 — Sweep API + artifacts + 3D surface HTML

Task: `/sweep` 端點加 turtle 分支，取代 `sweep_params_interactive_full` 的
console 互動：fix-or-range 掃 4 個 window 參數、可選 invest_pct 軸、產出
參考格式 CSV 與 surface.html。

Required behavior:
1. `POST /sweep` 在呼叫 `_validate_parameter_sweep_request` **之前**分流
   `strategy=="turtle"` → `_run_turtle_sweep_job`（沿用 `_sweep_jobs` registry
   與既有 status/jobs 端點；replay sweep 路徑一字不動）。
2. `expand_turtle_grid`：4 個 window 參數各自 `fixed` 或 `range lo~hi[:step]`
   （沿用既有 token 語法）；合法性條件 `sys1>leave1`、`sys2>leave2`、
   `sys2>sys1`、`leave1>=5`、`leave2>=5`、`leave2>leave1`；上限 valid ≤5000、
   raw ≤20000，違反回 400。
3. 可選 `invest_pct` 軸（百分比 range，如 `1~100:1`）：**要求 4 個 window 參數
   全固定**，否則 400。
4. 每組合跑 `run_turtle_backtest`，rows 欄位名 = 參考
   `index_parameter_result_full.csv` 全欄位（spec 列表）＋swept 時的
   `invest_pct`；以 `final_equity` 排序產生 `top_results`。
5. artifacts：`results/turtle_sweeps/<sweep_id>/summary.json`＋`rows.csv`；
   invest_pct 軸時另寫 `equity_curves.csv`（long 格式：invest_pct,date,equity）；
   恰好 2 個自由 window 參數且 invest_pct 固定時，產
   `surface.html`（模板嵌 rows JSON，`<script src="/vendor/plotly.min.js">`，
   2×3 佈局 5 指標，仿 `sweep_params_full.html`）。
6. 新端點：`GET /sweep/result/{sweep_id}`（summary＋rows＋curves JSON）、
   `GET /sweep/artifact/{sweep_id}/{name}`（allow-list：summary.json、rows.csv、
   equity_curves.csv、surface.html；防路徑跳脫）。
7. vendored `frontend/vendor/plotly.min.js`（pinned 2.x、MIT；來源與版本記進
   PR 描述），**不加進** Makefile `FRONTEND_JS` / frontend-check。
8. progress callback 至少每 2 秒或每 50 組合更新一次。

PERMITTED FILES:
- `src/okx_quant/api/routes_backtest.py`（turtle sweep 分支＋兩個新端點）
- `backtesting/turtle_backtest.py`（grid/sweep/surface 模板）
- `frontend/vendor/plotly.min.js`（新，vendored）
- `tests/unit/test_turtle_backtest.py`、`tests/unit/test_routes_backtest_turtle.py`

SCOPE LIMIT: 不動 `backtesting/parameter_sweep.py` 與 replay sweep 行為。

REQUIRED: `pytest tests/unit/test_turtle_backtest.py tests/unit/test_routes_backtest_turtle.py tests/unit/test_parameter_sweep.py -q`
（最後一項證明 replay sweep 無迴歸）。

ACCEPTANCE CRITERIA:
- [ ] grid 測試枚舉六條合法性規則的接受/拒絕案例＋cap 案例。
- [ ] 2 自由參數 sweep：rows.csv 欄位名與參考 CSV 完全一致；surface.html 存在
      且引用 /vendor/plotly.min.js；summary.json 記錄產出條件。
- [ ] invest_pct 軸 sweep（窗口全固定）：equity_curves.csv 存在、每個 invest_pct
      值一條完整日 equity 曲線；未滿足全固定時 400。
- [ ] 1 自由參數與 ≥3 自由參數：不產 surface.html，summary.json 註明原因。
- [ ] `GET /sweep/artifact/...` 對 allow-list 外名稱與 `../` 回 404/400。

---

## T4 — 前端：策略註冊、參數表單、invest_pct 拉桿、sweep 面板與視覺化

Task: 把 turtle 接進 Run Backtest UI 與 sweep 面板，並新增原生 heatmap 與
invest_pct 拉桿視覺化。

Required behavior:
1. `frontend/data.js` 策略註冊：`{ id:"turtle", name:"Turtle 海龜 (S1+S2)",
   tag:"Research", desc:"雙系統海龜突破：S1/S2 進出場、ATR 部位、加碼與停損" }`。
2. `frontend/view-config.js`：
   - turtle 參數表單（11 參數，預設值見 spec 表；own_capital 對映既有 capital
     欄位，預設 50000）；bar 選擇鎖 1D；顯示 warmup 提示（前
     max(enter_term_sys2, atr_period) 日為 rolling warmup、無訊號）；
     `invest_pct` 用 range slider 0.1%–100%、step 0.1%、預設 1%，hint
     「實務建議 ≤25%；拉高觀察 final equity（現金閘會讓高比例出現跳單，
     是參考實作的誠實行為）」。
   - ParameterSweepPanel turtle 分支：4 個 window 參數各自 fix 值或 range 輸入
     （預設範圍 5–30 / 31–60 / 5–20 / 5–25）、合法性條件 hint、invest_pct 軸
     開關＋range 輸入（開啟時鎖 4 參數為 fix）。
3. sweep 結果視覺化（turtle）：
   - 恰 2 自由參數：`frontend/charts.js` 新增 `Heatmap` SVG 元件（零第三方庫、
     viridis 類色階、hover 顯值、點格顯示該組合完整列），5 個指標小倍數
     （MDD、Win Rate、Final Equity、PLR、Expectancy）。
   - 1 自由參數：原生折線（指標 vs 參數）。
   - invest_pct 軸：`final_equity vs invest_pct` 折線＋拉桿 scrub：拉到哪個
     invest_pct 就渲染該值的 equity 曲線與讀數（final_equity、mdd、min_equity），
     資料來自 `GET /sweep/result/{sweep_id}`。
   - 「開啟 3D Surface」連結 → `GET /sweep/artifact/{sweep_id}/surface.html`
     新分頁（僅當 summary 說有產出時顯示）。
4. 單次 turtle run 的結果頁沿用既有 artifacts 渲染（equity、price＋indicator
   線＋trades 標記）；如 indicator/trade 欄位需要 mapping 調整，僅小幅補
   `view-backtest.js`。

PERMITTED FILES:
- `frontend/data.js`、`frontend/view-config.js`、`frontend/charts.js`、
  `frontend/view-backtest.js`（僅渲染 mapping 需要時）、`frontend/styles.css`
  （必要的最小樣式）

SCOPE LIMIT: 不動其他策略的表單/圖表行為；不引入 vendor 之外的第三方庫；
儀表板本體不直接 import plotly（只有 surface.html 用）。

REQUIRED: 對每個變更的 frontend JS 跑 `node --check`（等效 `make frontend-check`；
本機無 make 時逐檔跑並回報）；`pytest tests/unit/test_frontend_static_mime.py -q`
（如該測試涵蓋新 vendor 路徑）。

ACCEPTANCE CRITERIA:
- [ ] UI 可選 turtle、編輯全部參數、invest_pct 拉桿到 100% 可送出。
- [ ] sweep 面板可送出 fix/range 組合與 invest_pct 軸；後端 400 訊息如實顯示。
- [ ] 2 自由參數 sweep 完成後儀表板顯示 5 張 heatmap；hover/點擊正常。
- [ ] invest_pct sweep 完成後拉桿 scrub 流暢切換 equity 曲線與讀數。
- [ ] surface.html 連結在新分頁開啟並渲染 3D surfaces。
- [ ] 既有策略（ma/ema/macd/rotation/daily_winner）表單與 sweep 不受影響
      （目視＋node --check）。

---

## T5 — Docs、Change Manifest、handoff

Task: 補齊治理文件與 handoff。

Required behavior:
1. Change Manifest `docs/change_manifests/2026-07-03-turtle-strategy-runner.md`
   （新研究用 PnL/fee/fill 會計面；依 `docs/CHANGE_MANIFEST_TEMPLATE.md`）。
2. `docs/FEATURE_MAP.md` 新「Turtle Research Backtest」章節（檔案清單、tests、
   do-not-touch：research-only、不得接 gates/live）。
3. `docs/UI_MAP.md`（表單/拉桿/sweep 面板/heatmap/surface 連結）、
   `docs/DATA_FLOW.md`（DB 日線聚合 → turtle runner → run/sweep artifacts）、
   `docs/RUNBOOK.md`（如何跑單次/sweep、fixture 再生步驟、DB 需求）、
   `docs/GOLDEN_CASES.md`（parity fixture 條目：來源、param sets、再生步驟）。
4. `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`、`config/workstreams.yaml`
   （Turtle workstream 里程碑推進）、`docs/CHANGELOG_AI.md` 一行摘要。
5. 如有已知缺口（例：無 DB 環境不能跑），記 `docs/KNOWN_ISSUES.md`。

PERMITTED FILES: 上列 docs＋`docs/KNOWN_ISSUES.md`。

REQUIRED: `python scripts/docs/check_doc_metadata.py`、
`python scripts/docs/check_feature_map_links.py`、
`python scripts/docs/check_doc_impact.py`。

ACCEPTANCE CRITERIA:
- [ ] 三個 docs check 全綠；manifest 涵蓋 DOC_IMPACT_MATRIX 對應列。
- [ ] FEATURE_MAP 章節連結全部有效。

---

## 完成後回報（AGENTS.md 格式）＋ Questions for Claude review

Claude review 會特別查：parity 測試證據（非自報）、lookahead、fee/PnL 符號、
scope 違規（尤其 replay/parameter_sweep/config 未動）、vendor 檔未進
frontend-check、M2-R1 未被掃進 commit。

---

## 補救任務 RF1–RF3（Claude review 2026-07-03，使用者已批准）

審核結論：APPROVED WITH REQUIRED FIXES。Parity 已由 Claude 獨立確認
（逐字參考實作 vs 移植版，600 天 × 2 組參數完全吻合；fixture 已存
`tests/fixtures/turtle/`，附 README）。以下三項修完、全套件轉綠後才 commit。

## RF1 — 修全套件迴歸（1 失敗）

Task: 讓 `tests/unit/test_differential_validation.py::
test_reference_validation_contract_covers_all_declared_strategies` 恢復綠燈。

Required behavior:
1. `src/okx_quant/api/routes_backtest.py` 的 `_turtle_sweep_base_params` 中
   區域變數 `allowed` 改名（如 `param_keys`）——它劫持了該測試對 API
   allow-list 的 regex 抓取（測試抓檔案中**第一個** `allowed = {`）。
2. 在 `backtesting/differential_validation.py` 的
   `REFERENCE_VALIDATION_CONTRACTS` 加**一條**宣告式 `turtle` 條目（仿
   `daily_winner` 形狀：`validation_only`/research-only、引擎 status 用該
   registry 既有合法值，如 unsupported/not_planned——以測試接受的 status
   集合為準）。**使用者已批准（2026-07-03）此單條目範圍修正**；除這一條
   dict 條目外，該檔其他內容一字不動。

PERMITTED FILES: `src/okx_quant/api/routes_backtest.py`（僅改名）、
`backtesting/differential_validation.py`（僅新增一條 registry 條目）。

ACCEPTANCE: `pytest tests/unit/test_differential_validation.py -q` 全過；
`pytest tests/unit -q` 全綠。

## RF2 — invest_pct 拉桿 scrub UI（使用者核心需求）

Task: 在 `TurtleSweepPanel` 補上 invest_pct 軸 sweep 的視覺化。後端資料已
完整（`GET /api/backtest/sweep/result/{sweep_id}` 回傳 rows + equity_curves）。

Required behavior:
1. invest_pct 軸 sweep 完成後顯示「final_equity vs invest_pct」折線
   （沿用既有 LineChart 元件）。
2. 加一條 range 拉桿在掃過的 invest_pct 值之間 scrub：拉到哪個值就渲染該值
   的 equity 曲線（來自 equity_curves）與讀數（final_equity、mdd、
   min_equity，取自該值的 row）。
3. 順帶補齊 heatmap 小倍數為 5 個指標（加 profit_loss_ratio、expectancy）。

PERMITTED FILES: `frontend/view-config.js`、`frontend/charts.js`（如需）、
`frontend/styles.css`（最小樣式）。

ACCEPTANCE: 對每個變更 JS 跑 `node --check`；以假 sweep result payload
（或 DB 冒煙）目視確認拉桿切換曲線與讀數正常；既有策略面板不受影響。

## RF3 — golden fixture 接上 parity 測試

Task: 在 `tests/unit/test_turtle_backtest.py` 加 parity 測試，讀
`tests/fixtures/turtle/daily_ohlc.csv` 跑兩組參數（README 記載的
default 與 stress），逐欄比對 `expected_default.csv` / `expected_stress.csv`
（int/flag 精確；float rtol=atol=1e-9；全部 17 欄）。

PERMITTED FILES: `tests/unit/test_turtle_backtest.py`（fixture 檔已由
Claude 存入，不要重新產生或手改）。

ACCEPTANCE: `pytest tests/unit/test_turtle_backtest.py -q` 全過。

## RF 完成後

1. `pytest tests/unit -q` 全綠 + 三個 docs check。
2. 有 DB 環境時做一次真實 run + sweep 冒煙（RUNBOOK 的 Turtle 段落）。
3. Commit（`AI-Origin: Codex`）——**不要掃進平行 funding-xs-dispersion
   stream 的檔案**（`backtesting/funding_xs_dispersion_backtest.py`、
   `pipeline_stage3_registry.py`、其 manifest/tests/handoffs 與共用 docs 的
   該 stream 段落）；也不要掃進 Claude 的 turtle 規劃/審核 docs 以外的東西
   （或依使用者指示分開 commit）。
4. 更新 `docs/AI_HANDOFF.md` / `docs/CURRENT_STATE.md` /
   `config/workstreams.yaml` 並回報。

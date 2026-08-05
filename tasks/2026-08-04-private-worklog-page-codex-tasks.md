---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# 私有工作紀錄頁(GitHub Pages + private repo)— 交付 Codex 實作(2026-08-04)

使用者需求 2026-08-04:一個綁定 **private repo** 的 GitHub Pages,自動記錄
(1) Claude Code / Codex 工作時間、(2) 每次 commit 內容與每次 AI 產出/完成的內容、
(3) 每日一次策略投資組合快照(損益 + 回測指標)。

這是 `tasks/2026-08-04-public-status-page-codex-tasks.md` 的姊妹任務,沿用同一
「本機產 JSON → push 到發布 repo → Pages 服務」架構,但發布目標是**另一個
私有 repo**,且內容含 PnL(公開頁嚴禁的資料),兩者不可混用同一發布分支。

## 前提事實(已驗證,Codex 不要重新推導)

- Claude Code transcripts:`C:\Users\woody\.claude\projects\c--quant-strategy\<uuid>.jsonl`,
  每行 JSON 含 ISO8601 `timestamp`。**逐訊息即時落盤**,所以 session limit 打到也
  不會掉資料 —— 收集器讀磁碟即可,不需要任何 hook 或「limit 前搶救」機制。
- Codex sessions:`C:\Users\woody\.codex\sessions\YYYY\MM\DD\rollout-*.jsonl`,
  全域(非 per-project);rollout 檔內 session_meta 含 `cwd`,收集器須以
  `cwd == c:\quant_strategy`(不分大小寫、容忍斜線方向)過濾;無 cwd 欄位的行沿用
  該檔已知的 cwd。
- 帳號切換不影響:兩邊的紀錄都在本機同一路徑,與登入帳號無關。
- 回測產物:`results/<run_id>/metrics.json`(sharpe/sortino/max_drawdown/win_rate/
  total_return/cagr/calmar/profit_factor 等)與 `equity_curve.csv`。TimescaleDB 在
  本機,GitHub Actions 碰不到 → 每日刷新只能是本機排程。
- 目前 enabled 投組:funding_carry / ma_crossover / ema_crossover / macd_crossover
  (`config/strategies.yaml`)。
- AI 產出的既有落地形式:`tasks/*-handoff.md`、`tasks/*-codex-tasks.md`、
  `docs/worklogs/`。commit 紀錄本身就是「完成的內容」的主要載體。
- `scripts/worklog/` 已存在且含週報用的 `run_weekly_worklog_task.cmd` 與
  `weekly_worklog_prompt.md` —— 不要動它們,新檔案並存即可。

## 使用者前置決策與步驟(Codex 不代勞,寫進 RUNBOOK 即可)

1. 建私有 repo `Frisk0316/quant_worklog`(只放發布產物,不放程式碼)。
2. **GitHub Free 無法對 private repo 啟用 Pages,需 GitHub Pro。**
3. **風險揭露(需使用者確認後才啟用 Pages)**:private repo 的 Pages 網址仍然是
   公開可存取的(access control 只有 Enterprise 有)。本頁含 PnL 與工時,任何知道
   網址的人都能看。預設方案=接受此風險(網址不外流);替代方案=不啟用 Pages,
   直接本機開啟 clone 內的 index.html,功能完全相同。
4. 註冊每日 Windows 排程呼叫 `scripts/worklog/run_worklog_page_task.cmd`。

## 架構(已定案)

```
main (quant_strategy):  worklog_page/index.html            ← 版控的頁面原始檔
                        scripts/worklog/collect_ai_sessions.py
                        scripts/worklog/snapshot_portfolio.py
                        scripts/worklog/publish_worklog_page.py
                        scripts/worklog/run_worklog_page_task.cmd
quant_worklog (private): index.html + worklog.json + snapshots/*.json
                        + snapshots/index.json + .nojekyll   ← Pages 服務的內容
```

每日流程:collect sessions → 跑投組回測 → snapshot → assemble worklog.json →
複製到 `..\quant_worklog` clone → commit → push。無變更不產生空 commit。

---

## Task: 建立私有工作紀錄頁

Task: 新增只讀本機檔案的收集/快照/組裝腳本與一頁自足靜態頁,經私有 repo
`quant_worklog` 由 GitHub Pages 每日發布工時、commit、AI 產出與策略快照。
Plan source: 本檔 + `docs/CURRENT_STATE.md` + `tasks/2026-08-04-public-status-page-codex-tasks.md`(架構前例)
Strategy/spec source: n/a(不涉及任何策略假設;回測只是呼叫既有 runner)

### PERMITTED FILES(只能改這些)

- `scripts/worklog/collect_ai_sessions.py`(新增)
- `scripts/worklog/snapshot_portfolio.py`(新增)
- `scripts/worklog/publish_worklog_page.py`(新增)
- `scripts/worklog/run_worklog_page_task.cmd`(新增;比照 `scripts/run_public_status_task.cmd`)
- `worklog_page/index.html`(新增)
- `tests/unit/test_worklog_page.py`(新增)
- `docs/FEATURE_MAP.md`(新增一個 feature 區塊)
- `docs/RUNBOOK.md`(一次性設定、每日指令、rollback)
- `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`、`config/workstreams.yaml`(收尾同步)

### FORBIDDEN(不要碰)

- `src/okx_quant/strategies/`、`signals/`、`risk/`、`portfolio/`、`execution/`
- `config/risk.yaml`、`config/strategies.yaml`、`config/settings.yaml`
- `scripts/run_backtest.py`(只呼叫,不修改)、既有 `results/**` 產物
- `public_status/**`、`scripts/publish_public_status.py`、`public-status` 分支
  (公開頁與私有頁嚴格分離)
- `frontend/**`、`research/**`、`.gitignore`、`.github/workflows/**`

SCOPE LIMIT: 只做上述內容,不順手重構相鄰程式碼。

### 必要行為

**A. `collect_ai_sessions.py`** — 只讀 transcript 檔,輸出 sessions JSON。

- 輸入:上述兩個 transcript 樹(路徑可用 `--claude-dir` / `--codex-dir` 覆寫,
  預設取 `%USERPROFILE%` 推導)。
- 每行只取 timestamp;**嚴禁**讀取或輸出訊息內容、prompt、環境變數值 —— transcript
  內文含私密資料,一個字都不能進輸出。
- Session 切分:同一工具連續事件間隔 >30 分鐘視為新 session。輸出每
  session:`tool`(claude|codex)、`start`、`end`、`duration_minutes`、`event_count`;
  並彙總 `daily[]`:date、claude_minutes、codex_minutes、total_minutes。
- 解析失敗的行跳過並計數(`skipped_lines`),不得中斷整體。

**B. `snapshot_portfolio.py`** — 從一個 run 目錄產出當日快照。

- 輸入:`--run-dir results/<run_id>`(由 cmd 傳入當日剛跑完的 run;亦可手動指定
  歷史 run)。讀 `metrics.json` 全部欄位 + `config.json` 的策略清單 +
  `equity_curve.csv` 降採樣至最多 400 點(等距取樣,首尾必留)。
- 輸出 `snapshots/YYYY-MM-DD.json`:`date`、`run_id`、`strategies[]`、`metrics{}`、
  `equity[]`(ts + equity + drawdown 三欄)、`generated_at`。同日重跑覆寫同名檔。
- 缺 `metrics.json` 或 `equity_curve.csv` → 該區塊 `{"available": false, "reason": ...}`,
  不得補零。

**C. `publish_worklog_page.py`** — 組裝並寫進發布 clone。

- `--out-dir`(預設 `..\quant_worklog`)。組裝 `worklog.json`:
  - `commits[]`:`git log` 最近 365 天:hash(short)、date、author、subject、body、
    files_changed 數(不含 diff 內文)。
  - `sessions` / `daily`:A 的輸出原樣帶入。
  - `ai_outputs[]`:掃 `tasks/*.md` 與 `docs/worklogs/*.md`:date(檔名推導)、
    filename、第一個 `# ` 標題、type(handoff|codex-tasks|worklog|other)。只列
    索引,不內嵌全文。
  - 頂層 `generated_at`(UTC ISO8601)、`schema_version: 1`。
- 複製 `worklog_page/index.html` 到 out-dir;確保 `.nojekyll` 存在;維護
  `snapshots/index.json`(可用日期清單,新→舊)。
- 全程不連 DB、不連網路(git 除外,且 git 操作在 cmd 層,不在 Python 內)。

**D. `worklog_page/index.html`** — 單一自足檔案:inline CSS、vanilla JS、無外部
資源、無建置步驟。`fetch` worklog.json 與 snapshots 後渲染四塊:

1. 工時:近 30 日每日長條(claude/codex 疊色)+ 累計總時數。
2. Commits:日期分組清單,subject 展開可見 body。
3. AI 產出:ai_outputs 依日期列表。
4. 策略快照:日期選單(預設最新)、metrics 表格、equity 曲線與 drawdown
   (`<canvas>` 手繪折線即可,不引入圖表庫)。
   附歷史趨勢:各日快照的 total_return / sharpe 小型折線。

fetch 失敗顯示明確錯誤,不留白頁。頁尾顯示 `generated_at` 與「資料每日更新一次」。

**E. `run_worklog_page_task.cmd`** — 每日排程入口,依序:

1. 以 RUNBOOK 記載的固定指令呼叫既有 `scripts/run_backtest.py` 跑 enabled 投組
   回測(確切指令由 Codex 依現行 RUNBOOK 慣例選定並**寫死在 cmd 與 RUNBOOK**,
   不得每日漂移);失敗則跳過 B 但仍發布 A/C(工時與 commit 不因回測失敗斷更)。
2. A → B(帶入該 run 目錄)→ C → `git -C <clone> add -A` → 無變更即結束 →
   有變更 commit + `push origin main`。clone 路徑用環境變數,預設 `..\quant_worklog`。

**F. `tests/unit/test_worklog_page.py`** — 至少四個測試,全用 fixture(不碰真實
transcript 與 `results/`):

1. fixture transcripts(含跨 30 分鐘間隔與壞行)→ session 切分、daily 彙總、
   `skipped_lines` 正確。
2. **隱私金絲雀**:fixture transcript 行內含 `"content":"SECRET_CANARY_XYZ"` 與
   `"apiKey":"sk-test"`,斷言 A 的輸出序列化後不含 `SECRET_CANARY_XYZ`、`sk-`、
   `content` 鍵。
3. fixture run 目錄 → 快照含 metrics + 降採樣 equity(>400 點輸入 → 恰為上限點數,
   首尾保留);缺 metrics.json → `available: false`。
4. C 對 fixture repo 產出的 `worklog.json` 含四區塊且 `schema_version == 1`。

### REQUIRED ON COMPLETION

- `git diff --stat`
- 跑並貼出輸出尾段:
  - `python -m pytest tests/unit/test_worklog_page.py -v`
  - `ruff check scripts/worklog/ tests/unit/test_worklog_page.py`
  - `python scripts/docs/check_doc_metadata.py` 與 `check_feature_map_links.py`
  - `python scripts/docs/check_doc_impact.py`(advisory)
  - 一次真實產生:A 對真實 transcript 跑一次貼出 daily 彙總(這輸出無私密內容);
    C 以 `--out-dir <暫存路徑>` 跑一次,貼出 `worklog.json` 前 40 行
- 依 AGENTS.md docs-update matrix 更新 FEATURE_MAP 與 RUNBOOK;RUNBOOK 須含:
  建私有 repo、GitHub Pro 前提、啟用 Pages、clone 到 `..\quant_worklog`、
  註冊每日排程、rollback(停排程 + 刪 repo 或關 Pages)
- **不要** commit 到 `main`;在 feature branch 上工作,由使用者決定合併
- **不要** 自行建立 `quant_worklog` repo 或啟用 Pages(使用者手動,見 RUNBOOK)
- 不需要 Change Manifest:本任務不改 PnL/手續費/資金費/sizing/成交/閘門
  (回測只是呼叫既有 runner)。回報中明講這句並附 advisory `docs-impact` 結果。

### ACCEPTANCE CRITERIA(binary)

- [ ] `collect_ai_sessions.py` 輸出 JSON 不含任何 transcript 訊息內文:隱私
      金絲雀測試通過(無 `SECRET_CANARY_XYZ`、無 `sk-`、無 `content` 鍵)
- [ ] 三支 Python 腳本皆不 import DB/網路模組(`psycopg`、`requests`、`httpx`、
      `sqlalchemy` 皆不得出現)
- [ ] Codex session 有依 `cwd` 過濾(fixture 含他專案 cwd 的 rollout,不得計入)
- [ ] 快照缺輸入檔時輸出 `available: false`,不出現捏造的零值
- [ ] `index.html` 不含任何 `http://` 或 `https://` 外部資源引用
- [ ] equity 降採樣上限 400 點且首尾點保留(測試斷言)
- [ ] `.cmd` 在無變更時不產生空 commit;回測失敗時工時/commit 區塊仍照常發布
- [ ] `public_status/**` 與 `public-status` 分支零改動(公私分離)
- [ ] RUNBOOK 含 GitHub Pro 前提與「private repo 的 Pages 網址仍公開」風險揭露
- [ ] diff 只含 PERMITTED FILES

REPORT: 變更檔案、測試輸出尾段、做過的假設、任何 UNCONFIRMED 或跳過的項目。

---

## 已知限制

- 本機關機當天不更新;工時以 transcript 事件間隔近似,非精確碼表。
- Codex 工時只涵蓋本機跑的 session;雲端/他機 session 不在紀錄內。
- 「每次 AI 產出」以 commit + tasks/worklogs 檔為載體;未落地成檔的對話不記錄
  (內文涉隱私,設計上排除)。
- Pages 網址公開風險見「使用者前置決策」第 3 點;不接受則改為本機開啟。

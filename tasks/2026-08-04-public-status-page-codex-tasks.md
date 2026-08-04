---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# 公開研究進度頁（GitHub Pages）— 交付 Codex 實作（2026-08-04）

使用者授權 2026-08-04：公開範圍＝**研究進度 + shadow 觀測**（不含權益曲線、不含
策略參數與訊號值）；更新頻率＝**每日一次**，由本機排程推送。

## 前提事實（Codex 不要重新推導）

- `results/*/` 與 `frontend/research_funnel.json` 都在 `.gitignore`，目前 repo 內
  **沒有任何績效資料**。這個任務是一次**新的對外揭露**，範圍必須嚴格照下面的白名單。
- **沒有實盤、沒有 paper 績效可公開**：H-014 shadow 目前 3/8 週、journal 10 筆、
  全部 `not_rich`（零成交）。頁面必須如實呈現，不得暗示 live/demo/promotion readiness。
- TimescaleDB 在本機，GitHub Actions 碰不到，所以刷新只能是本機排程產 JSON 後 push。
- Repo `Frisk0316/quant_strategy` 已是 PUBLIC，Pages 尚未啟用。

## 架構（已定案，不要改成別的）

發布分支 `public-status` 是 orphan branch，**只含三個檔案**：`index.html`、
`status.json`、`.nojekyll`。GitHub Pages source 設為該分支根目錄。發布邊界因此
是結構性的 —— 該分支上不存在的東西不可能外洩，不需要任何 Actions workflow。

```
main:            public_status/index.html      ← 版控的頁面原始檔
                 scripts/publish_public_status.py
public-status:   index.html + status.json + .nojekyll   ← 唯一被 Pages 服務的內容
```

每日流程（本機 Windows 排程，沿用現有 `quant_h014_shadow_daily` 節奏）：
產 JSON → 寫進 `public-status` worktree → commit → push。

---

## Task: 建立公開研究進度頁

Task: 新增一支只讀本機檔案的產生器與一頁自足的靜態頁，透過 orphan branch
`public-status` 由 GitHub Pages 對外提供每日更新的研究進度與 shadow 觀測狀態。
Plan source: 本檔 + `docs/CURRENT_STATE.md`
Strategy/spec source: n/a（不涉及任何策略假設）

### PERMITTED FILES（只能改這些）

- `scripts/publish_public_status.py`（新增）
- `public_status/index.html`（新增）
- `scripts/run_public_status_task.cmd`（新增；排程包裝器，比照
  `scripts/run_h014_shadow_task.cmd`）
- `tests/unit/test_publish_public_status.py`（新增）
- `docs/FEATURE_MAP.md`（新增一個 feature 區塊）
- `docs/RUNBOOK.md`（新增一次性設定、每日指令、rollback）
- `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`、`config/workstreams.yaml`（收尾同步）

### FORBIDDEN（不要碰）

- `src/okx_quant/strategies/`、`signals/`、`risk/`、`portfolio/`、`execution/`
- `config/risk.yaml`、`config/settings.yaml`
- `frontend/**`（這是獨立靜態頁，不是儀表板的一部分）
- `results/**`、`research/**`、`.gitignore`
- `.github/workflows/**`（本方案不需要 workflow）

SCOPE LIMIT: 只做上述內容，不順手重構相鄰程式碼。

### 必要行為

**A. `scripts/publish_public_status.py`**

只讀檔，不連 DB、不連網路。`--out <path>` 指定輸出，預設
`public_status/status.json`。輸入與對應輸出欄位：

| 來源 | 輸出 | 規則 |
| --- | --- | --- |
| `config/workstreams.yaml` | `workstreams[]` | name / status / milestones / current / state / next 原樣帶出；`links` 只留檔名字串，不做連結 |
| `results/shadow_h014/bias_report.json` | `shadow_h014` | 只取 `journal_weeks`、`distinct_journal_weeks`、`minimum_weeks`、`eight_week_journal_met`、`generated_at` |
| `results/shadow_h014/journal.jsonl` | `shadow_h014.event_counts` | 只計數：總筆數、各 `status` 的筆數、最後一筆 `event_date` |
| `frontend/research_funnel.json` | `research_funnel[]` | 每個 family 一列：family、status、hypothesis id、實驗數、最終 outcome |

**硬性禁止欄位**：輸出中不得出現 `dvol`、`ivp`、`vrp`、`rv`、`z`、`px`、
`signal`、`legs`、`intent` 這些鍵，也不得出現其數值。這些是策略訊號本身。

缺檔時該區塊輸出 `{"available": false, "reason": "<檔名> not found"}`，
**不得補零或補假值**。頂層固定含 `generated_at`（UTC ISO8601）與 `schema_version: 1`。

**B. `public_status/index.html`**

單一自足檔案：inline CSS、vanilla JS、無外部資源、無建置步驟、無圖表函式庫
（只有數字與表格，沒有曲線）。`fetch("./status.json")` 後渲染四塊：
標頭免責聲明、workstreams、H-014 shadow 觀測、研究漏斗表。

頁首必須固定顯示（中英各一行即可）：

> 研究專案狀態頁。**無實盤交易、無 paper 交易績效**。H-014 shadow 為觀測用途，
> 目前 N/8 週且零成交。所有假說狀態如實顯示，包含 refuted 與 shelved。
> 本頁不構成任何投資建議，也不代表任何策略已通過推廣或上線閘門。

fetch 失敗顯示明確錯誤，不得留白頁。頁尾顯示 `generated_at` 與「資料每日更新一次」。

**C. `scripts/run_public_status_task.cmd`**

`publish_public_status.py --out <worktree>/status.json` → 複製
`public_status/index.html` 到 worktree → `git -C <worktree> add -A` →
無變更就結束（不產生空 commit）→ 有變更則 commit + `push origin public-status`。
worktree 路徑用環境變數，預設 `..\quant_public_status`。

**D. `tests/unit/test_publish_public_status.py`**

至少三個測試，用 fixture 檔（不碰真實 `results/`）：

1. 完整輸入 → 產出含四個區塊且 `schema_version == 1`。
2. **洩漏金絲雀**：把含 `signal`/`dvol`/`z` 的 journal 餵進去，斷言序列化後的
   JSON 字串中**不含**任何禁止鍵與其數值。
3. 缺 `bias_report.json` → `shadow_h014.available == false`，且不含任何數字欄位。

### REQUIRED ON COMPLETION

- `git diff --stat`
- 跑並貼出輸出尾段：
  - `python -m pytest tests/unit/test_publish_public_status.py -v`
  - `ruff check scripts/publish_public_status.py tests/unit/test_publish_public_status.py`
  - `python scripts/docs/check_doc_metadata.py` 與 `check_feature_map_links.py`
  - `python scripts/docs/check_doc_impact.py`（advisory）
  - 一次真實產生：`python scripts/publish_public_status.py --out <暫存路徑>`，
    貼出實際 JSON 的前 40 行
- 依 AGENTS.md docs-update matrix 更新 FEATURE_MAP 與 RUNBOOK
- **不要** commit 到 `main`；在 feature branch 上工作，由使用者決定合併
- **不要** 自行建立 `public-status` 分支或啟用 Pages —— 那兩步在 RUNBOOK 寫成
  使用者手動執行的指令即可

不需要 Change Manifest：本任務不改 PnL／手續費／資金費／sizing／成交／閘門。
請在回報中明講這一句，並附上 advisory `docs-impact` 的結果。

### ACCEPTANCE CRITERIA（binary）

- [ ] `publish_public_status.py` 不 import 任何 DB／網路模組（`psycopg`、`requests`、
      `httpx`、`sqlalchemy` 皆不得出現）
- [ ] 洩漏金絲雀測試通過：輸出 JSON 不含 `dvol`/`ivp`/`vrp`/`rv`/`z`/`px`/
      `signal`/`legs`/`intent` 任一鍵或其值
- [ ] 缺任一輸入檔時輸出 `available: false`，不出現捏造的零值
- [ ] `index.html` 不含任何 `http://` 或 `https://` 外部資源引用
- [ ] 頁面免責聲明含「無實盤」「無 paper 績效」「N/8 週」「不代表通過推廣或上線閘門」
- [ ] `.cmd` 在無變更時不產生空 commit
- [ ] RUNBOOK 含：建立 orphan branch、建立 worktree、啟用 Pages、註冊每日排程、
      rollback（停用排程 + 刪除 `public-status` 分支 + 關閉 Pages）
- [ ] diff 只含 PERMITTED FILES

REPORT: 變更檔案、測試輸出尾段、做過的假設、任何 UNCONFIRMED 或跳過的項目。

---

## 使用者需自行執行的三步（Codex 不代勞）

1. `git checkout --orphan public-status && git rm -rf . && touch .nojekyll`（首次）
2. GitHub → Settings → Pages → Source: `public-status` / `/ (root)`
3. 註冊每日 Windows 排程呼叫 `scripts/run_public_status_task.cmd`

## 已知限制

- 「實時」實際是每日一次；本機關機當天不更新，頁面會顯示上次更新時間。
- 無績效數字可展示，內容是研究進度而非報酬曲線。這是目前唯一誠實的公開內容。

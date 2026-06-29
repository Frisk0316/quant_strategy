---
status: draft
type: design
owner: human
created: 2026-06-26
last_reviewed: 2026-06-26
expires: none
superseded_by: null
---

# 進度面板改為 Workstream 里程碑視圖 — 設計 spec

> brainstorming 已完成（unit / 顯示方式 / 真相來源 / 移除 git / 實作者四項皆與
> 使用者逐一確認）。`status: draft` 表示等待使用者複審；複審通過後轉 writing-plans
> 產出交給 Codex 的實作計畫。本變更不碰任何 strategy / risk / config gate /
> demo / shadow / live 行為，純屬唯讀面板與其唯讀 API 的呈現方式。

## 問題 / 動機

目前 `進度 / Progress` 面板是 **git-centric**：上半是 commit timeline，下半是
從 `STATUS.md` 解析出來的 branch 卡，每張卡的「task bar」來自所連 plan 檔的
`- [ ]` / `- [x]` checkbox。

兩個問題：

1. **進度訊號是死的。** `docs/superpowers/plans/` 下每個 plan 檔都是 **0/N 勾選**
   （連已大致完成的 pipeline Stage 1、user manual 也是 0），因為沒有人會回去
   勾 checkbox。所以 task bar 一律顯示 0%，誤導。
2. **使用者要的不是 git 流水帳**，而是「**目前每個計劃推進到哪**」——一眼確認
   每條工作線的進度。

## 已定決策 (locked)

| # | 決策 | 選擇 |
|---|------|------|
| 1 | 一張卡 = 什麼 | **Workstream / initiative**（手動策展的工作線清單，例如 XS momentum、研究管線 batch 1、multi-venue P1），比 plan 檔或 branch 更貼近使用者的思考單位。 |
| 2 | 進度怎麼呈現 | **Milestone stepper**：每條 workstream 自帶一組有序里程碑，卡上顯示走到第幾步（done ✔／current ●／pending ○），不造假百分比，貼合本專案 gate 導向的特性。 |
| 3 | 真相來源 | **新的 YAML registry**（`config/workstreams.yaml`），手動維護，於 session 結束時與 `docs/AI_HANDOFF.md` 一併更新（沿用已能維持該檔誠實的同一套紀律）。面板經 `/api/progress` 讀取，使用者亦可直接編輯。 |
| 4 | git timeline / branch 卡 | **整段移除**。面板改為純 workstream 視圖；`routes_progress.py` 內的 git / `STATUS.md` 機制成為死碼，一併刪除。 |
| 5 | 實作者 | **Codex**（trading-core 以外的 API + 前端）。Claude 出 spec 與 plan。 |

## 資料模型 — `config/workstreams.yaml`（新增，手編）

```yaml
workstreams:
  - name: XS momentum
    status: blocked            # active | blocked | done | shelved
    milestones: [spec, impl, backtest, wf_cpcv, demo, live]
    current: wf_cpcv           # 此 milestone 之前 = done；此 = in-progress；之後 = pending
    state: "PSR 0.82 < 0.95, promotion blocked"
    next:  "re-run after portfolio-vol sizing fix"
    links: [docs/superpowers/plans/2026-06-23-xs-momentum-universe.md]
    updated: 2026-06-26        # optional
```

語意：

- `milestones` 為**每條 workstream 各自定義**（策略線的階段 ≠ 文件/UI 線的階段），
  因為 unit 是 workstream 而非固定 gate 集合，這是必要的彈性，不是過度設計。
- `current` 把里程碑切成 done / current / pending 三段。
- `status: done` → 全部視為 done；`shelved` → 整卡灰階；`blocked` → `current`
  節點以紅色呈現，由 `state` 說明原因。
- `state`、`next`、`links`、`updated` 皆為呈現用文字，`updated` 可省略。

### 驗證規則（手編檔 = 信任邊界，不可省）

| 情境 | 行為 |
|------|------|
| 檔案不存在 | `workstreams: []`，面板顯示空狀態，**非錯誤**。 |
| YAML 格式壞 | 該 payload 帶 `error` 字串，端點仍回 200，面板顯示錯誤訊息而非崩潰。 |
| 某 workstream 的 `current` 不在 `milestones` 內 | 該卡帶 per-card `error`，其餘卡正常呈現。 |
| 缺 `name` / `milestones` | 該卡帶 per-card `error`。 |

## 後端 — `src/okx_quant/api/routes_progress.py`

- **刪除** git / STATUS.md 機制：`_run_git`、`_timeline`、`_branch_names`、
  `_branch_git`、`_commit_branch`(已不存在)、`classify_actor`、`_interesting_doc`、
  `parse_status_md`、`_task_counts`，以及 `build_progress_payload` 內對應段落。
- **新增** `_load_workstreams(repo_dir) -> list[dict]`：以
  `yaml.safe_load(path.read_text(encoding="utf-8"))`（沿用 repo 既有 pattern）
  讀取，逐條套用上表驗證，回傳已標好 `done` / `current` / `pending` 的里程碑。
- `build_progress_payload` 改為純函式：回傳
  `{ "generated_at", "workstreams": [...], "error": None }`（不再含 timeline /
  branches / attribution / current_branch）。端點完全不再 spawn 子行程，順帶永久
  解決原本「Loading progress... 卡住」的問題。

### `/api/progress` 回傳形狀（變更）

```json
{
  "generated_at": "2026-06-26T...Z",
  "workstreams": [
    {
      "name": "XS momentum",
      "status": "blocked",
      "state": "PSR 0.82 < 0.95, promotion blocked",
      "next": "re-run after portfolio-vol sizing fix",
      "links": ["docs/superpowers/plans/2026-06-23-xs-momentum-universe.md"],
      "updated": "2026-06-26",
      "milestones": [
        {"name": "spec", "state": "done"},
        {"name": "impl", "state": "done"},
        {"name": "backtest", "state": "done"},
        {"name": "wf_cpcv", "state": "current"},
        {"name": "demo", "state": "pending"},
        {"name": "live", "state": "pending"}
      ],
      "error": null
    }
  ],
  "error": null
}
```

## 前端 — `frontend/view-progress.js`

- **移除** `TimelineItem`、`BranchCard`、timeline / branches 兩個 section 與相關
  helper（`fmtAge`、actor 色票等視 workstream 設計需要保留或刪除）。
- `ProgressView` 改為渲染 **Workstreams** 為唯一主體：
  - KPI 列：workstream 總數 + active / blocked / done 分佈。
  - 每條 workstream 一張 `card`：`name` + status chip · 水平 **milestone stepper**
    （done ✔ 實心／current ● accent，`status:blocked` 時 current 轉紅／pending ○ 空心，
    每個節點帶標籤）· `state` 行 · `next` 行 · `links` 以 chip 呈現。
  - `shelved` 卡整體降透明度。
  - per-card `error` 時，該卡顯示錯誤訊息。
- 重用既有 CSS（`card`、`chip ok/warn/bad/accent`、`between`、`mono`、`bar`），
  **不新增 CSS 檔**。`chipClass(status)` 沿用既有 done/blocked/waiting 對應。
- `window.API.fetchProgress()` 不變（路徑與 `_get` 10s timeout 不動）。

## Seed 資料

以 `docs/AI_HANDOFF.md` + `STATUS.md` 現況填入 `config/workstreams.yaml`，讓面板
一上線即有用；使用者之後自行增刪。初始建議至少含：

| name | status | milestones | current | 備註來源 |
|------|--------|-----------|---------|----------|
| XS momentum | blocked | spec, impl, backtest, wf_cpcv, demo, live | wf_cpcv | PSR 0.82 < 0.95 |
| 研究管線 batch 1 (S5/S6/S7) | blocked | spec, impl, backtest, wf_cpcv, review | wf_cpcv | S6 statistical_gate_passed:false |
| Multi-venue 合約規格 P1 (ADR-0007) | active | spec, impl, validation, consolidated_pr, merge | consolidated_pr | waiting on you：開合併 PR |
| 使用者手冊 | done | draft, write, verify | verify | 全章 written |

## 測試

- 單元（`tests/unit/test_routes_progress.py` 改寫）：
  - `_load_workstreams`：合法檔 → done/current/pending 切分正確；缺檔 → `[]`；
    `current` 不在 `milestones` → 該卡 error；YAML 壞 → payload error 不崩。
  - 既有 `test_progress_route_returns_200_*`：改為「缺 workstreams 檔仍回 200 且
    `workstreams == []`」。
  - **移除** `classify_actor` / `parse_status_md` 測試（對應函式已刪）。
- 前端：`node --check frontend/view-progress.js`（Windows 上 `make` 不可用時的既有
  JS 檢查法）。

## 維護契約（讓它不重蹈 checkbox 覆轍）

於 `AGENTS.md` / `CLAUDE.md` 的 **session-end 義務**加一行：更新
`docs/AI_HANDOFF.md` 時一併更新 `config/workstreams.yaml`。這是訊號保持誠實的唯一
機制。

## 非目標（要再說）

- 不從 git / handoff 自動推導 milestone（heuristic、易跳動，已否決）。
- 不顯示百分比數字。
- 不從 UI 編輯 registry（手編 YAML）。
- 不做 per-milestone 時間戳 / 歷史。
- 不動 `STATUS.md` 內容（檔案保留作人類 branch 板，只是不再餵面板）。

## 影響檔案

**Permitted（本任務只改這些）**

- `config/workstreams.yaml`（新增 + seed）
- `src/okx_quant/api/routes_progress.py`（刪 git 機制 + 加 loader）
- `frontend/view-progress.js`（改為 workstream 視圖）
- `tests/unit/test_routes_progress.py`（改寫測試）
- `docs/UI_MAP.md`、`docs/DATA_FLOW.md`、`docs/FEATURE_MAP.md`（面板/API 讀路徑說明）
- `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`（狀態 + 維護契約）
- `AGENTS.md`、`CLAUDE.md`（session-end 多一行）

**Forbidden（不得碰）**

- `src/okx_quant/strategies/`、`signals/`、`risk/`、`portfolio/`、`execution/`
- 任何 `config/*.yaml`（除新增的 `workstreams.yaml`）
- 其他 API route 檔、`scripts/run_server.py` 的非 progress 部分
- 任何 `results/` artifact、demo / shadow / live / config gate

## 驗收標準

- [ ] `/api/progress` 回傳新形狀（含 `workstreams`，不含 `timeline` / `branches`）。
- [ ] 缺 `config/workstreams.yaml` 時端點回 200 且 `workstreams == []`。
- [ ] YAML 壞 / `current` 非法時不崩，以 error 欄位呈現。
- [ ] 面板顯示每條 workstream 的 milestone stepper，done/current/pending/blocked
      樣式正確，timeline 與 branch 卡不再出現。
- [ ] 端點不再 spawn 任何 git 子行程（無 `subprocess` / `git` 殘留於 route）。
- [ ] `tests/unit/test_routes_progress.py` 全綠；`node --check view-progress.js` 通過。
- [ ] `AGENTS.md` / `CLAUDE.md` session-end 已加維護契約行。

## 風險 / 回滾

- **風險**：registry 仍需人維護才誠實——以 session-end 契約緩解，且空/壞檔皆安全
  退化。移除 git 機制會刪掉剛提交的 `_timeline` 效能修正（commit `08800f7`），
  此為預期——功能已改向，該碼不再被使用。
- **回滾**：本變更全在唯讀面板 + 唯讀 API；`git revert` 對應 commit 即還原舊
  git-centric 面板，無資料/schema/gate 副作用。

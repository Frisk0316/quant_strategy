---
status: draft
type: human_review_overview
owner: human
created: 2026-06-25
last_reviewed: 2026-06-25
topic: "In-Dashboard User Manual (使用手冊)"
source_docs:
  - docs/superpowers/specs/2026-06-25-user-manual-design.md
  - docs/superpowers/plans/2026-06-25-user-manual.md
  - docs/manual/manual.json
  - docs/manual/00-architecture.md
  - docs/manual/10-backtest-validation.md
  - docs/manual/20-strategies.md
  - docs/manual/30-risk-limits.md
decision_required: false
risk_level: low
human_must_read:
  - docs/superpowers/specs/2026-06-25-user-manual-design.md
  - docs/manual/10-backtest-validation.md
  - docs/manual/30-risk-limits.md
superseded_by: null
---

# Human Review Overview: In-Dashboard User Manual (使用手冊)

## 1. 這次在做什麼？

在現有 dashboard 加一個「使用手冊」頁面,讓新使用者或忘記某設計理由的你,能點進去看
系統架構與**每個參數的意義、設計用意與理由**(類似 vectorbt.dev 的 Get Started)。
內容是 `docs/manual/` 的 markdown,由一個 manifest 當目錄,前端 view 用 `marked` 渲染。
本批已完成:設計 spec、實作計畫、Claude 擁有的手冊內容(4 章寫滿 + 5 章 stub)+ manifest
smoke 測試。**前端 view / API / 導覽接線交給 Codex 實作。**

## 2. 為什麼要做？

專案原本沒有使用者手冊;最接近的 `README.md` 很長且偏 agent/治理導向,人類難快速看懂
設計。使用者要的是「點進去就能看懂架構與參數為什麼這樣設計」的入口。

## 3. 本次產生 / 修改了哪些文件？

| 文件 | 用途 | 必讀程度 | 備註 |
|---|---|---|---|
| docs/superpowers/specs/2026-06-25-user-manual-design.md | 設計 spec(三個 locked 決策) | 必讀 | status draft |
| docs/superpowers/plans/2026-06-25-user-manual.md | 實作計畫(Task1 Claude 內容 + Task2–4 Codex 程式) | 建議讀 | 交 Codex 的依據 |
| docs/manual/manual.json | 章節 manifest(TOC) | 可略讀 | 機器讀 |
| docs/manual/00-architecture.md | 系統架構總覽(寫滿) | 建議讀 | — |
| docs/manual/10-backtest-validation.md | 回測與驗證 gate(寫滿) | 必讀 | 描述 gate,須核對不偏離 source |
| docs/manual/20-strategies.md | 啟用策略與參數(寫滿) | 建議讀 | 真值來源 = config/strategies.yaml |
| docs/manual/30-risk-limits.md | 風控限制(寫滿) | 必讀 | 描述風控,須核對不偏離 config/DOMAIN_RULES |
| docs/manual/40–80-*.md | 5 章 stub(待補) | 可略讀 | 標「待補」+ 指向 source docs |
| tests/unit/test_manual_manifest.py | manifest smoke 測試 | 機器用 | 已通過 |

## 4. 這次真正的決策點

| 決策 | 預設選擇 | 為什麼 | 是否需要人類批准 |
|---|---|---|---|
| 形式 / 深度 / 內容來源 | 儀表板內頁面 / 分階段 / docs/manual markdown | 使用者 2026-06-25 brainstorm 逐一拍板 | 已批准 |
| 是否交 Codex 實作 view/API/接線 | 是 | 使用者 2026-06-25 指示「交與 codex 實作」 | 已批准 |

> 本 overview 無待決事項;設計已批准。剩餘是 Codex 實作與一次 spec/plan/content 複審。

## 5. 主要風險

| 風險 | 為什麼重要 | 對應防線 | 是否已機器檢查 |
|---|---|---|---|
| 手冊把某 gate / 風控門檻寫錯或寫死 → 與 config/source 漂移 | 誤導讀者對風險/驗證的理解 | drift 控制:手冊不寫死數值、連結真值來源(config/ai_collaboration/DOMAIN_RULES) | 否(需人工核對 10/30 章) |
| `marked` 從 CDN 載入失敗 | 手冊頁無法渲染 | view 有 fetch 失敗錯誤訊息;不白屏 | 否(Codex browser smoke) |
| 誤把手冊當 source of truth | 幻覺 | 每章結尾聲明以 source docs 為準;本功能不改任何邏輯 | N/A |

## 6. 不能只看摘要的地方

雖然本功能不改任何邏輯(低風險),但手冊**描述**了 gate 與風控,複審時請打開核對:

- `docs/manual/10-backtest-validation.md` vs `docs/ai_collaboration.md`(回測/部署 Gate
  條文)—— 確認手冊沒有把門檻或硬規則寫歪。
- `docs/manual/30-risk-limits.md` vs `config/risk.yaml` + `docs/DOMAIN_RULES.md` ——
  確認參數意義/理由與真值一致,且沒有把會變的數字寫死當權威。
- `docs/superpowers/specs/2026-06-25-user-manual-design.md` 的 scope 段 —— 確認本功能
  「不碰策略/回測/risk/live·demo·shadow gate 邏輯」。

## 7. AI 尚未驗證 / 不確定的地方

- Codex 的 Task 2–4(`/api/manual` router、`view-manual.js`、`app.js`/`index.html`
  接線)**尚未實作**;router/view 的測試尚未跑。
- 手冊頁的**瀏覽器實際渲染**(marked 解析、stub placeholder、nav)尚未視覺驗證。
- 5 章 stub(資料管線/部署 gate/前端各頁/設定檔/名詞)仍是「待補」,只指向 source docs。
- 4 章寫滿的內容雖以 README/config/spec 為據,仍可能有措辭層級的不精確;以 source
  docs 與 config 為準。

## 8. 測試與檢查狀態

| 檢查 | 狀態 | 指令 / 證據 |
|---|---|---|
| unit tests | pass(部分) | `python -m pytest tests/unit/test_manual_manifest.py`(已過);router/view 測試屬 Codex Task,未跑 |
| doc impact | not run | Codex Task 4 會跑 `check_doc_impact.py`(A7/A8 為 advisory、manifest=False) |
| schema validation | n/a | — |
| human overview check | pass | `python scripts/docs/check_human_overview.py` |

## 9. 對現有系統的影響

- **策略邏輯**:無。
- **回測**:無。
- **資料**:無。
- **execution**:無。
- **risk**:無(只是把既有風控限制**文件化**,不改任何值或邏輯)。
- **live / demo / shadow gate**:無。
- **UI / API**:是(Codex 將新增 `使用手冊` view 與 `/api/manual` 唯讀 router;不影響
  現有視圖與既有 API)。
- **文件與 handoff**:新增 spec、plan、`docs/manual/` 內容與本 overview;Codex Task 4
  會更新 `docs/UI_MAP.md`、`docs/FEATURE_MAP.md`。

## 10. 下一步

- **人類**:設計已批准;有空時複審 spec/plan 與 10/30 章內容(見 §6)。
- **Claude**:已交付 Task 1(手冊內容 + manifest + smoke 測試)與本 overview。
- **Codex**:依計畫實作 Task 2–4(router → view → 接線 + UI/FEATURE_MAP 文件),跑
  `test_routes_manual.py` 與 manifest 測試,做一次 browser smoke。
- **何時停止 / 升級給人類**:若實作過程發現需要改動策略 / 回測 / risk / live·demo·shadow
  gate 邏輯才能完成 —— 停止並升級。本功能不應碰那些。

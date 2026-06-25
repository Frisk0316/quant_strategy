---
status: draft
type: design
owner: human
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# 使用手冊 (In-Dashboard User Manual) — 設計 spec

> brainstorming 已完成(三個關鍵分叉由使用者逐一拍板:儀表板內新增頁面、分階段、
> 內容用 docs/manual/ markdown 由 view 渲染)。`status: draft` 表示等使用者複審;
> 複審通過後轉 writing-plans 產實作計畫。**本功能不改任何策略 / 回測 / risk /
> live·demo·shadow gate 邏輯**,只新增一個說明頁與其內容。

## 問題 / 動機

目前專案沒有「使用者手冊」。最接近的是很長的 `README.md` 與一大疊 agent /
governance 導向的 `docs/`,但沒有像 vectorbt.dev「Get Started」那種**給人**的、可
點進去瀏覽的指南,用來解釋系統設計架構,以及**每個參數的意義、設計用意與理由**。

目標:新使用者落地時能從這裡看懂系統;使用者自己忘記「某個設計為什麼是這樣」時,
也能點進去查。重點是「為什麼這樣設計」,不只是「這個旋鈕做什麼」。

## 已定決策 (locked)

| # | 決策 | 選擇 |
|---|------|------|
| 1 | 形式 | **儀表板內新增頁面**(現有 Preact/htm dashboard 加一個 `manual` view),不另建獨立文件網站、不引入新建置工具鏈。 |
| 2 | 深度 | **分階段**:完整架構總覽 + 全章節骨架一次到位,重點章節先寫滿,其餘以「待補」stub 顯示,之後逐次補齊。 |
| 3 | 內容來源 | **`docs/manual/*.md` markdown(Claude 擁有)由 view 渲染**;不把長文塞進 JS。 |
| 4 | 語言 | **zh-Hant**(對齊 `index.html` 的 `lang="zh-Hant"` 與使用者)。 |
| 5 | drift 控制 | 手冊**不複製** config 的精確數值/上限,只講意義與理由,並**連結真值來源**(`config/*.yaml`、`docs/FEATURE_MAP.md`、`docs/DOMAIN_RULES.md`、`docs/ai_collaboration.md` gate 條文)。config 仍是 single source of truth。 |

## 架構與流程

無建置步驟,沿用現有前端模式(Preact + htm,ESM importmap from esm.sh,每個 view
是一個 `window.XxxView` 模組;`view-glossary.js` 是最接近的靜態內容 view 範本)。

```text
docs/manual/                     ← Claude 擁有的內容(git 可審)
  manual.json                    ← 章節 manifest(TOC):有序清單
  00-architecture.md             ← 系統架構總覽   (written)
  10-backtest-validation.md      ← 回測與驗證 gate (written)
  20-strategies.md               ← 策略與其參數   (written)
  30-risk-limits.md              ← 風控限制       (written)
  40-data-pipeline.md            ← 資料管線        (stub)
  50-deployment-gates.md         ← 部署階段 gates  (stub)
  60-frontend-views.md           ← 前端各頁說明    (stub)
  70-config-files.md             ← 設定檔總覽      (stub)
  80-glossary.md                 ← 名詞對照(指向現有 Metrics Glossary)(stub)

FastAPI server  ──靜態服務或小 endpoint──▶  /manual/*.md + manual.json
                                              │
frontend/view-manual.js  ──fetch manifest──▶ 左側章節 sub-nav
                          ──fetch 章節 .md──▶ marked 渲染成 HTML 內容區
                          stub 章節 ──────────▶ 顯示「本章待補」placeholder
```

### manifest 格式 (`docs/manual/manual.json`)

```json
{
  "title": "使用手冊",
  "chapters": [
    { "slug": "architecture", "title": "系統架構總覽", "file": "00-architecture.md", "status": "written" },
    { "slug": "data-pipeline", "title": "資料管線", "file": "40-data-pipeline.md", "status": "stub" }
  ]
}
```

- `status: written | stub`。`stub` 章節即使檔案只有標題與「待補」,view 仍顯示在
  sub-nav(讓**全骨架可見**),但內容區顯示 placeholder + 「目前可先看 source docs」
  連結。

### 服務 (Codex,api/ 區)

FastAPI server 靜態服務 `docs/manual/`(例如 mount 一條 `/manual` 靜態路由指向
`docs/manual/`),或提供一個小 endpoint:`GET /api/manual` 回 manifest、
`GET /api/manual/{slug}` 回該章 raw markdown 文字。二擇一,取較貼合現有 server 結構
者;由實作計畫定 exact 掛載點。markdown 以 `text/plain`(或 `text/markdown`)回傳。

### 渲染 (Codex,frontend/ 區)

- `frontend/view-manual.js`:新 `window.ManualView`,鏡像 `view-glossary.js` 結構。
- 在 `index.html` importmap 加 `marked`(esm.sh),`view-manual.js` 用 `marked` 把
  markdown 轉 HTML。內容為**第一方可信文件**(非使用者輸入),允許
  `dangerouslySetInnerHTML`(Preact: `dangerouslySetInnerHTML`)。
  `// ponytail: 第一方 markdown,免 sanitizer;若日後接受外部投稿再加。`
- 左側 sub-nav 列 manifest 章節;點擊 fetch 對應 `.md` 並渲染;預設開第一章。
- 載入失敗顯示明確錯誤(「無法載入手冊內容」+ 章節檔名),不白屏。

### 接線 (Codex,`app.js` + `index.html`)

- `index.html`:加 `<script type="module" src="view-manual.js"></script>`;importmap
  加 `marked`。
- `app.js`:`NAV` 加 `{ id: "manual", label: "使用手冊", group: "Help", glyph: "manual" }`;
  `titleMap` 加 `manual: ["使用手冊", "系統架構與參數設計說明"]`;`NavGlyph` 加一個
  `manual` 圖示(沿用 1.5 stroke SVG 風格,例如書本/問號);`app-main` 加
  `${view === "manual" && html\`<${window.ManualView} />\`}`。

## 內容模型 (每章寫法)

每章遵循 **意義 → 設計理由 → 真值來源** 三層。參數段落用表格:

| 參數 | 意義 | 設計理由 | 真值來源 |
|---|---|---|---|
| `max_order_notional_usd` | 單筆下單名目上限 | $1k–$10k 資本下,限制單筆暴露、擋 fat-finger | `config/risk.yaml` → `risk.max_order_notional_usd` |

手冊**不寫死**「$500」這種會變的數字;寫「上限,真值見 config」。涉及 gate 的章節
直接連結 `docs/ai_collaboration.md` 對應條文,不重述 gate 規則細節。

## Phase-1 內容(先寫滿)+ 骨架(stub)

**先寫滿(最高價值):**
1. **系統架構總覽** — EventBus → Signal → Portfolio → Execution 事件流;`src/okx_quant/`
   模組地圖;canonical vs market 資料層;maker-only / post-only 的設計理由。連結
   `README.md#architecture`、`docs/FEATURE_MAP.md`、`docs/DATA_FLOW.md`。
2. **回測與驗證 gate** — replay 引擎、walk-forward / CPCV、DSR/PSR、honest `n_trials`、
   idealized-fill 排除、differential validation、ct_val provenance 的**意義與理由**。
   數值門檻與硬規則連結 `docs/ai_collaboration.md`(回測正確性 Gate / 部署 Gate)。
3. **策略與其參數** — 每個 active 策略(funding_carry、pairs_trading、
   technical_indicators、external_features):經濟想法 + 各參數意義/理由,真值來源 =
   `config/strategies.yaml`。連結 `research/strategy_synthesis.md`、`docs/FEATURE_MAP.md`。
4. **風控限制** — max notional / daily loss / soft·hard drawdown / max leverage:意義
   + 為何設這種等級,真值來源 = `config/risk.yaml`。連結 `docs/DOMAIN_RULES.md`。

**骨架 stub(可見、標「待補」):** 資料管線/ingestion、部署階段 gates、前端各頁說明、
設定檔總覽(settings/strategies/risk)、名詞對照(指向現有 Metrics Glossary view)。

## 角色 / scope

- **Claude**(本 spec 屬 docs):寫本 spec、`docs/manual/` markdown 內容 + `manual.json`、
  以及本批的 Human Review Overview(`docs/human_overviews/`,因為這是多文件 planning
  變更,依 `docs/AI_OUTPUT_CONTRACT.md` 必須建立)。
- **Codex**(實作):`frontend/view-manual.js`、markdown 服務(api/)、`app.js` +
  `index.html` 接線、以及 manifest smoke 測試。`frontend/`、`src/okx_quant/api/` 是
  Codex 所有權區。

## 測試 / 驗收

- Codex:view 能渲染 manifest 章節清單;點章節能渲染 markdown;stub 章節顯示
  placeholder;一個 smoke 檢查確認 `manual.json` 的每個 `file` 都存在於 `docs/manual/`。
- 不碰 trading-core / strategy / risk / 回測引擎 / live·demo·shadow gate 邏輯。
- 不宣稱任何策略通過驗證;手冊只解釋既有設計,不改變任何門檻。

## Out of scope (YAGNI)

- 不另建獨立文件網站(mkdocs/docusaurus)或新建置工具鏈。
- 不從程式碼自動產生參數文件(若日後 drift 變痛再做)。
- 不做全文搜尋(已有 Metrics Glossary;日後需要再加)。

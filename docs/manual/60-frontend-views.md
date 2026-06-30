---
status: current
type: manual
owner: human
created: 2026-06-25
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# 前端頁面導覽

前端導覽與 API ownership 以 `docs/UI_MAP.md` 為主。Dashboard 是檢視與操作介面，不是部署 Gate 本身。

| 頁面 | 用途 | 主要資料來源 |
| --- | --- | --- |
| Run Backtest | 啟動 replay、daily-winner、OHLCV rotation 等支援的回測 job | `/api/backtest/run`、config routes |
| Backtest Runs | 檢視 run summary、metrics、charts、signals、fills、risk events | `/api/backtest/*` |
| Validation Lab | 對既有 run 或 validation artifact 做跨引擎/資料檢查 | validation API endpoints |
| Compare Runs | 比較多個 run 的主要績效與風險指標 | backtest artifact summaries |
| Metrics Glossary | 解釋常見績效與風險指標 | static frontend glossary |
| Progress | 顯示 git timeline、Codex/Claude/user attribution、`STATUS.md` branch board | `/api/progress` |
| Risk Monitor | 讀取 live/offline risk 狀態；目前不可當部署核准 | live/risk API endpoints |
| 使用手冊 | 顯示本手冊 manifest 與 markdown chapters | `/api/manual` |

## UI 原則

- 前端不得自行發明缺失的驗證結論。
- API 若回傳缺欄位，先查 artifact 與 backend route，再決定是否修資料形狀。
- Progress panel 是 read-only；它只讀 local git、`STATUS.md` 與 linked plan checkboxes。
- 手冊頁面只顯示 `docs/manual/manual.json` 宣告的章節。

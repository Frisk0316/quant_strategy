---
status: draft
type: human_review_overview
owner: human
created: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
topic: "<short topic>"
source_docs:
  - path/to/source-doc-1.md
  - path/to/source-doc-2.md
decision_required: true
risk_level: low
human_must_read:
  - path/to/must-read-doc.md
superseded_by: null
---

<!--
複製這份 template 到 docs/human_overviews/<YYYY-MM-DD-topic-overview.md>，
把上面的 frontmatter 填成真實值，刪掉用不到的範例路徑。

frontmatter 規則（由 scripts/docs/check_human_overview.py 檢查）：
- type 必須是 human_review_overview
- risk_level 只能是 low / medium / high
- source_docs 與 human_must_read 裡的每個路徑都必須真的存在（相對 repo root）
- 不要放不存在的檔案進去，validator 會失敗
- 這份 overview 不是 source of truth；衝突時以 source_docs 為準
-->

# Human Review Overview: <Topic>

## 1. 這次在做什麼？

用 5–10 行白話說明這批文件到底做了什麼。給沒看過 source docs 的人也能懂。

## 2. 為什麼要做？

原本的痛點是什麼？這次改動想解決什麼？

## 3. 本次產生 / 修改了哪些文件？

| 文件 | 用途 | 必讀程度 | 備註 |
|---|---|---|---|
| path/to/doc.md | ... | 必讀 / 建議讀 / 可略讀 / 證據用 / 機器用 | ... |

## 4. 這次真正的決策點

| 決策 | 預設選擇 | 為什麼 | 是否需要人類批准 |
|---|---|---|---|
| ... | ... | ... | yes / no |

## 5. 主要風險

| 風險 | 為什麼重要 | 對應防線 | 是否已機器檢查 |
|---|---|---|---|
| ... | ... | ... | yes / no / N/A |

## 6. 不能只看摘要的地方

高風險時，人類必須打開底層 source docs，不能只看這份 overview。列出哪些情況、
哪些文件。例如：

- 影響 live / demo / shadow gate
- 影響 risk guard / sizing
- 影響 execution / fill model
- 影響 DSR / PSR / CPCV / n_trials
- 影響資料來源、look-ahead、survivorship bias
- 影響資金、槓桿、交易成本、下單模式

如果這批改動不碰上述任何一項，請明確寫「無—摘要足夠，細節僅供查證」。

## 7. AI 尚未驗證 / 不確定的地方

老實列出 unknowns。不准把「計畫要做」寫成「已經完成」。

## 8. 測試與檢查狀態

| 檢查 | 狀態 | 指令 / 證據 |
|---|---|---|
| unit tests | pass / fail / not run | ... |
| doc impact | pass / fail / not run | `python scripts/docs/check_doc_impact.py` |
| schema validation | pass / fail / not run | ... |
| human overview check | pass / fail / not run | `python scripts/docs/check_human_overview.py` |

## 9. 對現有系統的影響

逐項說明（沒影響就寫「無」）：

- 策略邏輯：
- 回測：
- 資料：
- execution：
- risk：
- live / demo / shadow gate：
- UI / API：
- 文件與 handoff：

## 10. 下一步

- 人類要做什麼：
- Claude 要做什麼：
- Codex 要做什麼：
- 何時應該停止或升級給人類：

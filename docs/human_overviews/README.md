---
status: current
type: overview
owner: human
created: 2026-06-25
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Human Review Overviews

這個資料夾是**給人類看的審核入口**。當 Claude / Codex 根據使用者想法產生一批
spec / plan / driver / governance / ledger 文件時，人類不需要在那一大疊 `.md`
裡大海撈針——先看這裡對應的 Human Review Overview。

## 這是什麼

每份 overview 對應「一批」AI 產生或修改的 planning / governance 文件，幫人類快速
判斷：

- 這批文件到底在做什麼、為什麼做
- 哪幾份必讀、哪些只是證據或細節
- 這次真正需要人類拍板的是什麼
- 有哪些風險、是否影響交易 / 回測 / gate / 資料
- 哪些地方**不能只看摘要**，必須打開底層 source docs
- AI 還沒驗證、不確定的是什麼
- 測試 / doc impact / schema 驗證跑了沒、結果如何
- 下一步是誰要做什麼

## 規則

- **overview 不取代 source docs。** source docs 永遠是 source of truth。
- **衝突時以 source docs 為準**，且 overview 必須把衝突講出來，不准悄悄改寫。
- 每份 overview 都必須在 frontmatter 的 `source_docs` 列出它所依據的底層文件。
- **高風險時，人類必須閱讀 `human_must_read` 裡的文件**，不能只看摘要。
- 當一次改動新增或修改了多份 planning / governance 文件時，**必須**新增或更新一份
  overview（規則細節見 [`../AI_OUTPUT_CONTRACT.md`](../AI_OUTPUT_CONTRACT.md)）。

## 怎麼用

- 從總索引進入：[`../review_index.md`](../review_index.md)。
- 新增 overview：複製
  [`../templates/HUMAN_REVIEW_OVERVIEW_TEMPLATE.md`](../templates/HUMAN_REVIEW_OVERVIEW_TEMPLATE.md)
  到 `docs/human_overviews/<YYYY-MM-DD-topic-overview.md>`，填好 frontmatter 與
  十個章節，然後在 `review_index.md` 加一列。
- 驗證格式：`python scripts/docs/check_human_overview.py`
  （檢查 frontmatter 欄位、`risk_level`、`source_docs` / `human_must_read` 路徑
  存在、以及必要章節）。`README.md` 不會被檢查。

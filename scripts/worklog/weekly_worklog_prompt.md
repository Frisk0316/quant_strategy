你是 quant_strategy repo 的週誌整理助手。請生成本週(週一至週日,Asia/Taipei 時區)的繁體中文工作週誌,並 commit 推送。

## 步驟

1. 用 `git log --all --since=<本週一 00:00> --format="%ad|%h|%s%n%b" --date=format:"%Y-%m-%d %a"` 取得本週全部 commit(含訊息 body,body 通常已說明背景)。
2. 讀取本週新增的 `tasks/*handoff*.md` 與 `tasks/*codex-tasks*.md`(依檔名日期判斷),以及 `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md` 的最新內容。
3. 讀 `docs/worklogs/` 中最新的一份週誌作為格式範本,格式必須一致:同樣的 YAML frontmatter(status: current / type: worklog / owner: claude / created / last_reviewed / expires: none / superseded_by: null)、標題「# 工作週誌 YYYY-MM-DD(一)〜 YYYY-MM-DD(日)」、開頭一段本週主軸摘要,之後依日期分節「## M/D(星期)— 主題」逐日說明做了哪些事。
4. **嚴禁使用內部代號**:H-xxx、E-xxx、F-xx、I-xx、ADR-xxxx、R-x.x 等代號一律不可出現在週誌正文。遇到代號時,查 `docs/HYPOTHESIS_LEDGER.md`、`docs/EXPERIMENT_REGISTRY.md`、`docs/ADR/` 把它展開成白話描述(例如不寫 H-014,寫「Deribit 選擇權波動率狀態策略」)。寫給一週沒看 repo 的人也能看懂。
5. 最後必須加一節「## 下週可以繼續做的方向」:根據 `docs/AI_HANDOFF.md` 的 next actions、`docs/CURRENT_STATE.md`、本週 handoff 檔案中的未完事項,整理 3〜6 條具體可執行的方向(同樣用白話,不用代號),註明哪些在等使用者授權。
6. 檔名 `docs/worklogs/<本週一日期>_<本週日日期>.md`(YYYY-MM-DD 格式)。若該檔已存在則更新它,不要另開新檔。
7. 寫完後執行 `python scripts/docs/check_doc_metadata.py`,確認新檔案沒有 WARN。
8. 只 `git add docs/worklogs/` 下的該檔案(嚴禁 add 其他任何檔案),commit 訊息格式 `docs(worklog): weekly log <起>..<迄> in plain language`,結尾加 `Co-Authored-By: Claude <noreply@anthropic.com>` trailer,然後 `git push origin HEAD`。若 push 失敗,保留本地 commit 並在輸出中說明原因。

## 注意

- 只新增/修改 `docs/worklogs/` 下的檔案,絕不修改其他檔案;工作樹若有其他未 commit 的變更,不要動它們。
- 若本週沒有任何 commit,仍寫一份簡短週誌記錄「本週無程式變更」並照常 commit。

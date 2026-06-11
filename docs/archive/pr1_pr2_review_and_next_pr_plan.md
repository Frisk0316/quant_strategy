---
status: archived
type: review
owner: codex
created: 2026-05-11
last_reviewed: 2026-06-11
expires: none
superseded_by: docs/AI_HANDOFF.md
---

# PR1 / PR2 修改建議與後續 PR 規劃

## 文件目的

本文件整理目前 `quant_strategy` repository 中 PR1 與 PR2 的審查結論、必要修改建議，以及後續 PR 的切分方式。

目前 repo 正在建立 AI-assisted development 的工程治理流程，核心目標是：

1. 降低 Codex / Claude 5-hour session limit 導致的上下文斷裂。
2. 讓 Claude / Codex / Human 的角色分工清楚。
3. 避免 AI 任意擴大修改範圍。
4. 建立 issue、branch、PR、CI、handoff、regression test 的固定流程。
5. 讓 repo 文件與測試成為 AI 的長期記憶，而不是依賴聊天紀錄。

---

# 一、PR1 審查結論與修改建議

## 1. PR1 整體結論

PR1 的方向正確，可以視為「大致通過」。

PR1 已經完成 AI 協作治理的核心文件，包括：

- `docs/AI_WORKFLOW.md`
- `docs/AI_HANDOFF.md`
- `docs/DEBUGGING_RUNBOOK.md`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `.github/ISSUE_TEMPLATE/ai_task.md`

這些文件已經能初步解決以下問題：

- Claude / Codex / Human 分工不清。
- Codex 修改範圍過大。
- Claude 只在事後 review，而不是先規劃。
- session 斷裂後沒有 handoff。
- PR 沒有 AI attribution、scope、test plan。
- bug 沒有標準 reproduction 與 evidence。
- AI task 沒有限制 permitted files / forbidden files。

因此 PR1 可以保留，但仍建議補幾個一致性與完整性問題。

---

## 2. `docs/AI_WORKFLOW.md` 修改建議

### 目前狀態

`AI_WORKFLOW.md` 已經有清楚定義：

- Claude 的職責：plan、review、risk analysis、acceptance criteria。
- Codex 的職責：依照 issue scope 實作、補測試、更新 handoff。
- Human 的職責：scope approval、tradeoff、local test、merge。
- Standard Task Flow。
- Session Start Checklist。
- Claude Plan Format。
- Codex Task Format。
- Commit trailer。
- Branch naming。
- Prohibited Actions。

整體符合需求。

### 建議修改

目前 Claude 的禁止事項中有提到：

```text
Does not directly modify src/okx_quant/strategies/, risk/, portfolio/, or execution/
unless the user explicitly overrides this.
```

這個方向正確，但建議補一段，避免 Claude 誤以為自己連 docs 都不能改：

```md
Claude may edit documentation-only files when the issue explicitly permits docs changes.
Claude must not modify trading-core code unless the issue explicitly allows it and the user approves the scope.
```

### 建議新增內容

在 `AI_WORKFLOW.md` 補上「文件修改例外」：

```md
## Documentation-only Exception

Claude may directly edit documentation files when all conditions are met:

- The issue or task is documentation-only.
- The permitted files list includes the target docs.
- No trading-core files are modified.
- AI_HANDOFF.md is updated after the session.

This exception does not apply to:
- strategy implementation
- portfolio accounting
- risk logic
- execution logic
- live / shadow deployment settings
```

---

## 3. `docs/AI_HANDOFF.md` 修改建議

### 目前狀態

`AI_HANDOFF.md` 結構完整，包含：

- Current Goal
- Current Branch
- Last Known Good Commit
- System Overview
- Recent Changes
- Known Bugs / Open Issues
- Do Not Touch
- Next Steps
- Open Questions
- Session Handoff Checklist

這非常符合原始需求。

### 主要問題

目前 `AI_HANDOFF.md` 的 Next Steps 仍然顯示：

```text
[PR 2] Write docs/ARCHITECTURE.md and docs/ADR/ after full source read
```

但現在 `docs/ARCHITECTURE.md` 與 ADR 0001–0005 已經存在。這代表 PR2 完成後 handoff 沒有更新。

這會違反 `AI_HANDOFF.md` 的核心目的：它應該是跨 session 的最新狀態，而不是過期工作清單。

### 建議修改

將 `Recent Changes` 補上 PR1 / PR2：

```md
## Recent Changes

| Commit / PR | Change | Risk |
|---|---|---|
| PR2 | Add ARCHITECTURE.md and ADR 0001–0005 | Some ADRs describe target behavior that may not be fully implemented |
| PR1 | Add AI workflow, handoff, debugging runbook, PR / issue templates | Governance docs only |
| cb022c5 | Add TradesView, CompareView, and RiskView components | Frontend regression risk if component imports break |
```

將 `Next Steps` 改成：

```md
## Next Steps

1. [PR 3] Fix PR1 / PR2 documentation consistency issues
2. [PR 4] Add CI skeleton: ruff + pytest unit gate
3. [PR 5] Add SWAP ct_val PnL regression test
4. [PR 6] Add frontend MIME smoke test
5. [PR 7] Add pairs trading hedge close regression test
6. [PR 8] Add replay terminal liquidation design or implementation
7. [PR 9] Fix shadow mode SimBroker vs OKX demo gap
```

### 建議補充

在 `Known Bugs / Open Issues` 增加：

```md
6. **ADR / implementation mismatch** (P0 docs):
   - ADR-0004 says `.js`, `.jsx`, `.mjs` MIME types are registered, but server.py currently registers only `.jsx` and `.mjs`.
   - ADR-0005 describes replay validation gates as enforced, but source code does not yet clearly enforce all gates.
   - ADR-0003 funding cashflow formula sign convention needs correction.
```

---

## 4. `docs/DEBUGGING_RUNBOOK.md` 修改建議

### 目前狀態

`DEBUGGING_RUNBOOK.md` 已經涵蓋：

- Frontend blank page
- Replay / backtest result looks wrong
- Funding carry PnL looks wrong
- Pairs trading hedge not closing
- Test suite fails
- API returns 500 or unexpected schema

這符合原始需求。

### 建議修改

Frontend blank page 章節目前主要以 `.js` 為主。由於前一輪問題來自 `.jsx` MIME type，而 repo 仍可能保留 legacy `.jsx` 討論或文件，建議補充 `.jsx` 檢查。

新增：

````md
If legacy `.jsx` modules still exist, also check:

```bash
curl -I http://localhost:8080/app.jsx
```

Expected Content-Type:

```text
application/javascript
```

or:

```text
text/javascript
```

Any of the following is invalid for ES modules:

```text
application/octet-stream
text/plain
text/html
```
````

### 建議新增：錯誤回報前 checklist

```md
## Before Filing a Bug

- [ ] Console error copied verbatim
- [ ] Network response status and Content-Type checked
- [ ] Exact command used to reproduce recorded
- [ ] Suspected layer selected
- [ ] Relevant files listed
- [ ] Out-of-scope constraints written
```

---

## 5. `.github/pull_request_template.md` 修改建議

### 目前狀態

PR template 已包含：

- Summary
- Related Issue
- AI Attribution
- Scope
- Out of Scope
- Risk
- Test Plan
- Screenshots / Logs
- Handoff Notes

整體符合需求。

### 主要缺口

目前缺少明確的 `Acceptance Criteria` 區塊。Test Plan 不等於 Acceptance Criteria。

### 建議新增

在 `Risk` 與 `Test Plan` 之間新增：

```md
## Acceptance Criteria

<!-- Copy the acceptance criteria from the issue and check each item. -->

- [ ] All issue acceptance criteria are satisfied
- [ ] Any unmet criteria are explicitly listed below
- [ ] If this PR only partially completes the issue, the remaining work is documented
```

### 建議調整 Test Plan

目前 Test Plan 寫：

```md
- [ ] pytest tests/integration/ -v — passed (or skipped with reason: )
```

可以補充：

```md
- [ ] Integration tests skipped because: <DB unavailable / not relevant / no integration tests yet>
```

避免 checkbox 被亂勾。

---

## 6. Issue templates 修改建議

### 6.1 `ai_task.md`

`ai_task.md` 很完整，可以視為通過。

它已經包含：

- Claude Plan Reference
- Strategy / Spec Source
- PERMITTED FILES
- FORBIDDEN
- SCOPE LIMIT
- Required Behavior
- Required Tests
- Acceptance Criteria
- Validation Commands
- Risk Concerns
- Do Not Do
- Claude Review Checklist
- Claude → Codex handoff

這份文件是 PR1 中最符合需求的一份。

### 6.2 `bug_report.md`

`bug_report.md` 有：

- Problem
- Evidence
- Suspected Layer
- Reproduction
- Expected Behavior
- Scope
- Out of Scope
- Acceptance Criteria
- Additional Constraints

方向正確。

#### 缺口

原始企畫要求每個 template 都有 AI Attribution 欄位，但目前 `bug_report.md` 沒有。

#### 建議補上

```md
## AI Attribution

| Role | Who |
|---|---|
| Planning | Claude / Human / None |
| Implementation | Codex / Claude / Human / None |
| Review | Claude / Human / None |
| Human-confirmed | yes / no |
```

### 6.3 `feature_request.md`

`feature_request.md` 也缺少 AI Attribution。

建議同樣補上：

```md
## AI Attribution

| Role | Who |
|---|---|
| Planning | Claude / Human / None |
| Implementation | Codex / Claude / Human / None |
| Review | Claude / Human / None |
| Human-confirmed | yes / no |
```

並補充：

```md
## First PR Scope

<!-- If this feature is large, define the smallest first PR. -->
```

因為 feature 很容易被 Codex 擴大範圍。

---

# 二、PR2 審查結論與修改建議

## 1. PR2 整體結論

PR2 的方向正確，但不建議直接視為完全通過。

PR2 新增：

- `docs/ARCHITECTURE.md`
- `docs/ADR/0001-ai-assisted-development.md`
- `docs/ADR/0002-backtest-result-schema.md`
- `docs/ADR/0003-position-pnl-accounting.md`
- `docs/ADR/0004-frontend-module-loading.md`
- `docs/ADR/0005-replay-validation-gates.md`

這些文件對 repo 很有幫助，尤其是：

- 把架構從 README 拆出來。
- 記錄 AI-assisted workflow。
- 記錄 backtest result schema。
- 記錄 PnL accounting 的 `ct_val` 原則。
- 記錄 frontend module MIME 原則。
- 記錄 replay validation gate 的設計方向。

但 PR2 有三個比較嚴重的問題：

1. ADR-0003 funding cashflow 公式與 sign convention 矛盾。
2. ADR-0004 與目前 `server.py` 不一致。
3. ADR-0005 把尚未完全實作的 validation gates 寫成已經 enforced。

這三個問題需要下一個 PR 立刻修正，否則未來 Codex / Claude 會根據錯誤文件做錯實作。

---

## 2. `docs/ARCHITECTURE.md` 修改建議

### 目前狀態

`ARCHITECTURE.md` 內容完整，包含：

- System Layers
- Event Flow
- Strategy Layer
- Signal Layer
- Portfolio Layer
- Execution Layer
- Risk Layer
- Data Layer
- Backtesting Layer
- API Layer
- Configuration Layer
- Engine Orchestration
- Deployment Stages

方向正確。

### 主要問題

文件中部分內容像是「目前已驗證實作」，但實際上可能只是「目標架構」。

例如：

- Shadow mode 可能仍有 SimBroker vs OKX demo mismatch。
- Replay validation gates 尚未完整 enforce。
- Terminal liquidation 可能尚未實作。
- Deployment stages 可能是政策目標，而不是目前 code 已保證的流程。

### 建議修改

在文件前面新增：

```md
## Document Semantics

This document distinguishes between:

- **Current implementation**: behavior verified in the current source code.
- **Target architecture**: intended behavior that may not be fully implemented yet.
- **Known gap**: documented mismatch between target design and current implementation.

Codex must not treat Target Architecture sections as implemented behavior.
If a section is marked Target or Known Gap, create an issue before modifying code.
```

並在關鍵章節補狀態標記。

範例：

```md
### Shadow Mode

Status: Known Gap

The target architecture is ShadowBroker = SimBroker primary + OKXBroker mirror.
However, AI_HANDOFF currently tracks a P0 issue that shadow mode may not yet perform a true SimBroker vs OKX demo comparison.
Do not rely on this behavior until the shadow mode issue is fixed and tested.
```

Replay validation 部分：

```md
### Replay Validation Gates

Status: Target Architecture

The desired gates are documented in ADR-0005.
They are not yet guaranteed to be fully enforced by the current replay engine.
```

---

## 3. ADR-0001 修改建議

### 目前狀態

ADR-0001 符合需求。

它定義：

- Claude plans first。
- Codex implements。
- Human merges。
- 每個 task 要有 GitHub issue。
- `AI_HANDOFF.md` 是 cross-session memory。

### 建議修改

不需要大改。

可以小補：

```md
## Enforcement

This ADR is enforced by:

- `.github/ISSUE_TEMPLATE/ai_task.md`
- `.github/pull_request_template.md`
- `docs/AI_HANDOFF.md`
- CI gates once available
```

---

## 4. ADR-0002 修改建議

### 目前狀態

ADR-0002 定義 backtest result schema freeze，方向正確。

它定義了：

- `result.json` top-level fields
- `metrics` required keys
- `trades.csv` required columns
- `fills.csv` required columns
- `equity_curve.csv` required columns

### 主要風險

目前 schema 仍主要由 `backtesting/artifacts.py` 實際決定。ADR-0002 是規範，但還沒有測試保證文件與實作一致。

### 建議修改

補上：

```md
## Implementation Status

This ADR defines the target stable schema.
Until schema regression tests are added, `backtesting/artifacts.py` remains the implementation source of truth.
Any mismatch between this ADR and `backtesting/artifacts.py` must be resolved by either:

1. updating the ADR, or
2. updating the artifact writer and tests.
```

### 後續測試要求

後續 PR 應新增：

```text
tests/unit/test_backtest_artifact_schema.py
```

測試：

```text
- FILL_COLUMNS includes all ADR required fill fields
- TRADE_COLUMNS includes all ADR required trade fields
- EQUITY_COLUMNS includes all ADR required equity fields
- minimal result artifact export includes required files
```

---

## 5. ADR-0003 修改建議

### 目前狀態

ADR-0003 對 SWAP / SPOT PnL 與 notional 的定義方向正確。

目前文件中：

```text
SWAP:
unrealized_pnl = size × ct_val × (last_price − avg_entry)
notional       = abs(size) × last_price × ct_val

SPOT:
unrealized_pnl = size × (last_price − avg_entry)
notional       = abs(size) × last_price
```

這是正確的。

### 嚴重問題：Funding cashflow 公式符號錯

目前 ADR-0003 寫：

```text
funding_pnl = perp_size × ct_val × funding_rate × mark_price
```

並且又寫：

```text
positive funding_rate means longs pay shorts
```

這兩句矛盾。

如果：

```text
perp_size > 0 = long
funding_rate > 0
```

用目前公式會得到正 cashflow，等於 long 收 funding。  
但實際 convention 是 positive funding rate 時 long pays short。

### 必修建議

改成：

```md
### Funding cashflow

Given position size convention:

- positive size = long
- negative size = short

```text
funding_cashflow = -perp_size × ct_val × funding_rate × mark_price
```

Therefore:

- long perp pays funding when `funding_rate > 0`
- short perp receives funding when `funding_rate > 0`
```

### 建議補充

加入測試範例：

```text
perp_size = -0.25 contracts
ct_val = 0.01
mark_price = 40,000
funding_rate = 0.0001

funding_cashflow = -(-0.25) × 0.01 × 40,000 × 0.0001
                 = +0.01 USDT
```

A short perp receives positive funding when funding rate is positive.

---

## 6. ADR-0004 修改建議

### 目前狀態

ADR-0004 寫：

```python
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".jsx")
mimetypes.add_type("application/javascript", ".mjs")
```

並且說 frontend modules 使用 `.js`。

目前 `frontend/index.html` 也確實全部引用 `.js`：

```html
<script type="module" src="tweaks-panel.js"></script>
<script type="module" src="charts.js"></script>
<script type="module" src="view-config.js"></script>
<script type="module" src="view-results.js"></script>
<script type="module" src="view-trades.js"></script>
<script type="module" src="view-backtest.js"></script>
<script type="module" src="app.js"></script>
```

### 問題

目前 `src/okx_quant/api/server.py` 只註冊：

```python
mimetypes.add_type("application/javascript", ".jsx")
mimetypes.add_type("application/javascript", ".mjs")
```

缺少：

```python
mimetypes.add_type("application/javascript", ".js")
```

這造成 ADR 與實作不一致。

### 必修建議

在 `server.py` 改成：

```python
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".jsx")
mimetypes.add_type("application/javascript", ".mjs")
```

並確認這三行在 `StaticFiles` mount 之前執行。

### 建議補測試

後續 PR 可新增 frontend MIME smoke test：

```text
GET /app.js
Content-Type should be application/javascript or text/javascript
```

---

## 7. ADR-0005 修改建議

### 目前狀態

ADR-0005 寫：

```md
The following validation gates are enforced in backtesting/replay.py and checked by scripts/run_replay_backtest.py
```

並列出：

- terminal position check
- `liquidate_on_end=True`
- terminal liquidation fills
- fill rate warning
- data coverage gate
- funding coverage warning
- `result.json` includes `"validation"`

### 問題

目前 source 看起來尚未完整實作上述 gates。

目前 `ReplayBacktestResult` dataclass 主要包含：

```text
returns
equity_curve
metrics
order_log
fill_log
funding_log
trade_log
signal_log
risk_event_log
rejected_log
cancel_log
```

沒有明確 `validation` 欄位。

`run_replay_backtest.py` 目前有 `--validate` 支援 wf / cpcv，但沒有明確 `--liquidate-on-end` 或 terminal liquidation toggle。

### 結論

ADR-0005 目前應該是「目標設計」，不是已經 accepted / enforced 的架構決策。

### 建議修改方式 A：改成 Proposed

建議先採用 A，因為這是文件修正 PR，不應同時實作 replay engine。

將 ADR-0005 改成：

```md
## Status

Proposed — 2026-05-11
```

並把：

```md
The following validation gates are enforced...
```

改成：

```md
The following validation gates are proposed for implementation.
They are not guaranteed to be fully enforced by the current replay engine yet.
```

新增：

```md
## Implementation Status

Not fully implemented.

Known gaps:
- `ReplayBacktestResult` does not yet expose a dedicated `validation` field.
- CLI does not yet expose `--liquidate-on-end` / `--no-liquidate-on-end`.
- Terminal liquidation behavior needs source verification and regression tests.
- Data coverage gate and funding coverage warning need explicit tests.
```

### 建議修改方式 B：補實作

若選 B，需要開較大的 PR，至少包含：

```text
1. config/backtest 加 liquidate_on_end
2. CLI 加 --liquidate-on-end / --no-liquidate-on-end
3. ReplayBacktestEngine.run() 結束前產生 terminal liquidation fills
4. ReplayBacktestResult 加 validation 欄位
5. artifact writer 寫 validation.json
6. result.json 加 validation
7. tests/integration/test_replay_engine.py 加 terminal liquidation test
```

目前建議先選 A，後續再開專門 PR 實作。

---

# 三、建議下一個 PR：PR3 文件一致性修正

## PR3 目標

修正 PR1 / PR2 的文件與實作不一致問題，不碰核心策略與回測邏輯。

## PR3 建議名稱

```text
docs/fix-ai-governance-consistency
```

或：

```text
docs/pr1-pr2-consistency-fixes
```

## PR3 Scope

### 允許修改

```text
docs/AI_WORKFLOW.md
docs/AI_HANDOFF.md
docs/DEBUGGING_RUNBOOK.md
docs/ARCHITECTURE.md
docs/ADR/0002-backtest-result-schema.md
docs/ADR/0003-position-pnl-accounting.md
docs/ADR/0004-frontend-module-loading.md
docs/ADR/0005-replay-validation-gates.md
.github/pull_request_template.md
.github/ISSUE_TEMPLATE/bug_report.md
.github/ISSUE_TEMPLATE/feature_request.md
src/okx_quant/api/server.py
```

### 禁止修改

```text
src/okx_quant/strategies/
src/okx_quant/portfolio/
src/okx_quant/risk/
src/okx_quant/execution/
backtesting/replay.py
config/risk.yaml
config/strategies.yaml
```

## PR3 必做項目

1. `server.py` 補 `.js` MIME registration。
2. ADR-0003 修 funding cashflow 公式。
3. ADR-0005 改成 Proposed 或標註 Not fully implemented。
4. `AI_HANDOFF.md` 更新 PR1 / PR2 狀態。
5. `bug_report.md` 與 `feature_request.md` 補 AI Attribution。
6. `pull_request_template.md` 補 Acceptance Criteria 區塊。
7. `ARCHITECTURE.md` 補 current / target / known gap 語義說明。

## PR3 驗收條件

```md
- [ ] ADR-0003 funding formula sign is correct
- [ ] ADR-0004 matches server.py MIME registration
- [ ] ADR-0005 no longer claims unimplemented gates are enforced
- [ ] AI_HANDOFF.md reflects PR1 and PR2 as completed
- [ ] All issue templates include AI Attribution
- [ ] PR template includes Acceptance Criteria
- [ ] No strategy / portfolio / risk / execution logic changed
```

## PR3 建議給 Codex 的 Prompt

```text
Task: Fix documentation consistency issues from PR1 and PR2.

Read:
- docs/AI_HANDOFF.md
- docs/AI_WORKFLOW.md
- docs/ADR/0003-position-pnl-accounting.md
- docs/ADR/0004-frontend-module-loading.md
- docs/ADR/0005-replay-validation-gates.md

PERMITTED FILES:
- docs/AI_WORKFLOW.md
- docs/AI_HANDOFF.md
- docs/DEBUGGING_RUNBOOK.md
- docs/ARCHITECTURE.md
- docs/ADR/0002-backtest-result-schema.md
- docs/ADR/0003-position-pnl-accounting.md
- docs/ADR/0004-frontend-module-loading.md
- docs/ADR/0005-replay-validation-gates.md
- .github/pull_request_template.md
- .github/ISSUE_TEMPLATE/bug_report.md
- .github/ISSUE_TEMPLATE/feature_request.md
- src/okx_quant/api/server.py

FORBIDDEN:
- src/okx_quant/strategies/
- src/okx_quant/portfolio/
- src/okx_quant/risk/
- src/okx_quant/execution/
- backtesting/replay.py
- config/risk.yaml
- config/strategies.yaml

Required changes:
1. Add .js MIME registration to server.py.
2. Fix ADR-0003 funding cashflow sign convention.
3. Mark ADR-0005 as Proposed or Not Fully Implemented.
4. Update AI_HANDOFF.md to mark PR1 / PR2 as completed and list PR3 next.
5. Add AI Attribution sections to bug_report.md and feature_request.md.
6. Add Acceptance Criteria section to pull_request_template.md.
7. Add Current / Target / Known Gap semantics to ARCHITECTURE.md.

Do not refactor. Do not modify trading logic. Do not touch unrelated files.
```

---

# 四、後續 PR 規劃

建議後續 PR 不要一次做太大，應該拆成小而可驗證的 PR。

---

## PR4：CI Skeleton

### 目標

建立最小 CI，先讓 repo 有自動檢查，不再完全依賴人工。

### 建議 branch

```text
ci/add-minimal-github-actions
```

### 允許修改

```text
.github/workflows/ci.yml
pyproject.toml
docs/AI_HANDOFF.md
```

### 禁止修改

```text
src/okx_quant/strategies/
src/okx_quant/portfolio/
src/okx_quant/risk/
backtesting/replay.py
```

### 建議 CI 內容

第一階段先跑：

```bash
python -m pip install -e ".[dev]"
ruff check src tests
pytest tests/unit -v
```

### 若目前 tests 不完整

如果 `tests/unit` 尚未存在或測試數量太少，CI 可以先這樣：

```yaml
- name: Run unit tests
  run: |
    if [ -d tests ]; then
      pytest tests/unit -v || pytest tests -v
    else
      echo "No tests directory yet; skipping pytest"
    fi
```

但這只能是暫時方案，後續 PR 必須補測試。

### 驗收條件

```md
- [ ] GitHub Actions workflow exists
- [ ] ruff check runs
- [ ] pytest runs or explicitly skips with documented reason
- [ ] CI does not require TimescaleDB in first version
- [ ] AI_HANDOFF.md updated
```

---

## PR5：SWAP `ct_val` PnL Regression Test

### 目標

防止 SWAP unrealized PnL / notional 少乘或多乘 `ct_val`。

這是目前最高優先級的 regression test，因為之前已經觀察到：

```text
fill notional 約 $100
但 equity curve / drawdown 像是 $10,000 部位在波動
```

### 建議 branch

```text
test/add-ctval-pnl-regression
```

### 允許修改

```text
tests/unit/test_position_pnl_accounting.py
docs/AI_HANDOFF.md
```

如果發現 bug 需要修：

```text
src/okx_quant/portfolio/positions.py
```

但需 issue explicit approve。

### 測試情境

```text
inst_id = BTC-USDT-SWAP
size = 0.25 contracts
ct_val = 0.01
avg_entry = 40000
last_price = 41000

expected unrealized_pnl = 0.25 × 0.01 × 1000 = 2.5
expected notional = 0.25 × 0.01 × 41000 = 102.5
```

### 驗收條件

```md
- [ ] Test fails if ct_val is omitted
- [ ] Test passes with correct ct_val formula
- [ ] pytest tests/unit/test_position_pnl_accounting.py -v passes
- [ ] No strategy logic changed
```

---

## PR6：Frontend MIME Smoke Test

### 目標

避免 `type="module"` frontend 再次因 MIME type 錯誤導致空白頁。

### 建議 branch

```text
test/add-frontend-mime-smoke
```

### 允許修改

```text
tests/unit/test_frontend_static_mime.py
src/okx_quant/api/server.py
docs/AI_HANDOFF.md
```

### 測試方向

使用 FastAPI TestClient 建立 app，檢查：

```text
GET /app.js
Content-Type should be application/javascript or text/javascript
```

若保留 legacy `.jsx`：

```text
GET /app.jsx
Content-Type should be application/javascript or text/javascript
```

### 驗收條件

```md
- [ ] /app.js returns JavaScript MIME type
- [ ] server.py registers .js / .jsx / .mjs
- [ ] pytest test passes
- [ ] No frontend rewrite
```

---

## PR7：Backtest Artifact Schema Regression Test

### 目標

讓 ADR-0002 不只是文件，而是可測試的 contract。

### 建議 branch

```text
test/add-backtest-schema-regression
```

### 允許修改

```text
tests/unit/test_backtest_artifact_schema.py
backtesting/artifacts.py
docs/AI_HANDOFF.md
```

### 測試內容

檢查：

```text
FILL_COLUMNS includes:
- ts
- datetime
- strategy
- inst_id
- side
- fill_px
- fill_sz
- fee
- state
- ct_val

TRADE_COLUMNS includes:
- ts
- datetime
- inst_id
- side
- fill_px
- fill_sz
- realized_pnl
- net_realized_pnl
- size_before
- size_after
- equity_after

EQUITY_COLUMNS includes:
- ts
- datetime
- equity
- drawdown
- return
```

### 驗收條件

```md
- [ ] Required schema columns are tested
- [ ] Tests fail if a frozen column is removed
- [ ] ADR-0002 and artifacts.py are consistent
```

---

## PR8：Pairs Trading Hedge Close Regression Test

### 目標

防止 pairs trading exit / stop 只關主腿、不關 hedge 腿，造成 orphan hedge position。

### 建議 branch

```text
test/add-pairs-hedge-close-regression
```

### 允許修改

```text
tests/unit/test_pairs_trading_hedge_close.py
docs/AI_HANDOFF.md
```

如果測出 bug 需要修：

```text
src/okx_quant/strategies/pairs_trading.py
src/okx_quant/portfolio/portfolio_manager.py
```

但這必須開專門 implementation PR，不建議 test PR 同時修。

### 測試情境

```text
1. Entry signal creates main leg + hedge leg
2. Exit signal occurs
3. Both main and hedge positions should close
4. No non-zero hedge position remains
```

### 驗收條件

```md
- [ ] Regression test reproduces orphan hedge risk
- [ ] Test clearly distinguishes main leg and hedge leg
- [ ] If test fails on current implementation, open separate fix PR
```

---

## PR9：Funding Carry Dual Leg Regression Test

### 目標

確認 funding carry 的 perp / spot 雙腿方向與 notional 對齊。

### 建議 branch

```text
test/add-funding-carry-dual-leg-regression
```

### 測試情境

正 funding：

```text
funding_rate > 0
strategy enters carry
perp leg should be sell
spot leg should be buy
perp notional ≈ spot notional
```

若有 reverse funding carry：

```text
reverse strategy:
perp leg should be buy
spot leg should be sell
```

### 驗收條件

```md
- [ ] Positive funding produces correct standard carry side
- [ ] Spot / perp notional roughly aligned
- [ ] Test catches missing or incorrect dual leg metadata
```

---

## PR10：Replay Terminal Liquidation Design / Implementation

### 目標

處理 ADR-0005 中提到但尚未完整落地的 terminal liquidation。

### 建議拆成兩階段

#### PR10A：Design only

```text
docs/replay_terminal_liquidation_plan.md
docs/ADR/0005-replay-validation-gates.md
docs/AI_HANDOFF.md
```

內容：

```text
- current replay behavior
- desired terminal liquidation behavior
- config / CLI design
- artifact schema impact
- test plan
- migration risk
```

#### PR10B：Implementation

允許修改：

```text
backtesting/replay.py
scripts/run_replay_backtest.py
backtesting/artifacts.py
src/okx_quant/core/config.py
tests/integration/test_replay_terminal_liquidation.py
```

### 驗收條件

```md
- [ ] liquidate_on_end configurable
- [ ] default behavior documented
- [ ] final positions zero when liquidate_on_end=true
- [ ] terminal liquidation fills written to fills/trades
- [ ] result validation records terminal liquidation status
- [ ] integration test passes
```

---

## PR11：Replay Validation Gates Implementation

### 目標

把 ADR-0005 從 Proposed 推進到 Accepted。

### 內容

實作：

```text
1. fill_rate warning
2. data coverage gate
3. funding coverage warning for funding_carry
4. validation object in result.json
5. CLI / API display validation warnings
```

### 驗收條件

```md
- [ ] result.json includes validation
- [ ] fill_rate < threshold emits warning
- [ ] data coverage < threshold fails explicitly
- [ ] funding_carry with no funding rows emits warning
- [ ] tests cover each validation gate
```

---

## PR12：Shadow Mode Gap Fix

### 目標

處理 `AI_HANDOFF.md` 中 P0：

```text
scripts/run_shadow.py claims SimBroker vs OKX demo comparison,
but engine only instantiates SimBroker in shadow mode.
No true comparison happens.
```

### 建議流程

這個 PR 風險較高，不應直接實作。應先開 design PR：

```text
docs/shadow_mode_parity_plan.md
```

設計內容：

```text
- current shadow mode behavior
- intended ShadowBroker behavior
- SimBroker primary vs OKX demo mirror design
- fill comparison metrics
- calibration logger requirements
- failure handling
- test plan
```

再開 implementation PR。

---

# 五、建議 PR 順序總覽

建議順序如下：

| PR | 類型 | 目標 | 風險 |
|---:|---|---|---|
| PR3 | docs + tiny server fix | 修 PR1 / PR2 文件一致性 | 低 |
| PR4 | CI | 建立 ruff + pytest 最小 gate | 低 |
| PR5 | test | SWAP ct_val PnL regression | 中 |
| PR6 | test | frontend MIME smoke test | 低 |
| PR7 | test | backtest artifact schema regression | 低 |
| PR8 | test | pairs trading hedge close regression | 中 |
| PR9 | test | funding carry dual leg regression | 中 |
| PR10A | design | terminal liquidation design | 低 |
| PR10B | implementation | terminal liquidation implementation | 高 |
| PR11 | implementation | replay validation gates | 高 |
| PR12A | design | shadow mode parity plan | 中 |
| PR12B | implementation | shadow mode fix | 高 |

---

# 六、建議 Claude Review Checklist

之後每個 PR 都讓 Claude 用這份 checklist review。

```md
## Claude Review Checklist

### Scope

- [ ] PR only touches permitted files
- [ ] No unrelated refactor
- [ ] No strategy / risk / execution changes unless explicitly allowed

### Documentation

- [ ] AI_HANDOFF.md updated
- [ ] ADRs do not claim unimplemented behavior is implemented
- [ ] Architecture docs distinguish current vs target behavior

### Tests

- [ ] Regression test added for bug fix
- [ ] Test would fail before the fix
- [ ] Test does not only assert trivial behavior
- [ ] pytest command documented

### PnL / Accounting

- [ ] SWAP uses ct_val
- [ ] Funding sign convention is correct
- [ ] Fees are included where relevant
- [ ] Spot and swap notional units are not mixed

### Replay / Backtest

- [ ] No lookahead bias introduced
- [ ] Result schema is not broken
- [ ] Open position behavior is documented
- [ ] Validation warnings are not silently ignored

### Frontend / API

- [ ] API response schema unchanged or frontend updated together
- [ ] Module MIME type preserved
- [ ] No silent blank page risk from import path changes

### AI Governance

- [ ] Commit includes AI-Origin trailer
- [ ] PR template filled
- [ ] Issue acceptance criteria satisfied
```

---

# 七、給後續 Codex 的通用限制 Prompt

```text
Before editing, read:

1. docs/AI_HANDOFF.md
2. docs/AI_WORKFLOW.md
3. the issue for this task
4. any relevant ADR

You may only edit files listed under PERMITTED FILES.

Do not:
- refactor unrelated code
- rename variables for style
- reorganize imports unless required
- touch strategy / portfolio / risk / execution unless explicitly permitted
- change config/risk.yaml unless explicitly permitted
- claim live/demo readiness

At completion, report:

1. changed files
2. summary of changes
3. tests run
4. tests not run and why
5. remaining risks
6. AI_HANDOFF.md update
```

---

# 八、最終建議

目前 PR1 / PR2 是好的開始，但下一步不要急著進入策略或 replay engine 大改。

建議先做：

```text
PR3：修文件一致性
PR4：建立 CI
PR5：補 SWAP ct_val PnL regression
```

這三個完成後，repo 才比較適合讓 Codex 繼續處理核心交易邏輯。

最重要的原則是：

```text
文件不能描述不存在的行為。
測試必須保護高風險邏輯。
Codex 必須被 issue scope 約束。
Claude 必須先 plan、後 review。
Human 永遠做最後 merge 決策。
```

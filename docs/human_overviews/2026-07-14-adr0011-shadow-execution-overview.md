---
status: current
type: human_review_overview
owner: codex
created: 2026-07-14
last_reviewed: 2026-07-14
topic: "ADR-0011 H-014 Deribit shadow-only execution"
source_docs:
  - docs/ADR/0011-deribit-options-shadow-execution.md
  - tasks/2026-07-14-deribit-shadow-execution-codex-tasks.md
  - docs/change_manifests/2026-07-14-deribit-options-shadow-execution.md
  - docs/MODULE_BRIEFS/deribit-shadow-execution.md
  - docs/KNOWN_ISSUES.md
decision_required: true
risk_level: high
human_must_read:
  - docs/ADR/0011-deribit-options-shadow-execution.md
  - docs/change_manifests/2026-07-14-deribit-options-shadow-execution.md
  - docs/KNOWN_ISSUES.md
superseded_by: null
expires: none
---

# Human Review Overview: ADR-0011 H-014 Shadow-Only Execution

## 1. 這次在做什麼？

Review whether the implementation faithfully realizes the already accepted
shadow-only ADR. Approval here accepts the code and manual workflow only. It
does not approve scheduling, parameter changes, private credentials, orders,
live trading, or promotion.

## 2. 為什麼要做？

H-014 needs real signal timing and public quote evidence before any live ADR
may even be discussed. This layer measures the distance between research
assumptions and a conservative, observable shadow path without order capability.

## 3. 本次產生 / 修改了哪些文件？

| Surface | Change | Authority | Review focus |
|---|---|---|---|
| shadow runner | Reuses research signal/strike/accounting functions and records public quotes plus hypothetical fills | ADR-0011, task T1/T2 | no re-derivation or private path |
| config | Freezes `ivp=85`, `z=0.5`, 1/30 tranche, 1.0 unit cap | accepted CPCV result | drift must fail closed |
| report | Reports fill bias, missed entries, mark error, valid weeks and gate state | task T3 | stale records excluded |
| governance | R8/I39/I40/F39, manifest, maps and runbook synchronized | Doc Sync Harness | current vs target is explicit |

## 4. 這次真正的決策點

| Decision | Encoded behavior | Authority | Reversible here? |
|---|---|---|---|
| frozen parameters | config validation rejects any drift | user + ADR-0011 | no; needs user approval |
| naked put ban | intent rejected before quotes/fills | R8.3/I39 | no |
| conservative fill | sells at bid, buys at ask; incomplete book misses whole entry | ADR-0011 | no |
| no live capability | public method allow-list and no broker/order object | ADR-0011/R7.2 | no |

## 5. 主要風險

| Risk | Current control | Remaining exposure | Human action now? |
|---|---|---|---|
| stale signal looks current | exact prior-day and 08:00 UTC boundary check | inputs need manual refresh while unscheduled | yes: accept manual operating boundary |
| partial multi-leg fill creates naked risk | all legs must have usable top-of-book or entry is missed | real fills can differ; not modeled | no live inference |
| append-only duplicate/manual rerun | deterministic event IDs and dedupe scan | single-process only | keep manual-only |
| public API semantics drift | method allow-list and smoke test | exchange can change fields | monitor during manual runs |

## 6. 不能只看摘要的地方

- Eight calendar weeks have not been collected; the exit gate is closed.
- Public quote reachability and hypothetical fills do not imply executable live
  orders, profitability, operational resilience, or deployment readiness.
- The two first-smoke stale records are audit history only and do not count.
- No parameter, data-source, schedule, risk policy, or live gate may be changed
  from this overview.

## 7. AI 尚未驗證 / 不確定的地方

Codex chose a single-process JSONL implementation because manual execution is
the approved scope. It discovered stale inputs and a stale-ID recovery edge,
then added F39/I40 fail-closed handling and signal-day-qualified IDs. Inputs
were refreshed through the existing bounded public ingestion workflows; no
scheduler was added. Claude has not completed the execution/risk critique.

## 8. 測試與檢查狀態

| Check | Status | Evidence / limitation |
|---|---|---|
| unit and R8 golden tests | pass | targeted suite covers parity, guards, fills, settlement and report |
| DB signal parity | pass | five common days satisfy `|ivp delta| < 0.5`, `|z delta| < 0.05` |
| public order book | pass | credentials-free Deribit endpoint returned bid/ask/mark |
| current operational cycle | pass | valid BTC/ETH records; both signals were `not_rich` |
| doc/config governance | pass | metadata, links, ledger, overview, config and strict doc impact |
| full parent unit suite | pass | 861 passed, 1 skipped; existing numerical warnings only |

## 9. 對現有系統的影響

No `research/` content, result artifact migration, DB schema, DB write path,
`risk.yaml`, live/demo/deployment gate, private endpoint, credential plumbing,
order submission, scheduler registration, or differential validation was
changed. Existing uncommitted Claude/user files were preserved.

## 10. 下一步

- Human: review the manifest and the fail-closed stale-data disclosure.
- Claude: critique signal parity, fill conservatism, R8 reuse and naked-risk guard.
- Codex: continue manual valid logging and surface any freshness or public-API
  failures; do not register a scheduler without a new user approval.
- Live remains blocked until at least 8 valid weeks, the bias report, a future
  live ADR discussion, and a separate R7.2 human approval.

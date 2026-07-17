---
status: current
type: task
owner: claude
created: 2026-07-16
last_reviewed: 2026-07-17
expires: on-completion
superseded_by: null
---

# Codex Tasks: Strategy History Document + Frontend Strategy Iteration View

Planner: Claude (2026-07-16). Template: `docs/ai/TASK_TEMPLATES.md` §2.
User goal: one document recording every past strategy (logic, ideation source,
benchmark, annualized return / backtest results, instruments) plus the pipeline
screening architecture, and a frontend view that shows strategy iteration
intuitively.

Ground rules for all tasks:
- Ledgers stay authoritative and READ-ONLY: never edit
  `docs/HYPOTHESIS_LEDGER.md` or `docs/EXPERIMENT_REGISTRY.md` content.
- Never fabricate numbers. If a metric (benchmark comparison, annualized
  return) is not recorded in a ledger/artifact, write `n/a (not recorded)`.
  Registry Notes carry WF/CPCV Sharpe + DSR/PSR — those are the recorded
  results; treat "benchmark" as a known gap unless a Stage-3 artifact has it.
- No new backend routes, no network ingest, no strategy/risk/execution code,
  no gate changes. `research/` is Claude-owned — read, never edit.
- No generated JSON checked into git (matches funnel-JSON precedent).

## Task A — `docs/STRATEGY_HISTORY.md` (hand-authored document)

Task: author the consolidated strategy history document.
Sources: `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
`research/strategy_synthesis.md` (read-only), `docs/ADR/0013-*`,
`docs/superpowers/pipeline/stage2-feasibility.md`.

Required content:
1. Pipeline architecture section: idea batch → Stage-2 data feasibility →
   Stage-2 statistical-power triage (ADR-0013, advisory) → Stage-3 full-PnL
   validation (WF/CPCV) → gates (DSR/PSR ≥ 0.95, K-budget, no gate-chasing
   retries). One diagram-in-text, ≤30 lines.
2. One section per hypothesis H-000..H-021: name/family, status, ideation
   source (ledger Source column, expanded to a sentence), strategy logic
   (2-5 lines, from the falsifiable hypothesis text + the matching
   `research/strategy_synthesis.md` strategy where one exists), instruments/
   universe and backtest window (from registry Setup), recorded results
   (WF/CPCV/DSR/PSR from registry Notes; annualized return/benchmark only if
   an artifact records it, else `n/a`), iteration chain (E-IDs in order with
   one line on what changed between runs), and outcome/lesson.
3. A "known gaps" note: benchmark-vs-buy-and-hold and annualized return are
   not systematically recorded; recording them is a future, separately
   approved change.

PERMITTED FILES: `docs/STRATEGY_HISTORY.md` (new), `docs/CONTEXT_INDEX.md`
(one index line), `docs/CURRENT_STATE.md` / `docs/AI_HANDOFF.md` (session end).
FORBIDDEN: ledgers, `research/**`, `src/okx_quant/**`, `config/risk.yaml`.
Verify: `make docs-check`.
ACCEPTANCE (binary):
- [ ] Every H-000..H-021 has a section with all fields above (n/a allowed).
- [ ] Every number in the doc is traceable to a ledger row or artifact path.
- [ ] `make docs-check` passes; diff contains only permitted files.

## Task B — funnel JSON schema v2 (per-family detail)

Task: extend `scripts/run_pipeline_funnel_report.py` (it already parses both
ledgers) to add per-family fields to the generated JSON: `source`,
`hypothesis_text`, `experiments: [{id, date, setup, outcome, notes}]` sorted
by date. Bump `schema_version` to 2; keep all v1 fields unchanged.
Instruments/window stay inside the raw `setup` string — do not over-parse.

PERMITTED FILES: `scripts/run_pipeline_funnel_report.py`,
`tests/unit/test_pipeline_funnel_report.py`, `docs/DATA_FLOW.md`.
FORBIDDEN: ledgers, `backtesting/pipeline_stage2_registry.py` gate logic,
any checked-in JSON.
Verify: `python -m pytest tests/unit/test_pipeline_funnel_report.py -q`.
ACCEPTANCE (binary):
- [ ] v2 JSON contains source/hypothesis_text/experiments per family; a family
      absent from the registry yields an empty experiments list, not a crash.
- [ ] All v1 consumers unaffected (existing tests still pass unmodified in
      intent; only additive assertions).
- [ ] `docs/DATA_FLOW.md` funnel-JSON entry updated to schema v2.

## Task C — frontend: strategy iteration detail in Ledger view

Task: extend `frontend/view-ledger.js` (no new view) with an expandable
detail row per family showing: ideation source, hypothesis/logic text,
experiment timeline (id, date, setup, outcome, notes — the iteration story),
and the existing deep links to both ledgers plus a link to
`docs/STRATEGY_HISTORY.md` via the existing markdown-serve route. Handle
schema v1 JSON gracefully (detail row shows "regenerate with schema v2"
hint). Keep the existing empty-state behavior.

PERMITTED FILES: `frontend/view-ledger.js`, `frontend/data.js` (only if the
fetcher needs a change), `docs/UI_MAP.md`, targeted frontend tests if the
repo pattern has them.
FORBIDDEN: new backend routes, other views, `frontend/app.js` beyond what the
detail row strictly needs (nav entry already exists).
Verify: `make frontend-check`; regenerate funnel JSON locally
(`python scripts/run_pipeline_funnel_report.py --json-output
frontend/research_funnel.json`) and eyeball one expanded row; do not commit
the JSON.
ACCEPTANCE (binary):
- [ ] Expanding a family row shows source, logic, and full experiment
      timeline from v2 JSON; v1 JSON degrades with a hint, no crash.
- [ ] `docs/STRATEGY_HISTORY.md` reachable from the view via the existing
      allow-list route (add to allow-list config only if that is the
      established pattern; name the file touched in the report).
- [ ] `make frontend-check` passes; diff contains only permitted files.

## Order and report

A → B → C (A gives B/C the authored text to link to). On completion report
per AGENTS.md "When finishing a task" block, including any allow-list file
touched and UNCONFIRMED items. This is observability/docs only: no Change
Manifest and no new ADR required; if implementation ever needs a gate or
rule change, STOP and return to Claude/user.

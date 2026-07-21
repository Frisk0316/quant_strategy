---
status: current
type: handoff
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Context Handoff: Strategy History and Ledger Iterations — 2026-07-17

## Goal (one sentence)

Deliver a consolidated strategy history, funnel schema v2, and intuitive
read-only Ledger iteration view without changing ledgers, research assumptions,
stored results, business rules, or trading/deployment gates.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `b2eb27e` plus the shared uncommitted
  2026-07-16 delivery and this verified 2026-07-17 delivery; no commit was
  requested.
- In-progress edits: none for this task. The shared working tree contains
  unrelated pre-existing changes that were preserved.
- What works right now: `docs/STRATEGY_HISTORY.md` covers H-000–H-021 and every
  E-000–E-056 iteration; the funnel generator emits schema v2; the Ledger view
  expands source, hypothesis, and the dated experiment timeline; schema v1
  renders a regeneration hint without crashing.
- What does not work / unfinished: implementation is complete. Claude source-
  fidelity review remains; no generated `frontend/research_funnel.json` is
  present or intended for version control.

## Decisions made (and why)

- Keep the history hand-authored and trace every claim to ledgers/artifacts —
  because the Markdown ledgers are authoritative and missing metrics must remain
  `n/a (not recorded)`.
- Preserve raw registry `setup`, `outcome`, and `notes` in schema v2 instead of
  interpreting free text — because interpretation would create a second source
  of truth and hide historical inconsistencies.
- Use native HTML `<details>` and the existing static projection route — because
  this gives progressive disclosure with no new dependency or backend route.
- Reuse the existing Progress allow-list for `docs/STRATEGY_HISTORY.md` — because
  link containment already exists and no broader file-serving surface is needed.
- Record H-002/E-005's artifact annualized return as the only found annualized
  return and leave all unrecorded returns/benchmarks as `n/a` — because no other
  valid values were present in the named sources.
- Preserve, rather than repair, H-009 chronology and historical trial-accounting
  caveats — because ledger mutation was explicitly forbidden.

## Open questions / unverified assumptions

- H-009's registry dates place E-031 before E-030 while the ledger chain presents
  E-028 → E-030 → E-031; the history reports this source conflict without choosing
  a new chronology.
- Some historical experiment notes use inconsistent trial-count terminology or
  shared artifact paths; a future ledger-normalization design needs separate
  approval.
- H-014 support applies to the RICH short-premium branch; the CHEAP long-straddle
  branch failed and must not inherit the supported label.

## Rules in play (preserve verbatim)

- Invariants touched: none; this task changes a read-only projection only.
- Domain rules touched: none; no Change Manifest or ADR is required.
- Authoritative sources remain `docs/HYPOTHESIS_LEDGER.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `research/strategy_synthesis.md`, accepted
  ADRs, and `config/` in the documented precedence order.
- Do-not-touch: both ledgers' content, `research/`, existing `results/**`,
  strategy/signal/risk/portfolio/execution code, DB schema, and every Stage-3,
  demo, shadow, live, promotion, and deployment gate.

## Context to load next (the reading list)

- Source of truth: `tasks/2026-07-16-strategy-history-doc-frontend-codex-tasks.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, and
  `research/strategy_synthesis.md` (read-only).
- Owning files: `docs/STRATEGY_HISTORY.md`,
  `scripts/run_pipeline_funnel_report.py`, `frontend/view-ledger.js`,
  `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, and `config/workstreams.yaml`.
- Supporting design: `docs/ADR/0013-stage2-statistical-power-triage.md` and
  `docs/superpowers/pipeline/stage2-feasibility.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` (no task-specific
  pack exists).

## Checks run

- `python -m pytest tests/unit/test_pipeline_funnel_report.py -q` — 3 passed.
- `python -m pytest tests/unit/test_routes_progress.py -q` — 10 passed.
- Targeted Ruff for funnel generator/test — PASS.
- Every Makefile frontend Node syntax check plus `frontend/view-ledger.js` —
  PASS.
- Docs metadata, Feature Map links, and ledger consistency — PASS.
- `scripts/validate_pipeline.py --check-config-only` — both checks PASS.
- Real disposable funnel generation — schema 2, 22 families; funding-carry
  family includes source, hypothesis, and E-018/E-021/E-024/E-026 in date/id order.
- Structural history audit — 22 H sections and 57 unique E records, with no
  missing H-000–H-021 or E-000–E-056.
- Playwright with Edge — schema-v2 expansion and schema-v1 fallback PASS; only
  the unrelated favicon 404 appeared in the console. Temporary browser/server
  artifacts and processes were cleaned up.
- Literal `make` — unavailable on this Windows host; the corresponding commands
  above were run directly.

## Approvals

- Human approval obtained through the explicit request to complete
  `tasks/2026-07-16-strategy-history-doc-frontend-codex-tasks.md`.
- No approval was requested or inferred for ledger edits, experiments, retries,
  ingest, strategy/business-rule changes, or any deployment action.

## Next action (single, concrete)

- Claude reviews the consolidated document and schema-v2 projection against the
  ledgers, focusing on chronology/source caveats and H-014's partial support.

## Human Learning Notes

Most of the desired UI information already existed in the two ledgers; the
missing piece was a faithful projection, not a new data model. Only E-005 exposed
a valid recorded annualized return in the named artifacts, so blank-looking
benchmark/return fields are honest evidence gaps rather than implementation
failures. Free-text registry history also makes chronology and trial accounting
inconsistencies visible; projecting those records verbatim is safer than silently
normalizing them.

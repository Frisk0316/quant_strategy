---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Context Handoff: OKX Liquidation Unattended Mode — 2026-07-15

## Goal (one sentence)

Move `quant_liq_okx_ingest` from logged-on-only execution to the approved
least-privilege unattended mode without changing ingestion semantics or gates.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: HEAD `87d38d7`; P1.4 changes are uncommitted.
- In-progress edits (files): `scripts/market_data/run_liq_ingest_task.cmd`,
  P1.4 RUNBOOK/feature/state docs, `config/workstreams.yaml`, and this handoff pair.
- What works right now: the wrapper uses the verified Python 3.12 executable;
  targeted ingest tests and dry-run pass; a manual scheduled-task run completed
  with result `0`; full unit, docs, config, and doc-impact checks pass.
- What does not work / unfinished: the host task still reports
  `woody / Interactive / Limited`. Task Scheduler rejected the principal update
  without Administrator rights, so logged-out execution is not activated yet.
- Unrelated existing work: `tests/fixtures/h014_shadow_db_signal.json` appeared
  untracked during this session and was not read, modified, or removed.

## Decisions made (and why)

- Use `woody / S4U / Limited` and keep the existing action and two-hour cadence
  because it solves logout retention without storing a password or elevating the
  ingestion process; would change if the task needed delegated Windows network
  credentials.
- Do not use SYSTEM because a user-writable repository script must not run as
  SYSTEM; this is the smallest safe option.
- Pin the current Python executable in the wrapper because S4U must not depend on
  an interactive PATH; update the one path only if Python moves.

## Open questions / unverified assumptions

- After Administrator registration, verify a real manual run under S4U returns
  `0`; this session could verify the wrapper only under the existing Interactive
  principal.

## Rules in play (preserve verbatim)

- Invariants touched: none; I15 remains unchanged — no live/shadow/demo claim
  without all gates passed plus human approval.
- Domain rules touched: none.
- Do-not-touch: H-014/shadow files, `research/`, existing `results/`,
  strategy/signal/risk/portfolio/execution, DB schema, deployment gates,
  differential validation, and the user-owned 127.0.0.1:8080 process.

## Context to load next (the reading list)

- Source of truth: P1.4 in
  `tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
- Owning files: `scripts/market_data/run_liq_ingest_task.cmd`,
  `scripts/market_data/ingest_external.py`,
  `tests/unit/test_ingest_external_liquidation.py`, `docs/RUNBOOK.md`.
- Context Pack: no market-ingestion pack exists; use
  `docs/CONTEXT_INDEX.md` plus the Market Data Ingestion section of
  `docs/FEATURE_MAP.md`.

## Checks run

- Targeted liquidation unit test — `5 passed`.
- Liquidation CLI dry-run — BTC and ETH dispatch passed.
- Manual `quant_liq_okx_ingest` run — result `0` at 2026-07-15 12:44:47 local.
- Full unit equivalent — `861 passed, 1 skipped, 1273 warnings` in 65.44s;
  skip is the existing Windows symlink-privilege case.
- Docs check — metadata, 225 feature-map paths, and 21 H / 53 E / 20 K ledger
  consistency passed.
- Config check and advisory docs-impact — passed.

## Approvals

- Human approval obtained: P1.4 unattended/service mode was approved in the
  authoritative 2026-07-12 task.
- Human Administrator action still required: run the RUNBOOK `/NP` registration,
  then verify `S4U / Limited` and manual-run result `0`.

## Next action (single, concrete)

- Run the P1.4 `schtasks /Create ... /NP` command from Administrator PowerShell
  and record the verified S4U result before marking P1.4 complete.

## Human Learning Notes

Windows can execute the existing task successfully yet still lose hours-scale
data after logout because `Interactive` is a principal property, not an action
or trigger property. S4U fixes that boundary without the SYSTEM privilege risk,
but registration itself requires an elevated Task Scheduler operation.

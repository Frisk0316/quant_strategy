---
status: current
type: handoff
owner: codex
created: 2026-07-31
last_reviewed: 2026-07-31
expires: none
superseded_by: null
---

# Session Handoff: H-039, CFTC COT, and Cboe ingestion - 2026-07-31

## Implementation summary

Implemented the three task adapters and their existing-ingestion/config wiring.
H-039 uses full-chain retention, total-variance 30d interpolation, nearest
fallback, and isolated per-source attempts; COT uses stable market codes and
publication lag; Cboe uses official CSVs with header-drift checks. Unit/config
and official-source validation pass. Persistence, backfills, and scheduling
remain blocked because the configured TimescaleDB endpoint refuses connections.

## Diff scope

- Files added: three external clients, three unit-test modules, and this context
  and session handoff pair.
- Files changed: external-client exports, external-ingest wiring, H-039 snapshot
  defaults/failure handling, external-data config, task acceptance record,
  feature/data/runbook/invariant/failure-mode docs, H-039 spec/ledger, current
  state, known issues, AI handoff/changelog, and workstreams.
- Files deleted: the superseded untracked `xvenue_option_surface.py` and its
  matching test were replaced before finalization; no tracked user artifact was
  deleted.

## Business-rule change?

- No. Existing R6.2 as-of/provenance rules apply; no Change Manifest or ADR is
  required.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; research ownership was not touched.
- `config/`: 17 task datasets and honest Progress workstreams updated.
- ADR: N/A; no schema, business-rule, or gate decision changed.

## Experiments

- HYPOTHESIS_LEDGER entries: H-039 wording synchronized; trials remain 0 and K
  remains 0/2.
- EXPERIMENT_REGISTRY entries: none for this ingestion task.

## Tests / checks run

- Targeted pytest with existing external-data tests: 19 passed; one
  cache-permission warning.
- Targeted Ruff: passed.
- Config-only validation and all three adapter dry-runs: passed.
- Doc metadata, feature-map links, ledger consistency, advisory doc impact, and
  `git diff --check`: passed; metadata retained two unrelated warnings and Git
  reported only line-ending notices.
- Official-source validation: 17/17 datasets parsed; exact source row counts,
  ranges, H-039 IVs, and retained chain sizes are in the task record.
- `ingest_external.py --dataset xvenue_opt_iv_okx_btc`: failed at store
  initialization with `ConnectionRefusedError [WinError 1225]`; no DB or
  scheduler state changed.

## Docs updated

- `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
  `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, the H-039 spec and hypothesis
  ledger, `docs/KNOWN_ISSUES.md`, `docs/CURRENT_STATE.md`,
  `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, and `config/workstreams.yaml`.

## Known limitations / risks

- DB acceptance boxes remain open: source counts are not persisted counts.
- COT publication uses the standard release schedule, not an exact historical
  holiday-release calendar; this must remain visible before research use.
- Cboe total put/call is archive-only through 2019-10-04.
- H-039 has no persisted observations and its 270-day clock has not started.

## Rollback plan

- Remove only the three new clients/tests and two new handoffs; remove their
  exports/ingest/config entries; restore the H-039 snapshot dataset defaults;
  and revert only the task-specific documentation paragraphs. No migration,
  persisted row, scheduled task, result artifact, or deployment setting needs
  rollback.

## Context Handoff

- See `tasks/2026-07-31-xvenue-cot-cboe-context-handoff.md`.

## Questions for human review

- Should Claude require exact CFTC holiday-release timestamps before any COT
  feature is allowed into a Stage-2 as-of join?

## Next recommended task

- Restore TimescaleDB, perform the documented backfills/manual snapshot, verify
  persisted counts and timestamps, then register only the current recurring
  feeds.

## Human Learning Notes (required)

The task's cheapest correct design was to reuse the external observation store
and keep replayable raw payloads, not add tables or dependencies. Holiday COT
reference dates and Cboe's discontinued PCR archive are source semantics that
must remain explicit. Public source success is not operational readiness until
the DB write and scheduler health are verified.

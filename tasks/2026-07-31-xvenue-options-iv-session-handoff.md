---
status: archived
type: handoff
owner: codex
created: 2026-07-31
last_reviewed: 2026-07-31
expires: none
superseded_by: tasks/2026-07-31-xvenue-cot-cboe-session-handoff.md
---

# Session Handoff: H-039 cross-venue options-IV Stage 0 - 2026-07-31

## Implementation summary

Implemented one shared public client for OKX, Bybit, and Deribit; wired six
BTC/ETH hourly datasets into existing external ingestion; added a snapshot
command, Windows wrapper, post-write gap alert, tests, and the required
hypothesis/operations/governance records. Public normalization and free-sample
schema calibration pass. DB persistence and scheduling remain intentionally
inactive because local TimescaleDB/Docker is offline.

## Diff scope

- Files added:
  `src/okx_quant/data/external_clients/xvenue_option_surface.py`,
  `scripts/market_data/snapshot_xvenue_options.py`,
  `scripts/market_data/run_xvenue_options_snapshot_task.cmd`,
  `tests/unit/test_xvenue_option_surface.py`, this handoff, and
  `tasks/2026-07-31-xvenue-options-iv-context-handoff.md`.
- Files changed: external-client exports, external-ingest wiring,
  `config/external_data.yaml`, `config/workstreams.yaml`, the H-039 spec,
  ledgers, invariant/failure-mode registries, feature/data/runbook maps, current
  state, AI handoff/changelog, and known issues.
- Files deleted: none.

## Business-rule change?

- No. Existing R6.2 as-of/provenance rules apply; no Change Manifest or ADR is
  required. `check_doc_impact.py` passed.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; research ownership was not touched.
- `config/`: six datasets plus one Progress workstream added.
- ADR: N/A; no schema, business-rule, or gate decision changed.

## Experiments

- HYPOTHESIS_LEDGER entries: H-039 updated to implemented/data-blocked.
- EXPERIMENT_REGISTRY entries: F-XVENUE-OPT-IV K-budget row only; no experiment
  ID, trial, or K consumption.

## Tests / checks run

- `python -m pytest tests/unit/test_xvenue_option_surface.py
  tests/unit/test_external_data.py -q` - 13 passed, one cache-permission warning.
- Targeted Ruff - passed.
- Config-only validation - passed.
- Doc metadata - passed with two unrelated pre-existing warnings.
- Feature-map links - passed.
- Ledger consistency - passed: 40 hypotheses, 77 experiments, 34 families.
- Advisory doc impact - passed.
- `git diff --check` - passed with line-ending warnings only.
- Public live smoke - six of six normalized rows passed.
- DB snapshot - connection refused before any write; Docker service unavailable.

## Docs updated

- `docs/superpowers/specs/2026-07-31-xvenue-options-iv-hypothesis.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, `docs/FEATURE_MAP.md`,
  `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`,
  `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, and
  `docs/CHANGELOG_AI.md`.

## Known limitations / risks

- No DB row counts or first/last timestamps exist yet; the 270-day accumulation
  clock has not started.
- Nearest-listed tenor and four selected raw legs implement the named H-039
  spec. The adjacent combined task's richer full-chain/two-expiry interpolation
  contract is not implemented and should be reconciled before activation.
- Upstream response schemas can change; I57/F60 locks the Bybit suffix class,
  while live smoke remains the activation check for other schema drift.

## Rollback plan

- Delete the four new implementation/test files and two handoffs, remove the
  six `xopt_iv_*` config blocks and H-039 ingest/export wiring, then revert only
  the H-039 paragraphs/rows added to the listed docs. No migration, stored row,
  scheduled task, result artifact, or deployment setting needs rollback.

## Context Handoff

- See `tasks/2026-07-31-xvenue-options-iv-context-handoff.md`.

## Questions for human review

- Should the named H-039 spec's nearest-listed/four-leg storage remain the
  activation contract, or should Claude revise it to the adjacent combined
  task's full-chain and two-expiry total-variance interpolation contract?

## Next recommended task

- Start TimescaleDB, obtain one successful six-row manual snapshot, then let the
  user register and verify the hourly task from `docs/RUNBOOK.md`.

## Human Learning Notes (required)

The only live schema defect found was Bybit's settlement suffix after call/put;
the shared parser fix is smaller and safer than venue-call-site guards. Public
API success alone is not persistence evidence, and the collector must remain
data-blocked until a DB row and healthy scheduled run are verified.

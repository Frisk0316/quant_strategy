---
status: current
type: handoff
owner: codex
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Session Handoff: F-VOL-REGIME-OPT Stage 2 / E-040 — 2026-07-13

## Implementation summary

Implemented a stdlib-only Stage-2 Tardis calibration probe with deterministic
IVP-extreme sampling, coherent nearest-08:00 as-of snapshots, nearest-30d leg
matching, actual-strike BS-on-DVOL comparison, aggregations, verdict logic, and
fail-closed artifacts. The official run processed 7 day×symbol pairs and then
failed closed on a 3.05 GB daily gzip exceeding the fixed 2 GiB limit, so the
verdict is not evaluated. Completed the Tardis/Amberdata/Laevitas report without
creating credentials or purchasing data.

## Diff scope

- Files added: `research/probes/f_vol_regime_opt_stage2.py`;
  `tests/unit/test_f_vol_regime_opt_stage2.py`;
  `results/stage2_probe_20260713_f_vol_regime_opt/{stage2_feasibility.json,per_day_legs.csv,chain_data_options.md}`;
  this handoff and the paired context handoff.
- Files changed: `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`.
- Files deleted: none.
- Pre-existing, untouched changes remain in `config/workstreams.yaml`,
  `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/CURRENT_STATE.md`, and
  Claude's Stage-1 spec/task/handoff files.

## Business-rule change?

- No. This is a research probe and fail-closed data-acquisition record. Per the
  approved task, no Change Manifest or ADR was created.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; not modified.
- `config/`: N/A; not modified.
- ADR: N/A.

## Experiments

- HYPOTHESIS_LEDGER entries: H-014 linked to E-040 and remains `proposed` /
  Stage-3-blocked.
- EXPERIMENT_REGISTRY entries: E-040, 0 trials, 0 K, fail-closed size limit;
  F-VOL-REGIME-OPT K-budget wording updated without changing 0/2.

## Tests / checks run

- Target unit: 1 passed.
- Ruff on new Python files: passed.
- Docs metadata: passed, 0 warnings.
- Feature-map links: passed, 214 concrete paths.
- Ledger consistency: passed, 15 H / 40 E / 14 K families.
- Artifact QA: passed for 35 rows; required leg fields populated and no quote
  local timestamp exceeds its snapshot.
- Formal network command: exited fail-closed after the 2 GiB size guard; exact
  command and error are in `stage2_feasibility.json`.

## Docs updated

- `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, and both required handoffs.
- `docs/RUNBOOK.md` was reviewed but not changed: E-040 is a one-off experiment,
  and its reproducible command is recorded in the artifact/registry/handoff.
- `docs/AI_HANDOFF.md` / `docs/CURRENT_STATE.md` were not changed because they
  carry another session's uncommitted PR #9 edits; this handoff preserves state
  without overwriting them.

## Known limitations / risks

- Only BTC=3 and ETH=4 pairs completed; the required six per symbol did not.
- `verdict.status=FAIL` means fail-closed, with `evaluated=false`; it is not a
  pricing rejection. Partial Q1/Q4 aggregates are diagnostic only.
- Result and research-probe paths are ignored by the current `.gitignore`; the
  files exist locally but require explicit force-add during an authorized commit.
- No full-history vendor offer was purchased or license-negotiated.

## Rollback plan

- Delete the new probe, unit test, Stage-2 result directory, and two handoffs;
  remove only the E-040 row/H-014 link and the E-040 paragraphs in FEATURE_MAP
  and DATA_FLOW. Do not revert Claude's E-039/H-014 additions or unrelated edits.

## Context Handoff

- See `tasks/2026-07-13-f-vol-regime-opt-stage2-codex-context-handoff.md`.

## Questions for human review

- Should the user authorize a larger local per-day limit, a one-off Tardis
  purchase quote, or neither? No retry should run before that decision.

## Next recommended task

- Claude review of E-040 under `docs/REVIEW_QUESTIONS.md` /
  `docs/CRITIQUE_PROTOCOL.md`; do not draft or start Stage 3 because Stage 2 did
  not PASS.

## Human Learning Notes (required)

The existing free monthly chain files can produce valid 08:00 snapshots, but
their size varies enough that a reproducible resource ceiling is part of data
quality, not just operations. A partial sample can look encouraging while still
being selection-biased; `evaluated=false` is the key result of this session.

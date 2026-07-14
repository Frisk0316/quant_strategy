---
status: current
type: handoff
owner: codex
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Session Handoff: F-VOL-REGIME-OPT Stage 2 / E-041 — 2026-07-13

## Implementation summary

Completed the authorized E-041 bounded rerun by applying only its three review
fixes to the existing stdlib probe: bytes-read size enforcement, DB hourly-DVOL
as-of pricing, and split probe/pricing statuses. The official run failed closed
before Tardis acquisition because the fixed sample begins in 2022 while the DB
hourly datasets begin in 2024. T1's E-040 artifacts and T2's vendor report remain
untouched; Stage 2 has no evaluated pricing verdict.

## Diff scope

- Files added: `results/stage2_probe_20260713_f_vol_regime_opt_r1/{stage2_feasibility.json,per_day_legs.csv}`;
  this handoff and the paired E-041 context handoff.
- Files changed for E-041: `research/probes/f_vol_regime_opt_stage2.py`,
  `tests/unit/test_f_vol_regime_opt_stage2.py`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`, and
  `config/workstreams.yaml`.
- Files deleted: none. Pre-existing Stage-1/E-040 and PR #9 follow-up working-tree
  changes were preserved.

## Business-rule change?

- No. This is A11 experiment/data-provenance evidence, not a rule, engine,
  schema, or gate change. The task explicitly excludes Change Manifest/ADR work.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; not modified.
- `config/`: progress text only; no runtime, risk, strategy, or gate value changed.
- ADR: N/A.

## Experiments

- HYPOTHESIS_LEDGER: H-014 links E-041 and remains `proposed`/Stage-3-blocked.
- EXPERIMENT_REGISTRY: E-041 registered as 0 trials, no K, fail-closed hourly
  coverage; E-040 row remains immutable.

## Tests / checks run

- Target unit: `3 passed`; Ruff on probe/test: passed.
- Formal E-041 command: expected fail-closed artifact at 0 pairs.
- Docs metadata, feature-map links, ledger consistency, docs impact: passed.
- Config validation: passed; Progress route regressions: `9 passed`.
- Artifact QA: identical E-040 sampling, exactly three declared behavior deltas,
  correct split fail-closed schema, and no E-040 artifact write.

## Docs updated

- Ledgers, Feature Map, Data Flow, AI handoff/current state, AI changelog,
  Progress mirror, and both required E-041 handoffs.

## Known limitations / risks

- No sampled real-vs-synthetic pricing ratio was produced; Stage 2 is not PASS.
- The DB hourly-DVOL start date blocks two fixed 2022/2023 sample dates per
  symbol before Tardis acquisition. Daily DVOL is deliberately not used.
- `research/probes/` and `results/` are gitignored and require explicit force-add
  during an authorized commit.

## Rollback plan

- Remove the new `_r1` result directory and E-041 handoffs; revert only the
  E-041 additions/status wording in the probe, test, ledgers, maps, state docs,
  changelog, and workstream. Do not alter E-039/E-040 files.

## Context Handoff

- See `tasks/2026-07-13-f-vol-regime-opt-stage2-e041-codex-context-handoff.md`.

## Questions for human review

- After Claude review, should a new task authorize pre-2024 hourly-DVOL
  backfill? No further retry is implied by this question.

## Next recommended task

- Claude review of E-041 under I13/F26. If accepted, wait for the human's data
  backfill decision; do not start Stage 3.

## Human Learning Notes (required)

Hourly and daily DVOL have different historical windows in the same DB. A
dataset described only as “present through date X” is insufficient for a fixed
historical sample; both min and max timestamps must be checked before acquisition.

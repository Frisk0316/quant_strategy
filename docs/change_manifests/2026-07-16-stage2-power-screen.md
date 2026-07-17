---
status: current
type: manifest
owner: codex
created: 2026-07-16
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Change Manifest: Stage-2 Statistical-Power Triage

## Summary

Add a deterministic Stage-2 statistical-power check that fails weak or
underpowered candidates before Stage 3, plus a ledger-derived funnel projection.
This is advisory research triage; it is not a deployment or promotion gate.

## Design-space expansion

**Problem:** Weak-breadth candidates can currently spend Stage-3 compute and K
before failing for a power limitation that is predictable from registered
inputs.

**Constraints:** Do not change PnL, Stage-3 grids or gates, live/shadow/demo
behavior, existing result artifacts, or ledger-owned Markdown; preserve legacy
artifact readability and use the family registry as trial-count authority.

- **Option A — no change:** Keep detecting power failures after Stage 3. Lowest
  blast radius, but continues predictable compute/K waste.
- **Option B — new promotion gate/service:** Centralize power and funnel state in
  a new backend contract. More current, but changes gate/API semantics and adds
  a second status store.
- **Option C — registry triage + derived projection:** Add one fail-fast check to
  registry-written Stage-2 artifacts and derive a static funnel from existing
  results and ledgers. Assumes the registry flow is the authoritative new-writer
  path; legacy artifacts remain readable.

**Axis:** operational freshness and coverage versus simplicity, reversibility,
and gate blast radius.

**Decision:** Option C, because it prevents predictable Stage-3 work while
keeping ledgers authoritative and avoiding a new backend or deployment gate.

**Follow-up implemented 2026-07-17:** the orchestrator now accepts an explicit
candidate-keyed power-input object. Missing inputs are caller errors before a
probe/artifact/status change; no research values are inferred.

## Business rule(s) affected

- R6.3: family-cumulative trial provenance is mandatory for Stage-2 power triage.
- R7.4: the screen inverts the current PSR/DSR definition without changing its
  thresholds or the Stage-3 gate.

## Trigger area(s) (DOC_IMPACT_MATRIX)

- A5 backtesting/research pipeline automation.
- A9 validation/gate tooling and `n_trials` provenance.

## Files changed

Task A's exclusive file list omitted the evaluator that owns serialized
`stage2_status`. The implementation therefore makes one minimal owning-file
expansion in `pipeline_feasibility.py`; otherwise a failing fourth check would
still serialize/validate as PASS. Repository-mandated manifest/ADR/state/handoff
files are also outside the task-local list.

- `backtesting/pipeline_power_screen.py` — closed-form PSR/DSR inversion.
- `backtesting/pipeline_stage2_registry.py` — registry-scoped fourth check,
  fail-closed input handling, override audit details, and trial provenance.
- `backtesting/pipeline_feasibility.py` — a present failing power check makes the
  serialized Stage-2 status fail while immutable legacy three-check artifacts
  remain readable.
- `scripts/run_pipeline_funnel_report.py` — result/ledger/registry projection.
- `tests/unit/test_pipeline_power_screen.py` — independent inversion cases.
- `tests/unit/test_pipeline_stage2_registry.py` — artifact, provenance, breadth,
  override, and fail-closed behavior.
- `tests/unit/test_pipeline_funnel_report.py` — funnel schema, filtering, metrics,
  and K accounting.
- `docs/superpowers/pipeline/stage2-feasibility.md` — fourth-check contract.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md` — R6.3/I23 enforcement.
- `docs/ADR/0013-stage2-statistical-power-triage.md` — durable A9 decision.
- `docs/DATA_FLOW.md` — derived funnel artifact path and authority boundary.

Follow-up caller files are `backtesting/pipeline_orchestrator.py`,
`scripts/run_pipeline_orchestrator.py`, and
`scripts/market_data/backfill_universe_funding.py`. The funnel now isolates
malformed artifacts under schema-v3 `stage2_artifact_errors`.

## Behavior delta

- Before: the registered Stage-2 writer assessed data, distinctness, and
  cost-after-edge only; predictable low-power candidates could proceed.
- After: new registry-written artifacts contain `statistical_power`; active
  callers reject missing values before writing candidate evidence, invalid
  computed inputs fail closed, and only a written ex-ante rationale can override
  triage. The report treats legacy missing-power artifacts as not power-feasible
  and isolates malformed files under schema-v3 `stage2_artifact_errors`.
- Money/risk impact: none. No PnL, fee, funding, sizing, fill, risk, Stage-3,
  promotion, demo, shadow, or live rule changes.

## Source-of-truth updates

- `research/strategy_synthesis.md`: unchanged; its validation convention remains
  the formula source and research files are read-only for this task.
- `config/`: no threshold or trading configuration changed.
- ADR: `ADR-0013` accepted. DOC_IMPACT A9 requires the decision record even
  though this is reversible advisory triage and not a promotion policy.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — R6.3 registry-trial provenance made explicit.
- [x] `docs/INVARIANTS.md` — I23 enforcement extended to the power screen.
- [x] `docs/ai_collaboration.md` — confirmed unchanged; promotion gates unchanged.
- [x] `docs/ADR/0013-stage2-statistical-power-triage.md` — decision and limits recorded.
- [x] `docs/DATA_FLOW.md` — optional derived JSON flow recorded.
- [x] `docs/EXPERIMENT_REGISTRY.md` — confirmed read-only; consumed as authority.

## Invariants / golden cases

- Invariants checked: I13, I23, I29.
- Golden cases affected: none; the screen is deterministic planning triage and
  does not alter backtest accounting.

## Tests / checks run

- Targeted and harness checks are recorded in the associated session handoff.

## Risks and rollback

- Risks: independent-bet breadth can be overstated; legacy immutable artifacts
  still lack the fourth check. The ratified `1.7206` reference value applies only
  to its recorded inputs and must not be copied as a universal constant.
- Rollback: revert the three power-related backtesting files, funnel script and
  tests, then revert the documentation updates. No stored artifacts need
  migration or deletion.

Claude's 2026-07-17 approve-with-fixes review independently reproduced the
`1.7206` reference case and five-line evaluator scope expansion; the user then
ratified both and authorized the caller/funnel repair.

## Approval

- Human approval required: yes; obtained through the user's explicit Task A
  request on 2026-07-16. This approval is limited to research triage and does not
  approve promotion or live/demo/shadow deployment.

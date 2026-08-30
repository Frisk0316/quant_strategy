---
status: current
type: task
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# H-047/E-096 Stage-2 first cell — build runner and execute (Codex)

Authority: user I27 ruling 2026-08-07 minting F-XS-REVERSAL-MW from the
admitted S-001 packet; spec
`docs/superpowers/specs/2026-08-07-f-xs-reversal-mw-hypothesis.md` (the
frozen cell, gates, and required artifact contents are THERE — this file
adds only mechanics). Read also: H-047 ledger row, E-096 registry row,
E-075 as the closest structural precedent
(`results/slate_stage2_20260729/f_variance_decomp/`).

## T1 — Deterministic Stage-2 probe

Implement the F-XS-REVERSAL-MW probe registered in
`backtesting/pipeline_stage2_registry.py::STAGE2_PROBES` following the
slate-probe pattern (async, `(conn, Stage2Context) -> FeasibilityResult`,
four checks). Signal, book, costs, window: exactly the spec's frozen cell.
The two mint-apart reconstructions (H-002 momentum params, H-038
residual-z) are deterministic re-computations from canonical data per
their registered specs — no result artifacts consumed, no new evaluation
semantics invented.

## T2 — Execute E-096 once against the real DB

Run the single frozen cell. Write the immutable SHA-bound artifact under
`results/<batch_id>/f_xs_reversal_mw/` including EVERY item in the spec's
"Required artifact contents" — the dated daily L/S return series and the
daily position matrix are mandatory, not optional. Then update the H-047
ledger row, E-096 registry row (planned → outcome), and the family K-budget
note with the measured numbers, honestly, whatever they are.

## T3 — (only if all four checks PASS) round-runner registration prep

Do NOT register in `REVIEWED_ROUND_RUNNERS` (that entry is added by Claude
review per phase-3 contract). Instead report the exact mapping line that
would be added.

Stop rules (restated from the spec, binding): any check FAIL → stop, no
grid, no retune, no sign flip, zero trials consumed, K untouched, no
Stage 3. Mint-apart breach ⇒ report for I27 ASSIGN; do not self-assign.

PERMITTED: `backtesting/pipeline_stage2_registry.py` (additive probe +
registration only), new probe module beside it if cleaner, targeted tests,
`scripts/` runner entry if the slate pattern needs one, `results/<new>/`
artifact dir, `docs/HYPOTHESIS_LEDGER.md` (H-047 row), 
`docs/EXPERIMENT_REGISTRY.md` (E-096 row + F-XS-REVERSAL-MW K note),
`docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`.
FORBIDDEN: `src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
`config/risk.yaml`, `research/`, existing `results/**`, any other ledger
row, any evaluator/power-screen/probe-contract change,
`backtesting/pipeline_round_runners.py` registries.

ACCEPTANCE (binary):
- [ ] Probe registered; targeted tests green (synthetic fixture: known
      positions → known breadth; corr gates fire on a planted correlated
      signal); Ruff clean; ledger consistency + doc-impact advisory pass.
- [ ] E-096 artifact exists, SHA-recorded, containing the four checks, both
      mint-apart correlations with common-day counts, derived breadth +
      n_obs, dated return series, and position matrix.
- [ ] Ledger/registry/K rows updated to the measured outcome; no other row
      touched; diff only in permitted files.
- [ ] Report states plainly which checks passed/failed, the derived
      breadth, both correlations, and that no grid/trial/K/Stage-3/
      promotion occurred.

REPORT: standard AGENTS.md block.

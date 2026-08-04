---
status: current
type: task
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Unblock H-024..H-027 probe: regenerate a dated E-025 distinctness reference

Context: `4c84a18` registered the four candidates + shared probe + fail-closed
I49 pre-flight (correct behavior). The whole-batch pre-flight stopped before DB
access because the ONLY E-025/F-PAIRS-OU artifact
(`results/pipeline_batch2_20260625/c1_pairs_ou/summary.json`) has **no dated
daily return series** (CPCV path_returns were not persisted), so H-027's
mandatory distinctness correlation cannot be computed. H-024/H-025/H-026
references are all present and dated (E-044, E-050, F-VOL-REGIME-OPT — verified
by Claude). This task provides the missing reference, then runs the probe.

Governing decision (Claude, planner): regenerating a dated daily return series
for the E-025 pairs-OU strategy at its already-selected params is a
**reference-series regeneration for distinctness, NOT a hypothesis retry**. It
does not reopen H-006/F-PAIRS-OU (refuted), consumes **no K**, adds **no
family trial**, and writes **no EXPERIMENT_REGISTRY row**. F-PAIRS-OU stays
refuted with K 0/2.

## R1 — Regenerate the dated E-025 reference (reference-only)

Reuse the SAME C1 pairs-OU runner that produced
`results/pipeline_batch2_20260625/c1_pairs_ou/summary.json` (do not
reimplement the strategy). Re-run it at E-025's frozen selected params, exactly:
`{bar: 1m, symbol_x: BTC-USDT-SWAP, symbol_y: ETH-USDT-SWAP,
lookback_days: 14, max_half_life_days: 3.0, max_hold_days: 14, z_enter: 2.5,
z_exit: 0.0, fee_bps: 2.0, slippage_bps: 2.0}`, over the E-025 window
`start=2024-01-01T00:00:00Z, end_exclusive=2026-06-17T00:00:00Z`,
`primary_exchange=binance`.

Persist a **dated** daily return series to
`results/pipeline_batch2_20260625/c1_pairs_ou/combo_daily_returns.csv`
with a `day` column (UTC date) + one return column for the selected param
combo (match the CSV shape the distinctness loader expects — same as
`results/h013_vrp_timing_20260714/combo_daily_returns.csv`).

Reproduction honesty:
- Record in a sibling `reference_regen_notes.md` how the regenerated series
  compares to E-025's recorded `full_sample_best_sharpe` /
  `cpcv_oos_sharpe = -0.9097`. If data drift since 2026-06-25 makes it
  non-identical, state that plainly — a faithful dated series of the same
  mechanism/params is the deliverable, not byte-identity with E-025.
- Do NOT modify `summary.json` or any existing artifact.

Acceptance (binary):
- [ ] `combo_daily_returns.csv` exists with ≥365 dated rows in the window.
- [ ] No EXPERIMENT_REGISTRY row, no HYPOTHESIS_LEDGER status change, no
      K-budget change for F-PAIRS-OU (grep-clean).
- [ ] `reference_regen_notes.md` records the reproduction basis vs E-025.

## R2 — Run the probe per the original task

With R1 in place, execute
`tasks/2026-07-28-moneyness-vol-probe-codex-tasks.md` unchanged: whole-batch
I49 pre-flight now passes (H-027's E-025 reference is dated), then run all four
candidates in the frozen order H-024 → H-025 → H-027 → H-026, writing one
EXPERIMENT_REGISTRY entry + ledger update per executed candidate, artifacts
under `results/moneyness_vol_probe_20260728/`. All the original task's
contract, frozen grids, gates, stop-rules, and acceptance criteria apply
verbatim.

If the regenerated E-025 series still yields <365 common days with H-027's
formal window, STOP and report to Claude (do not lower the threshold).

## PERMITTED FILES

- `results/pipeline_batch2_20260625/c1_pairs_ou/combo_daily_returns.csv` (new),
  `results/pipeline_batch2_20260625/c1_pairs_ou/reference_regen_notes.md` (new)
- everything in the original probe task's PERMITTED list

## FORBIDDEN

- Editing `results/pipeline_batch2_20260625/c1_pairs_ou/summary.json` or any
  other existing artifact
- Any F-PAIRS-OU ledger/K/trial change (this is reference-only)
- Everything in the original probe task's FORBIDDEN list

REPORT: R1 reproduction note + the original task's per-candidate verdict table.
Questions to Claude instead of silent deviation.

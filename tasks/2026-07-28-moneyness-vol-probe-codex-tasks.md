---
status: current
type: task
owner: claude
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# H-024..H-027 Deribit moneyness/vol limited probe — Codex tasks

Spec (read first, it is the contract):
`docs/superpowers/specs/2026-07-28-deribit-moneyness-vol-probe-hypotheses.md`
— user-authorized 2026-07-28 including H-026 as F-VRP-TIMING K retry 1/2.
Execution order: **H-024 → H-025 → H-027 → H-026** (H-026 last: it consumes
scarce K budget only if it reaches Stage 3).

Pattern precedent: `backtesting/taker_flow_probe.py` +
`backtesting/pipeline_stage2_registry.py` (E-058/E-059 shape). Reuse
`min_detectable_sharpe` (`backtesting/pipeline_power_screen.py`),
`load_reference_series`/`abs_correlation` (xvenue_leadlag_probe), and the
FeasibilityResult artifact schema. Windows: no `make`.

## Global contract (all four candidates)

- Stage-2 four checks per candidate: data / distinctness / cost / power.
  ANY fail → stop that candidate, write the artifact, register the honest
  outcome, NO retune, proceed to the next candidate.
- **I49 pre-flight (before any probe runs):** for every distinctness
  reference below, verify ≥365 common days exist between the candidate's
  formal window and the reference series. Structural impossibility is a
  contract error refused up front, never a "distinctness fail".
- Power convention: time-series books, breadth = 2.0 (BTC+ETH), n_obs =
  formal-window days (post-warmup), periods_per_year = 365, prospective
  n_trials = 4 per candidate — EXCEPT H-026: family-cumulative n_trials = 8
  (E-050's 4 + this grid's 4).
- Cost convention: 8 bps round-trip on turnover, daily rebalance, same
  net-proxy construction as the H-013/E-050 and E-058 probes.
- Data: hourly `external_observations` via the existing store/query patterns;
  optflow bucket fields exist from 2024-01-01, and the newest ~1 day may lack
  bucket fields (archive lag) — the formal window must end at the last day
  with complete fields, recorded in the artifact.
- Stage 3 (fold-refit WF/CPCV, 4-cell grid below, frozen here ex-ante) runs
  ONLY on a four-check PASS, via the registered stage3 path with
  family-cumulative n_trials and retained CPCV path returns. H-026's Stage-3
  run consumes F-VRP-TIMING K → 1/2 (record in the K-budget table); Stage-2
  fails consume nothing.
- Every executed candidate gets one EXPERIMENT_REGISTRY entry (next free
  E-numbers, sequential) + HYPOTHESIS_LEDGER status/resolution update +
  K-budget row update where applicable. Artifacts under
  `results/moneyness_vol_probe_20260728/<candidate_dir>/` with SHA-256s in
  the registry rows.

## Frozen signals and grids (ex-ante; do not tune)

| Cand. | Signal (daily, 08:00 UTC day, BTC+ETH) | Stage-3 grid (4 cells) |
|---|---|---|
| H-024 F-OPT-HEDGE-DEMAND | flat when z90(`otm_put_buy_amt` share of `premium_volume`, trailing L) ≥ z_cut, else long; vol-targeted | z_cut ∈ {1.0, 1.5} × L ∈ {24h, 72h} |
| H-025 F-OPT-MONEYNESS-STRUCTURE | flat when z90(OTM share of atm+itm+otm premium, trailing L) ≥ z_cut, else long | z_cut ∈ {1.0, 1.5} × L ∈ {24h, 72h} |
| H-027 F-XVOL-RATIO | long ETH/short BTC when z(ETH/BTC DVOL ratio, window W) ≤ −z_cut, mirror at ≥ +z_cut, flat in band; dollar-neutral | z_cut ∈ {1.5, 2.0} × W ∈ {90d, 180d} |
| H-026 F-VRP-TIMING retry 1 | long when z90(DVOL−RV30) ≥ z_cut AND RV30 < rolling median(W); flat otherwise | z_cut ∈ {1.0, 1.5} × W ∈ {90d, 180d} |

Stage-2 uses each candidate's first grid cell as the probe proxy (declare it
in the artifact), same convention as prior probes.

## Distinctness references (gating, |corr| < 0.30, ≥365 common days)

- H-024: E-044 series
  `results/idea_batch_20260713_taxonomy_003/f_optflow_positioning/combo_daily_returns.csv`
  (MANDATORY — the spec's kill criterion) + F-VOL-REGIME-OPT
  `results/h014_stage3_20260714/combo_daily_returns.csv`.
- H-025: H-024's candidate signal (mint-apart check: |corr| ≥ 0.30 → same
  family, H-025 ASSIGNs to F-OPT-HEDGE-DEMAND and stops as a duplicate) +
  E-044 + F-VOL-REGIME-OPT.
- H-027: E-025 F-PAIRS-OU return series (LOCATE the artifact under results/
  pipeline batch-2 dirs; if none exists with ≥365 common days, that is an
  I49 contract stop reported to Claude, not a probe fail) + F-VOL-REGIME-OPT.
- H-026: F-VOL-REGIME-OPT (MANDATORY — both condition on vol regime) +
  E-050 series `results/h013_vrp_timing_20260714/combo_daily_returns.csv`
  (same family: report the corr, non-gating, labeled advisory).

## Steps

1. **Registration commit:** four CandidateSpec entries + STAGE2_PROBES
   wiring in `backtesting/pipeline_stage2_registry.py`; probe modules
   `backtesting/moneyness_vol_probe.py` (shared helpers OK, one probe fn per
   candidate). Unit tests for feature extraction (bucket-share, DVOL ratio,
   VRP-regime series from fixture rows) and for the I49 pre-flight refusal.
2. **Run commits (one per candidate, in order):** execute Stage 2; on PASS
   run the frozen Stage-3 grid; write artifacts; update
   EXPERIMENT_REGISTRY.md + HYPOTHESIS_LEDGER.md (+ K-budget for H-026's
   Stage-3 only) in the same commit as its run.
3. **Wrap-up commit:** `python scripts/docs/check_doc_impact.py` (advisory) +
   ledger consistency + AI_HANDOFF/workstreams one-line sync.

## PERMITTED FILES

- `backtesting/moneyness_vol_probe.py` (new), `backtesting/pipeline_stage2_registry.py`,
  `backtesting/pipeline_stage3_registry.py` (registration only, if Stage 3 runs)
- `tests/unit/test_moneyness_vol_probe.py` (new)
- `results/moneyness_vol_probe_20260728/**` (new artifacts only)
- `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`

## FORBIDDEN

- `src/okx_quant/**` (all of it — probes live in backtesting/), `config/*.yaml`
  except workstreams, existing `results/**` artifacts, `research/**`
- Any signal/threshold change after seeing results (no retune, hard rule)
- Stage 3 for any candidate whose Stage 2 did not four-check PASS

ACCEPTANCE CRITERIA (binary):
- [ ] I49 pre-flight ran for all references before any probe; refusals (if
      any) reported, not recorded as distinctness fails.
- [ ] Four candidates each have: artifact with four named checks, registry
      entry with SHA-256, ledger status update. Order respected.
- [ ] H-025 mint-apart check vs H-024 executed and recorded.
- [ ] H-026 used family-cumulative n_trials=8; K updated only if its Stage-3
      grid ran.
- [ ] `python -m pytest tests/unit/test_moneyness_vol_probe.py -v` green;
      ledger consistency check passes; diff only in permitted files.

REPORT: standard AGENTS.md completion block + per-candidate verdict table
(check-by-check PASS/FAIL + headline numbers). Questions to Claude instead of
silent deviations.

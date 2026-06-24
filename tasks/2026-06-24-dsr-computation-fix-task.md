# Codex Task — Fix DSR computation in the CPCV validation harness

Plan source: `tasks/2026-06-24-xs-momentum-phase-c-review.md` (Re-review §).
Severity: validation-harness defect affecting **every** strategy that reports CPCV
DSR — not just XS momentum.

## Diagnosis
`results/xs_momentum_validation_20260624_leakfix/cpcv.json` reports `dsr:1.0`
alongside `psr:0.7961`. That is mathematically impossible: DSR deflates the Sharpe
benchmark *upward* for multiple trials, so it must be **< PSR(0)**.

Root cause — unit mismatch in `backtesting/cpcv.py:293-298` (the `path_returns_list`
branch):

- `deflated_sharpe(returns=combined_returns, sr=overall_sr, sr_list=path_sharpes, N=...)`.
- `overall_sr = np.mean(path_sharpes)` is an **annualized** (periods-scaled),
  mean-of-paths Sharpe.
- But `deflated_sharpe` (`src/okx_quant/analytics/dsr.py:68`) builds the z-stat
  `(sr - SR0) * sqrt(T-1) / denom`, which requires `sr` to be the
  **per-observation** Sharpe of the `returns` array. `T = len(combined_returns)` is
  thousands of per-bar observations, so `sqrt(T-1)` × an annualized SR saturates
  `norm.cdf(...)` → 1.0.
- Compounding bug: `combined_returns` concatenates the 5 CPCV paths, which **overlap
  in time** (each path covers the full timeline), so `T` is inflated ~5× and the
  observations are non-independent.

PSR stays sane because `psr()` (`dsr.py:91`) recomputes `sr_hat = mean/std` from the
series internally, keeping units consistent.

## PERMITTED FILES (only edit these)
- `src/okx_quant/analytics/dsr.py`
- `backtesting/cpcv.py`
- `tests/unit/` — add/extend DSR/PSR unit tests (new file ok, e.g. `test_dsr.py`)
- `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` — record the invariant + bug class
- `docs/change_manifests/` — new manifest (DSR is a gate/validation rule)
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` — state update on completion

## FORBIDDEN (do not touch)
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`
- any existing result artifact (regenerate into a new path if a rerun is needed)
- deployment/shadow/demo/live gate config

## SCOPE LIMIT
Fix the DSR unit/series mismatch only. Do not change PSR semantics, the leak fix,
or strategy logic. No refactor beyond what the fix requires.

## Required behavior
1. `deflated_sharpe` must be evaluated on a consistent basis: the `sr` it uses for
   the z-stat must be the per-observation Sharpe of the exact `returns` series whose
   length feeds `sqrt(T-1)` (mirror `psr()`'s internal `sr_hat`), and the deflation
   benchmark `SR0` (from `sr_list`/`N`) must be in the same units.
2. Do not feed overlapping/duplicated CPCV paths as if they were one independent
   series of length `T`. Use a single non-overlapping OOS series (or the correct
   effective sample size) for the `sqrt(T-1)` term.
3. `N` must be the honest researched trial count, not `len(path_sharpes)`. Plumb the
   real `n_trials` through and reconcile the `n_trials` vs `n_combinations` fields
   so the artifact is self-consistent.
4. Add a hard sanity invariant: **DSR ≤ PSR(0)** for the same series; assert it in a
   unit test with a known-Sharpe synthetic series, and have the harness flag/refuse
   to emit a DSR that violates it.

## REQUIRED ON COMPLETION
- List changed files.
- Run: `pytest tests/unit/test_dsr.py tests/unit/test_cpcv*.py -v` (and any existing
  DSR/CPCV tests) and `python scripts/docs/check_doc_impact.py`.
- Update the Change Manifest + INVARIANTS/FAILURE_MODES + handoff docs.
- Commit with `AI-Origin: Codex` trailer.

## ACCEPTANCE CRITERIA
- [ ] On a synthetic series, computed DSR `< PSR(0)` whenever `N > 1` (unit test).
- [ ] DSR no longer saturates to 1.0 for modest annualized Sharpe over long series.
- [ ] `n_trials` is honest and consistent with `n_combinations`/`sharpe_list`.
- [ ] Existing CPCV/DSR tests pass; `check_doc_impact.py` passes.
- [ ] No strategy/result-artifact/gate changes; invariant added to `INVARIANTS.md`.

## Hand back to Claude
Re-review the corrected DSR on the XS momentum leak-free series. Expectation: with a
fixed basis and honest `N`, DSR drops well below PSR=0.7961 — i.e. the prior
`dsr:1.0` was never a pass for any strategy.

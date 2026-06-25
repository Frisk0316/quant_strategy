# Codex Task B — Implement + two-pass backtest pipeline batch 1 (S5, S6, S7)

Pipeline: Strategy Research Pipeline batch 1. Stage 3 for all three candidates.
Driver: `docs/superpowers/pipeline/driver.md`;
Stage 3 template: `docs/superpowers/pipeline/stage3-implement-backtest.md`.

Spec sources (one per candidate — implement to these, do not drift):
- S7: `docs/superpowers/specs/2026-06-25-s7-basis-meanrev-hypothesis.md` (gated on Task A)
- S5: `docs/superpowers/specs/2026-06-25-s5-residual-meanrev-hypothesis.md`
- S6: `docs/superpowers/specs/2026-06-25-s6-ts-momentum-hypothesis.md`

## Sequencing
- **S5 and S6 can start now** (perp universe + funding data already in DB).
- **S7 is blocked on Task A** (spot canonical candles). Do S7 only after Task A
  reports spot coverage.

## Required behavior (per candidate)

1. New strategy module under `src/okx_quant/strategies/` + a research backtest
   runner under `backtesting/` (mirror `backtesting/xs_momentum_backtest.py`),
   `enabled: false`, `on_market()` no-op (research-tier, like xs_momentum).
2. **Leak regression test** (mandatory) proving signal at bar t uses only data ≤ t
   and trades at t+1 (analogue of
   `test_daily_close_target_is_not_traded_on_same_day`).
3. **Honest n_trials:** scan passes `prior_family_n_trials` into CPCV (I23). All
   three are **new families, prior = 0**: CPCV `n_trials` = S7:72, S5:72, S6:48.
4. Declare a `backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS`
   entry for each (status `adapter_required` if no portable adapter yet).
5. ct_val provenance attached; **no idealized-fill** as evidence.
6. **Two-pass backtest:** Pass A parquet research-tier coarse-grid WF (pre-screen,
   trials count toward family) → Pass B DB venue-scoped CPCV
   (N=6/k=2/embargo=2%/purge=1) on survivors with the family n_trials above.
7. Emit gate evidence to `results/<batch_id>/<candidate>/summary.json` with the
   Stage 3 schema (candidate_id, family_id, batch_id, grid_size_this_run,
   family_cumulative_n_trials, wf_oos_sharpe, cpcv_oos_sharpe, dsr, psr,
   leak_test_passed, portable_validation_gate, idealized_fill,
   ct_val_all_authoritative, promotion_gate_passed, status).
8. Reconcile the run-time trial counts into `docs/EXPERIMENT_REGISTRY.md`
   (supersede the planned E-006/E-007/E-008 rows with run-time rows).
9. **STOP at checkpoint ①** — do not write a shortlist, do not enable any strategy,
   do not claim promotion. Claude reviews the evidence next.

## Candidate-specific constraints
- **S5 must be residual MEAN-REVERSION, not momentum.** Residual momentum is a
  retry of `F-XS-MOMENTUM` (prior ≥ 24), not a new family. Reuse the point-in-time
  universe membership (survivorship guard, I20). Highest overfit risk — **do not
  tune past K=2**.
- **S6:** record realized return correlation vs `ohlcv_rotation` in the evidence
  notes (diversification check; not a gate).
- **S7:** bidirectional basis entry; funding charged R3.1 over the actual hold.

## PERMITTED FILES (only edit these)
- `src/okx_quant/strategies/` (new s5/s6/s7 modules, `enabled:false`)
- `backtesting/` (new per-candidate runners; reuse `walk_forward.py`, `cpcv.py`)
- `tests/unit/` (leak + n_trials regression tests)
- `config/strategies.yaml` (add `enabled:false` blocks), `config/universe.yaml` (S5 reuse)
- `backtesting/differential_validation.py` (REFERENCE_VALIDATION_CONTRACTS entries only)
- `results/<batch_id>/**` (new evidence artifacts)
- `docs/EXPERIMENT_REGISTRY.md` (supersede planned rows with run-time rows)

## FORBIDDEN (do not touch)
- `config/risk.yaml`, any demo/shadow/live/deployment gate
- `backtesting/cpcv.py` / `analytics/dsr.py` n_trials/DSR **semantics** (pass values, don't change)
- existing result artifacts' values; `xs_momentum` files
- enabling any strategy in UI/API (`routes_backtest` allowed set, `data.js`,
  `view-config.js`) — UI integration is part of "publish", which is post-gate and
  user-approved, NOT this task
- editing `HYPOTHESIS_LEDGER` verdicts (Claude sets those at checkpoint ①)

## REQUIRED ON COMPLETION
- List changed files + the three `summary.json` paths.
- Run: targeted `pytest tests/unit/test_<candidate>*.py` (incl. leak tests) and
  `python scripts/docs/check_doc_impact.py`.
- Report each candidate's DSR/PSR/n_trials/leak_test_passed/promotion_gate_passed.
- Commit with `AI-Origin: Codex` trailer.
- Hand back to Claude for checkpoint ① (do not proceed to shortlist/publish).

## ACCEPTANCE CRITERIA
- [ ] S5, S6 implemented + two-pass run with summary.json; S7 done iff Task A
      delivered spot data (else explicitly skipped as data-blocked).
- [ ] Each has a passing leak regression test and a REFERENCE_VALIDATION_CONTRACTS entry.
- [ ] CPCV n_trials == pre-registered family-cumulative (S7:72, S5:72, S6:48); I23 holds.
- [ ] S5 verified as residual mean-reversion (not momentum).
- [ ] No idealized-fill cited as evidence; ct_val provenance present.
- [ ] No strategy enabled; no gate/risk/artifact-value change; stopped at checkpoint ①.

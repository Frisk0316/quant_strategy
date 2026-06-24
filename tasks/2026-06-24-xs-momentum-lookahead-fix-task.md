# Codex Task — Fix XS Momentum look-ahead leak + re-run validation

Plan source: `tasks/2026-06-24-xs-momentum-phase-c-review.md`
Strategy/spec source: `docs/superpowers/plans/2026-06-23-xs-momentum-universe.md`
(Tasks C1–C3), `docs/DOMAIN_RULES.md` R3.1.

Task: Remove the daily→intraday look-ahead leak in the XS momentum runner, prove
it with a regression test, re-run WF/CPCV on leak-free returns, and retract the
invalid promotion claim. This is a business-rule (PnL/validation) change → needs
a Change Manifest update and `make docs-impact`.

## Diagnosis (from review)
`backtesting/xs_momentum_backtest.py:51-65`: the day-D target weight is a function
of D's own close (`_daily_close`, `:19-20`, bins at `00:00` but holds the day's
`23:00` close), then `target_daily.reindex(close.index).ffill()` lands it on D's
`00:00` bar and `positions = target.shift(1)` lags it by only one intraday bar.
The rebalance-day position is therefore traded with same-day-close hindsight,
inflating OOS Sharpe (2.4–5.1 at ~2–3% vol) and trivially passing DSR/PSR.

## PERMITTED FILES (only edit these)
- `backtesting/xs_momentum_backtest.py`  (lag fix only)
- `tests/unit/test_xs_momentum_backtest.py`  (add look-ahead regression test)
- `results/xs_momentum_validation_20260623/` regenerate via the runner, OR write
  a new dated artifact dir and mark the old one superseded (do not hand-edit JSON)
- `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`  (record the fix)
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`  (state update on completion)

## FORBIDDEN (do not touch)
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`
  (the vol-target quantity question in MAJOR 3 is a separate Claude/user decision;
  do NOT change `xs_momentum.py` sizing in this task)
- `config/`, deployment/shadow/demo/live gates
- any other existing result artifact

## SCOPE LIMIT
Fix only the timing leak. Do not refactor the runner, rename, or change the
vol-target / crash-filter / funding logic. No new features.

## Required behavior
1. Positions for day D must depend only on data through D-1's close. Lag the
   daily target a full day before reindexing to intraday (e.g.
   `target_daily.shift(1)` at the daily level), then reindex+ffill, then keep the
   existing execution-lag bar if desired — but the daily-close info of day D must
   never size day-D positions.
2. Add a regression test: a synthetic panel where same-day-close info would be
   profitable must produce ~0 PnL under the corrected lag (and clearly non-zero
   under the buggy one-bar lag, to prove the test bites).
3. Re-run `scan_xs_momentum` + WalkForward + CPCV on the leak-free runner;
   regenerate `summary.json` / `walk_forward.json` / `cpcv.json` with
   `promotion_gate_passed: false` (or field removed) and `status: review_required`.
   Mark the pre-fix `results/xs_momentum_validation_20260623/` as superseded.
4. Reconcile `n_trials` vs `n_combinations` in the CPCV output (review MINOR 5).

## REQUIRED ON COMPLETION
- List changed files.
- Run: `pytest tests/unit/test_xs_momentum_backtest.py tests/unit/test_xs_momentum.py -v`
  and `python scripts/docs/check_doc_impact.py`.
- Update the Change Manifest + `docs/AI_HANDOFF.md` + `docs/CURRENT_STATE.md`.
- Commit with `AI-Origin: Codex` trailer.

## ACCEPTANCE CRITERIA
- [ ] Regression test proves day-D positions use only data ≤ D-1 close.
- [ ] `pytest` above passes; `check_doc_impact.py` passes.
- [ ] Re-run OOS Sharpe/DSR/PSR reported on leak-free returns; no
      `promotion_gate_passed: true` anywhere.
- [ ] Pre-fix validation artifact marked superseded/invalid.
- [ ] No `enabled:true` / promotion / live claim introduced.

## Hand back to Claude
Re-review the leak-free WF/CPCV. DSR/PSR ≥ 0.95 on the corrected returns is what
decides whether the alpha stands. The vol-target quantity decision (MAJOR 3) is a
separate Claude/user item before any promotion path.

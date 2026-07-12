---
status: archived
type: task
owner: claude
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# C2 Funding Carry — Realism Re-Cost + Funding-Reversal Stress

Author: Claude (review). Implementer: Codex.

## Why

Batch-2 C2 (`F-FUNDING-CARRY`, E-024) "passed" the statistical gate with CPCV OOS
Sharpe 6.8913, DSR 1.0000, PSR 1.0000 — but the CPCV path daily std is **~1.4e-4
(≈ 0.27% annualized vol)**, which is physically implausible for a real delta-neutral
crypto carry book. The Sharpe is high only because modeled vol is near-zero. Root
cause is **backtest risk/cost fidelity**, not the validator (T1/T2 are correct):

1. The spot/perp hedge is treated as frictionless — no spot financing/capital cost,
   no realistic two-leg rebalance slippage, no basis-blowout / short-squeeze tail.
2. The entire 2024-2026 test window is one persistent **positive-funding regime**, so
   CPCV folds never test a funding flip. DSR/PSR=1.0 reflect a truncated left tail.

**Goal:** determine whether *any* edge survives realistic costs AND a non-positive-
funding regime. The expected honest outcome is that the Sharpe collapses toward ~1
or below and C2 is shelved — that is the gate working. **No adapter/promotion work
until C2 clears this.**

## Task

Re-cost C2 under realism and explicitly evaluate a funding-reversal / basis-blowout
regime. Do **not** overwrite the existing C2 artifact.

1. **Add a realistic cost/risk model** to the C2 research backtest (parameters, so
   idealized vs realistic are the same code path):
   - Spot-leg financing/capital cost and perp short margin cost (a `carry_cost_bps`
     daily drag, or an explicit per-leg model).
   - Two-leg rebalance slippage applied to **both** legs on every weight change (not a
     single flat 2bps on net turnover).
   - Basis-execution noise: do not assume both legs fill simultaneously at the same
     bar close. At minimum add a configurable basis-execution slippage; ideally route
     the candidate through the replay engine for realistic fills.
   - Funding paid (not just received) whenever the position is held through a flip —
     verify the existing `-(position * rate)` accounting actually charges the book
     when funding goes negative while a position is on.
2. **Funding-reversal / basis-blowout stress:** carve out the sub-window(s) in
   2024-2026 where BTC/ETH funding went negative or basis spiked, and report C2's
   PnL, max drawdown, and how often the book is caught mid-flip before the exit
   filter triggers. Report this separately from the full-window number.
3. **Re-run** the fold-refit WF/CPCV on the realistic config with honest
   family-cumulative `n_trials` (this is a **retry of F-FUNDING-CARRY** → prior=24,
   so the new run's `n_trials = 24 + this run's grid`). Retain CPCV `path_returns`.
4. **Record the realized modeled vol** in the summary so the artifact is self-checking
   (an annualized vol still < ~2% is a red flag the hedge is still too idealized).

## PERMITTED FILES (only edit these)

- `backtesting/c2_funding_carry_backtest.py` (add cost/risk params + the realistic
  path; keep the idealized path available behind a flag)
- `scripts/run_pipeline_batch1_checkpoint.py` **only if** a separate C2-realism
  runner entry is needed, or add a small `scripts/run_c2_realism.py`
- `tests/unit/test_c2_funding_carry_backtest.py` (cost + funding-flip-charge + a
  realized-vol sanity assertion)
- `results/pipeline_batch2_20260625/c2_funding_carry_realism/**` (new artifacts)
- Docs: `docs/HYPOTHESIS_LEDGER.md` (H-007), `docs/EXPERIMENT_REGISTRY.md` (new
  E-row, supersede-note style), `docs/change_manifests/` (new manifest),
  `docs/DOC_IMPACT_MATRIX.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, `config/workstreams.yaml`

## FORBIDDEN (do not touch)

- `src/okx_quant/strategies/funding_carry.py` and all of `src/okx_quant/strategies/`,
  `signals/`, `risk/`, `portfolio/`, `execution/` — the live carry strategy's
  behavior must not change; C2 is a research backtest only.
- `src/okx_quant/analytics/dsr.py`; `backtesting/cpcv.py`,
  `backtesting/walk_forward.py`, `backtesting/pipeline_refit.py` (the harness is
  correct; do not retune it to change the number).
- `config/risk.yaml`, `config/strategies.yaml` `enabled:` flags; any demo/shadow/
  live gate. C2 stays `enabled:false`.
- The existing `results/pipeline_batch2_20260625/c2_funding_carry/summary.json`
  (no in-place rewrite; write realism artifacts to the new `_realism/` dir).

## SCOPE LIMIT

Only the cost/risk realism + the stress-regime evaluation + the re-run. Do **not**
tune the signal to chase the gate, do not widen the grid to fish, do not start
portable-adapter work.

## REQUIRED ON COMPLETION

- List changed files.
- Run: `python -m pytest tests/unit/test_c2_funding_carry_backtest.py -q` and the
  realism re-run (report SKIP if DB/DSN unreachable — do not hand-write the summary).
- `python scripts/docs/check_doc_impact.py`.
- Add a superseding E-row; update H-007; Change Manifest; handoff docs.
- Commit with `AI-Origin: Codex` trailer when committing is requested.

## ACCEPTANCE CRITERIA

- [ ] Realistic cost/risk model added (spot financing + perp margin drag, two-leg
      rebalance slippage, basis-execution slippage), with a unit test; a unit test
      asserts funding is **charged** when held through a negative-funding bar.
- [ ] The summary records the realized annualized vol of the return stream; a test
      asserts the realistic run's vol is materially above the ~0.27% idealized figure.
- [ ] A funding-reversal / basis-blowout sub-window is evaluated and its
      PnL/drawdown reported separately.
- [ ] Realistic fold-refit WF/CPCV re-run with `n_trials = 24 + grid` (retry of
      F-FUNDING-CARRY), CPCV `path_returns` retained, in
      `results/pipeline_batch2_20260625/c2_funding_carry_realism/`.
- [ ] Verdict recorded: if realistic DSR/PSR < 0.95 → H-007 `refuted`/shelved.
      Adapter/ct_val/promotion work is unblocked **only** if it survives realism
      AND the funding-reversal regime — and even then only after Claude review.
- [ ] No live `funding_carry.py`, harness, `dsr.py`, gate, or config-enable changes;
      old C2 artifact untouched.

## Questions for Claude (answer in handback)

- Which specific 2024-2026 windows count as the funding-reversal / basis-blowout
  stress set (so the regime test is pre-registered, not cherry-picked)?

# Codex Task — XS Momentum vol-target: single-name → portfolio vol

Plan source: `tasks/2026-06-24-xs-momentum-phase-c-review.md` (MAJOR 3 + Re-review).
Decision: Claude/user approved the policy switch (correctness, **not** a promotion
attempt). Strategy/spec: `docs/superpowers/plans/2026-06-23-xs-momentum-universe.md`,
`docs/DOMAIN_RULES.md`.

## Context — read before implementing
This is a **leverage/scale** change. PSR/DSR are Sharpe-based and Sharpe is
scale-invariant, so this **will not move the promotion gate** (PSR stays ~0.80) and
must not be framed as promotion progress. `xs_momentum` stays `enabled:false`. The
rerun exists only to produce a spec-correct artifact.

## Diagnosis
`src/okx_quant/strategies/xs_momentum.py:122-128`: gross is sized from the **median
single-name** annualized vol with `gross = min(1.0, vol_target_annual/annual_vol)`.
For crypto single-name vol (~60–90%/yr) this pins gross ≈ 0.2–0.29 and the `1.0` cap
forbids levering up, so the diversified market-neutral book realizes ~3% vol against
a 17.5% target — chronic ~5× under-leverage. The targeted quantity is wrong: a
market-neutral book must target the **book's** realized vol, not a constituent's.

## PERMITTED FILES (only edit these)
- `src/okx_quant/strategies/xs_momentum.py` (vol-target sizing only)
- `backtesting/xs_momentum_backtest.py` (only if the portfolio-vol estimate must be
  computed/passed at the runner level)
- `tests/unit/test_xs_momentum.py`, `tests/unit/test_xs_momentum_backtest.py`
- `docs/change_manifests/` — **new** Change Manifest (sizing = business rule)
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md` if a sizing rule/invariant changes
- `results/xs_momentum_validation_20260624_portfoliovol/` — new rerun artifact dir
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` — state update on completion

## FORBIDDEN (do not touch)
- `risk/`, `portfolio/allocation.py` neutrality math, `execution/`, `signals/`
- funding sign, the leak fix, the crash filter logic
- existing result artifacts (write a new dated dir; do not overwrite leakfix run)
- deployment/shadow/demo/live gates; `enabled` stays `false`

## Required behavior
1. Size gross to target the **realized portfolio (book) vol**, e.g. estimate the
   neutral book's ex-ante vol (from constituent vols + the actual long/short weights;
   a covariance or a portfolio-return rolling-vol proxy) and set
   `gross ≈ vol_target_annual / realized_portfolio_vol_annual`.
2. **Cap maximum gross leverage** (pick a sane bound, document it) — uncapped
   inverse-vol sizing can blow up in calm regimes. This replaces the old `min(1.0)`
   cap, which was a correctness bug, not a risk cap.
3. Keep inverse-vol name weighting, dollar-neutrality, `max_name_weight`, funding
   sign, and the crash-regime scaler unchanged.
4. Add/extend a test asserting realized backtest vol lands near `vol_target_annual`
   (within a tolerance) on a controlled fixture, and that gross respects the cap.
5. Rerun WF + CPCV into the new artifact dir with `promotion_gate_passed:false`,
   `status:"review_required"`. Expect returns/vol ~5× the leakfix run and
   **Sharpe/PSR ~unchanged**.

## REQUIRED ON COMPLETION
- List changed files.
- Run: `pytest tests/unit/test_xs_momentum.py tests/unit/test_xs_momentum_backtest.py -v`,
  `python scripts/docs/check_doc_impact.py`, and `make docs-impact`.
- New Change Manifest + DOMAIN_RULES/INVARIANTS update if a rule changed.
- Update handoff docs. Commit with `AI-Origin: Codex` trailer.

## ACCEPTANCE CRITERIA
- [ ] Realized backtest annualized vol is near `vol_target_annual` (test-verified).
- [ ] Max gross leverage cap enforced and documented.
- [ ] Neutrality, funding sign, crash filter, and the leak fix unchanged (tests pass).
- [ ] New rerun artifact: `promotion_gate_passed:false`, `status:"review_required"`;
      Sharpe/PSR materially unchanged vs the leakfix run (confirms scale-invariance).
- [ ] New Change Manifest filed; `make docs-impact` passes; `enabled:false`.

## Hand back to Claude
Re-review the portfolio-vol rerun. Confirm realized vol ≈ target and that Sharpe/PSR
did not change (validates the scale-invariance reasoning). Promotion remains blocked
on PSR + the separate DSR fix; this task only makes the strategy spec-correct for
any future live sizing.

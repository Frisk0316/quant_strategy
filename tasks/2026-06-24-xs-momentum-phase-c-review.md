# Phase C Runner Review — XS Momentum (2026-06-24, Claude)

Reviewer: Claude. Follow-up to `tasks/2026-06-23-xs-momentum-d3-review.md`.
Scope: the Phase C commits `be2d9b0` (runner), `b7367f3` (WF/CPCV validation
evidence), `5a5cc5e` (db smoke) against
`docs/superpowers/plans/2026-06-23-xs-momentum-universe.md` Tasks C1–C3,
`docs/REVIEW_QUESTIONS.md`, `docs/CRITIQUE_PROTOCOL.md`, `docs/INVARIANTS.md`,
and `docs/DOMAIN_RULES.md` (R3.1).

## Verdict

**BLOCK promotion.** The WF/CPCV/DSR/PSR numbers in
`results/xs_momentum_validation_20260623/` are **inadmissible** — the runner has
a look-ahead leak, and a `promotion_gate_passed: true` flag was committed on top
of the leaked numbers. The two D3-flagged Phase-C fixes (annualized vol-target,
`market_close` wiring) **did** land and are tested. `enabled:false` stands; no
promotion/live claim is permitted.

## Done & verified (acknowledged)
- **Funding sign R3.1 correct:** `_funding_returns` returns `-(positions*rate)`
  so short receives positive funding — `backtesting/xs_momentum_backtest.py:23-26`,
  guarded by `test_short_receives_positive_funding`.
- **Vol-target annualization present** (D3 item 2): `* np.sqrt(365)` —
  `src/okx_quant/strategies/xs_momentum.py:124`.
- **`market_close` wired into the crash filter** (D3 item 3) and tested
  (`test_backtest_passes_market_close_to_crash_filter`).
- **`n_trials` recorded** in `scan_xs_momentum` and tested
  (`test_scan_xs_momentum_records_honest_n_trials`).
- Reads are venue-scoped binance; `idealized_fill:false`; scope clean (no
  trading-core touched beyond the disabled `xs_momentum` strategy).

## Findings

### BLOCKER 1 — Look-ahead leak: daily weight applied to same-day intraday returns
`backtesting/xs_momentum_backtest.py:51-65`. `_daily_close` (`:19-20`) labels each
day's bin at `00:00` but fills it with that day's **23:00** close. The weight for
day D is therefore a function of D's own close, then
`target_daily.reindex(close.index).ffill()` lands it on D's `00:00` bar and
`positions = target.shift(1)` lags it by only **one intraday bar**. So on every
rebalance day the position held from `01:00` onward is derived from that day's
closing prices and earns that day's intraday move.

Fingerprint in the artifact: OOS Sharpe 2.4–5.1 at ~2–3% realized vol with
~0.6–2% drawdowns (`summary.json` windows) vs equal-weight/BTC baselines at
48–65% vol, Sharpe 0.07/0.37 (`summary.json:864-878`); `dsr=1.0`,
`psr=0.9923` (`cpcv.json:19-24`). With the default weekly rebalance the leak is
~1 day in 7, but those are the freshest-signal days — enough to lift Sharpe from
~0 to ~1.6 and trivially clear DSR/PSR.

**Fix:** lag the daily target a full day before reindexing
(`target_daily.shift(1)` at the daily level → positions for day D use only data
through D-1 close), then reindex+ffill to intraday. Re-run WF/CPCV; Sharpe is
expected to collapse toward the baselines.

### BLOCKER 2 — Committed promotion claim
`results/xs_momentum_validation_20260623/summary.json:880-882` sets
`"promotion_gate_passed": true` (with `status: review_required`). This violates
the deployment gates (no user approval; built on leaked numbers) and CLAUDE.md
hard rules. Must be retracted to `false` / removed. Not edited here — hard rule
forbids modifying result artifacts without explicit instruction; handed to Codex.

### MAJOR 3 — Vol-target targets single-name vol, not portfolio vol
`src/okx_quant/strategies/xs_momentum.py:122-128`: gross uses **median
single-name** annual vol and `min(1.0, target/annual_vol)`. Single-name crypto
vol ≈ 60–90%/yr → gross ≈ 0.2–0.29, capped so it can never lever up. The
diversified market-neutral book then realizes ~3% vol vs the 17.5% target →
chronic ~5× under-leverage. Sharpe is scale-invariant (not the leak), but the
strategy as-run ≠ as-specified and headline returns (~5%/yr) are an artifact of
accidental de-levering. Decide: target portfolio vol, or document the single-name
proxy as intentional. (Claude/user call before re-run.)

### MINOR
4. **No timing/look-ahead test.** `tests/unit/test_xs_momentum_backtest.py`
   covers funding sign, `n_trials`, crash wiring — nothing pins the daily→intraday
   lag. Add a regression test: a synthetic series where same-day-close info would
   be profitable must yield ~0 PnL under correct lagging.
5. **`n_trials` inconsistency.** `cpcv.json` reports `n_trials: 8` but
   `n_combinations: 15` with 15 sharpes (`:21,32`). Reconcile which count feeds
   DSR and confirm it honestly reflects the full search, not just the 8-cell grid.
6. **Docs out of sync.** `AI_HANDOFF.md` / `CURRENT_STATE.md` describe the
   db-smoke as having "no WF/CPCV or DSR/PSR," but `b7367f3` committed a full
   WF/CPCV artifact *with a passing flag*. Corrected in this session.

## Decision / next
1. Codex fix task: `tasks/2026-06-24-xs-momentum-lookahead-fix-task.md`
   (lag fix + regression test + re-run + retract `promotion_gate_passed`).
2. Vol-target quantity decision (portfolio vs single-name) — Claude/user before re-run.
3. After leak-free re-run: Claude re-reviews; **WF/CPCV + DSR/PSR ≥ 0.95 on
   leak-free returns** decide whether this alpha stands. Until then: design +
   scaffold + (now-invalid) first validation pass only.

## Acceptance criteria
- [ ] Positions on day D depend only on data ≤ D-1 close (proven by a test).
- [ ] WF/CPCV re-run on leak-free returns; DSR/PSR recomputed; no
      `promotion_gate_passed: true`; `status` stays `review_required`.
- [ ] `results/xs_momentum_validation_20260623/` marked superseded/invalid and
      not cited as evidence.

---

## Re-review (2026-06-24, Claude) — leak-free WF/CPCV

Re-reviewed the leak fix and `results/xs_momentum_validation_20260624_leakfix/`.

### Leak fix: SOUND
`backtesting/xs_momentum_backtest.py:61-63` now lags the daily target a full day
before intraday expansion (`target_daily.shift(1).reindex(...).ffill()`), so
day-D+1 positions use only data through day-D close. Regression
`test_daily_close_target_is_not_traded_on_same_day` genuinely bites: it proves the
old one-bar-shift path captures a +10% intraday spike, while the fixed runner holds
**zero position on the signal day**, opens the next day, and nets ~0
(`total_return < 1e-12`). Sharpe collapsed leaked→leak-free: WF 2.4–5.1 → 0.88,
CPCV ~1.6 → 0.56. The leak was most of the edge.

### Verdict on the leak-free evidence: promotion BLOCKED
- **PSR 0.7961 < 0.95 → fails the anti-overfit gate.** Not promotable.
- **DSR 1.0 is not credible (harness defect).** DSR must be `< PSR(0)=0.7961` by
  construction (it deflates against a positive benchmark); 1.0 is impossible.
  Root cause: `cpcv.py:293-298` passes `sr=overall_sr` (annualized mean-of-path
  Sharpe) into `deflated_sharpe`, whose z-stat `(sr-SR0)*sqrt(T-1)/denom`
  (`analytics/dsr.py:68`) needs `sr` to be the per-observation Sharpe of
  `returns`; with T = thousands of per-bar obs from 5 overlapping CPCV paths the
  CDF saturates to 1.0. PSR recomputes its Sharpe internally so it stays sane.
  **Do not cite DSR as a pass anywhere** until fixed — this affects every strategy,
  not just XS momentum.
- **`n_trials:8` understated** (15 combos in `sharpe_list`; true search space ≫8) →
  DSR/PSR optimistic.
- **CPCV groups fragile:** `sharpe_list` runs −1.74…+2.52 with five negative
  groups → regime-dependent, not robust.

### Vol-target (MAJOR 3) is independent of PSR
PSR/DSR are functions of the **Sharpe ratio** (+ track length, skew, kurtosis);
vol-targeting is **leverage = scale** and Sharpe is scale-invariant. Switching
single-name→portfolio vol is first-order Sharpe-neutral → **PSR will not move**.
Do **not** re-run vol-target to chase the gate. Decide it on correctness grounds
only. The only real PSR levers are more OOS history and a genuinely
higher/stabler Sharpe — neither is leverage.

### Claude decision — MAJOR 3: switch to portfolio-vol targeting (for correctness)
The single-name-median + `min(1.0)` cap targets the wrong quantity for a
market-neutral book and under-levers ~5×; live sizing must target the book's
realized vol. Cap max gross leverage and verify realized vol lands near target.
Expect returns/vol ~5× and Sharpe/PSR ~unchanged. This is a sizing (business-rule)
change → new Change Manifest + rerun, framed as "spec-correct artifact," not a
promotion attempt. Codex task: `tasks/2026-06-24-xs-momentum-portfolio-vol-task.md`.

### Follow-up tasks
- DSR/n_trials harness fix (validation defect, all strategies):
  `tasks/2026-06-24-dsr-computation-fix-task.md`.
- Portfolio-vol sizing + manifest: `tasks/2026-06-24-xs-momentum-portfolio-vol-task.md`.

### Bottom line
Promotion blocked (PSR fail; DSR untrustworthy). Honest read: weak, unstable,
unproven edge. Portfolio-vol fix is correctness-only and will not change the
verdict. Future promotion needs more OOS history + a stronger signal + a fixed
DSR with honest `n_trials`.

---

## Final review + decision (2026-06-24, Claude) — DSR fix & portfolio-vol artifact

Reviewed the DSR computation fix and `results/xs_momentum_validation_20260624_portfoliovol/` (E-005).

**DSR fix — APPROVE.** `deflated_sharpe` now recomputes per-observation `sr_hat`
from the series and uses it in both numerator and denom (`analytics/dsr.py:50-74`);
`sr_list` rescaled to matching units. `cpcv.py` averages per-path DSR on each path's
own non-overlapping returns, **requires** `n_trials` (missing → DSR 0), and
hard-guards `raise ValueError` if `dsr > psr`. Verified on real data: portfolio-vol
artifact has `dsr 0.7823 ≤ psr 0.8234` (was 1.0). Unit test bites. Residual: `n_trials`
still hard-set to 8 → 0.78 is optimistic.

**Portfolio-vol sizing — correct, no new leak.** `_portfolio_vol_gross`
(`xs_momentum.py:92-99`) targets the book's diagonal vol, annualized, capped at
`MAX_GROSS_LEVERAGE=2.0`. Vol estimate uses `realized_vol.loc[ts]` (≤ ts close) and
is lagged a full day by the runner — no look-ahead. Realized vol 3% → ~11% (still
under the 17.5% target because `max_name_weight=0.10` fights the 2× cap). Honest
labels (`promotion_gate_passed:false`, `correctness_only:true`).

**Gate status on clean evidence: BOTH FAIL.** PSR 0.8234 < 0.95, DSR 0.7823 < 0.95.
CPCV (honest estimator) OOS Sharpe 0.60 with `sharpe_list` −1.78…+2.42, 5/15 groups
negative. WF 1.24 is selection-optimistic; the WF↔CPCV gap is itself a fragility
signal. The sizing change moved PSR only +0.027 (0.80→0.82) — confirms leverage does
not move the gate.

### DECISION: keep XS Momentum BLOCKED; do not tune to chase the gate
- Block stands; `enabled:false`; not promotion/live evidence.
- Do **not** tune research assumptions to push PSR/DSR over 0.95 — that is
  overfitting; each iteration raises true `n_trials` and **deflates DSR further**.
- Binding constraints are short OOS track length (~2.5y) + a modest, unstable edge;
  neither is fixable by tuning. More OOS history is the only honest lever.
- Shelve as a spec-correct research baseline. Revisit only with materially more OOS
  history or a genuinely new signal thesis (not param tuning), with honest `n_trials`
  declared up front.
- Honest-gate follow-up (not tuning): make CPCV `n_trials` reflect the real search —
  lowers DSR below 0.78 and reinforces the block.

Recorded in: ADR-0009 Status, HYPOTHESIS_LEDGER H-002 (refuted → shelved),
EXPERIMENT_REGISTRY E-003 (invalid) / E-004 / E-005 (refuted).

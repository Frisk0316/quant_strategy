# Codex Task — Recheck DSR across all strategies after the harness fix

Plan source: `tasks/2026-06-24-xs-momentum-phase-c-review.md` (Final review §);
DSR fix committed in `fecdd98`. Severity: the pre-fix DSR was inflated (often
~1.0) for **every** strategy that reported a CPCV DSR, so prior "DSR passed"
claims are suspect.

## Diagnosis (already fixed in code, now audit the consequences)
Before `fecdd98`, `deflated_sharpe` was fed an annualized `sr` over thousands of
per-bar observations and overlapping CPCV paths, saturating the CDF to ~1.0
(`analytics/dsr.py` / `backtesting/cpcv.py`). Any artifact whose
`cpcv.dsr` was produced by the old code is untrustworthy and may have shown a
false pass.

## PERMITTED FILES (only edit these)
- `scripts/` — a new audit/recompute script (e.g. `scripts/recheck_dsr.py`)
- `docs/results_validation_manifest.md` — annotate affected artifacts
- `docs/EXPERIMENT_REGISTRY.md` — supersede rows whose DSR was pre-fix
- `docs/KNOWN_ISSUES.md` — record the pre-fix-DSR caveat
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` — state update on completion

## FORBIDDEN (do not touch)
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`
- `analytics/dsr.py` / `cpcv.py` (already fixed; do not re-edit here)
- existing result artifacts' numeric payloads (annotate/supersede, do not rewrite)
- deployment/shadow/demo/live gates

## Required behavior
1. Scan `results/**/*.json` (and `results/strategy_validation/**`) for any
   artifact carrying a `cpcv.dsr` / `dsr` field. List them with their reported
   DSR/PSR and whether they were generated before `fecdd98`.
2. For each, decide: **recompute** (if the raw path/combo returns are available
   in the artifact) under the fixed code, or **flag untrusted** (if only a summary
   DSR was stored and a rerun isn't feasible offline).
3. Recompute where feasible; record old vs new DSR. Any artifact whose
   promotion-relevant claim depended on DSR ≥ 0.95 must be re-evaluated and, if it
   now fails, marked so it cannot be cited as promotion evidence.
4. Add the runtime invariant already enforced in `cpcv.py` (`DSR ≤ PSR(0)`) to the
   audit output as a sanity check.

## REQUIRED ON COMPLETION
- List changed files + the table of affected artifacts (old DSR → new DSR / status).
- Run: `pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py -q` and
  `python scripts/docs/check_doc_impact.py`.
- Update manifest / registry / KNOWN_ISSUES / handoff docs.
- Commit with `AI-Origin: Codex` trailer.

## ACCEPTANCE CRITERIA
- [ ] Every artifact with a CPCV DSR is listed and classified (recomputed | untrusted).
- [ ] No remaining citation treats a pre-fix DSR ~1.0 as a pass.
- [ ] Tests + `check_doc_impact.py` pass.
- [ ] No strategy/gate/result-payload changes; corrections are annotations/supersedes.

## Note
This is the highest-value spillover from the XS momentum leak investigation: it
protects every strategy's overfit gate, not just `xs_momentum`. Honest `n_trials`
(still hard-set to 8 in the XS run) should be addressed in the same pass where the
recompute touches `n_trials`.

---
status: current
type: task
owner: claude
created: 2026-07-16
last_reviewed: 2026-07-16
expires: 2026-10-16
superseded_by: null
---

# Codex Task A: Stage-2.5 Power/Breadth screen + pipeline funnel report

Claude-authored plan (user-requested 2026-07-16). Codex implements; Claude
reviews every diff and report. Motivation: the recurring failure mode across
H-013/H-015..H-020 is short history / low breadth / same daily-z-score form, so
candidates burn Stage-3 compute and K before dying for structurally predictable
reasons (H-019 breadth-1 failed "exactly the pre-registered power caveat"). Add a
cheap ex-ante power screen that kills those before Stage 3, and a funnel report
that makes the pipeline's per-stage hit rate and K spend visible.

This screen is TRIAGE, not a new deployment gate. It does not touch any Stage-3
grid, PnL formula, or gate threshold.

## Filled Implementation template

```text
Task: Add an ex-ante statistical-power screen to Stage 2 and a pipeline funnel report.

Strategy/spec source: docs/superpowers/pipeline/stage2-feasibility.md;
  backtesting/pipeline_stage2_registry.py; DSR/PSR defn in
  research/strategy_synthesis.md#validation-status-convention.

Required behavior:
- New check `statistical_power` written into the SAME stage2_feasibility.json.
  Inputs (all cheap, deterministic, no backtest): breadth = independent bets
  (cross-section width x rebalance count; 1 for single-instrument long/flat),
  n_obs = OOS observations over the frozen window, n_trials = family cumulative
  trials, plus the cost-after-edge plausible net Sharpe already estimated.
- Compute `min_detectable_sharpe`: the smallest observed Sharpe over n_obs that
  clears BOTH PSR>=0.95 and DSR>=0.95 at the given n_trials (invert the
  closed-form PSR/DSR; assume normal skew/kurt unless a sample estimate passed).
- status = PASS iff plausible_net_sharpe >= min_detectable_sharpe; else FAIL with
  both numbers in `reason`. FAIL records 0 grid trials, same policy as a data
  FAIL, and is overridable ONLY with a written ex-ante rationale (mirror K rules).
- New scripts/run_pipeline_funnel_report.py: scan results/**/stage2_feasibility.json
  + docs/EXPERIMENT_REGISTRY.md and emit a funnel (candidates -> data-feasible ->
  power-feasible -> Stage-3-run -> gate-pass) with counts and K spent per family,
  as JSON + a markdown table.

Example: breadth=1 daily long/flat, n_obs~=900 (2.5y), n_trials=4
  -> min_detectable_sharpe ~= 1.9; plausible edge 0.6 -> statistical_power=FAIL
  (the H-019 case, killed before Stage-3).

PERMITTED FILES (only edit these):
- backtesting/pipeline_power_screen.py            (new: the DSR/PSR inversion)
- backtesting/pipeline_stage2_registry.py         (wire the new check + threshold dataclass)
- scripts/run_pipeline_funnel_report.py           (new)
- tests/unit/test_pipeline_power_screen.py         (new)
- tests/unit/test_pipeline_stage2_registry.py      (extend)
- docs/superpowers/pipeline/stage2-feasibility.md  (document the 4th check)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ signals/ risk/ portfolio/ execution/
- config/risk.yaml
- research/ and any existing results/**/result.json or stage2_feasibility.json artifact
- docs/HYPOTHESIS_LEDGER.md, docs/EXPERIMENT_REGISTRY.md (ledger-owned; read-only here)

SCOPE LIMIT: add one Stage-2 sub-check + one report script; no changes to any
Stage-3 grid, PnL, or gate threshold. This screen is triage, NOT a new gate.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run the new/extended pytest files and paste the output tail.
- Update docs/DATA_FLOW.md only if a new artifact path is introduced (else "n/a").
- Do not commit unless committing was requested.

ACCEPTANCE CRITERIA (binary):
- [ ] statistical_power appears in stage2_feasibility.json; stage2_status=FAIL when it fails.
- [ ] Unit test asserts min_detectable_sharpe against a hand-computed DSR/PSR inversion (+-1e-3).
- [ ] Breadth-1 / 2.5y / n_trials=4 fixture -> FAIL; H-014-like breadth/length fixture -> PASS.
- [ ] Funnel report runs over the existing results/ tree and prints per-family K spent.
- [ ] No PnL formula or existing artifact changed; pytest subset green.
- [ ] Diff contains only permitted files.

REPORT: changed files, test tail, the min_detectable_sharpe formula used, any
assumption about skew/kurt or breadth counting left UNCONFIRMED.
```

## Reviewer notes (Claude)

- The power floor is only as honest as `n_trials`; read it from the family
  cumulative column in EXPERIMENT_REGISTRY, do not recompute a smaller number.
- Do NOT let this become a back-door gate relaxation: it can only FAIL-fast a
  candidate, never mark a Stage-3 failure as a pass.
- Verification: dispatch a fresh verifier per docs/ai/MODEL_DISPATCH.md; the
  authoring session does not self-verify.

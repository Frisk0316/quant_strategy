---
status: current
type: manifest
owner: codex
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Change Manifest: C2 Funding-Carry Realism Re-Cost

## Summary

Added realism cost components and stress-regime reporting to the C2
research-only funding-carry backtest, then reran the C2 family retry into a new
artifact directory. The retry refutes/shelves H-007; no live strategy,
deployment gate, risk, portfolio, execution, or existing result artifact changed.

## Business rule(s) affected

No rule text changed. Rules reviewed: R3.1 funding sign, R6.1 leakage, R6.3
honest `n_trials`, R7.1 idealized-fill exclusion, R7.4 DSR/PSR gate
interpretation.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow and A11 experiments / research runs.

## Files changed

- `backtesting/c2_funding_carry_backtest.py` - added fixed-parameter realism
  costs, negative-funding/stress accounting metrics, and realized-vol self-checks.
- `scripts/run_c2_realism.py` - small DB-backed C2 realism rerun entrypoint.
- `tests/unit/test_c2_funding_carry_backtest.py` - regression coverage for
  two-leg costs, negative-funding charge, stress summary, and realized vol.
- `results/pipeline_batch2_20260625/c2_funding_carry_realism/summary.json` - new
  realism artifact only; old C2 checkpoint artifact untouched.
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - recorded H-007
  refutation/shelving and E-026 with family-cumulative `n_trials=48`.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml` -
  current-state and Progress panel updates.
- `tasks/2026-06-29-c2-funding-carry-realism-*.md` - session/context handoffs.

## Behavior delta

- Before: C2 E-024 reported statistical-pass WF/CPCV under an unrealistically
  calm vectorized hedge and was blocked pending realism review.
- After: C2 realism retry applies spot/perp carry drag, two-leg rebalance
  slippage, basis-execution slippage, and a mechanical stress set. The retry
  fails the statistical gate: WF OOS Sharpe -1.5093, CPCV OOS Sharpe -0.2349,
  DSR 0.0041, PSR 0.4457, `promotion_gate_passed:false`.
- Money/risk impact: research-artifact interpretation only. No live money path,
  risk limit, portfolio accounting, execution, demo/shadow/live gate, or config
  enable behavior changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; Claude-owned and not modified.
- config/: `config/workstreams.yaml` progress metadata only; no strategy/risk/gate
  config changed.
- ADR: N/A; no result schema, gate policy, DB schema, or business-rule text
  changed.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - H-007/E-026
  status, metrics, stress result, and trial count.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - current-state handoff.
- [x] `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/GOLDEN_CASES.md`,
  `docs/INVARIANTS.md`, ADR-0002/0005, `docs/KNOWN_ISSUES.md` - reviewed; no
  text change needed because this is a C2 research-only artifact rerun, not a
  durable data path, ownership change, golden-case change, invariant change,
  schema change, gate-policy change, or durable backlog item.

## Invariants / golden cases

- Invariants checked: I4 funding sign, I8/I24 no lookahead/fold-refit evidence,
  I13/I23 honest family trial accounting, I25 retained CPCV returns.
- Golden cases affected: N/A.

## Tests / checks run

- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_c2_funding_carry_backtest.py -q`
  - 4 passed; pytest cache warning.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -B -c "import scripts.run_c2_realism as m; print(m.CANDIDATE_DIR)"`
  - Passed; printed `c2_funding_carry_realism`.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_c2_realism.py`
  - Completed DB-backed realism rerun and wrote the new summary artifact.
- `python scripts/docs/check_doc_impact.py`
  - Passed with 26 changed files and no impact-matrix violations after setting
    temporary `GIT_CONFIG_*` safe-directory variables for the sandbox user.

## Risks and rollback

- Risks: the vectorized C2 hedge remains too calm even after re-costing
  (`realized_annualized_volatility=0.247%`, below the 2% red flag), so this is a
  refutation/shelving artifact, not proof of fully realistic execution.
- Rollback: revert the listed code/test/doc files and remove
  `results/pipeline_batch2_20260625/c2_funding_carry_realism/` if this retry
  should be discarded.

## Approval

- Human approval required: yes for any future adapter, promotion, demo, shadow,
  live, config-gate, or live `funding_carry.py` work. Not requested or obtained
  in this session.

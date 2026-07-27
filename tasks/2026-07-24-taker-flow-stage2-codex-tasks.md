---
status: current
type: task
owner: claude
created: 2026-07-24
last_reviewed: 2026-07-24
expires: 2026-10-24
superseded_by: null
---

# Codex Task: F-TAKER-FLOW (H-022) Stage-2 probe — E-058

User-authorized 2026-07-24. Spec (pre-registered, read first):
`docs/superpowers/specs/2026-07-23-f-taker-flow-hypothesis.md`. Scout gate:
`tasks/2026-07-23-free-data-scout-report.md` (Claude review: S1 YES —
zero-download parse of `market_klines.raw_payload.raw[9]/[10]`, Option A).
Stage-2 ONLY. Stage-3, grid backtests, DSR/PSR runs are NOT authorized.

## Filled Implementation template

```text
Task: Register H-022/E-058, then run the four Stage-2 feasibility checks for
F-TAKER-FLOW and write the stage2_feasibility.json artifact.

Required behavior, in EXACT order (registration-before-run must be provable
in git — lesson from the E-057 review):

STEP 1 (commit #1, before any probe code runs against data):
- docs/HYPOTHESIS_LEDGER.md: add H-022 / F-TAKER-FLOW row, status
  `proposed`, hypothesis text and grid from the spec, n_trials
  contribution 0 until Stage-3.
- docs/EXPERIMENT_REGISTRY.md: register E-058 (Stage-2 feasibility probe,
  ex-ante fields: window 2024-01-01 -> 2026-06-17, PIT universe, grid
  n_trials=4 reserved-not-consumed, K 0/2) and the F-TAKER-FLOW K-budget
  row. Declare the R6.6 distinctness contract HERE, ex-ante:
  gating references F-FUNDING-XS-DISPERSION and F-VOL-REGIME-OPT with their
  available reference-series date ranges; advisory reference H-002
  XS-momentum (shelved, relabel check per spec). The feasibility guard
  (check-style mirroring xvenue) must confirm >= MIN_COMMON_DAYS achievable
  per gating reference BEFORE the probe executes.

STEP 2 (commit #2, the probe):
- New backtesting/taker_flow_probe.py:
  * Parse taker_buy_base from market_klines.raw_payload.raw[9] (binance 1m)
    aggregated to daily per PIT member. QUERY SHAPE CONSTRAINT: ts-bounded
    chunk-friendly queries (per symbol-month/year windows); the scout's
    single full-scan aggregate exceeded the 120s statement timeout — do not
    reuse that shape. Read-only connection.
  * data_availability: member-day coverage of parseable taker fields over
    the window; PASS >= 0.95. Malformed/missing arrays count as missing
    (fail-degrade, never imputed).
  * distinctness: compute candidate daily XS signal (spec formula:
    own-history z of net_flow_ratio, 90d, then XS z) and correlate the
    resulting daily long-short factor proxy against the declared gating
    reference series; |corr| < 0.30 to PASS; advisory H-002 momentum
    correlation reported either way.
  * cost_after_edge: decile-spread (0.2 fraction) gross capture measured on
    the WEEKLY-rebalance variant (cheapest turnover) vs round-trip cost +
    short-leg funding drag from the engine cost model; PASS only if gross
    exceeds cost with the margin the spec's plausible_net_sharpe demands.
  * statistical_power: explicit inputs breadth=6, n_obs=actual window days
    after warmup, n_trials=4, plausible_net_sharpe from the cost check;
    floor recomputed by backtesting/pipeline_power_screen (do not hardcode
    0.7014).
- Wire STAGE2_PROBES["F-TAKER-FLOW"] with the same fail-closed contracts as
  F-XVENUE-LEADLAG (missing declarations/power inputs -> explicit refusal
  before any artifact write).
- Artifact: results/e058_taker_flow_stage2_<date>/stage2_feasibility.json
  (schema per docs/superpowers/pipeline/stage2-feasibility.md, all four
  checks) + SHA-256 recorded in the registry row.
- Tests: refusal-before-artifact on both entry paths; parse-function unit
  test with a malformed-array fixture; distinctness-guard feasibility test;
  a small deterministic fixture proving the signal formula (no DB).

STEP 3 (commit #3): registry/ledger updated with E-058 outcome (PASS -> H-022
`testing`, or FAIL -> honest reason + `shelved`/`inconclusive` per result);
state docs sync. NO Stage-3 work regardless of outcome.

PERMITTED FILES (only edit these):
- backtesting/taker_flow_probe.py (new), backtesting/pipeline_stage2_registry.py
- tests/unit/test_taker_flow_probe.py (new),
  tests/unit/test_pipeline_stage2_registry.py (extend)
- docs/HYPOTHESIS_LEDGER.md, docs/EXPERIMENT_REGISTRY.md (H-022/E-058 rows)
- results/e058_taker_flow_stage2_*/** (new artifact only)
- docs/change_manifests/2026-07-24-taker-flow-stage2.md (new; A5 row will
  demand it — include DATA_FLOW or FEATURE_MAP one-line update as strict
  requires; whitelist pre-expanded per the B1 lesson)
- docs/DATA_FLOW.md, docs/FEATURE_MAP.md (one-line additions only)
- docs/CURRENT_STATE.md, docs/AI_HANDOFF.md, config/workstreams.yaml,
  handoff files (state sync)

FORBIDDEN (do not touch):
- Existing results/**, other ledger rows, research/
- src/okx_quant/** trading core, config/risk.yaml
- Any schema change/migration (Option A parse only), any network download
- Stage-3 runner, grid backtest, DSR/PSR computation

ACCEPTANCE CRITERIA (binary):
- [ ] Commit #1 (registration + ex-ante declarations) precedes commit #2
      (probe) in git history.
- [ ] Distinctness feasibility guard passes ex-ante with declared ranges.
- [ ] All four checks present in the artifact; power floor computed by the
      screen with explicit inputs, not hardcoded.
- [ ] Probe queries complete without statement timeout on the real DB.
- [ ] Refusal tests green on both entry paths; full unit suite green;
      Ruff, ledger consistency, docs-impact --strict PASS.
- [ ] Artifact SHA-256 recorded; no existing artifact touched.
- [ ] Diff contains only permitted files.

REPORT: per-check status + key numbers (coverage, correlations, gross
capture vs cost, plausible_net_sharpe vs floor), test tails, artifact path +
hash, anything UNCONFIRMED. 完成後交 Claude 審。
```

## Reviewer notes (Claude)

- The most likely honest outcomes, pre-declared: distinctness FAIL against
  momentum-correlated references, or cost FAIL at the weekly variant. Either
  stops the family at 0 grid trials — that is the pipeline working.
- If E-058 PASSES all four checks, Stage-3 still requires separate user
  authorization; the reserved n_trials=4 is consumed only when Stage-3 runs.

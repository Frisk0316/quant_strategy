---
status: current
type: task
owner: claude
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Claude → Codex Task: Engine-Consistency Smoke (short-window real-data fixture)

## Task
Add a fast, offline, repeatable smoke that proves **our replay engine agrees with
external public engines (vectorbt + backtrader) on signal logic** for the
technical strategies, using a **frozen short-window BTC-USDT-SWAP / Binance / 1H
fixture** instead of a 20k-bar live run.

## Why (verified facts, do not re-litigate)
- The differential-validation harness is already fully implemented and PASSES:
  on `results/codex_macd_signal_point_fixture/.../validation_result.json` all of
  vectorbt + backtrader (`reference_signals_only`) and nautilus (`advisory`)
  report `signal_logic.status == "PASS"`, `actionable_mismatch_count == 0`, and
  `portable_validation_gate.passed == true`.
- The ONLY blocker on the real long-window runs is **runtime**, not adapters.
  Measured on `validation_lab_ma_crossover_btc_binance_1h_20260622_maxord250_pospct1_strategyfill`
  (20400 bars): vectorbt alone = **125s** and returns `signal_logic PASS`;
  vectorbt+backtrader together time out at 240s (backtrader is the bottleneck).
- `make strategy-signal-validation` already cross-checks engines, but on
  **synthetic** price fixtures. The missing piece is a **real Binance OHLCV**
  short window, which is what the user wants for "our engine == public engines"
  confidence and (later) a required CI check.

## Strategy/spec source
- `docs/ai_collaboration.md` Deployment Gate "Differential validation" (signal-logic-only scope).
- `backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS`
  (ma/ema/macd_crossover, vectorbt+backtrader `reference_signals_only`).
- This task does NOT change any gate text or tolerance — it only adds a runner + frozen fixture + test.

## Required behavior
1. Pick a short BTC-USDT-SWAP / Binance / 1H window large enough that **each of
   ma_crossover (10/200), ema_crossover (10/200), macd_crossover (12/26/9)**
   produces **≥ 3 signals** after warmup, and small enough that
   **vectorbt + backtrader each finish in < ~15s per strategy**.
   - Note MA/EMA 10/200 need 200 bars of warmup. Recommended window ≈ 720–1440
     bars (30–60 days). Tune to the ">=3 signals & fast" target; record the exact
     window in the fixture and the smoke output.
2. Generate the three short-window `strategy_fill` runs once from real Binance
   data (reuse `scripts/run_replay_backtest.py --execution-profile strategy_fill`),
   then **freeze them as a committed fixture** under
   `tests/fixtures/engine_consistency/` (or `results/engine_consistency_fixture/`
   following the existing `codex_*_fixture` pattern). Each frozen run needs only
   the differential-validation inputs: `result.json`, `price_series.csv`,
   `signals.csv`.
3. Add a one-click entrypoint:
   - Script `scripts/run_engine_consistency_smoke.py` that, for each of the three
     strategies, calls the existing run-scoped differential validation
     (`backtesting.differential_validation.run_differential_validation` or shells
     `scripts/run_differential_validation.py --run-id <frozen> --engines vectorbt,backtrader`)
     against the frozen fixture, then **asserts** for every strategy:
     `portable_validation_gate.passed == true`, and for vectorbt and backtrader
     `engines.<e>.comparison.signal_logic.status == "PASS"` with
     `actionable_mismatch_count == 0`.
   - Exit non-zero if any strategy/engine fails (so it can become a required CI check).
   - Must run **offline**: `NUMBA_DISABLE_JIT=1`, no DSN, no network. The frozen
     fixture must be self-contained.
   - `Makefile` target `engine-consistency-smoke` invoking the script. Optionally
     wire it into `smoke:`/`verify:` ONLY if total runtime stays < ~60s.
4. nautilus is `advisory` and OPTIONAL here. If included, it must not be required
   for pass/fail (gate only needs the two independent engines).

## PERMITTED FILES (only edit/create these)
- `scripts/run_engine_consistency_smoke.py` (new)
- `tests/fixtures/engine_consistency/**` or `results/engine_consistency_fixture/**` (new frozen fixture)
- `tests/unit/test_engine_consistency_smoke.py` (new)
- `Makefile` (add `engine-consistency-smoke` target)
- `docs/RUNBOOK.md` (document the command)
- `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md` (only if the new artifact path/flow needs a row)
- `.github/workflows/ci.yml` (OPTIONAL: add job; do NOT set as required check — user configures branch protection)

## FORBIDDEN (do not touch)
- `backtesting/differential_validation.py` (no contract/tolerance/gate-logic edits — only call it)
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`
- Any live/shadow/demo or deployment-gate wording, `config/*.yaml`
- Existing result artifacts under `results/**` (do not modify or migrate; the
  frozen fixture is NEW files only)
- DB schema / migrations

## SCOPE LIMIT
Add the smoke + frozen fixture + test only. Do not refactor differential
validation, do not "fix" backtrader speed on the long-window path, do not change
strategy or execution behavior. This produces **signal-logic engine-consistency
evidence only** — it is NOT promotion, edge, or live-readiness evidence, and the
fixture runs are `strategy_fill` / `idealized_fill` so the existing exclusion
gate still applies.

## REQUIRED ON COMPLETION
- List changed/added files.
- Run and paste output of:
  - `python scripts/run_engine_consistency_smoke.py` (or `make engine-consistency-smoke`)
  - `python -m pytest tests/unit/test_engine_consistency_smoke.py -q`
  - `python scripts/docs/check_doc_metadata.py` and `check_feature_map_links.py` if docs changed
- Report wall-clock time of the smoke (target < ~60s).
- Update `docs/RUNBOOK.md`; note in `docs/AI_HANDOFF.md` / `docs/CURRENT_STATE.md`
  that an offline engine-consistency smoke exists.
- This is a docs/governance-adjacent + backtest-workflow change, NOT a business
  rule change to PnL/fee/funding/sizing/fills/gates — no Change Manifest required
  (it calls the gate, it does not change it). Confirm `make docs-impact` is clean.

## ACCEPTANCE CRITERIA
- [ ] `make engine-consistency-smoke` runs **offline** (no DSN/network) and finishes < ~60s total.
- [ ] For ma/ema/macd_crossover on the frozen short fixture: vectorbt AND backtrader
      `signal_logic.status == "PASS"`, `actionable_mismatch_count == 0`,
      `portable_validation_gate.passed == true`.
- [ ] Each strategy's frozen fixture contains ≥ 3 post-warmup signals; window
      recorded in fixture + smoke output.
- [ ] Smoke exits non-zero if any assertion fails (verified by a deliberately
      broken-fixture unit test or a monkeypatched failing engine result).
- [ ] No edits to `differential_validation.py`, trading-core, gates, config, or
      existing `results/**` artifacts.
- [ ] Smoke output and fixture are labeled signal-logic-only / not promotion evidence.

## Risks / regression scenarios for reviewer (Claude) to check on the diff
- Window too short → 0 signals for MA 10/200 (200-bar warmup eats the window) →
  false "PASS" on an empty comparison. The ≥3-signal assertion guards this; verify it.
- Fixture accidentally carries a DSN-dependent path or absolute Windows path in
  `result.json` → smoke fails on a clean checkout. Fixture must be self-contained
  and path-relative.
- Someone later cites the smoke as edge/live evidence — labeling must make the
  signal-logic-only scope explicit.
- backtrader runtime creep if the window is enlarged — keep the < ~15s/engine budget.

## Next recommended task (separate)
Decide the realistic-execution small-order fill policy (deferred by user), and
later layer WF/CPCV for strategy-edge validation. Both are out of scope here.

---
status: current
type: task
owner: claude
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Task (Claude → Codex): C3 Fear & Greed Sentiment — Stage 3 runner + Stage-2 gate tz bugfix

## Task

C3 (`F-SENTIMENT`, H-008) is now **data-unlocked**. Claude ingested the full
Alternative.me Fear & Greed history into `external_observations`
(`dataset_id='fear_greed_btc'`, 3,067 daily rows; 897 in the
`2024-01-01 → 2026-06-17` window). The External-Feature Coverage Gate now passes
read-only (`event_count=897`, `missing_ratio=0.0`, `stale_ratio=0.0`,
`feature_gate_passed=True`).

Two blocking gaps remain before C3 can produce a real Stage-3 checkpoint:

1. **Latent tz bug** in `run_pipeline_batch2_checkpoint.py::_c3_feature_gate`
   crashes now that real rows exist (it never executed on an empty result set).
2. **C3 has no Stage-3 runner.** `run_c3()` only evaluates the Stage-2 gate and
   writes `status:"stage2_passed_stage3_not_run"`. C1/C2 each drive Stage 3 with a
   vectorized research backtest module; C3 does not have one.

Build the C3 Stage-3 runner by mirroring the established C1/C2 pattern, reusing
`FearGreedSentimentStrategy`'s entry/hold/exit logic, and fix the tz bug. Stop at
Claude evidence checkpoint ①. **No promotion, enable, demo, shadow, or live work.**

## Strategy / spec source

- `docs/superpowers/specs/2026-06-29-c3-sentiment-hypothesis.md` (authoritative).
- `research/strategy_synthesis.md` Strategy 9.
- Logic source of truth: `src/okx_quant/strategies/external_features.py::FearGreedSentimentStrategy`
  (entry on Extreme Fear by label OR `value_num ≤ extreme_fear_threshold`; exit when
  `value_num ≥ exit_value_threshold`; hold through Fear/Neutral; long/flat only).
- Pattern to copy: `run_c1()`/`run_c2()` in
  `scripts/run_pipeline_batch2_checkpoint.py` and the modules
  `backtesting/c1_pairs_ou_backtest.py` / `backtesting/c2_funding_carry_backtest.py`.

## Required behavior

1. **tz bugfix** — `scripts/run_pipeline_batch2_checkpoint.py:317`:
   `pd.Timestamp(row["published_at"], tz="UTC")` raises on tz-aware datetimes from
   asyncpg. Change to `pd.Timestamp(row["published_at"]).tz_convert("UTC")` (rows
   come back tz-aware from a `timestamptz` column). No other line in
   `_c3_feature_gate` needs changing.
2. **New module** `backtesting/c3_sentiment_backtest.py` — research-only vectorized
   long/flat sentiment backtest:
   - Inputs: BTC-USDT-SWAP daily close + BTC perp funding (venue-scoped Binance
     canonical, like C1) and the daily `fear_greed_btc` series from
     `external_observations` (as-of `published_at`).
   - Decision logic must match `FearGreedSentimentStrategy` (entry/hold/exit).
   - **Leak-free:** day-D position uses only F&G observations with
     `published_at ≤ D-1` and is applied with a one-day target lag, identical in
     spirit to the C1/C2 `*_target_is_not_traded_on_same_day` tests.
   - Funding cashflow R3.1-correct for the BTC perp leg (`-(position * rate)`).
   - Expose a params dataclass (`C3SentimentParams`) and a
     `run_c3_sentiment_backtest(close, funding, fng, params)` entrypoint and a
     `load_c3_inputs(...)` loader, paralleling C1.
3. **Wire Stage 3 into `run_c3()`** — after the gate PASSES, run the pre-registered
   grid `{extreme_fear_threshold ∈ [20,25,30], exit_value_threshold ∈ [50,55,60]}`
   = 9 combos through the existing `_precompute_records` → `_refit_validation` →
   `_base_summary` → `_write_summary` helpers. New family `F-SENTIMENT`,
   `prior_family_n_trials=0`, so caller-declared family `n_trials=9` (I23). Retain
   CPCV `path_returns` (I25). Keep the gate fields in the summary.
4. **`promotion_gate_passed` must stay `false`** regardless of metrics (no user
   approval; portable-validation path unchanged). Do not change the existing
   `fear_greed_sentiment` `REFERENCE_VALIDATION_CONTRACTS` entry — it already exists.

## PERMITTED FILES (only edit/create these)

- `backtesting/c3_sentiment_backtest.py` (new)
- `scripts/run_pipeline_batch2_checkpoint.py` (tz fix + `run_c3` Stage-3 wiring only)
- `tests/unit/test_c3_sentiment_backtest.py` (new)
- `tests/unit/test_pipeline_batch2_checkpoint_runner.py` (assert C3 Stage-3 path)
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`
- `docs/change_manifests/2026-06-29-c3-sentiment-stage3.md` (new)
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`
- `tasks/2026-06-29-c3-sentiment-stage3-*.md` (handoffs)
- `results/pipeline_batch2_20260625/c3_sentiment/**` (the candidate's own
  checkpoint output — regenerating it from FAIL to PASS+Stage3 is in scope; it is
  gitignored)

## FORBIDDEN (do not touch)

- `src/okx_quant/strategies/**` (reuse `FearGreedSentimentStrategy`; do **not**
  modify the live strategy or its logic), `src/okx_quant/signals/`,
  `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`
- `backtesting/differential_validation.py` (contract already present)
- `config/risk.yaml`, `config/strategies.yaml` (do not enable or re-tune the live
  strategy)
- `research/**`
- C1/C2 result artifacts under `results/pipeline_batch2_20260625/{c1_pairs_ou,c2_funding_carry,c2_funding_carry_realism}/**`

## SCOPE LIMIT

Fix only the tz bug and add the C3 Stage-3 path. Do not refactor the shared
`_precompute_records`/`_refit_validation`/`_base_summary` helpers beyond what C3
strictly needs. Do not re-run or re-cost C1/C2.

## REQUIRED ON COMPLETION

- List changed/added files.
- Run: `python -m pytest tests/unit/test_c3_sentiment_backtest.py tests/unit/test_pipeline_batch2_checkpoint_runner.py -q`
- Run: `python scripts/run_pipeline_batch2_checkpoint.py` (or a C3-only entry) and
  confirm `results/pipeline_batch2_20260625/c3_sentiment/summary.json` shows
  `stage2_status:"PASS"` and a real Stage-3 validation block.
- Run: `python scripts/docs/check_doc_impact.py` (Change Manifest + matrix).
- Update `docs/HYPOTHESIS_LEDGER.md` (flip H-008 off "DATA-BLOCKED/UNTESTED" to the
  Stage-2 PASS + actual Stage-3 verdict) and add an `EXPERIMENT_REGISTRY.md` row
  (next id E-027) with family `n_trials=9`.
- Update `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`.
- Write Context + Session Handoffs with Human Learning Notes.
- Commit with `AI-Origin: Codex` trailer when committing is requested.

## ACCEPTANCE CRITERIA (binary)

- [ ] `_c3_feature_gate` runs without raising on the populated DB and returns
      `feature_gate_passed:true` (event_count=897, missing_ratio≈0, stale_ratio≈0).
- [ ] `run_c3()` writes `c3_sentiment/summary.json` with `stage2_status:"PASS"`,
      `nonzero_grid_activity:true`, a WF + CPCV validation block, DSR/PSR, family
      `n_trials:9`, retained CPCV `path_returns`, and `promotion_gate_passed:false`.
- [ ] A leak regression test proves day-D positions cannot use F&G values published
      after D-1 (parallel to the C1/C2 same-day tests) and **passes**.
- [ ] A parity test confirms the vectorized C3 entry/hold/exit matches
      `FearGreedSentimentStrategy` on a small fixture.
- [ ] Funding sign is R3.1-correct for the BTC perp leg; ct_val provenance is BTC
      SWAP authoritative or explicitly attested.
- [ ] No idealized-fill / `fill_all_signals` path is used.
- [ ] H-008 and a new E-027 row reflect the actual Stage-2 PASS and Stage-3 verdict;
      Change Manifest created; `check_doc_impact.py` clean.
- [ ] No live strategy, risk, portfolio, execution, config-gate, demo/shadow/live,
      or C1/C2 artifact behavior changed.

## Risks / regression scenarios for Claude review

- Logic drift: the vectorized C3 must reproduce the event-driven strategy's
  hold-through-Fear/Neutral behavior, not a naive threshold flip — verify with the
  parity test, not just metrics.
- Stale/missing handling: F&G is daily, TTL 48h; confirm the as-of join uses
  `published_at ≤ D-1` and that a missing day produces "no signal" (no forward-fill
  that manufactures a fresh signal).
- Most likely honest outcome (per spec): a thin/insignificant edge the gate
  rejects. A surprising high-Sharpe pass should trigger the same idealized-artifact
  scrutiny that flagged C2 (E-024) — check realized vol and turnover.

## Verification it is already unlocked (Claude, 2026-06-29, read-only)

`external_observations` `fear_greed_btc`: total 3,067, in-window 897, first
`2024-01-01`, last `2026-06-16`. Gate math replicated read-only:
`missing_ratio=0.000000`, `stale_ratio=0.000000`, `FEATURE_GATE_PASSED=True`.

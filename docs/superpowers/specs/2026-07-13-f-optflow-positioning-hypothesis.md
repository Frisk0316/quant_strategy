---
status: draft
type: design
owner: claude
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# F-OPTFLOW-POSITIONING — Stage 1 Hypothesis (idea batch taxonomy_003 top pick)

Strategy Research Pipeline Stage 1 output for `H-015`. Not a promotion claim.
Top-ranked candidate of `results/idea_batch_20260713_taxonomy_003/idea_batch.json`,
generated and probed by Claude solo per the explicit 2026-07-13 user
instruction (no Codex delegation for this round). The mechanism was reserved
as its own future family by `research/deribit_data_strategy_research.md` §3 C2
and unblocked by the accepted D4 ingestion.

- **family_id:** `F-OPTFLOW-POSITIONING` (new family; `prior_family_n_trials = 0`)
- **Status:** draft — Stage-3 grid requires user sign-off; E-042
  data-availability probe already ran (0 trials, no K).

## Design-space expansion (per `docs/DESIGN_SPACE.md`)

**Problem:** turn the hourly Deribit put/call taker-buy premium imbalance
(`value_num = (put_taker_buy − call_taker_buy) / max(total_taker_buy, ε)`,
per the D4 aggregation docstring in
`src/okx_quant/data/external_clients/deribit_option_flow.py`) into ONE
falsifiable, small-grid, time-series hypothesis on BTC/ETH perps.

**Constraints:** hard — 2 symbols only (Deribit tape covers BTC/ETH);
usable window starts 2024-01-01 (optflow ingestion range — verified, and the
E-041 lesson applies: every sample/probe design must check the data range
FIRST); `published_at` as-of joins (bucket-end labeling verified 100% by the
E-042 probe; F26 guard); DSR/PSR ≥ 0.95; K = 0/2; pre-registered small grid.
Soft — reuse daily vectorized research-runner mechanics.

**Option A — put-extreme risk-off long/flat (CHOSEN):** long the perp by
default, flat when the put-buy imbalance z-score is extreme. Ex-ante
direction from the informed-flow literature (Pan & Poteshman 2006: buyer-
initiated put volume predicts negative underlying returns): follow the flow,
do not fade it. Blast radius: one research module.

**Option B — two-sided long/short on both extremes:** doubles the grid for
the weaker half (call-buying extremes are contaminated by covered-call
sellers' hedging in crypto); rejected to keep 4 combos.

**Option C — vol-regime overlay:** imbalance as a vol predictor collides
with `F-VOL-REGIME-OPT` at minting; rejected.

**Option D — flow-momentum (Δimbalance):** derivative of the same series;
subsumable later as a registered twist, not a separate family.

**Axis:** most direct falsifiable expression of "options tape carries
informed positioning" on instruments we can trade, at minimum grid size.

**Decision:** Option A. **Would change if:** Stage-3 family minting returns
`ASSIGN` vs `F-FUNDING-XS-DISPERSION` or `F-OI-POSITIONING` (fold per I27),
or the E-042 integrity numbers degrade on refresh.

**User sign-off:** PENDING — this spec + the idea-batch ranking await
ratification; Stage-3 may not run before it.

## Hypothesis (falsifiable)

A daily-rebalanced long/flat time-series book on BTC-USDT-SWAP and
ETH-USDT-SWAP that is **flat when the trailing L-day mean of the hourly
Deribit put/call taker-buy premium imbalance is high versus its own 90-day
distribution (z ≥ z_cut), and long otherwise**, vol-targeted at the
portfolio level, earns a positive net-of-cost Sharpe surviving WF and CPCV
with **DSR ≥ 0.95 and PSR ≥ 0.95**. Buy-hold is reported for context only.

## Testable spec

- **Instruments/prices:** BTC/ETH-USDT-SWAP, Binance venue-scoped canonical
  1m closes collapsed to daily last close; window 2024-01-01 → optflow end
  (2026-07-10 at spec time). `ct_val` provenance per I16.
- **Signal series:** `optflow_deribit_{btc,eth}` from `external_observations`
  (E-042: coverage 0.9999/0.9998, max gap 2h, `published_at` = bucket-end
  100%, daily zero-Δ ratio 0.0). Day-t sample: mean of hourly `value_num`
  with `published_at` ≤ day-t daily close, over the trailing `L` days
  (exclude `quality_status='suspect'`). z-score vs fixed 90-day window
  (warmup, no positions). Day with no rows: carry previous day's position.
- **Position:** flat if `z_t ≥ z_cut`, else long. Day-t target trades at t+1
  (same shift discipline as `test_daily_close_target_is_not_traded_on_same_day`).
- **Sizing/costs:** equal weight across active legs; portfolio vol-target
  0.175, 28d window (fixed); `fee_bps=2.0`, `slippage_bps=2.0`; funding
  cashflow per R3.1.
- **Grid (pre-registered):** `{L ∈ [1, 3] days, z_cut ∈ [1.0, 1.5]}` →
  **4 combos**; nothing else varies. `prior_family_n_trials = 0` → CPCV
  `n_trials = 4`. Power note: 2 correlated majors over ~2.5y at n=4 →
  observed-Sharpe bar ≈ 1.7; a marginal fail is a plausible outcome with no
  retry entitlement.

## Distinctness vs testing/active families

| | F-VRP-TIMING (H-013) | F-VOL-REGIME-OPT (H-014) | F-OI-POSITIONING (H-012) | This spec |
|---|---|---|---|---|
| Data | DVOL − RV | DVOL, option chains | Contract-count OI | Options trade tape (taker premium) |
| State variable | Risk premium level | Vol regime richness | Positioning stock | Informed/hedging flow (transactions) |
| Return source | VRP as risk appetite | Option premium carry | Unwind reversal | Short-horizon information in option flow |

Shape caveat (stated honestly, per H-013 precedent): this is again a BTC/ETH
long/flat regime book — the refuted `F-SENTIMENT` had the same shape; the
realized position series may correlate with H-013's even though the data and
mechanism differ. **Mandatory Stage-3 preflight:** family-minting checker vs
the `F-FUNDING-XS-DISPERSION` and `F-OI-POSITIONING` reference series (the
only available references); `ASSIGN` folds budgets per I27.

## Stage-2 feasibility (E-042, ran 2026-07-13)

Data availability PASS — see `results/idea_batch_20260713_taxonomy_003/feasibility.json`
(`c1_optflow`): 22,126/22,125 hourly rows, coverage ≥ 0.99986, max gap 2h,
bucket-end labeling 100%, frozen-feed zero-Δ 0.0. Availability only: no
signal metric was computed (I13 clean). Distinctness and cost-after-edge
remain Stage-3 preflight items.

## Hand-off to Stage 3 — PENDING USER SIGN-OFF

Per the 2026-07-13 user ruling, Claude (not Codex) implements this round
end-to-end when authorized: research backtest module patterned on
`backtesting/oi_positioning_backtest.py` (published_at as-of sampling, t+1
shift, corrected vol-target path, retained CPCV `path_returns`, caller-
declared `n_trials=4`, leak tests for both known classes), registered in
`backtesting/pipeline_stage3_registry.py`; stop at checkpoint ①. No adapter,
promotion, demo, shadow, or live work.

## Scope / role

Claude-authored research/design output plus the E-042 availability probe.
No trading-core, config, gate, or engine file changes.

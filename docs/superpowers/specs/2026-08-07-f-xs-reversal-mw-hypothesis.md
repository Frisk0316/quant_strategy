---
status: current
type: spec
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# H-047 F-XS-REVERSAL-MW — multi-week cross-sectional reversal

Admitted via `tasks/2026-08-07-s001-s002-candidate-packets.md` (S-001; every
computable gate passed, B3 gross/cost 10.6 conservative). Family minted by
user I27 ruling 2026-08-07. Registered as H-047/E-096 (planned).

**Citation.** Kiefer & Nowotny (2026), "Reversal in Cryptocurrency Returns",
SSRN 6703978 — 70 USDT-quoted Binance tokens, 2021-01..2026-03: losers over
the prior 8–10 weeks outperform winners; baseline L/S Sharpe 0.96 (NW
t = 2.10), high-vol subset 1.37. Corroboration: Dobrynskaya, SSRN 3913263
(2014–2020 reversal beyond one month). Boundary evidence: Zaremba et al.,
IRFA 2021 — at the one-day horizon reversal is an illiquidity artifact and
large caps show daily momentum, so the mechanism is strictly multi-week.

**Mechanism.** Delayed correction of multi-week overreaction. The paying
counterparty is the trend-extrapolating buyer of recent multi-week winners.

**Distinct from consumed families because** the sign is opposite to
F-XS-MOMENTUM (correction vs continuation), the input is raw trailing
return not a factor residual (vs F-S5-RESIDUAL-MEANREV), and the horizon is
8–10 weeks, not days. Both neighbors are K-exhausted; neither saved dated
returns, so distinctness is decided at the SIGNAL level (below).

**Data.** Source-aware canonical 1m Binance candles → daily closes,
2024-01-01..2026-06-16 (A1-verified 2026-08-07: 43,587,613 rows, 36
inst_ids); PIT universe `data/universe/universe_membership.parquet`
(101,910 rows, 43 symbols). E-095 precedent coverage 17,271/17,272
member-days at the 0.95 threshold.

**Hypothesis.** See the H-047 ledger row (identical wording).

**Frozen single cell (E-096; NO grid — any grid extension consumes family
trials per R6.3):**

- Universe: PIT-eligible members, ADR-0015 aliases applied.
- Formation: trailing 63 trading days ending 7 calendar days before the
  rebalance timestamp (8–10-week window, 1-week skip vs STR).
- Book: quintile sort; equal-weight long bottom / short top quintile;
  nine overlapping weekly sub-books (Jegadeesh-Titman calendar-time);
  weekly rebalance; lagged 17.5% vol target (E-075 precedent).
- Costs: 8 bps round trip on traded notional; funding spread measured from
  `funding_rates`, never assumed away.
- Window: 2024-01-01..2026-06-16; first tradable rebalance after warmup.

**Decisive Stage-2 gates (ex ante, ADR-0013 four checks + two mint-apart):**

1. `data_availability`: ≥ 0.95 member-day coverage (E-095 contract).
2. Mint-apart A: abs corr of the formation signal vs the H-002 momentum
   signal reconstructed at its registered params, over the common window —
   gate 0.30 (E-075 precedent). Breach ⇒ ASSIGN per I27 ⇒ candidate closes
   (F-XS-MOMENTUM has no K).
3. Mint-apart B: abs corr vs the H-038 residual-z signal reconstructed per
   its spec — gate 0.30. Breach ⇒ closes (F-S5 terminal).
4. `cost_after_edge` and `statistical_power` per the registered evaluator,
   with breadth DERIVED from the actual position matrix using the canonical
   formula string
   `mean_d(count_i(abs(actual_position[d,i]) > 0)), aligned to daily return observations`
   (must match `BREADTH_FORMULAS` in `backtesting/pipeline_round_runners.py`
   verbatim). Fail-closed breadth 1 cannot pass (floor 1.05 vs plausible
   ~0.91); the packet's viability line is derived breadth ≥ 3 AND
   attenuation ≤ 25%. If derived breadth < 3, power fails — stop, no grid.

**Required artifact contents (closes the E-014 dated-returns gap class):**
the four checks; the dated daily L/S return series; the daily position
matrix; both mint-apart correlations with their common-day counts; derived
breadth + n_obs; SHA-256 manifest. Immutable once written.

**Stop rules.** Any gate FAIL stops before the (nonexistent) grid: zero
trials, K 0/2 untouched, no retune, no sign flip, no Stage 3, no promotion
or deployment claim. Stage 3 requires separate explicit user authorization.

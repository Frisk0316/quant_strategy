---
status: accepted
type: design
owner: claude
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# F-VOL-REGIME-OPT — Stage 1 Hypothesis (Deribit inverse-options vol regime)

Strategy Research Pipeline Stage 1 output for `H-014`. Not a promotion claim;
nothing here is wired into any gate. Second candidate from the Deribit data
workstream. User rulings 2026-07-13: (1) this is a **new family**
`F-VOL-REGIME-OPT`, distinct from `F-VRP-TIMING` (same VRP state variable,
different instrument and return source — option premium vs directional perp);
(2) Stage-1 probe approved; (3) **final target is the two-sided regime switch
(Option C below)**, reached in stages.

- **family_id:** `F-VOL-REGIME-OPT` (new family; `prior_family_n_trials = 0`)
- **Backlog source:** 2026-07-13 user strategy request (Deribit BTC/ETH
  coin-margined options; covered call; sell premium when vol is "super high",
  buy premium when "super low"); literature survey in References below.

## Design-space expansion (per `docs/DESIGN_SPACE.md`)

**Problem:** turn "sell options when volatility is super high, buy when super
low" into ONE falsifiable, small-grid hypothesis on Deribit BTC/ETH
coin-margined (inverse) options, with a regime definition that measures
*richness* (IV vs expected RV), not raw IV level.

**Constraints:** hard — no options execution adapter, no options backtest
engine, no historical option-chain data in this repo (DVOL index + flow
aggregates only; surface snapshots are forward-only from 2026-07); inverse
options settle in coin, so the put side carries wrong-way risk (payoff
`max(K−S,0)/S` in coin is unbounded as S→0 while collateral collapses);
DSR/PSR ≥ 0.95 gates; small pre-registered grid; K = 0/2. Soft — coin
(BTC/ETH) is the accounting unit for this book, per the user's framing.

**Option A — smallest change:** research-only probe, no execution: classify
regimes from existing DVOL + realized vol and measure synthetic option-payoff
separation across regimes. Blast radius: zero trading-core files.

**Option B — regime-filtered covered call only:** sell 30d ~25Δ calls on held
coin when the regime is rich, else hold coin. Bounded coin loss (short inverse
call payoff ≤ 1 coin), directly comparable to the Anchorage covered-call
study; needs only single-leg expiry settlement to backtest. Failure mode:
sustained breakout bull markets bleed coin through the strike.

**Option C — two-sided vol switch (USER-SELECTED FINAL TARGET):** rich regime
→ sell 30d ~25Δ strangle with the put side as a **put spread** (long a
further-OTM put) to cap the coin-denominated crash tail; cheap regime → long
30d ATM straddle; normal → flat. Failure modes: short leg dies by jump (gamma
loss is quadratic in the move), long leg bleeds because average VRP > 0 makes
unconditional long vol negative-carry.

**Axis:** risk containment and testability vs completeness of the user's
economic idea.

**Decision:** staged — A now (this spec's probe E-039), B as the first
tradable/backtestable leg, C as the final target once the options backtest
capability exists. The put side of C is a spread, not a naked put, because of
the inverse-payoff wrong-way risk; the cheap-regime long leg stays OFF by
default until probe/Stage-3 evidence shows the cheap bucket is not
negative-carry (literature says unconditional long vol loses to positive VRP).

**Would change if:** the E-039 probe shows regime buckets do NOT separate
synthetic payoffs (kills the mechanism); or the Stage-3 family-minting checker
returns `ASSIGN` vs `F-VRP-TIMING` (fold per I27); or BTC VRP is shown to have
structurally decayed (Chicago Fed WP-2025-17 pattern).

**User sign-off:** APPROVED 2026-07-13 in-session (new family + probe + C as
final target). This authorizes Stage-1 probe E-039 only — no Stage-3 grid, no
adapter, no engine work, no promotion claims.

## Hypothesis (falsifiable)

A daily-signaled Deribit BTC/ETH inverse-options book that (i) in the RICH
regime sells 30d ~25Δ covered calls (and, in the C target, a 25Δ/10Δ put
spread), (ii) in the CHEAP regime buys 30d ATM straddles, and (iii) is flat
otherwise, earns a positive **coin-denominated** net-of-cost return per
30d cycle whose Sharpe survives WF/CPCV with **DSR ≥ 0.95 and PSR ≥ 0.95**,
where regimes are defined ex-ante as:

- RICH: DVOL IV-percentile over trailing 365d ≥ `ivp_min` AND VRP z-score
  (DVOL − trailing RV, normalized over 90d) ≥ `z_min`
- CHEAP: IV-percentile ≤ 20 AND VRP z ≤ 0 (fixed, not grid)
- NORMAL: otherwise → flat

## Pre-registered grid (BEFORE any probe ran; deliberately small)

`{ivp_min ∈ [75, 85], z_min ∈ [0.5, 1.0]}` → **4 combos**.
Fixed, not grid: tenor 30d, short-call delta 25, put-spread deltas 25/10,
RV window 28d, VRP normalization window 90d, CHEAP thresholds (20 / 0.0),
daily signal with non-overlapping position cycles at Stage 3.
`prior_family_n_trials = 0` → first Stage-3 CPCV `n_trials = 4`.
Power note: 2 correlated symbols, observed-Sharpe bar ≈ 1.7 at n=4; a
marginal fail is a plausible outcome and carries no retry entitlement.

## Stage plan

1. **E-039 (this task, 0 trials, no K):** synthetic-pricing probe. Data:
   daily DVOL (2021-03→now) and daily settlement-proxy closes from the Deribit
   public API (no chain data needed). Price 30d legs with Black-Scholes at
   IV = DVOL, hold to expiry, measure coin-PnL distributions per regime bucket
   at FIXED illustrative thresholds (ivp 80 / z 1.0 — midpoint of grid, no
   selection). Purpose: does the regime classifier separate outcomes at all,
   and is the CHEAP-bucket long straddle non-negative? Known biases, stated
   ex-ante: flat smile (25Δ call IV = DVOL understates skewed wings), vanilla
   instead of inverse pricing, daily close instead of 08:00 UTC delivery TWAP,
   premium haircut 5% for fees+spread. These bias *levels*, not the
   *between-bucket separation* the probe tests.
2. **Stage 2 (separate task):** real-premium spot-check with Tardis.dev
   first-of-month free CSVs to calibrate the synthetic-pricing bias, plus the
   standard feasibility artifact (`stage2_feasibility.json`).
3. **Stage 3 (Codex, needs user authorization):** Option B leg first (single
   leg, expiry settlement, coin accounting) through fold-refit WF/CPCV with
   the 4-combo grid; family-minting distinctness run vs `F-VRP-TIMING`,
   `F-FUNDING-XS-DISPERSION`, `F-OI-POSITIONING`. Option C legs only after B
   evidence review. Inverse-option coin accounting is a new DOMAIN_RULES area:
   requires a Change Manifest and ADR before any engine work.

## E-039 probe outcome (ran 2026-07-13, after pre-registration above)

Artifacts: `results/stage1_probe_20260713_f_vol_regime_opt/`. Per-symbol
coin-PnL per 30d cycle at the fixed midpoint thresholds:

| Leg | Bucket | BTC mean / hit | ETH mean / hit |
|---|---|---|---|
| Covered call | RICH | +2.35% / 0.94 | +1.74% / 0.91 |
| Covered call | NORMAL | −0.09% / 0.82 | −0.16% / 0.81 |
| Strangle + put spread | RICH | +3.83% / 0.90 | +2.66% / 0.78 |
| Strangle + put spread | NORMAL | −0.30% / 0.65 | −1.23% / 0.59 |
| Long ATM straddle | CHEAP | −3.17% / 0.29 | −5.21% / 0.25 |

Reading: (1) the regime classifier separates outcomes in the hypothesized
direction — unfiltered (NORMAL) short premium is ≈ zero-to-negative, exactly
the Anchorage full-cycle finding, while RICH-bucket short premium is strongly
positive; (2) the CHEAP-bucket long straddle FAILS its non-negativity check on
both symbols, so the C target's long leg stays OFF by default (an event-driven
trigger would be a separately registered twist); (3) the RICH bucket is thin —
49 BTC / 95 ETH overlapping days ≈ 2–4 non-overlapping cycles — so this is
mechanism support, not edge evidence. Stage-2 real-premium spot-check remains
required before any Stage-3 ask.

## Distinctness vs F-VRP-TIMING (H-013)

| | F-VRP-TIMING (H-013) | F-VOL-REGIME-OPT (this spec) |
|---|---|---|
| Instrument | BTC/ETH USDT perps | Deribit BTC/ETH inverse options |
| Position | Long/flat directional | Short/long premium, delta-capped |
| Return source | Underlying drift conditioned on VRP state | The VRP itself (IV−RV spread) as premium carry |
| Accounting | USDT | Coin (BTC/ETH) |

Same state variable (VRP z), different harvested premium — user-ruled new
family 2026-07-13. The Stage-3 quantitative minting check is still mandatory;
`ASSIGN` folds budgets per I27 and corrects the H-014 ledger row.

## Known gaps this spec does NOT close

No historical option-chain data (Tardis/Amberdata/Laevitas are the sources);
no options backtest engine (expiry settlement, coin margin, Greeks); no
Deribit trading adapter (existing four clients are data-only); coin-margined
PnL accounting absent from DOMAIN_RULES.

## References (retrieved 2026-07-13)

- Alexander & Imeraj, *The Bitcoin VIX and Its Variance Risk Premium* —
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3383734
- Alexander & Chen, *Inverse and Quanto Inverse Options in a Black-Scholes
  World* — https://arxiv.org/abs/2107.12041 (Mathematical Finance 2023:
  https://onlinelibrary.wiley.com/doi/10.1111/mafi.12410)
- Sepp & Lucic, *Valuation and hedging of cryptocurrency inverse options* —
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4606748
- *On the implied volatility of inverse options under stochastic volatility* —
  https://arxiv.org/html/2401.00539v3
- Deribit DVOL methodology — https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- Anchorage, *Systematic Covered Call Writing on Bitcoin* (2026-06) —
  https://www.anchorage.com/research/synthetic-yield-on-bitcoin-implementation-discipline-and-performance-boundaries-of-systematic-covered-call-writing
- *Risk Premia in the Bitcoin Market* — https://arxiv.org/html/2410.15195v2
- *Jump risk premia in the presence of clustered jumps* —
  https://arxiv.org/pdf/2510.21297
- *Volatility models for cryptocurrencies* (GARCH beats IV for RV forecasts) —
  https://www.sciencedirect.com/science/article/abs/pii/S1042443121001359
- Chicago Fed WP 2025-17, *The Decline of the Variance Risk Premium* —
  https://www.chicagofed.org/-/media/publications/working-papers/2025/wp2025-17.pdf
- Atanasova et al., *Illiquidity Premium and Crypto Option Returns* —
  https://acfr.aut.ac.nz/__data/assets/pdf_file/0006/969378/950002_Atanasova_Illiquidity-Premium-and-Crypto-Option-Returns.pdf
- Data: Tardis.dev (https://docs.tardis.dev/historical-data-details/deribit),
  Amberdata (https://www.amberdata.io/deribit-market-data), Laevitas
  (https://www.laevitas.ch/), CryptoDataDownload
  (https://www.cryptodatadownload.com/data/deribit/)

## Scope / role

Claude-authored research/design output plus the user-approved E-039 probe.
No trading-core, config, gate, engine, or adapter file changes.

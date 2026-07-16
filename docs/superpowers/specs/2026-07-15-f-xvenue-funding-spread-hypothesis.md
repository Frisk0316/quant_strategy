---
status: draft
type: design
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# F-XVENUE-FUNDING-SPREAD — Stage 1 hypothesis

Strategy Research Pipeline Stage-1 contract for `H-021` and
`idea_batch_20260715_taxonomy_004`. This is a research-only candidate, not a
promotion or deployment claim.

- **family_id:** `F-XVENUE-FUNDING-SPREAD` (provisional new family)
- **prior family trials:** 0
- **funding-proxy grid:** 4 combinations per run; family cumulative 8 after
  the F41-invalid E-053 and corrected E-054 reprobe
- **K budget:** 0/2; Stage-2-failed/data-blocked rows do not consume K

## Design-space expansion

**Problem:** express the C4 same-symbol cross-venue funding-divergence idea
using only locally available, point-in-time data without relabeling a failed
funding family or fabricating a Deribit execution leg.

**Hard constraints:** BTC/ETH only; Deribit `interest_1h` must be summed over
each completed Binance 8h funding interval; no use of overlapping Deribit
`interest_8h`; decision at event `t` applies no earlier than event `t+1`;
equal-USD-delta legs; all four cells are counted; no Stage-3 PnL claim without
venue-scoped Deribit perpetual prices and inverse-contract accounting.

**Option A — two-perp convergence (chosen):** long the lower-funding venue and
short the higher-funding venue. This directly expresses C4 and is distinct in
mechanism from single-venue carry and cross-symbol funding ranks.

**Option B — Binance-only positioning signal:** rejected because underlying
price beta would dominate the claimed cross-venue convergence mechanism.

**Option C — DVOL overlay on an existing funding strategy:** rejected because
it is an overlay/retry, not C4, and would need its own ex-ante rationale.

**Option D — stop at data inventory:** safest but does not answer whether the
funding component is even capable of covering two-leg costs.

**Decision:** Option A, with a funding-only Stage-2 proxy and an explicit full-
PnL data gate. **Would change if:** a reviewed strategy source changes the C4
mechanism, or authoritative Deribit perpetual price/contract inputs make a
full inverse-perp implementation possible.

## Falsifiable hypothesis

For both BTC and ETH, at least one common pre-registered parameter cell has
positive next-event cross-venue funding capture after complete two-leg
turnover costs under both the repository research defaults and a conservative
taker-cost stress. The candidate must also be feature-distinct from the
existing funding-carry and funding-XS mechanisms and must have the tradable
price/contract data required for Stage 3.

## Frozen signal and accounting contract

- **Window:** `2024-01-02T00:00:00Z <= t < 2026-07-03T00:00:00Z`.
- **Symbols:** BTC and ETH. Binance instruments are `BTC-USDT-SWAP` and
  `ETH-USDT-SWAP`; Deribit datasets are `funding_deribit_btc` and
  `funding_deribit_eth`.
- **Observed spread:** at each Binance 8h settlement `t`,
  `s_t = sum(Deribit interest_1h for t-8h < h <= t) - Binance funding_t`.
  All eight Deribit rows must be non-suspect, `rate_1h_decimal`, and published
  no later than `t`; otherwise that event is unavailable.
- **Forecast:** trailing mean of `s_t` over `L` completed events.
- **Entry/exit:** when flat, enter only if `abs(forecast) >= entry_bps`.
  Positive forecast means long Binance / short Deribit; negative means the
  reverse. Hold until forecast sign reversal; on reversal, reverse only if the
  threshold is met, otherwise go flat. The target formed at `t` first applies
  to the next 8h event.
- **Sizing:** each venue leg is 0.5 of pair NAV, so pair gross is 1.0. Funding
  capture is therefore `0.5 * position * s_t`, not the unscaled spread.
- **Turnover:** scalar position change equals total gross turnover across the
  two 0.5 legs. Include entry, sign flips, and a final forced exit.
- **Cost base:** repository research defaults, `fee_bps=2` plus
  `slippage_bps=2` per unit of leg turnover.
- **Cost stress:** `fee_bps=5` plus `slippage_bps=2` per unit of leg turnover.
  This is a conservative research stress, not a change to production config.
- **Grid:** `{L in [3, 9] completed 8h events, entry_bps in [1, 2]}` = 4.
  All four funding-proxy cells count as trials in E-053 even though no full
  price/basis PnL is claimed.

## Stage-2 gates

1. **Data availability:** each symbol needs at least 730 common days, >=99%
   Binance-event coverage, >=99% eight-hour Deribit alignment, no suspect/null
   rows, and >=95% venue-scoped Deribit perpetual 1m price coverage. Funding
   readiness and full-PnL readiness are reported separately; the overall check
   fails closed if either is missing.
2. **Distinctness:** daily C4 funding-spread features must have absolute
   correlation <0.70 to a Binance funding-level carry proxy and to a BTC/ETH
   cross-sectional Binance-funding proxy. This is provisional feature-level
   evidence; human mechanism review remains required.
3. **Cost after edge:** a cell passes only when aggregate lagged funding capture
   exceeds complete turnover cost for both BTC and ETH. The family check passes
   only if the same cell passes under both base cost and conservative stress;
   any missing 8h event fails this gate rather than compressing time.

## Stage-3 stop condition

No Stage-3 runner is authorized by this spec. The current engine has no
venue-scoped Deribit perpetual mark/OHLC series, no reviewed Deribit inverse-
perpetual collateral/PnL contract, and no config-owned Deribit fee/instrument
spec. A funding-only proxy cannot measure basis PnL, collateral FX, liquidation,
margin, or executable slippage. The pipeline must stop rather than substitute
the Deribit index price or call this a backtest.

## Stage-2 result (E-053/E-054)

- E-053 is invalid evidence: exact timestamp equality dropped jittered Binance
  settlements and evaluated the grid on only 1,782/2,739 events per symbol.
  The result was inspected, so its four proxy cells remain in trial accounting.
- F41/I41 now allows only <=1 second settlement-boundary canonicalization.
  E-054 reused the identical grid and corrected coverage to 2,739/2,739 for
  BTC and ETH (912.7 common days); family cumulative proxy trials are 8 and
  K remains 0/2 because neither row reached a valid Stage-3 validation.
- Provisional feature distinctness passes: max absolute correlation is 0.2921
  versus the funding-carry proxy and 0.1692 versus funding XS, below 0.70.
- Data availability fails: Deribit venue-scoped perpetual 1m coverage is 0%
  for both symbols. Funding is ready; full price/basis PnL is not.
- Cost-after-edge fails the frozen robust gate. At repo-default 2+2 bps,
  `L9/H1` and `L9/H2` are positive for both symbols. Under 5+2 bps, no BTC
  cell is positive (closest: `L9/H2`, -2.89 bps across only four episodes),
  so no cell passes both cost scenarios on both symbols.

**Verdict:** Stage-2 `FAIL`; H-021 is inconclusive/data-blocked. No Stage 3,
retune, CPCV, checkpoint, promotion, or deployment work may cite this round.

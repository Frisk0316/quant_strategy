---
status: current
type: spec
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Literature-backed slate, first two: H-030 / H-031

**Positioning (ADR-0016):** these are the first two entries of a slate being
built toward a complete round (≥8 verified-paper-backed new mechanisms + ≥2
existing-strategy iterations). Until the slate reaches the 10–15/8/2 contract
this remains a **limited probe**, per I53. Registered before any result exists.

**Why these two:** the H-024..H-029 post-mortem showed four of six recent
Stage-2 deaths were statistical-power fails on daily breadth-2 books (floors
0.85–1.26). H-030 attacks that structurally (intraday event counts in the tens
of thousands). H-031 is the strongest-mechanism candidate found (forced,
identifiable counterparty) even though its usable history is short.

---

## H-030 F-INTRABAR-PERIODICITY — quarter-hour boundary flow

**Citation.** Kim, Chan & Hansen, Peter Reinhard, "The Quarter-Hour Effect:
Periodic Algorithmic Trading and Return Predictability in Cryptocurrency
Futures", arXiv:2607.09426v2 (2026). Sample: six Binance USDT-margined
perpetuals, 2021-01-01 → 2024-10-31; independent data validation/replication
study commissioned by the authors.

**Mechanism / who is the counterparty.** Scheduled algorithms are synchronized
to the standardized 1/5/15/60-minute bar grid embedded in exchange APIs and
charting tools. Their order flow arrives in bursts at bar boundaries; liquidity
providers do not fully absorb these structural bursts, leaving predictable
post-boundary drift. The paying counterparty is the boundary-synchronized
algorithmic flow itself (a scheduling artifact, not an informed trade), which
is why the pattern is structural rather than competed away.

**What the paper actually claims (quoted).** "Opening returns are predictable
out of sample, while opening order imbalance predicts returns over four to
twelve hours, with much weaker effects at finer clock-time frequencies."
Quarter-hour openings show ~26% larger absolute returns than ordinary minutes.

**Honest limitations — read before trading this.**
- The paper does **not** address transaction costs anywhere. The 10-second
  horizon result is untradable for us (8 bps round trip cannot be recovered on
  a 10-second move); only the **4–12 hour order-imbalance horizon** is a
  candidate, and this spec tests only that.
- Sample ends 2024-10; our test window extends past it, so part of our
  evidence is genuine out-of-sample for the paper.
- **Distinctness risk is the kill criterion:** the signal is an order-imbalance
  predictor, and F-TAKER-FLOW (H-022) is shelved. The claimed distinction is
  *when* the flow is measured (quarter-hour boundary bursts, intraday horizon)
  versus *the level* of rolling taker pressure (cross-sectional, weekly). If
  the return streams correlate at or above the MINT threshold, the mechanism
  claim is false — stop at distinctness, do not reshape.

**Data.** Binance 1m canonical candles 2020+ (we hold these) plus per-minute
taker buy/sell volume parsed from `market_klines.raw_payload.raw[9]/[10]` —
the same fields `backtesting/taker_flow_probe.py` already parses, so no new
ingestion is required.

**Hypothesis (falsifiable).** On Binance BTC/ETH-USDT-SWAP, a long/flat
vol-targeted book that takes a position at quarter-hour boundaries in the
direction of that boundary minute's signed taker imbalance when |imbalance
z-score vs trailing 90d| ≥ z_cut, held for H hours and costed 8 bps round
trip per traded event, earns positive net-of-cost Sharpe surviving fold-refit
WF/CPCV with DSR ≥ 0.95 and PSR ≥ 0.95.

**Frozen grid (4 cells, ex-ante):** z_cut ∈ {1.5, 2.0} × H ∈ {4h, 12h}
(the paper's stated horizon band). Stage-2 proxy = first cell (1.5, 4h).

**Power inputs (honest).** Events = boundary minutes clearing the z gate.
Declare measured n_obs; breadth = 1.5 (BTC/ETH correlate); periods_per_year =
the realized traded-event rate, not 365. Expected n_obs is large (tens of
thousands), which is the point of this candidate.

**Distinctness references (gating, |corr| < 0.30 on daily-aggregated PnL,
≥365 common days):** F-TAKER-FLOW / E-059 (**mandatory, decisive**);
F-VOL-REGIME-OPT (`results/h014_stage3_20260714/combo_daily_returns.csv`).

---

## H-031 F-OPT-EXPIRY-GAMMA — expiration-day reversal under dealer short gamma

**Citation.** "Bitcoin option expiration, gamma exposure, and intraday price
reversals", Finance Research Letters (2026),
https://www.sciencedirect.com/science/article/pii/S1544612326008688 — verified
3-of-3 by adversarial review on 2026-07-29 for both the headline reversal and
its V-shape/negative-gamma conditioning. Supporting: Atanasova, Miao, Segarra
& Willeboordse, "Aggregate illiquidity and crypto option returns", Finance
Research Letters (2025), which builds an aggregate gamma inventory from
Deribit trade/quote data 2021–2024 and shows dealers trade *with* momentum
when inventory gamma is negative.

**Mechanism / who is the counterparty.** Option market makers who are net
short gamma must hedge pro-cyclically (buy as price rises, sell as it falls).
That forced, mechanical flow pushes price away pre-expiration and unwinds at
settlement — a V-shaped reversal. The forced counterparty is the hedging
dealer, and the flow is a hedging obligation rather than a view, which is why
it is not arbitraged away.

**Quoted claim.** Reversals "are concentrated on days with high at-the-money
open interest and are strongest when net gamma exposure is negative", and are
"typically V-shaped, with significantly negative pre-expiration returns
followed by reversal after expiry".

**Honest limitations.**
- **Dealer gamma is not directly observable in our data.** `optsurf_deribit_*`
  carries open interest by strike but is snapshot-only and starts accruing
  ~2026-07 — it has no usable history. A gamma proxy must therefore be built
  from cumulative `optflow_deribit_*` per-trade data (2024-01+), i.e. net
  customer buying by moneyness bucket since inception, which is an
  approximation with an unknown initial position. This is the same
  taker-flow-based approach practitioners use, and its weakness must be stated
  in the artifact, not hidden.
- Usable event history is therefore ~2024-01 onward: roughly 130 weekly
  Deribit expiries. That is a modest event count; the Stage-2 power screen may
  well fail, and that would be an honest stop, not a reason to widen the
  window.
- Max-pain/pinning framing was screened OUT: its support is practitioner
  commentary with recent contradicting episodes, not a rigorous study.

**Data.** Deribit `optflow_deribit_{btc,eth}` with moneyness buckets
(2024-01+, from the 2026-07-27 backfill) for the gamma proxy; Binance 1m
canonical candles for the price legs; Deribit expiry calendar (Fridays
08:00 UTC) derivable from instrument names already in the flow rows.

**Hypothesis (falsifiable).** On Binance BTC-USDT-SWAP, a long/flat book that
enters at expiry-day 08:00 UTC settlement in the direction OPPOSITE to the
prior D-day cumulative return, only on expiries where the flow-derived dealer
gamma proxy is negative and ATM bucket activity is in the top tercile, exiting
after H hours and costed 8 bps round trip, earns positive net-of-cost Sharpe
surviving fold-refit WF/CPCV with DSR ≥ 0.95 and PSR ≥ 0.95.

**Frozen grid (4 cells, ex-ante):** D ∈ {2d, 5d} × H ∈ {8h, 24h}.
Stage-2 proxy = first cell (2d, 8h).

**Power inputs.** n_obs = qualifying expiries (expect ~50–130 after
conditioning); breadth = 1.0 (BTC only — ETH expiries are simultaneous and not
independent); periods_per_year = realized expiry rate (~52). A power fail here
is a likely and acceptable outcome.

**Distinctness references (gating):** F-OPT-HEDGE-DEMAND / E-064 (nearest
options-flow neighbour, **mandatory**); F-VOL-REGIME-OPT; F-VRP-TIMING /
E-050 (advisory, both are options-derived vol conditioning).

---

## Slate pipeline — vetted, not yet registered (raw material for the complete round)

These cleared the literature bar in the 2026-07-29 research pass but are not
registered yet; each still needs a frozen signal/grid and a distinctness plan
before it becomes a hypothesis. Listed so the work is not lost.

| Candidate mechanism | Strongest citation | Our data | Main risk |
| --- | --- | --- | --- |
| Vol-of-vol predicts BTC excess returns; VRP sign turns time-varying once VoV is modeled | Du et al., "Pricing Cryptocurrency Options With Volatility of Volatility", *Journal of Futures Markets* (2025) | DVOL + RV30 2021+ | Adjacency to shelved F-VRP-TIMING — must mint apart on the VoV term, not the VRP level |
| Pre-FOMC drift and multi-day post-FOMC drift in BTC | "Do FOMC and macroeconomic announcements affect Bitcoin prices?", *Finance Research Letters* (2019); "Scheduled FOMC statements and intraday macro event risk in cryptocurrency markets", FRL (2026); NY Fed Staff Report 1052 | FRED + 1m candles; FOMC calendar is public and fixed | Only ~8 events/year (~48 usable) — power screen is the binding constraint |
| Variance decomposition: positive-jump and jump-robust variance predict *lower* subsequent weekly returns cross-sectionally | "Variance Decomposition and Cryptocurrency Return Prediction", *Journal of Financial and Quantitative Analysis* | 1m candles 2020+ (realized measures computable) | Distinctness vs shelved H-023/F-XS-IDIOVOL is decisive — the claim is that decomposed jump components carry information residual vol does not |
| Aggregate gamma inventory (dealer rebalancing pressure) drives option illiquidity and loads on the first priced factor | Atanasova, Miao, Segarra & Willeboordse, "Aggregate illiquidity and crypto option returns", FRL (2025) | optflow 2024+ (proxy build) | Same proxy weakness as H-031; likely overlaps H-031's family |

## Screened out during this research pass (recorded so they are not re-proposed)

- **Implied-volatility skew slope → returns.** "Implied volatility slopes and
  jumps in bitcoin options market" (Journal of Empirical Finance, 2024) finds
  both left and right IV slopes **lack** return predictability, though they do
  forecast weekly realized volatility. A skew-direction return strategy is
  therefore refuted before registration; only a vol-forecast use survives.
- **Max pain / expiry pinning.** No rigorous study; practitioner sources
  conflict.
- **Stablecoin exchange-flow signals.** Mechanism plausible (7–14 day
  correlation reported) but we hold **no on-chain stablecoin flow data**, so
  it is not testable here.
- **Overnight/hour-of-day seasonality (22:00–23:00 UTC).** Reported magnitude
  is small relative to transaction costs by the sources themselves.

---
status: current
type: spec
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Literature-backed slate, remainder: H-032 … H-037

Companion to `2026-07-29-literature-slate-h030-h031.md`. Together the two specs
carry **eight distinct new mechanisms** (H-030, H-031, H-032…H-037), which is
the ADR-0016 new-mechanism minimum. The round is still **not complete** until
≥2 eligible existing-strategy iterations join them and the 10–15 total is met —
see "Remaining gap" at the end. Registered before any result exists.

Shared conventions (unless a candidate overrides): Binance BTC/ETH-USDT-SWAP,
daily 08:00 UTC decisions, vol-targeted, 8 bps round trip per traded event,
Stage-2 four checks then a pre-registered 4-cell Stage-3 grid, DSR ≥ 0.95 and
PSR ≥ 0.95, no retune, one registry entry per executed candidate.

---

## H-032 F-VOL-OF-VOL — volatility-of-volatility as a return signal

**Citation.** Du et al., "Pricing Cryptocurrency Options With Volatility of
Volatility", *Journal of Futures Markets* (2025) — option-implied factors,
particularly VoV, predict BTC excess returns; modeling VoV explicitly lets the
variance risk premium take **time-varying signs** rather than the
predominantly-positive static VRP assumed elsewhere (adversarially verified
2-0, 2026-07-29).

**Mechanism.** VoV proxies uncertainty about future uncertainty. When VoV is
elevated, variance sellers demand more compensation and hedging demand is
front-loaded, so the risk premium embedded in the vol surface reprices; the
counterparty is the hedger paying up for convexity in uncertain regimes.

**Distinct from the refuted list because** it trades the *second moment of the
vol process* (VoV), not the VRP level — the exact quantity whose omission the
paper blames for the wrong static-sign conclusion that our shelved
F-VRP-TIMING assumed.

**Data.** DVOL 1h 2021-03+ (VoV = realized volatility of DVOL over a window),
RV30, canonical candles.

**Hypothesis.** A long/flat vol-targeted book that is long when VoV z-scores
≤ −z_cut vs its trailing W-day distribution (calm-uncertainty regime) and flat
otherwise earns positive net-of-cost Sharpe surviving fold-refit WF/CPCV with
DSR ≥ 0.95 and PSR ≥ 0.95. **Grid:** z_cut ∈ {1.0, 1.5} × W ∈ {90d, 180d}.
**Distinctness (mandatory):** F-VRP-TIMING E-050 and H-026/E-067 — if the VoV
signal cannot mint apart from the VRP-level signals, the paper's central claim
does not carry to our construction; stop.

## H-033 F-MACRO-EVENT-DRIFT — FOMC pre/post-announcement drift

**Citation.** "Do FOMC and macroeconomic announcements affect Bitcoin prices?",
*Finance Research Letters* (2019); "Scheduled FOMC statements and intraday
macro event risk in cryptocurrency markets", FRL (2026); Benigno & Rosa, "The
Bitcoin–Macro Disconnect", NY Fed Staff Report 1052. Reported: BTC ≈ +0.96%
the day before the announcement and ≈ −1% on announcement day, with a
significant multi-day post-meeting drift; a 1 bp unexpected tightening in the
2-year yield maps to ≈ −0.25% BTC.

**Mechanism.** Scheduled, calendar-known risk events force position adjustment
by leveraged and mandate-constrained participants around a fixed timestamp;
the pre-event risk premium and post-event repricing are the compensation.

**Distinct from the refuted list because** the trigger is an exogenous
macro calendar timestamp, not any crypto-internal price, funding, flow, or vol
state variable — none of the dead families conditioned on scheduled events.

**Data.** FOMC calendar (public, fixed); FRED 2-year yield for the surprise
proxy; canonical candles.

**Hypothesis.** A long/flat book long from T−1 close to the announcement, and
positioned post-announcement in the direction implied by the sign of the
2-year-yield surprise for H days, earns positive net-of-cost Sharpe surviving
fold-refit WF/CPCV with DSR ≥ 0.95 and PSR ≥ 0.95. **Grid:** pre-window ∈
{1d, 2d} × H ∈ {2d, 5d}. **Honest constraint:** only ~8 events/year (~48
usable since 2020); the Stage-2 power screen is the binding gate and a fail
there is the expected modal outcome. Do not widen the window to manufacture
power.

## H-034 F-VARIANCE-DECOMP — jump-component variance in the cross-section

**Citation.** "Variance Decomposition and Cryptocurrency Return Prediction",
*Journal of Financial and Quantitative Analysis* — cryptocurrencies with higher
realized variance earn **lower** subsequent weekly returns, and the negative
predictability is attributable specifically to the **positive-jump** and
jump-robust variance components.

**Mechanism.** Lottery-like demand concentrates in assets with recent upside
jumps; that demand is overpriced and mean-reverts. The paying counterparty is
the retail lottery buyer.

**Distinct from the refuted list because** the signal is a *decomposition* of
realized variance into positive-jump / negative-jump / continuous parts, and
the paper's finding is that the predictive content sits in components that a
single residual-volatility measure averages away — the exact measure our
shelved H-023/F-XS-IDIOVOL used. **Distinctness vs E-062 is the decisive gate.**

**Data.** 1m canonical candles 2020+ across the point-in-time USDT-perp
universe (realized semivariance and jump measures computable intraday).

**Hypothesis.** A weekly, dollar-neutral cross-sectional book long the lowest
and short the highest positive-jump-variance quintile earns positive
net-of-cost Sharpe surviving fold-refit WF/CPCV with DSR ≥ 0.95 and PSR ≥ 0.95.
**Grid:** lookback ∈ {7d, 28d} × quantile ∈ {quintile, tercile}.

## H-035 F-OPT-LARGE-TRADE-INFO — informed large option trades

**Citation.** "Net buying pressure and the information in bitcoin option
trades", *Journal of International Financial Markets, Institutions & Money*
(2022) / arXiv:2109.02776 — ATM option prices are driven largely by volatility
traders, while **OTM options are additionally driven by traders with
proprietary information about future bitcoin price movements**, and
**transaction size is a significant determinant of price leadership**, with
larger trades reflecting informed behaviour.

**Mechanism.** Informed traders choose OTM options for leverage and choose
size when conviction is high; dealers absorbing those trades hedge into spot,
transmitting the information with a lag.

**Distinct from the refuted list because** the conditioning variable is
**trade size** (informed-trade identification), not aggregate directional
flow. Our refuted H-015 used the aggregate put/call taker-buy imbalance and our
inconclusive H-024 used the OTM put-buy *share* — neither conditioned on size,
which is precisely the variable the paper identifies as carrying the
information. **Distinctness vs E-044 and E-064 is mandatory and decisive.**

**Data.** `optflow_deribit_*` per-trade rows with amounts and moneyness
buckets, 2024-01+ (from the 2026-07-27 backfill).

**Hypothesis.** A long/flat book positioned in the direction of the net
signed premium of **top-decile-size OTM option trades** over a trailing L
hours, when that measure z-scores ≥ z_cut, earns positive net-of-cost Sharpe
surviving fold-refit WF/CPCV with DSR ≥ 0.95 and PSR ≥ 0.95. **Grid:**
z_cut ∈ {1.0, 1.5} × L ∈ {24h, 72h}. **Constraint:** ~2.5 y of history and the
newest ~1 day lacks bucket fields until archive catch-up.

## H-036 F-XASSET-MACRO-LEAD — cross-asset macro state leads crypto

**Citation.** IMF Working Paper 2023/213, "New Evidence on Spillovers Between
Crypto Assets and Financial Markets"; Köse et al., *Journal of Forecasting*
(2025) — gold is the most relevant global determinant of BTC, followed by the
US dollar index; BTC behaves as a risky asset, responding negatively to VIX
increases during turbulence, with significant spillovers from USD, gold, and
oil.

**Mechanism.** Crypto is a high-beta risk asset held by cross-asset allocators
whose risk budgets are driven by global volatility and dollar liquidity;
their rebalancing arrives with a lag relative to the macro signal.

**Distinct from the refuted list because** every dead family used a
crypto-internal state variable; this uses exogenous cross-asset state (VIX,
DXY, gold) with no crypto input in the signal.

**Data.** FRED (VIX, broad dollar index, gold, 2-year yield) + canonical
candles. Daily frequency only.

**Hypothesis.** A long/flat book flat when the cross-asset risk state (VIX
z-score up and dollar-index z-score up, both vs trailing W days) is adverse,
long otherwise, earns positive net-of-cost Sharpe surviving fold-refit WF/CPCV
with DSR ≥ 0.95 and PSR ≥ 0.95. **Grid:** z_cut ∈ {1.0, 1.5} × W ∈ {60d, 180d}.
**Honest constraint:** daily breadth-2 design — the same shape that failed on
power four times in the H-024..H-029 batch; it earns its place on mechanism
novelty, not on power, and should be expected to be power-marginal.

## H-037 F-CME-LEADERSHIP — regulated-venue price leadership

**Citation.** "Price discovery in bitcoin spot and futures markets", *Journal
of International Money and Finance* (2025) — the CME bitcoin futures market
plays a leading role in price formation, with transaction size a critical
determinant of leadership.

**Mechanism.** Institutional flow that cannot access offshore perps expresses
views on CME first; that information propagates to perps, especially across
CME's closed sessions (nights/weekends) when the information cannot be
immediately arbitraged.

**Distinct from the refuted list because** shelved H-010/F-XVENUE-LEADLAG
compared two offshore perp venues trading continuously; CME is a
different-hours, different-clientele regulated venue, so the mechanism is a
session-boundary information gap rather than a continuous microstructure lag.

**Data.** CME BTC futures daily + canonical candles.

**Hypothesis.** A long/flat book positioned over the CME-closed session in the
direction of the CME settlement-to-settlement move when |that move| ≥ x_cut
earns positive net-of-cost Sharpe surviving fold-refit WF/CPCV with DSR ≥ 0.95
and PSR ≥ 0.95. **Grid:** x_cut ∈ {0.5σ, 1.0σ} × session ∈ {overnight, weekend}.
**Honest constraint (weakest of the eight):** we hold CME data at **daily**
resolution only, so the intraday leadership the paper measures is not directly
testable; this tests a coarse session-boundary implication of it. Distinctness
vs H-010/E-057 and the existing `cme_gap_fill` research baseline is mandatory.

---

## Iteration-eligibility audit (2026-07-29) — only ONE qualifies

Every family with remaining K budget was checked against I28 (a refuted /
shelved / inconclusive family may only be re-entered with an explicit twist,
never as a bare rerun). Result:

| Family | K | Prior outcome | Eligible? |
| --- | --- | --- | --- |
| F-S5-RESIDUAL-MEANREV | 1/2 | E-014 produced **no grid activity** — recorded explicitly as "a data-universe artifact, not strategy refutation or support" | **YES** — the blocker was data, and the data has since been materially repaired (ADR-0014 source-aware canonical candles, ADR-0015 economic-asset aliases, universe rebuild). Same class of legitimate data-repair twist that justified E-059 for H-022. |
| F-S7-BASIS-MEANREV | 1/2 | E-016 statistical fail (WF −0.44, CPCV −1.11) | No — bare rerun would be gate-chasing |
| F-S6-TS-MOMENTUM | 1/2 | E-015 statistical fail (WF 0.009, DSR 0.20) | No — same |
| F-FUNDING-CARRY | 1/2 | E-026 refuted after realism re-cost | No — terminal |
| F-FUNDING-XS-DISPERSION | 1/2 | E-063 retry already failed | No — twist already spent |
| F-XS-ILLIQUIDITY | 0/2 | E-045 statistical fail | No twist available |
| F-STABLECOIN-LIQUIDITY | 0/2 | E-046 WF −0.91, labelled one-regime inconclusive | No — deeply negative WF; more regimes is not a mechanism twist |
| F-ONCHAIN-FLOW | 0/2 | E-048 WF −0.22, breadth-1 | No |
| F-XVENUE-LEADLAG | 0/2 | E-057 shelved on missing OKX funding | No — blocked on data we do not have |
| F-XVENUE-FUNDING-SPREAD | 0/2 | E-056 refuted at Stage-3 full PnL | No — explicitly terminal |
| F-OPT-HEDGE-DEMAND | 0/2 | H-024 inconclusive, observed Sharpe 0.17 vs floor 1.26 | No — data accrual cannot close a gap that size; proposing it would contradict the honest read already recorded |

**Consequence, stated plainly:** the ADR-0016 8/2/10 contract **cannot honestly
be met today**. One eligible iteration exists, not two, and manufacturing a
second would require exactly the gate-chasing the rules forbid. A manifest
built from this slate will therefore be labelled `limited_probe` by
`pipeline_round.validate_round_manifest` — which is the validator working
correctly, not a defect.

The honest routes to a second iteration are (a) wait for a currently-blocked
family's data to arrive (e.g. OKX funding for F-XVENUE-LEADLAG), or (b) let one
of the eight new mechanisms fail in a way that produces a genuine twist for an
existing family. Neither is available on demand.

## Remaining gap to a complete ADR-0016 round

1. **≥2 eligible existing-strategy iterations** — audited above: only 1
   (H-038). Blocking.
2. **10–15 total** executable candidates — currently 8 new + 1 iteration = 9.
   Blocking.
3. **Registered deterministic Stage-2 runners** for each counted candidate
   (ADR-0016 phase 3): every candidate still needs a probe module before it is
   "execution ready" for a sealed manifest. Blocking.

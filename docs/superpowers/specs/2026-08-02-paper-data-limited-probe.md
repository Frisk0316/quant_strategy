---
status: current
type: specification
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# 2026-08-02 paper-data limited probe — pre-registration

## Authority and claim boundary

This research run is authorized by the user's 2026-08-02 request to mine
free data and papers, backtest applicable strategies, and report usable,
near-threshold, and promising directions.

The run is intentionally an **incomplete ADR-0016 round / limited probe**.
Primary-source research found five genuinely new, paper-backed mechanisms that
can be expressed honestly with data available or downloadable in this session,
plus two material iterations of data-blocked macro hypotheses. It did not find
eight genuinely distinct, execution-ready new mechanisms. Parameter variants,
near-duplicate families, unavailable data, and unverified papers are not used
to inflate the count. The run must always report:

- `round_type: limited_probe`;
- `complete_round: false`;
- `portable_validation_gate: false`;
- `promotion_gate_passed: false`;
- `live_trading_authorized: false`.

Passing Stage 2 permits deterministic Stage 3 only. Passing the statistical
gate remains research evidence, not demo, shadow, promotion, or live authority.

## Design-space expansion

| Option | Smallest implementation | Benefit | Binding problem | Decision |
| --- | --- | --- | --- | --- |
| A. Research report only | Cite papers and inventory data without executing signals | No code or result risk | Does not satisfy the user's backtest request | Reject |
| B. Finish all ADR-0016 automation phases | Generalize the legacy registry/orchestrator for arbitrary candidates | Could support future complete rounds | Large refactor; current manifest drops executable contracts and no honest eight-new slate exists | Defer |
| C. Narrow table-driven limited probe | Reuse external observations, PIT prices, Stage-2 power, WF, and CPCV in one deterministic runner | Executes every honest candidate while preserving fail-closed gates | Cannot be called a complete round | **Select** |
| D. Split papers into parameter/data-source variants until the slate reaches ten | Minimal apparent execution work | Produces a nominal quota | Violates I53/ADR-0016 distinctness and hidden-trial rules | Reject |

The decision changes only if additional verified papers yield genuinely new
mechanisms with available data and registered deterministic runners. Same-run
results cannot be used to manufacture replacements or retune a candidate.

## Discovery and deduplication funnel

| Direction considered | Funnel decision | Reason |
| --- | --- | --- |
| Wikipedia trend-conditioned attention | Counted new mechanism | Auditable CC0 data and a paper-specific interaction distinct from Fear & Greed |
| Active-address network adoption | Counted new mechanism | Blockchain fundamental distinct from the prior hash-ribbon timing rule |
| Severe USDT depeg next-day reversal | Counted new mechanism | Peg-price event, not prior stablecoin-supply H-017 |
| Cross-sectional salience | Counted new mechanism | State-dependent salience weighting, not momentum, idio-vol, or semivariance |
| CFTC participant-positioning regime | Counted new mechanism | Weekly participant composition, not exchange OI level H-012 |
| FOMC/yield post-publication repair | Counted existing iteration | DGS2 is now present, but the old decision-date join was not tradable; definition is repaired ex ante |
| Cross-asset macro state with official yield curve | Counted existing iteration | Replaces the unused/unavailable gold requirement and fixes business-day as-of coverage |
| GitHub technology-flaw shock | Rejected from executable slate | Paper-reported next-day edge is about 7 bps, below the frozen 8 bps round trip before classification error; no PIT classifier/data contract |
| Network adoption × hashrate as a second candidate | Deduplicated | Same paper/fundamental family; Coin Metrics Community disables free hashrate, so only the active-address leg is executable |
| Stablecoin exposure-off gate plus rebound as two candidates | Deduplicated | Same depeg event family; only the paper's severe-event next-day rebound implication is tested |
| Multiple CFTC categories/signs | Deduplicated | Same weekly participant-positioning mechanism; one frozen specification only |
| Settlement-latency-gated cross-venue dislocation | Rejected from new track | Existing H-010 cross-venue iteration and required PIT settlement-latency data are unavailable |
| Plain DeFi TVL or revenue multiple | Rejected | Recent evidence does not establish an independent premium after market exposure |
| H-038 S5 terminal retry | Rejected from this slate | Explicit terminal-K authorization was not obtained; the broad research request does not silently consume F-S5 K 2/2 |

## Frozen candidate slate

| ID | Track | Family | Paper provenance | Required data | Signal reference |
| --- | --- | --- | --- | --- | --- |
| H-040 | new research | F-WIKI-ATTENTION-TREND | Kristoufek (2013), DOI [10.1038/srep03415](https://doi.org/10.1038/srep03415) | `wiki_pageviews_bitcoin_en`, Binance BTC close/funding | `wiki_attention_trend` |
| H-041 | new research | F-NETWORK-ADOPTION | Bhambhwani, Delikouras, Korniotis (2023), DOI [10.1016/j.intfin.2023.101788](https://doi.org/10.1016/j.intfin.2023.101788) | `cm_btc_active_addresses`, `cm_eth_active_addresses`, Binance BTC/ETH close/funding | `network_adoption` |
| H-042 | new research | F-STABLECOIN-DEPEG-REVERSAL | Foley, Lee, Milunovich (2026), DOI [10.1111/acfi.70201](https://doi.org/10.1111/acfi.70201) | `cm_usdt_price_usd`, Binance BTC/ETH close/funding | `usdt_depeg_reversal` |
| H-043 | new research | F-XS-SALIENCE | Cai and Zhao (2024), DOI [10.1016/j.jbankfin.2023.107052](https://doi.org/10.1016/j.jbankfin.2023.107052) | PIT Binance USDT-perp universe, close/funding | `xs_salience` |
| H-044 | new research | F-CFTC-PARTICIPANT-REGIME | Hung, Liu, Yang (2021), DOI [10.1016/j.jempfin.2021.03.001](https://doi.org/10.1016/j.jempfin.2021.03.001) | `cot_cme_btc`, `cot_cme_eth`, Binance BTC/ETH close/funding | `cftc_participant_regime` |
| H-045 | existing iteration of H-033 | F-MACRO-EVENT-DRIFT | H-033 sources plus official FOMC calendar | `dgs2`, FOMC fixture, Binance BTC/ETH close/funding | `fomc_yield_published_iteration` |
| H-046 | existing iteration of H-036 | F-XASSET-MACRO-LEAD | H-036 sources; official yield-curve extension | `vixcls`, `dtwexbgs`, `dgs10`, `dgs2`, Binance BTC/ETH close/funding | `macro_state_yieldcurve_iteration` |

The literature count is five, the iteration count is two, and the executable
slate count is seven. These values are deliberately below the complete-round
8/2/10 minimum and must not be relabeled after results are known.

## Shared data, timing, PnL, and validation contract

- Market data: Binance `canonical_candles`, `bar='1m'`,
  `source_primary='binance'`, `quality_status!='suspect'`; daily close is the
  last retained minute for each UTC day.
- Funding: Binance-only `funding_rates`, daily **sum** of actual settlements.
  A long pays positive funding and a short receives it.
- External features: `external_observations` excluding `quality_status='suspect'`;
  a row is unavailable before its stored `published_at`.
- Execution: every target is shifted by one full daily bar. An external row
  first usable on day `t` cannot affect gross return, funding, turnover, or cost
  before day `t+1`.
- PnL: `gross = sum(executed_weight * close_return)`;
  `funding = -sum(executed_weight * daily_funding_rate)`;
  `turnover = sum(abs(executed_weight.diff()))`;
  `cost = turnover * 4 bps`, representing 2 bps fee plus 2 bps slippage per
  one-way notional. A complete entry and exit costs 8 bps.
- Position scale: gross absolute target exposure is at most 1.0; no leverage,
  volatility target, or hidden optimizer.
- Formal market window: `[2020-01-01, 2026-07-29)` where the candidate's
  feature history permits; H-043 uses `[2024-01-01, 2026-06-17)` because the
  PIT derivatives universe begins there.
- Stage 2: data availability, quantitative/mechanism distinctness,
  cost-after-edge, and statistical power must all pass.
- Cost-after-edge: annualized engine-net Sharpe must be strictly positive and
  mean weekly engine-net return must be strictly positive.
- Power: existing `min_detectable_sharpe`, candidate breadth, actual daily
  observations, one prospective trial, and measured sample skew/kurtosis.
- Distinctness for new families: absolute return correlation below `0.70`
  against BTC buy-and-hold, BTC/ETH equal-weight buy-and-hold, E-031 funding
  dispersion, and every retained E-045 XS-illiquidity cell. Each required
  comparison needs at least 365 common days and nonzero variance; undefined
  fails closed per I42.
- Existing iterations remain assigned to their existing family. Correlations
  are advisory; no new-family mint is attempted.
- Stage 3 is pass-only: walk-forward 365/90 and CPCV N=6, k=2, embargo 2%,
  purge 1, with caller-declared family-cumulative `n_trials=1`. Raw CPCV path
  returns (or combined returns) and periods/lengths must be retained.
- Statistical pass: DSR >= 0.95, PSR >= 0.95, DSR <= PSR, nonzero activity,
  and reconciled trial count. Promotion remains false.

## Frozen signal definitions

### H-040 — Wikipedia attention conditioned on the 7-day trend

1. Use English Wikipedia `Bitcoin` daily human pageviews, all access modes.
2. Use the log change in views. Attention is rising only when the change is
   strictly positive.
3. On rising-attention days, target +1 BTC when close is above its trailing
   seven-day moving average and -1 when below; otherwise target zero.
4. Align the observation to stored D+1 publication and apply the shared t+1
   execution lag. No alternative page, language, threshold, or MA is tested.

### H-041 — active-address network adoption

1. For BTC and ETH separately, compute seven-day log growth in Coin Metrics
   active addresses.
2. At the fixed weekly rebalance, target +0.5 in a coin when growth is positive
   and -0.5 when negative; missing or zero growth receives zero weight.
3. Hold until the next weekly rebalance. Publication alignment and t+1 apply.
4. This tests a network-adoption implication only; it does not claim the
   paper's unavailable free hashrate/security leg.

### H-042 — severe USDT depeg next-day reversal

1. On Coin Metrics USDT/USD, define a severe negative event only when price is
   below 0.99 and its expanding-past 60-day z-score is at most -3.0.
2. After publication and the shared t+1 lag, hold +0.5 BTC and +0.5 ETH for one
   daily return, then exit.
3. No contemporaneous exposure-off claim is tested, avoiding same-day
   lookahead and duplicate depeg-family hypotheses.

### H-043 — cross-sectional salience

1. For every eligible PIT asset, calculate daily return relative to that day's
   equal-weight universe return.
2. Over the trailing seven days use
   `sigma = abs(r_i-r_m)/(abs(r_i)+abs(r_m)+theta)`, `theta=0.1`.
3. Rank each day within the window from most to least salient. Set raw decision
   weights to `delta^(rank-1)`, `delta=0.7`, normalize them to mean one, and
   calculate `ST = mean(weight*r_i) - mean(r_i)`.
4. Weekly, long the bottom ST quintile and short the top ST quintile, equal
   weighted within legs, dollar neutral, with at least two assets per leg.
5. Hold to the next weekly rebalance; PIT eligibility is applied before ranks;
   t+1 execution applies. No alternative formation, delta, theta, or quantile.

### H-044 — CFTC leveraged-money participant regime

1. For each CME BTC/ETH report compute leveraged-money net position divided by
   open interest using the retained official fields.
2. At each release compute its change over four released reports; target +0.5
   in the matching crypto if positive and -0.5 if negative.
3. Hold until the next release. Tuesday report dates are never tradable before
   the official following-Friday publication timestamp and shared t+1 lag.
4. The paper motivates participant composition and price discovery, not a
   guaranteed return sign; the directional mapping is the falsifiable transfer
   hypothesis tested here.

### H-045 — H-033 publication-safe FOMC/yield iteration

1. Calendar leg: because the decision date is public ex ante, hold an
   equal-weight long BTC/ETH book from the prior UTC close into the decision
   date, paying a full round trip.
2. Yield leg: compute the DGS2 change attached to the decision observation,
   but do not use it before the row's stored D+1 `published_at`. After the
   shared execution lag, hold `-sign(change)` in equal-weight BTC/ETH for two
   days, then exit.
3. Combine nonoverlapping calendar and yield legs. This explicitly replaces
   the old decision-date match; it is a material iteration, not a silent fix to
   the immutable E-072 definition.

### H-046 — H-036 publication-safe macro state with official yield curve

1. Construct VIX, broad-dollar, and `DGS10-DGS2` curve series from values
   available by `published_at` only.
2. Forward-fill onto calendar days for at most seven days. Longer gaps are
   missing and fail coverage rather than being silently carried forever.
3. Compute 60-day z-scores using a distribution shifted one day.
4. Risk-off votes are VIX z >= 1, dollar z >= 1, and curve z <= -1. When at
   least two votes are true, target zero; otherwise target +0.5 BTC/+0.5 ETH.
5. Apply shared t+1 execution. The official yield curve replaces the obsolete,
   unused gold requirement; no Yahoo gold proxy is promotion evidence.

## Pre-registered experiments

| Experiment | Candidate | Planned action | Prospective trials |
| --- | --- | --- | ---: |
| E-077 | H-040 | Stage 2; pass-only Stage 3 | 1 |
| E-078 | H-041 | Stage 2; pass-only Stage 3 | 1 |
| E-079 | H-042 | Stage 2; pass-only Stage 3 | 1 |
| E-080 | H-043 | Stage 2; pass-only Stage 3 | 1 |
| E-081 | H-044 | Stage 2; pass-only Stage 3 | 1 |
| E-082 | H-045 | Stage 2; pass-only Stage 3 | 1 |
| E-083 | H-046 | Stage 2; pass-only Stage 3 | 1 |

The execution evidence will append E-084 through E-090. A Stage-2 stop consumes
zero grid trials/K. A Stage-3 execution consumes the one frozen prospective
trial for that family. No same-run retry is allowed.

## Data-license and deployment boundary

- Wikimedia Pageviews is documented under CC0 and is the cleanest new source.
- Coin Metrics Community access is keyless but its free/community license is
  research/noncommercial; H-041/H-042 can only be research evidence until a
  compatible commercial license is approved.
- CFTC, Cboe, FRED, exchange, and Yahoo terms/attribution remain source-specific.
- Free access does not imply redistribution or commercial-live rights.
- No candidate in this run may become demo/live evidence from this artifact.

## Stop and reporting rules

- Missing or invalid data produces a named Stage-2 terminal fail/error; it is
  never proxied after results are visible.
- One candidate exception does not erase the remaining terminal evidence.
- Stage-2 failure creates no Stage-3 artifact.
- No parameter, threshold, window, paper, source, or candidate replacement may
  be changed after the pre-registration receipt is sealed.
- The deterministic JSON result is canonical. The stakeholder HTML report may
  summarize it but cannot alter metrics or verdicts.


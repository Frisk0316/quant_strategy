# Crypto Strategy Synthesis

This file converts the literature survey into strategy hypotheses for the
current OKX system. These are not live recommendations. Each idea must survive
OKX-specific fees, maker-only constraints, replay or walk-forward testing, and
Deflated Sharpe Ratio checks before promotion.

## Strategy 1: Multi-Level OFI Maker Skew

- **Theoretical basis:** Glosten and Milgrom 1985; Cont, Kukanov and Stoikov
  2014; Xu, Gould and Howison 2018; Kolm, Turiel and Westray 2021.
- **Core logic:** Replace or augment L1 OBI with depth-weighted multi-level OFI.
  Use the signal to shift fair value inside AS/OBI market making, while keeping
  all execution maker-only.
- **Signal source:** OKX L2 book updates, best-level OFI, depth-weighted OFI,
  short EWMA half-lives.
- **Sizing rule:** Base clip from `portfolio/sizing.py`; reduce size when OFI
  disagreement across levels is high or when VPIN is above threshold.
- **Execution:** Compute fair value = mid + alpha coefficient * MLOFI; feed into
  `strategies/as_market_maker.py` quote logic; submit `post_only` orders only.
- **Applicable instruments:** BTC-USDT-SWAP, ETH-USDT-SWAP first; alts only
  after liquidity and tick-size review.
- **Expected edge:** Microstructure edge from short-horizon order-book pressure.
- **Risk controls:** Max inventory, VPIN spread multiplier, cancel on crossed
  quote, stale-book guard, queue-age filter for spoofing.
- **Fit with existing system:** Extend `src/okx_quant/signals/obi_ofi.py`; plug
  into `strategies/as_market_maker.py` and `strategies/obi_market_maker.py`.
- **Backtest path:** Use `backtesting/replay.py` or `nautilus_backtest.py` with
  L2/tick data, maker fill assumptions, and fee-aware PnL.

## Strategy 2: VPIN Jump-Risk Throttled Market Making

- **Theoretical basis:** Easley, Lopez de Prado and O'Hara 2012; Andersen and
  Bondarenko 2014; recent Bitcoin VPIN jump-risk studies.
- **Core logic:** Treat VPIN as a toxicity and jump-risk throttle, not as a
  directional alpha. In high-toxicity regimes, widen spreads, cut size, and
  optionally quote one side only if inventory is already risky.
- **Signal source:** OKX trades, volume buckets, BVC trade classification,
  rolling VPIN percentile.
- **Sizing rule:** Size multiplier = 1.0 in normal flow, 0.5 in warning flow,
  0.0-0.25 in extreme toxicity depending on inventory.
- **Execution:** Quote refresh remains maker-only; spread multiplier increases
  with VPIN percentile and realized volatility.
- **Applicable instruments:** BTC/ETH perps where trade data is dense enough.
- **Expected edge:** Loss avoidance and adverse-selection reduction rather than
  standalone alpha.
- **Risk controls:** False-positive guard using realized-vol and spread filters;
  avoid hard shutdown on a single VPIN spike.
- **Fit with existing system:** Extend `src/okx_quant/signals/vpin.py`; expose a
  toxicity state to `risk/risk_guard.py` and market-making strategies.
- **Backtest path:** Compare market-maker PnL with and without VPIN throttle
  during volatile windows.

## Strategy 3: Funding Carry with Basis and Crowding Filter

- **Theoretical basis:** Makarov and Schoar 2020; crypto perpetual futures and
  funding-rate literature; Liu, Tsyvinski and Wu crypto factor work.
- **Core logic:** Keep the existing long spot / short perp carry, but only enter
  when funding is high enough after costs and when basis/crowding indicators do
  not imply elevated reversal or liquidation risk.
- **Signal source:** OKX funding history, premium index, spot/perp basis, open
  interest if available, realized volatility.
- **Sizing rule:** Target delta-neutral notional based on expected funding APR,
  basis z-score, realized vol, and max liquidation distance. Cap with
  quarter-Kelly or fixed fractional sizing.
- **Execution:** Build both legs with maker orders when possible; rebalance only
  when delta drift exceeds threshold.
- **Applicable instruments:** BTC/ETH spot plus USDT perpetuals.
- **Expected edge:** Funding carry and basis convergence.
- **Risk controls:** Funding reversal stop, basis blowout stop, liquidation
  buffer, exchange risk cap, max capital allocation.
- **Fit with existing system:** Extend `src/okx_quant/strategies/funding_carry.py`
  and `portfolio/sizing.py`.
- **Backtest path:** Use existing funding parquet plus candles; validate with
  `backtesting/walk_forward.py` and stress windows.

## Strategy 4: Dynamic BTC-ETH Pair with OU Half-Life Gate

- **Theoretical basis:** Gatev, Goetzmann and Rouwenhorst 2006; Bertram 2009;
  Avellaneda and Lee 2010; Tadic and Kortchemski 2021.
- **Core logic:** Trade BTC/ETH relative value only when rolling cointegration,
  Kalman hedge ratio stability, and OU half-life pass quality gates.
- **Signal source:** BTC and ETH perp or spot prices, rolling hedge ratio, spread
  z-score, OU half-life.
- **Sizing rule:** Dollar-neutral or beta-neutral sizing; reduce exposure when
  half-life rises, spread volatility jumps, or hedge ratio uncertainty widens.
- **Execution:** Enter at |z| > 2, scale down near z = 0.5, exit near z = 0 or on
  half-life break. Prefer maker orders unless risk stop is hit.
- **Applicable instruments:** BTC-USDT-SWAP / ETH-USDT-SWAP; spot pair for lower
  leverage variants.
- **Expected edge:** Mean reversion in relative value.
- **Risk controls:** Cointegration break stop, |z| hard stop, max holding time,
  liquidity filter.
- **Fit with existing system:** Extend `src/okx_quant/strategies/pairs_trading.py`.
- **Backtest path:** Walk-forward test rolling parameter estimation; add CPCV for
  threshold selection.

## Strategy 5: Crypto Factor Residual Basket

- **Theoretical basis:** Avellaneda and Lee 2010; Liu and Tsyvinski 2019; Liu,
  Tsyvinski and Wu 2022; Gu, Kelly and Xiu 2018.
- **Core logic:** Build a liquid OKX perp universe, remove common BTC/ETH market
  factors, then trade residual mean reversion or residual momentum with strict
  liquidity and cost filters.
- **Signal source:** Liquid perp returns, BTC/ETH factors, volume, volatility,
  funding, residual z-scores.
- **Sizing rule:** HRP or inverse-vol allocation across active residual signals;
  cap per-symbol notional and total alt exposure.
- **Execution:** Maker-preferred rebalance at low frequency; no trade if expected
  edge is below maker plus slippage cost.
- **Applicable instruments:** Top liquid OKX USDT perps only.
- **Expected edge:** Cross-sectional residual mispricing after common crypto beta.
- **Risk controls:** Universe liquidity floor, factor beta cap, crowding stop,
  delisting/news exclusion.
- **Fit with existing system:** New strategy module under
  `src/okx_quant/strategies/`; extend `portfolio/allocation.py`.
- **Backtest path:** Start in `backtesting/vectorbt_scanner.py`, then
  walk-forward and CPCV.

## Strategy 6: Slow Time-Series Momentum Overlay

- **Theoretical basis:** Jegadeesh and Titman 1993; Moskowitz, Ooi and Pedersen
  2012; Daniel and Moskowitz 2016; Hurst, Ooi and Pedersen 2018; Lim, Zohren and
  Roberts 2020.
- **Core logic:** Add a low-turnover trend sleeve or regime overlay that trades
  only when trend strength exceeds costs and volatility-adjusted sizing is
  acceptable. Avoid pure taker breakout scalping.
- **Signal source:** Multi-horizon returns, realized volatility, drawdown state,
  funding context.
- **Sizing rule:** Vol-targeted exposure with drawdown-based size reduction and
  max leverage cap.
- **Execution:** Maker-first entries on pullbacks or scheduled rebalance; taker
  only for risk exits if live policy allows.
- **Applicable instruments:** BTC/ETH perps; maybe liquid majors after testing.
- **Expected edge:** Trend persistence and crisis convexity.
- **Risk controls:** Momentum crash filter, volatility spike de-risking, max
  holding loss, DSR gate.
- **Fit with existing system:** New strategy module; reuse `signals/regime.py`
  and `portfolio/sizing.py`.
- **Backtest path:** Hourly/daily candles through `walk_forward.py`; include fee
  and slippage assumptions.

## Strategy 7: Basis Z-Score Mean Reversion

- **Theoretical basis:** Bertram 2009; Makarov and Schoar 2020; perpetual funding
  literature.
- **Core logic:** Model perp/spot basis as a mean-reverting spread. Enter
  delta-neutral positions when basis z-score is extreme and expected funding plus
  convergence exceeds costs.
- **Signal source:** Spot price, perp mark/index price, funding rate, basis
  z-score, OU half-life.
- **Sizing rule:** Scale by expected convergence edge divided by realized basis
  volatility; cap by liquidation distance and capital allocation.
- **Execution:** Long spot / short perp when basis and funding are rich; reverse
  only if borrow, fees, and short constraints make sense.
- **Applicable instruments:** BTC/ETH spot and perps.
- **Expected edge:** Basis convergence plus funding carry.
- **Risk controls:** Basis blowout stop, max holding period, funding flip exit,
  minimum net APR threshold.
- **Fit with existing system:** Extend `funding_carry.py` or create
  `basis_trading.py`.
- **Backtest path:** Combine existing `candles_1H.parquet` and `funding.parquet`;
  add basis series collection if missing.

## Strategy 8: Volatility Regime Filter for All Strategies

- **Theoretical basis:** Moreira and Muir 2017; Daniel and Moskowitz 2016; VPIN
  toxicity literature; Leland 1985 for cost-aware hedging intuition.
- **Core logic:** Use realized volatility, VPIN, spread, and drawdown state as a
  shared regime filter across market making, funding carry, pairs, and trend.
- **Signal source:** Realized volatility, VPIN percentile, spread percentile,
  drawdown tracker, liquidation-like price moves.
- **Sizing rule:** Global risk multiplier from 0.0 to 1.0; strategy-specific caps
  remain in place.
- **Execution:** No direct alpha trades. It modulates quote width, clip size,
  carry allocation, and pair entry permission.
- **Applicable instruments:** All current OKX instruments.
- **Expected edge:** Drawdown reduction and lower adverse-selection losses.
- **Risk controls:** Avoid overreacting to one noisy metric; require confirmation
  across at least two state variables.
- **Fit with existing system:** Extend `signals/regime.py`,
  `risk/risk_guard.py`, and `portfolio/sizing.py`.
- **Backtest path:** Run ablations against existing strategies with and without
  the regime multiplier.

## Strategy 9: Crypto Fear & Greed Sentiment Long-Flat (Research Baseline Only)

- **Theoretical basis:** Baker and Wurgler 2006 sentiment-as-mispricing; crypto
  retail-sentiment studies. Treated here as a behavioral baseline, not as a
  validated alpha hypothesis.
- **Core logic:** Long/flat BTC perp. Enter long when Alternative.me classifies
  the index as `Extreme Fear`; stay in position through `Fear` and `Neutral`;
  exit only on `Greed` or `Extreme Greed`. This is a deliberate hold-through-
  retracement assumption — a mean-reversion bet that sentiment must rebound to
  the upper half of the scale before alpha is realised. It is **not** a trend
  filter; `Fear` and `Neutral` are intentionally non-exits.
- **Signal source:** Alternative.me public Crypto Fear & Greed Index (dataset
  `fear_greed_btc`), daily cadence, no publish lag.
- **Sizing rule:** Standard fixed-fractional / vol-target via
  `portfolio/sizing.py`; no sentiment-conditional sizing in v1.
- **Execution:** Maker-only on OKX BTC-USDT-SWAP; reuses long/flat exit close
  sizing established by the MA/MACD baseline. `enabled: false` by default.
- **Applicable instruments:** BTC-USDT-SWAP only. Alternative.me does not
  publish per-asset indices.
- **Expected edge:** Unknown. The hypothesis is that holding through `Fear` /
  `Neutral` and exiting only on `Greed`+ captures the sentiment-rebound regime.
  This must be measured via walk-forward and CPCV before any promotion claim.
- **Risk controls:** Required feature: stale or missing observations produce no
  signal (`max_age_seconds=172800`). Counters `missing_no_signal_count` and
  `stale_no_signal_count` are written to `validation.external_features` for
  audit.
- **Known caveats (must resolve before promotion):**
  - Label match is case-sensitive against Alternative.me free-text. Mitigated:
    `FearGreedSentimentParams` enforces an allow-list at config load and the
    strategy carries numeric `extreme_fear_threshold` / `exit_value_threshold`
    fallbacks on `value_num`; promotion ADR must state which path is
    canonical.
  - `Fear` and `Neutral` hold-through assumption has not been backtested with
    DSR ≥ 0.95.
  - Coverage-gate thresholds (see Promotion Checklist) must be measured on a
    full replay run, not yet executed.
- **Fit with existing system:** Implemented in
  `src/okx_quant/strategies/external_features.py::FearGreedSentimentStrategy`.
  Signals carry `metadata["research_only"] = True`.
- **Backtest path:** Replay with `--strategy fear_greed_sentiment`; cross-check
  against `dgs10`-conditioned variants once the macro feature is wired.

## Strategy 10: CME BTC Daily Weekend-Gap Research Baseline (Not Real-Time)

- **Theoretical basis:** Caporale, Plastun and Pochinkov 2019; weekend / overnight
  gap mean-reversion studies in equity index futures. Here used as a research
  reference, not as a tradable real-time strategy.
- **Core logic:** Detect Friday-close → Monday-open price gaps on the CME BTC
  futures daily series of at least `min_gap_bps` (default 10 bps). Take an
  OKX BTC-USDT-SWAP position opposite to the gap direction and exit when OKX
  touches the prior Friday CME close or the holding-time cap (`max_hold_days`,
  default 5) elapses.
- **Critical timing assumption (must be acknowledged before any deployment
  claim):**
  - Source is **daily**, not intraday. The Monday CME bar is `observed_at` at
    Monday 00:00 UTC and `published_at` at Tuesday 00:00 UTC under
    `publish_lag_days=1`.
  - As a result, the replay engine cannot emit the gap-detection FEATURE event
    until **the Tuesday after the weekend**, by which point OKX (which trades
    24/7) has typically already absorbed the CME gap.
  - This baseline therefore measures *OKX response to a one-day-delayed CME
    daily signal*. It is **explicitly not a real-time weekend gap-fill
    strategy**. Treat any reported PnL as a daily-cadence research reference,
    not an executable edge.
- **Signal source (official, budget-blocked):** `cme_btc1_continuous` (Nasdaq
  Data Link), daily OHLCV. `CHRIS/CME_BTC1` was discontinued by Nasdaq Data
  Link in 2022-03; replacement official feeds (CME DataMine, Databento
  `GLBX.MDP3`, Polygon CME feed) are paid subscriptions and **not currently
  provisioned under this project's budget**. Treat as aspirational; no near-
  term plan to subscribe.
- **Signal source (operating under budget constraint):** `cme_btc_yfinance`,
  built from Yahoo Finance `BTC=F` daily OHLC. This is the **operating signal
  source** for this strategy under the current budget, not a temporary
  placeholder waiting for an official feed. It remains an **unofficial proxy
  for CME BTC futures** — not the official CME settle and not comparable in
  fidelity. Numbers can be used for directional sanity checks and parameter
  iteration; **they are not admissible as deployment or promotion evidence**
  and any artefact must carry `source: research_proxy_only` in its
  `research_status` block. See Research Feature Data Caveats below.
- **Execution venue and instrument:** The actual trading venue is **OKX
  BTC-USDT-SWAP** (perpetual swap, USDT-margined), maker-preferred, reusing
  the long/flat exit close sizing. The strategy is **cross-venue**: CME BTC
  futures (or its yfinance proxy) provides the *signal*, and we trade the
  USDT-quoted crypto perp on OKX. We do **not** trade CME BTC futures
  themselves — the broader project trades only crypto / USDT pairs on OKX,
  and this strategy is BTC-specific only because the CME gap signal is
  BTC-specific. Signals carry `metadata["research_only"] = True` and the
  strategy is `enabled: false` in `config/strategies.yaml`.
- **Applicable instruments:** Trading venue is **OKX BTC-USDT-SWAP**; signal
  source is CME BTC futures daily OHLC (currently the yfinance proxy). The
  cross-venue setup is *signal-to-trade*, not arbitrage — there is no
  position taken on CME.
- **Expected edge (research proxy, two in-sample runs, yfinance,
  2024-01-01 → 2026-05-19):**
  - **Baseline run** (`min_gap_bps=10`, `max_hold_days=5`, no stop-loss,
    `allow_direction=both`): 112 gaps, fill probability 82.1%, 109 trades.
    Total return **-33.3%**, Sharpe -0.52, max drawdown -49.2%, win rate
    76% but PF 0.78 — 27 timeouts sum -12,978 bps vs. 82 target-fills
    +9,791 bps. The capped-win / uncapped-loss payoff is the structural
    flaw.
  - **Post-fix run** (`min_gap_bps=25`, `max_hold_days=2`,
    `stop_loss_bps_mult=1.5`, `allow_direction=both`): 99 trades, total
    return **-28.1%**, Sharpe -0.82, max drawdown -37.0%, win rate 55.6%,
    PF 0.71. Stop-loss capped tail damage (worst -980 bps vs prior
    -2,059) but converted 35/82 prior target-fills into stop-loss losses
    (sum -8,094 bps), so the run remains net negative.
  - **Direction breakdown of the post-fix run:** down-gaps (long BTC)
    +803 bps over 46 trades, win 63%, PF 1.24; up-gaps (short BTC)
    **-3,799 bps** over 53 trades, win 49%, PF 0.45. The short side
    fights BTC's 2024-2026 long-run drift and is the dominant drag.
- **Methodology note on prior in-sample envelopes (lesson learned):** An
  earlier Claude review estimated that a 1.5× stop-loss would flip the run
  to **+3,308 bps positive**. That estimate was wrong because it only
  re-priced the 27 timeout trades and assumed all 82 target-fill trades
  remained untouched. The real bar-by-bar simulator triggers stop-loss on
  intra-trade adverse high/low excursions, converting many fills into
  earlier stop-outs. Any future in-sample envelope on this style of
  exit-replacement must walk every bar of every trade, not just re-cap
  existing exit reasons.
- **Status of CME-evidence claims:** None of the above numbers are admissible
  as deployment evidence because they are derived from a research proxy
  (`cme_btc_yfinance`), not from the official CME settle series.
- **Known caveats (must resolve before any promotion claim):**
  - `CHRIS/CME_BTC1` was discontinued by Nasdaq Data Link in 2022-03. The
    official adapter target is non-functional. `cme_btc_yfinance` is wired as
    a research-only proxy and is not a substitute for the official feed.
  - Weekend-gap detection currently requires
    `current_observed.weekday() in {0, 6}`, which silently misses US holiday
    Mondays (gap rolls to Tuesday).
  - Continuous back-adjusted / Yahoo-stitched series introduce artificial
    roll-day gaps that must be filtered. The strategy and analyzer already
    accept a `roll_dates` list; it must be populated before any claim.
  - **Mitigated**: cross-venue target basis. Both the strategy and the
    analyzer now anchor the target on the OKX entry mid plus the CME
    `gap_bps`, not on the absolute CME `prev_close`.
  - To become a *real-time* gap-fill strategy this baseline would have to be
    re-implemented on minute-resolution CME data with `publish_lag_minutes`
    semantics, which is a separate research item.

- **Status of structural changes (already implemented in code):**
  Stop-loss (`stop_loss_bps_mult=1.5`), dust-bucket exclusion
  (`min_gap_bps=25`), and shortened hold (`max_hold_days=2`) are now in
  `CMEGapFillStrategy` and `analyze_cme_gaps.py`. They cap tail damage and
  shrink hold time, but on this yfinance proxy they do **not** flip the run
  positive when both directions are traded — they merely move the loss
  from -33% to -28% with a different exit-reason mix.
- **Default-direction decision (Route B, 2026-05-19, default flipped in
  commit `655af31`):** Because up-gaps (short BTC) were -3,799 bps versus
  down-gaps (long BTC) +803 bps in the post-fix `both`-directions run, the
  research default is now **`allow_direction="long_only"`** in
  `CMEGapFillParams`, `config/strategies.yaml`, `CMEGapFillStrategy`,
  `detect_weekend_gaps`, `simulate_reverse_gap_trades`, and the
  `analyze_cme_gaps.py` CLI. Regression tests in
  `tests/unit/test_external_feature_strategies.py
  ::test_cme_gap_fill_default_skips_up_gaps_and_trades_down_gaps` and
  `tests/unit/test_cme_gap_analysis.py
  ::test_simulate_reverse_gap_trades_default_excludes_short_side` lock the
  default behaviour.
  - **Re-run on default config**
    (`results/cme_gap_research_long_only_default.json`, 2026-05-19):
    47 down-gaps detected, 46 trades, 26 target-fills / 13 stop-losses /
    7 timeouts. Total return **+7.09%**, annualised +3.07%, Sharpe +0.35,
    max drawdown -14.7%, win rate 63.0%, PF 1.24, worst trade -980 bps.
  - **Route B is still explicitly regime-fitted to BTC 2024-26; bear-regime
    walk-forward remains required before any promotion claim.** `long_only`
    aligns with BTC's 2024-2026 multi-year uptrend. A bear regime that
    systematically gaps up after weekend de-risking would invert the
    result. Any walk-forward or CPCV evaluation must include at least one
    extended bear or sideways regime; if `long_only` fails on that
    segment, the default must revert to "do not deploy" and the strategy
    retired. See AI_HANDOFF Known Bug #15 and Next Step 6d.
  - **Even with `long_only`, this is not validated alpha.** +7.09% over 46
    trades / 2.4 years averages ~+15 bps per trade — only ~3 bps above the
    12 bps round-trip cost — with a single -980 bps worst trade. The edge
    is razor-thin; one bad trade erases months. Promotion ADR must state
    this explicitly.
- **Not deployment-ready under any direction setting.** The structural
  fixes reduce blow-up risk but do not constitute validated alpha on a
  research proxy. **Live trading would ideally require** (a) an official
  CME signal source (not yfinance), (b) walk-forward / CPCV pass on
  bear-regime data, (c) DSR ≥ 0.95. **Operating reality under current
  budget**: gate (a) is not on the roadmap, so the practical path is to
  run gates (b) and (c) on the yfinance proxy and accept the elevated
  source-fidelity risk in any promotion ADR. If a promotion ADR is opened
  on the proxy alone, it must explicitly attest to the signal-source
  fidelity gap and require post-promotion ground-truth monitoring against
  any later official feed.
- **Exit throttle (`exit_requested`):** After the strategy emits its first
  exit signal for an active gap (target / stop / timeout), it sets
  `gap.exit_requested = True` and the in-position branch early-returns on
  every subsequent `on_market` call until the fill confirmation arrives via
  `on_fill` (which clears `_in_position` and `_active_gap`). This aligns the
  replay strategy with the analyzer's one-entry-one-exit-per-gap baseline
  assumption. Without the throttle the strategy would re-emit an exit signal
  every bar that still satisfies target/stop/timeout — each one carries
  `cancel_existing=True` and would cancel-and-replace the pending exit,
  diverging materially from the analyzer's single round-trip model.
  Regression test: `test_cme_gap_fill_does_not_repeat_exit_signal_while_exit_order_pending`
  in `tests/unit/test_external_feature_strategies.py`. Known orphan risk:
  if the exit order is cancelled or rejected externally before any fill,
  the strategy stays `_in_position=True` with `exit_requested=True` and
  will not re-emit — same shape as the MA/MACD long-flat baseline,
  acceptable for v1 research.
- **Analyzer ↔ replay measurement divergence (must be acknowledged in any
  comparison):**
  - The analyzer (`simulate_reverse_gap_trades`) uses each OKX bar's
    **`high` / `low`** to check target / stop touches. The replay engine
    feeds the strategy a single L1 book event per bar synthesised from the
    bar **close** via `_synthetic_l1_from_candles`, so the strategy's
    `_target_touched` / `_stop_loss_touched` only see the close mid. On
    1H bars the intra-bar range is routinely 20-100 bps, so many trades
    the analyzer counts as `target_fill` (winners) become `timeout` in
    replay (small to large losses) — replay is systematically more
    negative than the analyzer on the same gap signal.
  - **Secondary divergence sources:** funding payments (perp pays funding
    every 8h; analyzer ignores), maker queue / partial-fill mechanics
    (replay `ReplayExecutionModel.queue_fill_fraction` vs analyzer's
    instant-fill-at-level assumption), entry-price reference (analyzer
    bar `open` vs replay close mid), and broker-modelled fees / slippage
    vs analyzer's flat 12 bps round-trip.
  - **Interpretation rule for artefacts:** the analyzer JSON
    (`cme_gap_research_long_only_default.json`) is an **upper bound**
    under an idealised execution model. The replay artefact is a
    **coarse close-mid approximation** that biases toward timeouts and
    under-states the signal. The true tradable expectancy sits between
    them and cannot be estimated without either (i) feeding bar
    high/low into the replay's market events (changes strategy
    semantics, separate research item) or (ii) shadow trading on OKX
    for ground truth. **Neither artefact is admissible as deployment
    evidence in isolation.**
- **Fit with existing system:** Implemented in
  `src/okx_quant/strategies/external_features.py::CMEGapFillStrategy`.
  Offline analysis lives in `scripts/analyze_cme_gaps.py`.
- **Backtest path:** Replay with `--strategy cme_gap_fill` on the current
  yfinance proxy; rerun `analyze_cme_gaps.py` for fill-probability
  diagnostics with roll-day and holiday filters in place. Any comparison
  table between the two outputs must cite the divergence note above.

## Research Feature Data Caveats

These are caveats that apply to the external-feature datasets feeding research
strategies above. They are not strategies in themselves, but every consumer must
acknowledge them.

### `dgs10` (FRED 10-Year Treasury Constant Maturity Rate)

- **Cadence:** Business-daily; missing on US federal holidays and weekends.
  Stored in `external_observations` under dataset id `dgs10`,
  `required: false` (long stretches of absent values are expected).
- **Publish-lag policy:** `publish_lag_days=1`. Real FRED H.15 release is the
  same trading day at ~16:30 ET; a 1-day lag (next 00:00 UTC) is conservative
  and safe by ~2.5 hours. Configuration must enforce `publish_lag_days >= 1`
  at schema load to prevent same-day lookahead.
- **Vintage policy: latest-vintage only, NOT point-in-time.** FRED occasionally
  revises DGS10 historicals. The current ingest schema
  (`external_observations` PRIMARY KEY `(dataset_id, observed_at)` with
  `ON CONFLICT DO UPDATE`) overwrites any prior value when a revised vintage
  is re-ingested. Backtests run after a revision therefore see the **latest**
  rate at every historical observed_at, not the rate that was actually
  available at that moment in time. This is a known subtle lookahead bias for
  any DGS10-conditioned research.
  - To make this strict point-in-time would require FRED's ALFRED vintage
    endpoint plus `realtime_start` / `realtime_end` semantics in
    `external_observations`. Not in v1 scope.
  - Until upgraded, any DGS10-conditioned signal must be flagged
    `research_only` and excluded from live promotion. DSR results on
    DGS10-conditioned variants must explicitly note the latest-vintage
    caveat.
- **Stale-handling:** Strategies consuming `dgs10` should set
  `max_age_seconds` ≥ 604800 (7 days) to cover long holiday weekends without
  spurious stale flags.

### `fear_greed_btc` (Alternative.me Crypto Fear & Greed Index)

- **Cadence:** Daily; index labels are free-text strings.
- **Publish-lag policy:** None — Alternative.me publishes same-day.
  `published_at = observed_at` is correct.
- **Label-stability dependency:** Strategy label matching is case-sensitive
  against the upstream string set
  `{Extreme Fear, Fear, Neutral, Greed, Extreme Greed}`. Any upstream
  capitalization or punctuation drift would silently disable label-only signal
  emission. **Mitigated in code**: `FearGreedSentimentParams` enforces a
  config-load allow-list via `validate_extreme_fear_label`, and the strategy
  carries numeric `extreme_fear_threshold` (default 25.0) and
  `exit_value_threshold` (default 51.0) fallbacks driven off `value_num` so
  signals can still fire if upstream label text drifts. Promotion ADR should
  attest which path (label match vs. numeric thresholds) is canonical for the
  proposed live run.
- **TTL:** `max_age_seconds=172800` (48h) tolerates one missed publication.

### `cme_btc1_continuous` (Nasdaq Data Link CME BTC Futures, official, budget-blocked)

- **Status: budget-blocked, no near-term plan.** `CHRIS/CME_BTC1` was
  discontinued by Nasdaq Data Link in 2022-03; replacement official feeds
  (paid CME DataMine, Databento `GLBX.MDP3`, Polygon CME feed, or equivalent)
  are all paid subscriptions and **not currently provisioned under this
  project's budget**. There is no active roadmap item to subscribe. Treat
  this entry as aspirational; the operating signal source for the strategy
  is `cme_btc_yfinance` below.
- **Cadence:** Intended daily settle. Real-time / intraday gap-fill is **not**
  supported by this dataset; see Strategy 10 caveats.
- **Continuous-contract artefact:** Back-adjustment introduces synthetic
  roll-day price jumps. Detection logic must filter roll days or switch to a
  front-month series before any statistic can be trusted.
- **Cross-venue price comparability:** Back-adjusted CME continuous prices are
  not directly comparable to OKX BTC-USDT-SWAP price levels; the strategy and
  analyzer now anchor targets on OKX entry mid, not on the absolute CME
  `prev_close`.

### `cme_btc_yfinance` (Yahoo Finance `BTC=F`, operating signal source under budget)

- **Status: operating signal source under current budget; not interim.**
  Wired in 2026-05 because the official CME and Nasdaq Data Link sources are
  paid subscriptions that this project has not provisioned. There is no
  near-term plan to upgrade. **The strategy operates on this proxy
  indefinitely under current budget**, and any research / parameter
  iteration / walk-forward must be done on this proxy. Yahoo's `BTC=F` is
  Yahoo's representation of CME BTC futures front-month continuous quotes;
  it is **not** CME's official settle and is not provided under a market-
  data licence suitable for production trading attribution.
- **Hard rule:** Numbers derived from this dataset are admissible only as
  preliminary directional sanity checks. They are **never** admissible as
  deployment, shadow-promotion, or live-trading evidence. Any artefact must
  carry `source: research_proxy_only` (or equivalent) in `research_status`,
  and any PR / handoff / ADR citing them must label them as such.
- **Quality caveats:**
  - Quote delay: Yahoo `BTC=F` is typically a delayed quote (15-30 min).
  - Continuous-contract stitching: Yahoo's continuous-series logic is not
    documented; behaves like an undisclosed back-adjusted or rolled series.
    Roll-day artefacts are likely and must be filtered.
  - Adjustments: Yahoo applies its own adjustments (splits, missing-data
    forward fill); not directly comparable to CME settle.
  - Date convention: Yahoo's date labels do not match CME's official Globex
    trade-date convention in all cases.
- **Use as a research proxy:** OK for measuring (a) is there a stable
  weekend-gap fill rate? (b) does a stop-loss / dust-bucket / direction
  filter materially improve the payoff distribution? (c) does the gap
  signal survive walk-forward / CPCV on different regimes within this
  proxy window? OK to run parameter studies, walk-forward, and CPCV
  *on the proxy itself*. **Not** OK as deployment / promotion / shadow
  evidence, and not OK for measuring backtest PnL that anyone will rely
  on as a tradable expectation.
- **Trading venue separation:** This dataset is a *signal*, not a trading
  venue. The strategy that consumes it trades **OKX BTC-USDT-SWAP**, not
  CME futures. The broader project trades crypto / USDT pairs only.
  Quote delay / continuous stitching / Yahoo adjustments on `BTC=F` affect
  the *signal* fidelity, not the trading instrument.
- **If an official CME source is later provisioned (no current plan):**
  re-run every yfinance-derived analysis side-by-side; treat directional
  agreement
  as a sanity check, not as confirmation of edge.

## Strategies Rejected For Now

| Idea | Reason to reject for now |
|---|---|
| Pure taker intraday momentum | VIP0 taker fees make small short-horizon edges hard to monetize. |
| Ultra-low-latency HFT | Requires colocated or highly optimized infrastructure and realistic queue modeling. |
| Fully autonomous RL market making | Sim-to-live gap and reward hacking risk are too high before replay simulator maturity. |
| Social-media sentiment trading | Data quality, bot manipulation, and latency make it weak as a primary signal. |
| Short BTC/ETH options volatility on OKX | Liquidity, tail risk, and missing options hedging infrastructure. |
| Broad altcoin residual basket live trading | Needs robust universe filters, delisting handling, and cost validation first. |

## Validation Status Convention

Every backtest artifact must declare exactly one validation status before it is
used in promotion discussion, handoff notes, or strategy comparison. The label
describes how the reported metrics were produced; it does not change the
artifact schema or imply live readiness.

| Status | Fit/eval separation | Parameters adjusted on this dataset? | Deployment meaning |
|---|---|---|---|
| `naive_backtest` | No | No, and commit history or accompanying notes prove parameters were frozen before this dataset was downloaded or inspected. | Not OOS evidence. |
| `in_sample` | No | Yes, or cannot prove no. | Not OOS evidence. |
| `hold_out` | Yes, single split | Only on the IS segment; the OOS segment was frozen before inspection. | May be cited with scope limits. |
| `walk_forward` | Yes, rolling | Programmatic fit per window via `backtesting/walk_forward.py::WalkForward.evaluate()`. | May be cited if replay/cost/leakage gates pass. |
| `cpcv` | Yes, combinatorial purged | Programmatic fit per combination via `backtesting/cpcv.py::CPCV.evaluate()`, with honest `n_trials` recorded. | May be cited if DSR/PSR and replay/cost/leakage gates pass. |

Classification process:

1. If the artifact was produced by `WalkForward.evaluate()`, mark it
   `walk_forward`.
2. Else if it was produced by `CPCV.evaluate()`, mark it `cpcv`.
3. Else if the accompanying notes explicitly state a frozen-before-evaluation
   hold-out split, mark it `hold_out`.
4. Else if there is commit-history or documentary evidence that parameters were
   frozen before this dataset was downloaded or inspected, mark it
   `naive_backtest`.
5. Otherwise mark it `in_sample`.

The default under uncertainty is intentionally conservative: inability to prove
that parameters were frozen before the dataset was downloaded or inspected
means the artifact is `in_sample`, not `naive_backtest`. Single-period
backtests and parameter sweeps are therefore IS-only unless proven otherwise.
`naive_backtest` and `in_sample` have the same deployment limitation: neither is
OOS evidence, neither may be cited as edge evidence, and neither may satisfy a
promotion gate without follow-up `hold_out`, `walk_forward`, or `cpcv`
validation.

### Idealized-fill exclusion (research-only `fill_all_signals`)

The `fill_all_signals` research mode (CLI flag, API request field, frontend
"Fill all signals" checkbox, and per-strategy parameter on `ohlcv_rotation`) is
**capacity / execution sensitivity analysis only**. When enabled it raises
`max_order_notional_usd` to 1e12, `max_pos_pct_equity` to 1e6, `stale_quote_pct`
to 1e6, sets `queue_fill_fraction = 1.0` with zero latency, switches the replay
broker to `fill_all_on_submit`, and (for `ohlcv_rotation`) bypasses `top_k`,
`rank_exit_buffer`, and the `max_position_weight` cap. The resulting PnL,
fill log, and equity curve do not correspond to any reachable live execution
path.

Admissibility rule (applies retroactively to all current and future artefacts):

- Any artefact where `result.validation.fill_all_signals == true` (equivalently
  `result.validation.idealized_fill == true`, written by
  `backtesting/artifacts.py`) is **not OOS evidence, not edge evidence, and
  not promotion evidence**, regardless of its `validation_status`.
- This applies even when `validation_status` is `walk_forward` or `cpcv`:
  WF / CPCV on top of idealized fills measures only signal-side fit, not
  execution-reachable PnL.
- Such artefacts may **only** be used to answer:
  (a) "If every signal were instantly fillable at the bar reference price,
       what is the upper bound on PnL / turnover / capacity utilisation?"
  (b) "Is the realistic-fill backtest being constrained by execution
       (queue / latency / risk caps) versus by signal quality?"
- Promotion ADRs and the `docs/ai_collaboration.md` Deployment Gate explicitly
  exclude such artefacts; see the **Idealized fill 排除** row in that table.

A correctly-classified `fill_all_signals` artefact therefore carries:
`validation_status` *(IS / hold-out / WF / CPCV per the table above)* **plus**
`idealized_fill: true`. Both fields must be reported together; citing the
`validation_status` without `idealized_fill` is a governance violation.

## Promotion Checklist

| Requirement | Threshold |
|---|---|
| Data quality | No unexplained gaps in the test window; timestamps aligned. |
| Cost model | OKX maker/taker fees, spread, slippage, and missed fills included. |
| Validation | Each artifact declares `validation_status`; promotion evidence requires walk-forward, CPCV, or documented hold-out with no shared IS/OOS boundary leakage. Artefacts with `idealized_fill: true` (i.e. produced under `fill_all_signals`) are inadmissible regardless of `validation_status` — see Idealized-fill exclusion above. |
| Overfit control | DSR >= 0.95 and PSR >= 0.95 before promotion; `n_trials` must be reported honestly. |
| Risk | Max order notional, drawdown stops, and circuit breakers active. |
| Execution | Maker-only by default; taker usage explicitly justified for risk exits. |
| ct_val provenance | `validation.ct_val_all_authoritative = true` (every symbol's ctVal from `db`, `config_override`, or `spot_unit`). |
| Reduce-only audit (per ADR-0006) | Shadow run produced at least one `allowed_reduce_only_bypass:*` event sample for reviewer inspection (or a documented attestation that none occurred in the window). |

### External-Feature Coverage Gate

Strategies consuming `external_observations` must satisfy the following before
any live or shadow promotion. These thresholds are inputs to the per-strategy
promotion ADR and must be reported from `validation.external_features.<name>`
in the replay artefact.

| Gate | Threshold | Reported via |
| --- | --- | --- |
| Required-dataset availability | `event_count > 0` for every `required: true` dataset over the test window. | `data_coverage.json::features[]` |
| Stale-rate | `stale_no_signal_count / total_market_bars <= 0.10` (i.e. ≤ 10% of bars within the test window may be blocked by a stale feature). | `validation.external_features.<strategy>.stale_no_signal_count` |
| Missing-rate | `missing_no_signal_count / total_market_bars <= 0.05` after warmup. A `required: true` dataset that exceeds this is a hard fail. | `validation.external_features.<strategy>.missing_no_signal_count` |
| Vintage attestation | For non-PIT datasets (currently `dgs10`), the promotion ADR must explicitly accept latest-vintage exposure or upgrade ingest to ALFRED-vintage before promotion. | ADR text |
| Source-stability attestation | For each external dataset, the promotion ADR must name the live upstream endpoint and a fallback. Discontinued sources (e.g. current `CHRIS/CME_BTC1`) block promotion. | ADR text |
| Label-stability attestation (text-valued features) | For label-matched features (currently `fear_greed_btc`), promotion ADR must confirm either a config-load allow-list validator or numeric-threshold replacement is in place. | ADR text |

Strategies flagged `research_only: true` in their signal metadata
(Strategies 9-10 above) must not be merged into any live/shadow deployment
configuration until every applicable row of this gate is satisfied and a
strategy-specific promotion ADR has been accepted.


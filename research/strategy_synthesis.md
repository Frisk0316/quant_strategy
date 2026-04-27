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

## Strategies Rejected For Now

| Idea | Reason to reject for now |
|---|---|
| Pure taker intraday momentum | VIP0 taker fees make small short-horizon edges hard to monetize. |
| Ultra-low-latency HFT | Requires colocated or highly optimized infrastructure and realistic queue modeling. |
| Fully autonomous RL market making | Sim-to-live gap and reward hacking risk are too high before replay simulator maturity. |
| Social-media sentiment trading | Data quality, bot manipulation, and latency make it weak as a primary signal. |
| Short BTC/ETH options volatility on OKX | Liquidity, tail risk, and missing options hedging infrastructure. |
| Broad altcoin residual basket live trading | Needs robust universe filters, delisting handling, and cost validation first. |

## Promotion Checklist

| Requirement | Threshold |
|---|---|
| Data quality | No unexplained gaps in the test window; timestamps aligned. |
| Cost model | OKX maker/taker fees, spread, slippage, and missed fills included. |
| Validation | Walk-forward or CPCV; no shared IS/OOS boundary leakage. |
| Overfit control | DSR >= 0.95 before promotion. |
| Risk | Max order notional, drawdown stops, and circuit breakers active. |
| Execution | Maker-only by default; taker usage explicitly justified for risk exits. |


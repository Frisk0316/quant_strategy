# Quantitative Strategy Papers Database

This database is organized for strategy research, not academic completeness.
Records include practical fields needed by the OKX system: data requirement,
time horizon, transaction-cost treatment, evidence quality, implementation
readiness, and known failure modes.

## Coverage Summary

| Bucket | Paper count |
|---|---:|
| Foundational / Pre-2010 | 9 |
| 2010-2015 | 12 |
| 2016-2019 | 10 |
| 2020-2023 | 10 |
| 2024-present | 8 |
| **Total** | **49** |

## Quick Index

| Year | Paper | Primary Category | Key Signal / Concept | Crypto Applicability | Evidence Quality |
|---:|---|---|---|---|---|
| 1981 | Ho and Stoll, The Dynamics of Dealer Markets | Market Making | Inventory-dependent dealer quotes | Medium | Theoretical |
| 1985 | Glosten and Milgrom, Bid, Ask and Transaction Prices | Market Microstructure | Adverse selection spread | High | Theoretical |
| 1985 | Leland, Option Pricing and Replication with Transactions Costs | Options & Derivatives | Hedging cost adjustment | Medium | Theoretical |
| 1993 | Jegadeesh and Titman, Returns to Buying Winners and Selling Losers | Momentum | Cross-sectional momentum | Medium | Empirical |
| 2006 | Gatev, Goetzmann and Rouwenhorst, Pairs Trading | Statistical Arbitrage | Distance pairs convergence | Medium | Empirical |
| 2007 | Tetlock, Giving Content to Investor Sentiment | Alternative Data | News pessimism | Low / Medium | Empirical |
| 2008 | Avellaneda and Stoikov, High-Frequency Trading in a Limit Order Book | Market Making | Inventory-risk optimal quotes | High | Theoretical / simulation |
| 2009 | Carr and Wu, Variance Risk Premiums | Options & Derivatives | IV minus expected RV | Medium | Empirical |
| 2009 | Bertram, Analytic Solutions for Optimal Statistical Arbitrage Trading | Mean Reversion | OU entry/exit thresholds | High | Theoretical |
| 2010 | Avellaneda and Lee, Statistical Arbitrage in the U.S. Equities Market | Statistical Arbitrage | PCA/ETF residual reversion | Medium | Empirical |
| 2011 | Bollen, Mao and Zeng, Twitter Mood Predicts the Stock Market | Alternative Data | Social mood | Low | Empirical / disputed |
| 2011 | Loughran and McDonald, When Is a Liability Not a Liability? | Alternative Data | Finance-specific text tone | Medium | Empirical |
| 2012 | Easley, Lopez de Prado and O'Hara, Flow Toxicity and VPIN | Market Microstructure | VPIN toxicity | Medium | Empirical / disputed |
| 2012 | Moskowitz, Ooi and Pedersen, Time Series Momentum | Momentum | Own-asset trend | High | Empirical |
| 2013 | Gueant, Lehalle and Fernandez-Tapia, Dealing with Inventory Risk | Market Making | Ergodic market making | High | Theoretical |
| 2013 | Cartea, Jaimungal and Ricci, Buy Low Sell High | Market Making | Alpha-aware market making | High | Theoretical |
| 2014 | Cont, Kukanov and Stoikov, The Price Impact of Order Book Events | Market Microstructure | OFI | High | Empirical |
| 2014 | Bailey and Lopez de Prado, The Deflated Sharpe Ratio | Portfolio Construction | Multiple-testing adjustment | High | Methodological |
| 2014 | Andersen and Bondarenko, VPIN and the Flash Crash | Market Microstructure | VPIN critique | High | Empirical critique |
| 2014 | Zeng and Lee, Pairs Trading under OU Dynamics | Mean Reversion | OU stopping rules | Medium | Theoretical |
| 2015 | Sirignano and Cont, Universal Features of Price Formation | Machine Learning | LOB deep learning | High | Empirical |
| 2016 | Lopez de Prado, Building Diversified Portfolios that Outperform OOS | Portfolio Construction | Hierarchical Risk Parity | High | Empirical / methodological |
| 2016 | Daniel and Moskowitz, Momentum Crashes | Momentum | Momentum crash risk | High | Empirical |
| 2017 | Moreira and Muir, Volatility-Managed Portfolios | Portfolio Construction | Vol targeting | High | Empirical |
| 2017 | Fischer and Krauss, Deep Learning with LSTM for Financial Markets | Machine Learning | LSTM return prediction | Low / Medium | Empirical |
| 2018 | Zhang, Zohren and Roberts, DeepLOB | Machine Learning | CNN/LSTM LOB prediction | High | Empirical |
| 2018 | Xu, Gould and Howison, Multi-Level Order-Flow Imbalance | Market Microstructure | MLOFI | High | Empirical |
| 2018 | Hurst, Ooi and Pedersen, A Century of Evidence on Trend-Following | Momentum | Multi-asset trend | High | Empirical |
| 2018 | Gu, Kelly and Xiu, Empirical Asset Pricing via Machine Learning | Machine Learning | ML factor prediction | Medium | Empirical |
| 2019 | Liu and Tsyvinski, Risks and Returns of Cryptocurrency | Cryptocurrency | Crypto momentum / attention | High | Empirical |
| 2019 | Lehalle and Laruelle, Market Microstructure in Practice | Market Microstructure | Execution and queue logic | High | Practitioner / synthesis |
| 2020 | Makarov and Schoar, Trading and Arbitrage in Cryptocurrency Markets | Cryptocurrency | Cross-exchange arbitrage limits | High | Empirical |
| 2020 | Easley et al., Microstructure of Cryptocurrency Markets | Cryptocurrency | Crypto market quality | High | Empirical |
| 2020 | Alexander and Imeraj, Bitcoin Options and Volatility | Options & Derivatives | Crypto IV/RV | Medium | Empirical |
| 2020 | Lim, Zohren and Roberts, Enhancing Time-Series Momentum with Deep Learning | Machine Learning | Deep trend filters | Medium | Empirical |
| 2021 | Kolm, Turiel and Westray, Deep Order Flow Imbalance | Machine Learning | Deep OFI | High | Empirical |
| 2021 | Cong, Li and Wang, Tokenomics: Dynamic Adoption and Valuation | Cryptocurrency | Network/adoption factors | Medium | Theoretical / empirical |
| 2021 | Tadi and Kortchemski, Pairs Trading in Cryptocurrency Markets | Statistical Arbitrage | Dynamic cointegration | High | Empirical |
| 2022 | Liu, Tsyvinski and Wu, Common Risk Factors in Cryptocurrency | Cryptocurrency | Crypto factors | High | Empirical |
| 2022 | Nagy, Frey and Sapora, Deep Hedging of Derivatives | Options & Derivatives | Learned hedging with costs | Medium | Empirical / simulation |
| 2023 | Buehler et al., Deep Hedging | Options & Derivatives | Risk-aware hedging | Medium | Empirical / simulation |
| 2023 | Zeng et al., Financial Time Series Forecasting using CNN and Transformer | Machine Learning | CNN-transformer sequence model | Medium | Empirical |
| 2024 | Lucchese, Pakkanen and Veraart, Short-Term Predictability of Returns in Order Book Markets | Market Microstructure | LOB deep learning / alpha decay | High | Empirical |
| 2024 | He, Manela, Ross and von Wachter, Fundamentals of Perpetual Futures | Cryptocurrency | Perp no-arbitrage / funding | High | Theoretical / empirical |
| 2024 | Almeida et al., Risk Premia in the Bitcoin Market | Options & Derivatives | Bitcoin VRP / pricing kernel | Medium | Empirical |
| 2024 | Lalor and Swishchuk, Reinforcement Learning in Non-Markov Market-Making | Market Making | SAC quote control | Medium | Simulation |
| 2026 | Kitvanitphasu et al., Bitcoin Wild Moves | Market Microstructure | VPIN jump-risk warning | High | Empirical |
| 2025 | Exploring Risk and Return Profiles of Funding Rate Arbitrage on CEX and DEX | Cryptocurrency | Funding arbitrage risk/return | High | Empirical |
| 2025 | Pinto, High-Frequency Dynamics of Bitcoin Futures | Market Microstructure | BTC/ETH perp intraday microstructure | High | Empirical |
| 2026 | Raffaelli et al., Forecasting Bitcoin Price Movements using Hawkes and LOB Data | Market Microstructure | Hawkes + Bitcoin LOB | High | Empirical |

## By Year

### Foundational / Pre-2010

#### 1981 The Dynamics of Dealer Markets Under Competition
- **Authors:** Thomas S. Y. Ho, Hans R. Stoll
- **Source:** Journal of Finance, [JSTOR / publisher record](https://www.jstor.org/stable/2327553)
- **Strategy Type:** Market Making
- **Method:** Models dealer bid/ask quotes as a function of inventory risk and competition. The core practical idea is that inventory should move reservation prices even when the midprice forecast is unchanged.
- **Key Signal/Factor:** Inventory level, spread compensation, dealer risk aversion.
- **Reported Performance:** Theoretical.
- **Data Requirement:** Quotes, inventory, fills.
- **Time Horizon:** Intraday to high frequency.
- **Transaction Cost Assumption:** Endogenous spread model, not a live fee model.
- **Evidence Quality:** Theoretical.
- **Crypto Applicability:** Medium. The inventory logic maps to OKX, but modern crypto queueing, maker fees, and 24/7 funding are absent.
- **Implementation Readiness:** Ready as a conceptual constraint for `strategies/as_market_maker.py`.
- **Main Caveat / Failure Mode:** Does not model latency, cancellation, queue priority, or toxic flow.

#### 1985 Bid, Ask and Transaction Prices in a Specialist Market with Heterogeneously Informed Traders
- **Authors:** Lawrence R. Glosten, Paul R. Milgrom
- **Source:** Journal of Financial Economics, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/0304405X85900448)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Explains bid/ask spreads as compensation for adverse selection against informed traders. This is the theoretical root for treating OFI, OBI, and VPIN as information-asymmetry diagnostics.
- **Key Signal/Factor:** Trade direction, adverse selection probability.
- **Reported Performance:** Theoretical.
- **Data Requirement:** Trade signs and quotes.
- **Time Horizon:** Trade-by-trade.
- **Transaction Cost Assumption:** Spread arises endogenously.
- **Evidence Quality:** Theoretical.
- **Crypto Applicability:** High. Crypto perps are order-flow-driven and adverse-selection-heavy, especially around liquidations and news.
- **Implementation Readiness:** Ready as a design principle for spread widening and post-only quoting.
- **Main Caveat / Failure Mode:** Static specialist model; does not capture fragmented venues or spoofing.

#### 1985 Option Pricing and Replication with Transactions Costs
- **Authors:** Hayne E. Leland
- **Source:** Journal of Finance, [JSTOR / publisher record](https://www.jstor.org/stable/2327572)
- **Strategy Type:** Options & Derivatives
- **Method:** Adjusts option replication logic for proportional transaction costs. Useful for crypto options and delta-hedged volatility strategies where hedging cadence can erase the volatility edge.
- **Key Signal/Factor:** Hedging frequency, proportional cost, adjusted volatility.
- **Reported Performance:** Theoretical.
- **Data Requirement:** Options, underlying prices, fees/slippage.
- **Time Horizon:** Intraday to expiry.
- **Transaction Cost Assumption:** Explicit.
- **Evidence Quality:** Theoretical.
- **Crypto Applicability:** Medium. OKX options are less liquid than Deribit, so cost-aware hedging is essential.
- **Implementation Readiness:** Needs options data and hedge simulator.
- **Main Caveat / Failure Mode:** Simplified cost and diffusion assumptions.

#### 1993 Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency
- **Authors:** Narasimhan Jegadeesh, Sheridan Titman
- **Source:** Journal of Finance, [JSTOR / publisher record](https://www.jstor.org/stable/2328882)
- **Strategy Type:** Momentum / Trend Following
- **Method:** Documents intermediate-horizon cross-sectional momentum in equities. The generalizable concept is ranking assets by prior returns and holding winners against losers.
- **Key Signal/Factor:** 3- to 12-month past return excluding the most recent month.
- **Reported Performance:** Historically significant U.S. equity momentum profits before modern crowding.
- **Data Requirement:** Cross-sectional return history.
- **Time Horizon:** Weeks to months.
- **Transaction Cost Assumption:** Limited by modern standards.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. Cross-sectional crypto momentum exists, but OKX VIP0 costs and altcoin liquidity filters matter.
- **Implementation Readiness:** Needs universe scanner and portfolio layer extension.
- **Main Caveat / Failure Mode:** Momentum crashes and crowding.

#### 2006 Pairs Trading: Performance of a Relative-Value Arbitrage Rule
- **Authors:** Evan Gatev, William N. Goetzmann, K. Geert Rouwenhorst
- **Source:** Review of Financial Studies, [Oxford Academic](https://academic.oup.com/rfs/article-abstract/19/3/797/1610229)
- **Strategy Type:** Statistical Arbitrage
- **Method:** Forms equity pairs based on historical distance and trades convergence when normalized spreads diverge. It is a foundational empirical template for relative-value trading.
- **Key Signal/Factor:** Normalized pair distance, spread divergence and convergence.
- **Reported Performance:** Reports economically meaningful historical excess returns before full modern costs.
- **Data Requirement:** Cross-sectional prices.
- **Time Horizon:** Days to months.
- **Transaction Cost Assumption:** Discussed, but not equivalent to crypto order-book costs.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. The convergence logic maps to BTC/ETH and baskets, but crypto regimes drift faster.
- **Implementation Readiness:** Partly implemented in `strategies/pairs_trading.py`.
- **Main Caveat / Failure Mode:** Correlation breakdown and crowded convergence trades.

#### 2007 Giving Content to Investor Sentiment: The Role of Media in the Stock Market
- **Authors:** Paul C. Tetlock
- **Source:** Journal of Finance, [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2007.01232.x)
- **Strategy Type:** Alternative Data / Sentiment
- **Method:** Uses newspaper pessimism to study sentiment effects on market
  returns and trading volume. The reusable lesson is that text signals need a
  domain-specific event clock and careful decay assumptions.
- **Key Signal/Factor:** Media pessimism score.
- **Reported Performance:** Empirical predictability evidence, not a complete
  trading system.
- **Data Requirement:** Time-stamped news text and market data.
- **Time Horizon:** Daily.
- **Transaction Cost Assumption:** Limited.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Low / Medium. Useful for event-risk filtering, but
  crypto news is noisier and more manipulation-prone.
- **Implementation Readiness:** Watchlist only.
- **Main Caveat / Failure Mode:** Text source bias and decay instability.

#### 2008 High-Frequency Trading in a Limit Order Book
- **Authors:** Marco Avellaneda, Sasha Stoikov
- **Source:** Quantitative Finance, [arXiv](https://arxiv.org/abs/0711.2146)
- **Strategy Type:** Market Making
- **Method:** Solves an optimal market-making problem with CARA utility, stochastic midprice, inventory penalty, and distance-dependent fill intensity. Produces reservation price and optimal bid/ask spread formulas.
- **Key Signal/Factor:** Inventory, volatility, risk aversion, fill intensity.
- **Reported Performance:** Theoretical and simulation-based.
- **Data Requirement:** Quotes, fills, volatility, fill-intensity calibration.
- **Time Horizon:** High frequency.
- **Transaction Cost Assumption:** Spread/fill model; exchange fee model must be added.
- **Evidence Quality:** Theoretical / simulation.
- **Crypto Applicability:** High. The current system already implements an ergodic AS variant with OBI/OFI alpha and VPIN spread control.
- **Implementation Readiness:** Implemented in `strategies/as_market_maker.py`; needs calibration research.
- **Main Caveat / Failure Mode:** Brownian midprice and exponential fill assumptions are fragile in crypto jump regimes.

#### 2009 Variance Risk Premiums
- **Authors:** Peter Carr, Liuren Wu
- **Source:** Review of Financial Studies, [Oxford Academic](https://academic.oup.com/rfs/article-abstract/22/3/1311/1598132)
- **Strategy Type:** Options & Derivatives
- **Method:** Studies compensation for bearing variance risk across asset classes. Provides the conceptual foundation for short-volatility and variance-risk-premium strategies.
- **Key Signal/Factor:** Implied variance minus expected realized variance.
- **Reported Performance:** Documents persistent variance risk premia in traditional markets.
- **Data Requirement:** Options surface, realized volatility.
- **Time Horizon:** Days to months.
- **Transaction Cost Assumption:** Not a crypto execution model.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. BTC/ETH options often show high implied volatility, but liquidity and tail risk dominate.
- **Implementation Readiness:** Needs options data and risk-managed hedging module.
- **Main Caveat / Failure Mode:** Short-volatility tail losses can overwhelm steady carry.

#### 2009 Analytic Solutions for Optimal Statistical Arbitrage Trading
- **Authors:** William K. Bertram
- **Source:** Physica A, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0378437109003851)
- **Strategy Type:** Mean Reversion
- **Method:** Derives optimal entry and exit thresholds for spreads modeled as Ornstein-Uhlenbeck processes. Useful for turning OU half-life and volatility estimates into explicit trading bands.
- **Key Signal/Factor:** OU mean, speed, volatility, threshold distance.
- **Reported Performance:** Theoretical.
- **Data Requirement:** Spread time series.
- **Time Horizon:** Intraday to multi-day.
- **Transaction Cost Assumption:** Can include costs in threshold selection.
- **Evidence Quality:** Theoretical.
- **Crypto Applicability:** High. Directly maps to BTC/ETH spread z-scores and basis mean reversion.
- **Implementation Readiness:** Partly implemented through OU logic in `strategies/pairs_trading.py`.
- **Main Caveat / Failure Mode:** OU parameters are unstable in regime shifts.

### 2010-2015

#### 2010 Statistical Arbitrage in the U.S. Equities Market
- **Authors:** Marco Avellaneda, Jeong-Hyun Lee
- **Source:** Quantitative Finance, [Taylor & Francis](https://www.tandfonline.com/doi/abs/10.1080/14697680903124632)
- **Strategy Type:** Statistical Arbitrage
- **Method:** Trades residual mean reversion after removing common factors through PCA or ETF regressions. The structure is useful for crypto basket residuals after removing BTC and ETH beta.
- **Key Signal/Factor:** Factor residual z-score.
- **Reported Performance:** Reports strong historical Sharpe before recent decay and capacity pressure.
- **Data Requirement:** Cross-sectional prices, factor returns.
- **Time Horizon:** Intraday to daily.
- **Transaction Cost Assumption:** Discussed, but equity-specific.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. Useful for liquid perp baskets, but smaller OKX universe and fees limit breadth.
- **Implementation Readiness:** Needs basket scanner and factor residual signal.
- **Main Caveat / Failure Mode:** Alpha decay and factor misspecification.

#### 2011 Twitter Mood Predicts the Stock Market
- **Authors:** Johan Bollen, Huina Mao, Xiaojun Zeng
- **Source:** Journal of Computational Science, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S187775031100007X)
- **Strategy Type:** Alternative Data / Sentiment
- **Method:** Tests whether aggregate social mood from Twitter predicts market index moves. It introduced a popular social-sentiment framing, but replication and live usability are mixed.
- **Key Signal/Factor:** Social mood and sentiment dimensions.
- **Reported Performance:** Reports predictive accuracy improvements for DJIA direction.
- **Data Requirement:** Social media firehose, NLP model, market data.
- **Time Horizon:** Daily.
- **Transaction Cost Assumption:** Limited.
- **Evidence Quality:** Empirical / disputed.
- **Crypto Applicability:** Low. Crypto Twitter is noisy, manipulable, and hard to source cleanly.
- **Implementation Readiness:** Not practical for current OKX system.
- **Main Caveat / Failure Mode:** Look-ahead, data snooping, bot manipulation.

#### 2011 When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks
- **Authors:** Tim Loughran, Bill McDonald
- **Source:** Journal of Finance, [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2010.01625.x)
- **Strategy Type:** Alternative Data / Sentiment
- **Method:** Shows that general-purpose dictionaries misclassify finance text
  and introduces finance-specific word lists. This is a cautionary paper for
  building any crypto NLP signal from generic sentiment models.
- **Key Signal/Factor:** Finance-specific negative, positive, uncertainty, and
  litigious terms.
- **Reported Performance:** Empirical text-classification and return-relevance
  evidence.
- **Data Requirement:** Text corpus and market/event alignment.
- **Time Horizon:** Event to daily.
- **Transaction Cost Assumption:** Not a trading system.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. The method matters if exchange
  announcements, token filings, or news feeds are later used.
- **Implementation Readiness:** Research-only.
- **Main Caveat / Failure Mode:** Crypto vocabulary changes faster than equity
  filing language.

#### 2012 Flow Toxicity and Liquidity in a High-Frequency World
- **Authors:** David Easley, Marcos Lopez de Prado, Maureen O'Hara
- **Source:** Review of Financial Studies, [Oxford Academic](https://academic.oup.com/rfs/article-abstract/25/5/1457/1581626)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Introduces VPIN as a volume-clock toxicity metric based on buy/sell volume imbalance. For market making, VPIN is better used as a spread and participation control than as a directional signal.
- **Key Signal/Factor:** Volume-synchronized probability of informed trading.
- **Reported Performance:** Empirical warning metric around toxicity episodes.
- **Data Requirement:** Trades, trade classification, volume buckets.
- **Time Horizon:** Minutes to intraday.
- **Transaction Cost Assumption:** Not a trading cost model.
- **Evidence Quality:** Empirical / disputed.
- **Crypto Applicability:** Medium. The current system already uses VPIN directionlessly for spread width.
- **Implementation Readiness:** Implemented in `signals/vpin.py`; needs crypto-specific calibration.
- **Main Caveat / Failure Mode:** Mechanical correlation with volatility can create false alarms.

#### 2012 Time Series Momentum
- **Authors:** Tobias J. Moskowitz, Yao Hua Ooi, Lasse Heje Pedersen
- **Source:** Journal of Financial Economics, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0304405X11002613)
- **Strategy Type:** Momentum / Trend Following
- **Method:** Shows that an asset's own past return predicts its future return across futures and asset classes. For crypto, this suggests slower trend overlays rather than pure taker scalping.
- **Key Signal/Factor:** 1- to 12-month own return, volatility scaling.
- **Reported Performance:** Strong diversified trend-following performance across asset classes.
- **Data Requirement:** OHLCV returns across instruments.
- **Time Horizon:** Weeks to months.
- **Transaction Cost Assumption:** Included at a broad futures level.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Works naturally with perp/spot data, but turnover must be limited.
- **Implementation Readiness:** Needs new trend strategy or portfolio overlay.
- **Main Caveat / Failure Mode:** Trend reversals and crowded deleveraging.

#### 2013 Dealing with the Inventory Risk: A Solution to the Market Making Problem
- **Authors:** Olivier Gueant, Charles-Albert Lehalle, Joaquin Fernandez-Tapia
- **Source:** Mathematics and Financial Economics, [Springer](https://link.springer.com/article/10.1007/s11579-012-0087-0)
- **Strategy Type:** Market Making
- **Method:** Extends market-making control with inventory constraints and an infinite-horizon style solution. This is especially relevant to crypto because there is no daily close or terminal inventory horizon.
- **Key Signal/Factor:** Inventory penalty, asymptotic quote offsets.
- **Reported Performance:** Theoretical.
- **Data Requirement:** Quotes, fills, inventory, volatility.
- **Time Horizon:** High frequency.
- **Transaction Cost Assumption:** Spread/fill model.
- **Evidence Quality:** Theoretical.
- **Crypto Applicability:** High. The current README already notes fixed `T_minus_t=1.0` for 24/7 markets.
- **Implementation Readiness:** Implemented conceptually in AS market maker.
- **Main Caveat / Failure Mode:** Fill intensity calibration can drift quickly.

#### 2013 Buy Low Sell High: A High Frequency Trading Perspective
- **Authors:** Alvaro Cartea, Sebastian Jaimungal, Jason Ricci
- **Source:** SIAM Journal on Financial Mathematics, [SIAM](https://epubs.siam.org/doi/10.1137/120886238)
- **Strategy Type:** Market Making
- **Method:** Models optimal market making with alpha signals and inventory control. Supports the current design of adding OBI/OFI fair-value skew before applying inventory-aware quote placement.
- **Key Signal/Factor:** Short-term alpha, inventory, order arrival.
- **Reported Performance:** Theoretical / simulation.
- **Data Requirement:** Quotes, fills, alpha signal.
- **Time Horizon:** High frequency.
- **Transaction Cost Assumption:** Model-based.
- **Evidence Quality:** Theoretical / simulation.
- **Crypto Applicability:** High. Directly maps to OBI/OFI alpha plus AS quote logic.
- **Implementation Readiness:** Ready as a design reference for `as_market_maker.py`.
- **Main Caveat / Failure Mode:** Alpha half-life must exceed queue and cancel latency.

#### 2014 The Price Impact of Order Book Events
- **Authors:** Rama Cont, Arseniy Kukanov, Sasha Stoikov
- **Source:** Journal of Financial Econometrics, [Oxford Academic](https://academic.oup.com/jfec/article/12/1/47/816163)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Defines order flow imbalance from best bid/ask updates and shows a near-linear relationship with short-horizon price changes. It separates informative order-book updates from simple trade prints.
- **Key Signal/Factor:** OFI, depth-adjusted impact slope.
- **Reported Performance:** Empirical explanatory power for short-horizon price changes.
- **Data Requirement:** L1 quote updates.
- **Time Horizon:** Sub-second to minutes.
- **Transaction Cost Assumption:** Not a trading strategy paper.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Current `signals/obi_ofi.py` already uses this family of logic.
- **Implementation Readiness:** Implemented; extend with depth-normalized coefficients.
- **Main Caveat / Failure Mode:** Spoofing and queue churn can contaminate raw OFI.

#### 2014 The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality
- **Authors:** David H. Bailey, Marcos Lopez de Prado
- **Source:** Journal of Portfolio Management / SSRN, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
- **Strategy Type:** Portfolio Construction
- **Method:** Adjusts Sharpe ratio for multiple testing, non-normal returns, and selection bias. This is central for preventing parameter mining across many crypto strategies.
- **Key Signal/Factor:** Deflated Sharpe Ratio.
- **Reported Performance:** Methodological.
- **Data Requirement:** Backtest return series and trial count estimate.
- **Time Horizon:** Any.
- **Transaction Cost Assumption:** Depends on input returns.
- **Evidence Quality:** Methodological.
- **Crypto Applicability:** High. The repo already requires DSR >= 0.95 before live promotion.
- **Implementation Readiness:** Implemented in `analytics/dsr.py`.
- **Main Caveat / Failure Mode:** Trial count is hard to estimate honestly.

#### 2014 VPIN and the Flash Crash
- **Authors:** Torben G. Andersen, Oleg Bondarenko
- **Source:** Journal of Financial Markets / SSRN, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1881731)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Critiques VPIN's predictive interpretation and argues parts of its signal can be mechanically linked to volatility and volume. It is a required counterweight before using VPIN as a live risk switch.
- **Key Signal/Factor:** VPIN critique, false warning analysis.
- **Reported Performance:** Empirical critique.
- **Data Requirement:** Trades, volume buckets, event windows.
- **Time Horizon:** Intraday.
- **Transaction Cost Assumption:** Not applicable.
- **Evidence Quality:** Empirical critique.
- **Crypto Applicability:** High. Prevents overfitting VPIN thresholds in BTC/ETH.
- **Implementation Readiness:** Use to constrain VPIN to risk/spread control, not direction.
- **Main Caveat / Failure Mode:** Critique is based on futures microstructure, not crypto specifically.

#### 2014 Optimal Pairs Trading under Geometric Brownian Motions
- **Authors:** Zengjing Chen, Min Dai, Yiqing Du
- **Source:** Mathematical Finance, [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/mafi.12032)
- **Strategy Type:** Mean Reversion
- **Method:** Studies optimal pairs trading entry and liquidation under stochastic spread dynamics. Useful as a rigorous framing for stop and entry bands.
- **Key Signal/Factor:** Spread thresholds, liquidation boundary.
- **Reported Performance:** Theoretical.
- **Data Requirement:** Pair spread series.
- **Time Horizon:** Intraday to multi-day.
- **Transaction Cost Assumption:** Can be modeled in boundary choice.
- **Evidence Quality:** Theoretical.
- **Crypto Applicability:** Medium. Good for BTC/ETH, less reliable for unstable alt pairs.
- **Implementation Readiness:** Needs threshold optimization in `pairs_trading.py`.
- **Main Caveat / Failure Mode:** Model assumptions can fail in structural repricing.

#### 2015 Universal Features of Price Formation in Financial Markets
- **Authors:** Justin Sirignano, Rama Cont
- **Source:** SSRN / later Quantitative Finance, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2818143)
- **Strategy Type:** Machine Learning & Deep Learning
- **Method:** Uses deep learning on limit order books across stocks and finds shared price-formation patterns. Suggests that LOB models can learn transferable microstructure features.
- **Key Signal/Factor:** LOB tensor features.
- **Reported Performance:** Empirical predictive gains in equity LOB data.
- **Data Requirement:** Deep LOB snapshots and event labels.
- **Time Horizon:** Short horizon.
- **Transaction Cost Assumption:** Mostly prediction-focused.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium / High. Transfer idea is relevant, but OKX data volume and label leakage controls are critical.
- **Implementation Readiness:** Needs model training pipeline.
- **Main Caveat / Failure Mode:** Prediction accuracy may not survive costs and queue priority.

### 2016-2019

#### 2016 Building Diversified Portfolios that Outperform Out-of-Sample
- **Authors:** Marcos Lopez de Prado
- **Source:** Journal of Portfolio Management / SSRN, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678)
- **Strategy Type:** Portfolio Construction
- **Method:** Introduces Hierarchical Risk Parity to allocate without inverting unstable covariance matrices. Useful for combining strategy sleeves under limited capital.
- **Key Signal/Factor:** Tree clustering, inverse-variance allocation within clusters.
- **Reported Performance:** Reports improved out-of-sample robustness versus mean-variance in simulations.
- **Data Requirement:** Return covariance matrix.
- **Time Horizon:** Portfolio rebalance horizon.
- **Transaction Cost Assumption:** Not central.
- **Evidence Quality:** Empirical / methodological.
- **Crypto Applicability:** High. Good fit for combining AS, OBI, funding, and pairs risk budgets.
- **Implementation Readiness:** Could extend `portfolio/allocation.py`.
- **Main Caveat / Failure Mode:** Correlations jump toward one during crypto stress.

#### 2016 Momentum Crashes
- **Authors:** Kent Daniel, Tobias J. Moskowitz
- **Source:** Journal of Financial Economics, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0304405X16301490)
- **Strategy Type:** Momentum / Trend Following
- **Method:** Shows momentum strategies suffer severe crash risk after market stress and during rebounds. Supports volatility scaling and regime filters for crypto trend strategies.
- **Key Signal/Factor:** Momentum exposure, market stress, rebound regime.
- **Reported Performance:** Empirical; documents severe crash episodes and dynamic mitigation.
- **Data Requirement:** Return history and volatility/regime variables.
- **Time Horizon:** Weeks to months.
- **Transaction Cost Assumption:** Broad empirical treatment.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Crypto momentum is crash-prone after liquidation cascades.
- **Implementation Readiness:** Use as a risk overlay in trend strategy.
- **Main Caveat / Failure Mode:** Crash predictors are themselves unstable.

#### 2017 Volatility-Managed Portfolios
- **Authors:** Alan Moreira, Tyler Muir
- **Source:** Journal of Finance, [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513)
- **Strategy Type:** Portfolio Construction
- **Method:** Scales factor exposure inversely with recent volatility. The key implementation idea is to target risk dynamically rather than keep notional exposure fixed.
- **Key Signal/Factor:** Realized volatility target.
- **Reported Performance:** Reports large alpha improvements for several equity factors.
- **Data Requirement:** Strategy returns or asset returns.
- **Time Horizon:** Daily to monthly.
- **Transaction Cost Assumption:** Considered at portfolio level, but not crypto-specific.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Current `portfolio/sizing.py` already supports vol targeting.
- **Implementation Readiness:** Implemented conceptually; extend per-strategy risk budget.
- **Main Caveat / Failure Mode:** Volatility spikes can force selling after losses.

#### 2017 Deep Learning with Long Short-Term Memory Networks for Financial Market Predictions
- **Authors:** Thomas Fischer, Christopher Krauss
- **Source:** European Journal of Operational Research, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0377221717310652)
- **Strategy Type:** Machine Learning & Deep Learning
- **Method:** Tests LSTM models for equity return prediction. Provides an early deep-learning benchmark but not a microstructure-aware trading system.
- **Key Signal/Factor:** LSTM sequence features.
- **Reported Performance:** Reports strong equity prediction/backtest results in the sample period.
- **Data Requirement:** Panel return history.
- **Time Horizon:** Daily.
- **Transaction Cost Assumption:** Limited relative to HFT.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Low / Medium. Better as a slow regime classifier than direct high-turnover signal.
- **Implementation Readiness:** Needs ML pipeline and strict leakage controls.
- **Main Caveat / Failure Mode:** Overfitting and regime instability.

#### 2018 DeepLOB: Deep Convolutional Neural Networks for Limit Order Books
- **Authors:** Zihao Zhang, Stefan Zohren, Stephen Roberts
- **Source:** IEEE Transactions on Signal Processing, [arXiv](https://arxiv.org/abs/1808.03668)
- **Strategy Type:** Machine Learning & Deep Learning
- **Method:** Combines CNN and LSTM/Inception-style modules for LOB price movement classification. It is a major template for converting multi-level order books into short-horizon forecasts.
- **Key Signal/Factor:** LOB tensor, short-horizon direction label.
- **Reported Performance:** Reports strong classification performance on benchmark LOB data.
- **Data Requirement:** L2/L3 order book snapshots.
- **Time Horizon:** Events to seconds/minutes.
- **Transaction Cost Assumption:** Prediction-focused; execution costs must be added.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. OKX book data can feed this, but maker-only execution must be modeled.
- **Implementation Readiness:** Needs model training and walk-forward inference pipeline.
- **Main Caveat / Failure Mode:** Accurate direction labels may still be untradeable after queue costs.

#### 2018 Multi-Level Order-Flow Imbalance in a Limit Order Book
- **Authors:** Christopher Xu, Martin D. Gould, Sam D. Howison
- **Source:** arXiv, [arXiv](https://arxiv.org/abs/1804.09912)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Extends L1 OFI to multiple book levels and shows deeper levels add explanatory power. This is a natural next upgrade from the current OBI/OFI module.
- **Key Signal/Factor:** MLOFI across depth levels.
- **Reported Performance:** Empirical explanatory improvement over L1 OFI.
- **Data Requirement:** L2 order book updates.
- **Time Horizon:** Short horizon.
- **Transaction Cost Assumption:** Prediction-focused.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Crypto books are deep but noisy; depth-weighted filters are practical.
- **Implementation Readiness:** Extend `signals/obi_ofi.py`.
- **Main Caveat / Failure Mode:** Spoofing and fleeting liquidity can dominate deeper levels.

#### 2018 A Century of Evidence on Trend-Following Investing
- **Authors:** Brian Hurst, Yao Hua Ooi, Lasse Heje Pedersen
- **Source:** AQR working paper, [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- **Strategy Type:** Momentum / Trend Following
- **Method:** Reviews long-term trend-following evidence across asset classes and crisis periods. Useful for sizing crypto trend as a slower sleeve rather than a standalone scalper.
- **Key Signal/Factor:** Multi-horizon trend with volatility scaling.
- **Reported Performance:** Positive long-run trend-following evidence across many decades.
- **Data Requirement:** Liquid asset returns.
- **Time Horizon:** Weeks to months.
- **Transaction Cost Assumption:** Broadly discussed.
- **Evidence Quality:** Empirical synthesis.
- **Crypto Applicability:** High. BTC/ETH perps are liquid and trend strongly, but tail events require stops.
- **Implementation Readiness:** Add trend overlay or portfolio sleeve.
- **Main Caveat / Failure Mode:** Long flat periods and whipsaws.

#### 2018 Empirical Asset Pricing via Machine Learning
- **Authors:** Shihao Gu, Bryan Kelly, Dacheng Xiu
- **Source:** Review of Financial Studies, [Oxford Academic](https://academic.oup.com/rfs/article/33/5/2223/5758276)
- **Strategy Type:** Machine Learning & Deep Learning
- **Method:** Benchmarks many ML methods for return prediction using firm characteristics. The broader lesson is that nonlinear models need disciplined validation and economically meaningful features.
- **Key Signal/Factor:** ML-predicted expected returns.
- **Reported Performance:** Reports improved predictive performance versus linear methods.
- **Data Requirement:** Rich cross-sectional features.
- **Time Horizon:** Monthly equity context.
- **Transaction Cost Assumption:** Not crypto microstructure focused.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. Useful methodology, but crypto feature sets differ.
- **Implementation Readiness:** Needs feature store and CPCV adaptation.
- **Main Caveat / Failure Mode:** Model complexity can hide overfitting.

#### 2019 Risks and Returns of Cryptocurrency
- **Authors:** Yukun Liu, Aleh Tsyvinski
- **Source:** Review of Financial Studies, [Oxford Academic](https://academic.oup.com/rfs/article/34/6/2689/5912028)
- **Strategy Type:** Cryptocurrency-Specific
- **Method:** Studies crypto returns, risk factors, and predictors such as momentum and investor attention. Provides evidence that crypto behaves differently from traditional currencies and commodities.
- **Key Signal/Factor:** Momentum, attention, crypto-specific factors.
- **Reported Performance:** Empirical predictability evidence.
- **Data Requirement:** Crypto returns, attention proxies.
- **Time Horizon:** Daily to weekly.
- **Transaction Cost Assumption:** Not OKX-specific.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Directly relevant to BTC/ETH and liquid crypto baskets.
- **Implementation Readiness:** Add slower crypto factor sleeve.
- **Main Caveat / Failure Mode:** Early-sample crypto effects may decay.

#### 2019 Market Microstructure in Practice
- **Authors:** Charles-Albert Lehalle, Sophie Laruelle
- **Source:** World Scientific, [publisher](https://www.worldscientific.com/worldscibooks/10.1142/11030)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Practitioner synthesis of microstructure, execution, queueing, and optimal trading. Useful as an implementation reference for turning academic signals into execution-aware logic.
- **Key Signal/Factor:** Queue, execution cost, market impact.
- **Reported Performance:** Practitioner / methodological.
- **Data Requirement:** Quotes, trades, fills.
- **Time Horizon:** Intraday.
- **Transaction Cost Assumption:** Central.
- **Evidence Quality:** Practitioner synthesis.
- **Crypto Applicability:** High. OKX maker-only edge depends on execution details more than signal novelty.
- **Implementation Readiness:** Use across execution and risk modules.
- **Main Caveat / Failure Mode:** Not crypto-specific.

### 2020-2023

#### 2020 Trading and Arbitrage in Cryptocurrency Markets
- **Authors:** Igor Makarov, Antoinette Schoar
- **Source:** Journal of Financial Economics, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0304405X20301951)
- **Strategy Type:** Cryptocurrency-Specific
- **Method:** Documents large and persistent crypto price deviations across exchanges, showing limits to arbitrage. The key lesson is that apparent spreads are constrained by capital, settlement, and exchange risk.
- **Key Signal/Factor:** Cross-exchange basis and price dispersion.
- **Reported Performance:** Empirical arbitrage spread evidence.
- **Data Requirement:** Cross-exchange prices, fees, transfer constraints.
- **Time Horizon:** Minutes to days.
- **Transaction Cost Assumption:** Discussed at market level.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Useful for interpreting OKX basis and funding dislocations.
- **Implementation Readiness:** Needs multi-venue data if used directly.
- **Main Caveat / Failure Mode:** Exchange risk and withdrawal latency can dominate.

#### 2020 The Microstructure of Cryptocurrency Markets
- **Authors:** David Easley, Maureen O'Hara, Soumya Basu
- **Source:** SSRN / Journal work, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3590441)
- **Strategy Type:** Cryptocurrency-Specific
- **Method:** Studies how crypto market design and fragmentation affect liquidity and price discovery. Relevant for deciding when OKX-only signals need cross-venue confirmation.
- **Key Signal/Factor:** Liquidity, spreads, market quality.
- **Reported Performance:** Empirical market-quality analysis.
- **Data Requirement:** Crypto trades/quotes across venues.
- **Time Horizon:** Intraday to daily.
- **Transaction Cost Assumption:** Market quality focus.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High.
- **Implementation Readiness:** Use as rationale for cross-venue filters.
- **Main Caveat / Failure Mode:** Venue structure changes quickly.

#### 2020 Bitcoin Options and the Volatility Risk Premium
- **Authors:** Carol Alexander, Arben Imeraj
- **Source:** Journal of Alternative Investments / SSRN, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3485098)
- **Strategy Type:** Options & Derivatives
- **Method:** Examines Bitcoin option implied volatility, realized volatility, and variance risk premium. Provides a starting point for crypto option carry ideas.
- **Key Signal/Factor:** BTC implied volatility minus realized volatility.
- **Reported Performance:** Empirical evidence of crypto volatility premia.
- **Data Requirement:** BTC options, realized volatility, hedging costs.
- **Time Horizon:** Days to months.
- **Transaction Cost Assumption:** Must be modeled carefully.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. Relevant but OKX option liquidity is a bottleneck.
- **Implementation Readiness:** Research-only until options data and hedging simulator exist.
- **Main Caveat / Failure Mode:** Volatility jumps and liquidity gaps.

#### 2020 Enhancing Time-Series Momentum Strategies Using Deep Neural Networks
- **Authors:** Bryan Lim, Stefan Zohren, Stephen Roberts
- **Source:** Journal of Financial Data Science / arXiv, [arXiv](https://arxiv.org/abs/1904.04912)
- **Strategy Type:** Machine Learning & Deep Learning
- **Method:** Uses neural networks to improve trend-following allocation and nonlinear exposure. For crypto, this is better framed as a trend-sizing model than a black-box direction predictor.
- **Key Signal/Factor:** Multi-asset lagged returns and volatility features.
- **Reported Performance:** Empirical improvements over simple time-series momentum benchmarks.
- **Data Requirement:** Multi-asset returns.
- **Time Horizon:** Daily to monthly.
- **Transaction Cost Assumption:** Portfolio-level.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium. Useful for slower BTC/ETH trend sizing.
- **Implementation Readiness:** Needs ML pipeline.
- **Main Caveat / Failure Mode:** Model instability and difficult attribution.

#### 2021 Deep Order Flow Imbalance: Extracting Alpha at Multiple Horizons from the Limit Order Book
- **Authors:** Petter N. Kolm, Jeremy Turiel, Nicholas Westray
- **Source:** Mathematical Finance, [arXiv](https://arxiv.org/abs/2106.09459)
- **Strategy Type:** Machine Learning & Deep Learning
- **Method:** Builds deep learning models from OFI features across horizons. The practical lesson is that engineered OFI features can be a strong input even before raw LOB deep models.
- **Key Signal/Factor:** Multi-horizon OFI features.
- **Reported Performance:** Empirical alpha extraction across horizons.
- **Data Requirement:** LOB updates and OFI feature construction.
- **Time Horizon:** Seconds to minutes.
- **Transaction Cost Assumption:** Prediction-focused; execution model needed.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Natural extension to `signals/obi_ofi.py`.
- **Implementation Readiness:** Add multi-horizon OFI features before deep model complexity.
- **Main Caveat / Failure Mode:** Feature alpha decays fast and can be fee-sensitive.

#### 2021 Tokenomics: Dynamic Adoption and Valuation
- **Authors:** Lin William Cong, Ye Li, Neng Wang
- **Source:** Review of Financial Studies, [Oxford Academic](https://academic.oup.com/rfs/article/34/3/1105/5863394)
- **Strategy Type:** Cryptocurrency-Specific
- **Method:** Models token valuation through user adoption and platform network effects. It is less directly tradeable, but helpful for longer-horizon crypto factor thinking.
- **Key Signal/Factor:** Adoption, network value, user growth.
- **Reported Performance:** Theoretical / empirical framing.
- **Data Requirement:** Token fundamentals and adoption data.
- **Time Horizon:** Weeks to months.
- **Transaction Cost Assumption:** Not a trading-cost paper.
- **Evidence Quality:** Theoretical / empirical.
- **Crypto Applicability:** Medium. Less relevant to BTC/ETH perps, more relevant to altcoin selection.
- **Implementation Readiness:** Not immediate.
- **Main Caveat / Failure Mode:** Fundamental data quality is uneven.

#### 2021 Pairs Trading in Cryptocurrency Markets
- **Authors:** Nikola Tadic, Milan Kortchemski
- **Source:** arXiv, [arXiv](https://arxiv.org/abs/2109.10662)
- **Strategy Type:** Statistical Arbitrage
- **Method:** Tests cointegration and dynamic pair selection in crypto markets. Useful for upgrading static pairs into rolling selection and regime-aware filters.
- **Key Signal/Factor:** Cointegration tests, dynamic hedge ratio, spread z-score.
- **Reported Performance:** Empirical crypto pairs results with meaningful drawdowns.
- **Data Requirement:** Crypto price panels.
- **Time Horizon:** Intraday to daily.
- **Transaction Cost Assumption:** Needs careful exchange-specific modeling.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Direct fit with `strategies/pairs_trading.py`.
- **Implementation Readiness:** Extend pair selection and validation.
- **Main Caveat / Failure Mode:** Cointegration breaks and liquidity varies by coin.

#### 2022 Common Risk Factors in Cryptocurrency
- **Authors:** Yukun Liu, Aleh Tsyvinski, Xi Wu
- **Source:** Journal of Finance / NBER, [NBER](https://www.nber.org/papers/w25882)
- **Strategy Type:** Cryptocurrency-Specific
- **Method:** Proposes and tests common crypto risk factors. Useful for decomposing strategy returns into market, size, momentum, and network-like exposures.
- **Key Signal/Factor:** Crypto factor exposures.
- **Reported Performance:** Empirical factor evidence.
- **Data Requirement:** Cross-sectional crypto returns and characteristics.
- **Time Horizon:** Daily to monthly.
- **Transaction Cost Assumption:** Not OKX execution-specific.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Helps avoid mistaking beta for alpha.
- **Implementation Readiness:** Add attribution layer before deploying basket strategies.
- **Main Caveat / Failure Mode:** Factor definitions evolve with the crypto universe.

#### 2022 Deep Hedging: Learning to Simulate Equity Option Markets
- **Authors:** Hans Buehler and coauthors
- **Source:** Quantitative Finance / arXiv, [arXiv](https://arxiv.org/abs/1802.03042)
- **Strategy Type:** Options & Derivatives
- **Method:** Learns hedging policies under costs and risk preferences. Relevant if crypto options are later added, especially because cost-aware hedging is more important than Black-Scholes deltas alone.
- **Key Signal/Factor:** Learned hedging policy, risk measure.
- **Reported Performance:** Simulation / empirical hedging improvements.
- **Data Requirement:** Options, underlying, cost model.
- **Time Horizon:** Intraday to expiry.
- **Transaction Cost Assumption:** Explicit.
- **Evidence Quality:** Empirical / simulation.
- **Crypto Applicability:** Medium. Useful but beyond current OKX strategy set.
- **Implementation Readiness:** Not immediate.
- **Main Caveat / Failure Mode:** Training realism and tail behavior.

#### 2023 Financial Time Series Forecasting using CNN and Transformer
- **Authors:** Zhen Zeng, Rachneet Kaur, Suchetha Siddagangappa, Saba Rahimi, Tucker Balch, Manuela Veloso
- **Source:** arXiv, [arXiv:2304.04912](https://arxiv.org/abs/2304.04912)
- **Strategy Type:** Machine Learning & Deep Learning
- **Method:** Combines CNNs for local patterns with transformers for longer
  dependencies in intraday stock-price forecasting. For this repo, this is a
  template for feature learning or regime classification, not a reason to trade
  raw predictions directly.
- **Key Signal/Factor:** CNN-transformer sequence forecast.
- **Reported Performance:** Reports outperformance versus several statistical
  and deep-learning baselines on intraday stock data.
- **Data Requirement:** Large clean intraday sequence dataset.
- **Time Horizon:** Intraday.
- **Transaction Cost Assumption:** Prediction-focused; execution costs need to be
  added.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium.
- **Implementation Readiness:** Research-only.
- **Main Caveat / Failure Mode:** Leakage, overfitting, and unstable live inference.

### 2024-present

#### 2024 The Short-Term Predictability of Returns in Order Book Markets: A Deep Learning Perspective
- **Authors:** Lorenzo Lucchese, Mikko S. Pakkanen, Almut E. D. Veraart
- **Source:** International Journal of Forecasting, [DOI record](https://doi.org/10.1016/j.ijforecast.2024.02.001)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Studies short-term return predictability from order-book data
  using deep learning. The main takeaway for OKX is that raw prediction must be
  mapped to maker-fill probability, queue survival, and fee-aware PnL.
- **Key Signal/Factor:** LOB imbalance, OFI, depth, short-horizon labels.
- **Reported Performance:** Empirical predictability evidence, dataset-dependent.
- **Data Requirement:** L2 order book snapshots and trades.
- **Time Horizon:** Milliseconds to minutes.
- **Transaction Cost Assumption:** Often incomplete.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High.
- **Implementation Readiness:** Extend `signals/obi_ofi.py` and replay backtests first.
- **Main Caveat / Failure Mode:** Label quality and fee/queue realism.

#### 2024 Fundamentals of Perpetual Futures
- **Authors:** Songrun He, Asaf Manela, Omri Ross, Victor von Wachter
- **Source:** arXiv / SSRN, [arXiv:2212.06888](https://arxiv.org/abs/2212.06888)
- **Strategy Type:** Cryptocurrency-Specific
- **Method:** Derives perpetual futures no-arbitrage pricing and trading-cost
  bounds, then documents empirical deviations and arbitrage opportunities in
  crypto markets. Directly relevant to delta-neutral spot/perp carry and basis
  timing.
- **Key Signal/Factor:** Funding rate, premium index, basis, open interest.
- **Reported Performance:** Reports high-Sharpe implied arbitrage opportunities,
  with deviations declining over time.
- **Data Requirement:** Funding history, spot/perp prices, borrow/fee data.
- **Time Horizon:** Hours to weeks.
- **Transaction Cost Assumption:** Must include exchange fee, borrow, and rebalancing.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High. Current `funding_carry.py` is the direct implementation surface.
- **Implementation Readiness:** Implemented baseline; add regime and crowding filters.
- **Main Caveat / Failure Mode:** Funding reversals, liquidation risk, exchange risk.

#### 2024 Risk Premia in the Bitcoin Market
- **Authors:** Caio Almeida, Maria Grith, Ratmir Miftachov, Zijin Wang
- **Source:** arXiv, [arXiv:2410.15195](https://arxiv.org/abs/2410.15195)
- **Strategy Type:** Options & Derivatives
- **Method:** Studies Bitcoin first- and second-moment risk premia using options
  and realized returns. Useful for a future small-size volatility sleeve, but not
  yet a fit for the current production system.
- **Key Signal/Factor:** BTC IV/RV spread, skew, term structure.
- **Reported Performance:** Finds Bitcoin has a higher variance risk premium
  than the S&P 500, with regime-dependent premia.
- **Data Requirement:** Options chain, Greeks, realized volatility, hedging simulator.
- **Time Horizon:** Days to expiry.
- **Transaction Cost Assumption:** Must be explicit.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** Medium.
- **Implementation Readiness:** Research-only until options module exists.
- **Main Caveat / Failure Mode:** Jump risk and liquidity gaps.

#### 2024 Reinforcement Learning in Non-Markov Market-Making
- **Authors:** Luca Lalor, Anatoliy Swishchuk
- **Source:** arXiv, [arXiv:2410.14504](https://arxiv.org/abs/2410.14504)
- **Strategy Type:** Market Making
- **Method:** Applies soft actor-critic reinforcement learning to a market-making
  problem with semi-Markov and Hawkes jump-diffusion dynamics. The practical use
  in this repo should be parameter adaptation, not direct unsupervised live
  quoting.
- **Key Signal/Factor:** State-dependent quote offsets and inventory policy.
- **Reported Performance:** Simulation and training/test results; not a live
  crypto trading record.
- **Data Requirement:** Event-level simulator with realistic fills.
- **Time Horizon:** High frequency.
- **Transaction Cost Assumption:** Depends on simulator realism.
- **Evidence Quality:** Survey / empirical.
- **Crypto Applicability:** Medium.
- **Implementation Readiness:** Use only after replay simulator is trusted.
- **Main Caveat / Failure Mode:** Sim-to-live gap and reward hacking.

#### 2026 Bitcoin Wild Moves: Evidence from Order Flow Toxicity and Price Jumps
- **Authors:** Atiwat Kitvanitphasu, Khine Kyaw, Tanakorn Likitapiwat, Sirimon Treepongkaruna
- **Source:** Research in International Business and Finance, [EconPapers](https://econpapers.repec.org/article/eeeriibaf/v_3a81_3ay_3a2026_3ai_3ac_3as0275531925004192.htm)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Tests the dynamic relationship between VPIN order-flow toxicity and
  Bitcoin price jumps using high-frequency data and VAR modeling. For this repo,
  the conservative use remains jump-risk throttling rather than directional
  prediction.
- **Key Signal/Factor:** VPIN, jump probability, volume imbalance.
- **Reported Performance:** Finds VPIN significantly predicts future Bitcoin
  price jumps in the studied sample.
- **Data Requirement:** Trades, volume buckets, jump labels.
- **Time Horizon:** Minutes to hours.
- **Transaction Cost Assumption:** Not a full execution model.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High.
- **Implementation Readiness:** Extend `signals/vpin.py` with jump-risk calibration.
- **Main Caveat / Failure Mode:** VPIN thresholds may be venue-specific.

#### 2025 Exploring Risk and Return Profiles of Funding Rate Arbitrage on CEX and DEX
- **Authors:** Warodom Werapun, Tanakorn Karode, Jakapan Suaboot, Tanwa Arpornthip, Esther Sangiamkul
- **Source:** Blockchain: Research and Applications, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2096720925000818)
- **Strategy Type:** Cryptocurrency-Specific
- **Method:** Studies funding-rate arbitrage across centralized and decentralized
  perpetual futures venues. It is directly relevant to separating apparent APR
  from liquidation, venue, and basis risk.
- **Key Signal/Factor:** Funding rate, venue type, open interest, risk/return.
- **Reported Performance:** Empirical CEX/DEX funding arbitrage risk-return
  evidence.
- **Data Requirement:** Funding, prices, venue data, liquidity and cost estimates.
- **Time Horizon:** Hours to weeks.
- **Transaction Cost Assumption:** Venue-specific and central to interpretation.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High.
- **Implementation Readiness:** Extend `funding_carry.py` with risk-return
  filters before adding any venue expansion.
- **Main Caveat / Failure Mode:** CEX/DEX results may not transfer directly to
  OKX-only execution.

#### 2025 High-Frequency Dynamics of Bitcoin Futures: An Examination of Market Microstructure
- **Authors:** Mateus Gonzalez de Freitas Pinto
- **Source:** Borsa Istanbul Review, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2214845025001188)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Studies high-frequency BTC and ETH perpetual futures from 2020 to
  2024 and compares market microstructure frameworks such as the Mixture of
  Distributions Hypothesis and Intraday Trading Invariance Hypothesis. Useful for
  calibrating intraday volatility, trade-size, and activity assumptions.
- **Key Signal/Factor:** Intraday volume, trade count, trade size, volatility per
  transaction.
- **Reported Performance:** Empirical market-structure evidence, not a trading
  strategy.
- **Data Requirement:** High-frequency perp trade data.
- **Time Horizon:** 1-minute to daily aggregation.
- **Transaction Cost Assumption:** Not a trading-cost model.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High.
- **Implementation Readiness:** Use to calibrate replay/backtest assumptions and
  volatility regime filters.
- **Main Caveat / Failure Mode:** Binance futures data may not transfer perfectly
  to OKX.

#### 2026 Forecasting Bitcoin Price Movements using Multivariate Hawkes Processes and Limit Order Book Data
- **Authors:** Davide Raffaelli, Raffaele Giuseppe Cestari, Daniele Marazzina, Simone Formentin and coauthors
- **Source:** Decisions in Economics and Finance, [Springer](https://link.springer.com/article/10.1007/s10203-026-00570-z)
- **Strategy Type:** Market Microstructure & HFT
- **Method:** Uses multivariate Hawkes processes and Bitcoin LOB data to forecast
  short-term price movements. This is relevant for event-time modeling of order
  arrivals and cancellations.
- **Key Signal/Factor:** Hawkes intensity, LOB state, short-term Bitcoin returns.
- **Reported Performance:** Empirical forecast evaluation.
- **Data Requirement:** Bitcoin LOB event data.
- **Time Horizon:** Event time to short horizon.
- **Transaction Cost Assumption:** Forecasting-focused; execution costs must be
  added.
- **Evidence Quality:** Empirical.
- **Crypto Applicability:** High.
- **Implementation Readiness:** Research-only; could inform simulator and order
  arrival modeling.
- **Main Caveat / Failure Mode:** Forecast accuracy does not automatically imply
  maker-fill profitability.

## By Strategy Category

### Market Microstructure & HFT

Core papers: Glosten and Milgrom 1985; Easley, Lopez de Prado and O'Hara 2012;
Cont, Kukanov and Stoikov 2014; Andersen and Bondarenko 2014; Xu, Gould and
Howison 2018; Lehalle and Laruelle 2019; recent 2024-2026 crypto LOB and VPIN
studies.

**Reusable signals:** OBI, OFI, multi-level OFI, microprice, VPIN, venue lead-lag.

**Best OKX fit:** Extend `signals/obi_ofi.py`; keep VPIN as spread/risk control,
not direction.

### Market Making

Core papers: Ho and Stoll 1981; Avellaneda and Stoikov 2008; Gueant, Lehalle and
Fernandez-Tapia 2013; Cartea, Jaimungal and Ricci 2013; recent RL market-making
benchmarks.

**Reusable signals:** Inventory skew, fill-intensity calibration, alpha-aware fair
value, toxicity-aware spread widening.

**Best OKX fit:** Extend `strategies/as_market_maker.py` and
`strategies/obi_market_maker.py`.

### Statistical Arbitrage

Core papers: Gatev, Goetzmann and Rouwenhorst 2006; Avellaneda and Lee 2010;
Tadic and Kortchemski 2021.

**Reusable signals:** Pair z-score, cointegration, Kalman hedge ratio, factor
residual mean reversion.

**Best OKX fit:** Extend `strategies/pairs_trading.py` with dynamic pair
selection and factor residual baskets.

### Momentum / Trend Following

Core papers: Jegadeesh and Titman 1993; Moskowitz, Ooi and Pedersen 2012; Daniel
and Moskowitz 2016; Hurst, Ooi and Pedersen 2018.

**Reusable signals:** Time-series trend, cross-sectional momentum, volatility
scaling, crash-risk filters.

**Best OKX fit:** Add slow trend sleeve; avoid pure taker short-horizon momentum.

### Mean Reversion

Core papers: Bertram 2009; Chen, Dai and Du 2014; crypto pairs literature.

**Reusable signals:** OU half-life, optimal entry/exit bands, basis z-score.

**Best OKX fit:** Improve pairs and basis/funding timing.

### Machine Learning & Deep Learning

Core papers: Sirignano and Cont 2015; Fischer and Krauss 2017; DeepLOB 2018; Gu,
Kelly and Xiu 2018; Lim, Zohren and Roberts 2020; Kolm, Turiel and Westray 2021;
recent transformer and crypto-perp ML studies.

**Reusable signals:** Multi-horizon OFI, LOB tensors, regime classification,
nonlinear trend sizing.

**Best OKX fit:** Start with engineered features and walk-forward models before
raw deep networks.

### Portfolio Construction

Core papers: Bailey and Lopez de Prado 2014; Lopez de Prado 2016; Moreira and
Muir 2017.

**Reusable signals:** Deflated Sharpe Ratio, HRP, volatility targeting.

**Best OKX fit:** Already partly implemented in `analytics/dsr.py` and
`portfolio/sizing.py`; extend to multi-strategy allocation.

### Cryptocurrency-Specific

Core papers: Liu and Tsyvinski 2019; Makarov and Schoar 2020; Easley, O'Hara and
Basu 2020; Liu, Tsyvinski and Wu 2022; funding/perp and price-discovery studies.

**Reusable signals:** Funding carry, basis, crypto momentum, exchange
fragmentation, crypto factor attribution.

**Best OKX fit:** Extend `strategies/funding_carry.py`; add basis/funding
regime filters.

### Alternative Data / Sentiment

Core papers: Bollen, Mao and Zeng 2011; crypto sentiment literature.

**Reusable signals:** Social mood, attention, NLP tone.

**Best OKX fit:** Watchlist only unless clean data source exists. Use as a slow
risk filter, not a primary execution signal.

### Options & Derivatives

Core papers: Leland 1985; Carr and Wu 2009; Alexander and Imeraj 2020; deep
hedging and Bitcoin VRP papers.

**Reusable signals:** Variance risk premium, IV/RV spread, cost-aware hedging.

**Best OKX fit:** Research-only until options data and a hedge simulator are
added.

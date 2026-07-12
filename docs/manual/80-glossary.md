---
status: current
type: manual
owner: human
created: 2026-06-25
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Glossary

| Term | Meaning |
| --- | --- |
| artifact | Reviewable output from a backtest or validation run, such as result JSON, CSV, summary, or DB payload |
| backfill | Historical ingest for a fixed UTC range |
| canonical candles | DB candle rows selected by canonical source policy |
| checkpoint / resume | Ingest state that lets a long backfill restart from the last completed cursor |
| CPCV | Combinatorial Purged Cross-Validation; uses purge/embargo to reduce leakage |
| `ct_val` | Contract value; affects notional, PnL, funding, margin, and liquidation |
| DB parity | Check that artifact price/funding/external observations match DB source rows |
| DVOL | Deribit volatility index; an implied-volatility index level, not a tradable perp price |
| DSR | Deflated Sharpe Ratio; adjusts Sharpe evidence for multiple trials/selection |
| external observations | Rows in `external_observations` for non-OHLCV datasets such as Deribit, Binance Vision OI, Fear & Greed, FRED, or yfinance |
| fill rate | Signal/order rows that turn into fills |
| forward accumulation | Repeated live/recent-window ingest when full history is unavailable or intentionally snapshot-only |
| funding cashflow | Funding payment/receipt applied to a perpetual position |
| idealized fill | Best-case fill mode; never promotion or live-readiness evidence |
| inverse option | Deribit BTC/ETH option contract whose premium is in the base currency rather than USDC |
| maker / post-only | Maker order intent that should not intentionally cross as taker |
| max pain | Option strike where aggregate expiry payoff to option holders is minimized, computed from open interest |
| observed_at | Market event or bucket timestamp; never ingest time |
| option flow | Aggregated option trade tape metrics such as premium volume, taker side, IV, and liquidation counts |
| option surface | Snapshot of option chain open interest/IV state across listed instruments |
| PIT / as-of | Point-in-time rule: only data published by the decision timestamp may be used |
| portable validation | Reference-engine validation of strategy signal logic |
| promotion gate | Required evidence before demo, shadow, or live consideration |
| PSR | Probabilistic Sharpe Ratio; probability that true Sharpe exceeds a benchmark |
| published_at | Earliest safe timestamp for as-of joins; for bucketed aggregates, the bucket end |
| purge / embargo | Gap around train/test splits to reduce leakage |
| put/call ratio | Put open interest divided by call open interest; Deribit option-surface rows include put/call OI ratio |
| shadow / demo / live | Deployment stages; require explicit gates and human approval |
| source data validation | Checks data source, coverage, DB parity, funding, and external observations |
| `strategy_fill` | Strategy-side fill profile; useful for research review but not deployment evidence |
| taker premium imbalance | Deribit option-flow `value_num`: put taker-buy premium minus call taker-buy premium, divided by total taker-buy premium |
| `dual_output` | Paired strategy-fill and realistic-execution child runs plus comparison artifact |
| `n_trials` | Number of attempted trials counted for overfit/statistical controls |
| USDC-linear exclusion | Deribit option-flow v1 excludes USDC-linear options from inverse BTC/ETH aggregates and records the excluded count |
| volatility risk premium | Difference between implied volatility and later realized volatility; a research concept, not itself a trading signal |
| walk-forward | Rolling train/test validation over time |

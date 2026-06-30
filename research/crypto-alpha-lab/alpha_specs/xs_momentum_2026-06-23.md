# Alpha Candidate: Cross-Sectional Momentum (Market-Neutral)

## Identity

- Candidate ID: `xs_momentum_market_neutral`
- Title: Dollar-Neutral Cross-Sectional Momentum over a Point-in-Time Liquid Perp Universe
- Source paper IDs: Jegadeesh-Titman 1993; Moskowitz-Ooi-Pedersen 2012; Daniel-Moskowitz 2016; Liu-Tsyvinski 2019 (see parent `research/papers_database.md`)
- Status: design (ledger H-002) — not implemented, not validated

## Hypothesis

A dollar-neutral book that goes long the top-quantile and short the
bottom-quantile of a point-in-time top-30 liquid USDT-perp universe, ranked by
vol-normalized trailing return, earns a positive net-of-cost (fees + slippage +
short-leg funding) Sharpe that beats an equal-weight universe basket under
walk-forward, surviving DSR ≥ 0.95 and PSR ≥ 0.95.

## Signal Definition

- Inputs: 1m OHLCV (Binance canonical) → derived daily closes; trailing realized
  vol; point-in-time `universe_membership`.
- Transform: trailing return over lookback (default 28d, optional skip) divided
  by trailing realized vol → risk-adjusted momentum; cross-sectional rank.
- Timestamp convention: weekly rebalance on the daily close; no same-bar
  lookahead.
- Direction: long top quantile / short bottom quantile (dollar-neutral).
- Confidence or score: rank-based; quantile membership (default q=0.30).

## Trading Rules

- Entry: at each weekly rebalance, set target weights from the long/short
  quantiles among eligible (membership) symbols.
- Exit: roll out of names that leave the quantile or the universe at the next
  rebalance.
- Sizing: inverse-vol within each leg; legs scaled to equal gross
  (dollar-neutral); portfolio vol target ~15-20% annual; per-name and gross/net
  caps; crash-regime exposure scaler.
- Risk controls: momentum-crash filter, ADV liquidity floor, point-in-time
  membership (survivorship guard), explicit short-leg funding accounting.

## Backtest Mapping

- Path: vectorized_scan → walk_forward → cpcv
- Symbols: point-in-time top ~30 Binance USDT perps (survivorship-controlled)
- Timeframe: 1m base, daily-derived signal, weekly rebalance
- Fill assumption: realistic maker-first; `fill_all_signals` is capacity-only,
  never edge evidence
- Cost assumption: OKX/Binance maker fees + slippage + short-leg funding
- Required artifacts: `results/xs_momentum_wf_<date>.json`,
  `results/xs_momentum_cpcv_<date>.json`, `data/universe/universe_membership.parquet`

## Failure Modes

- Data leakage: weekly signal must use only closes available at rebalance time.
- Lookahead: survivorship via point-in-time membership; a symbol is never
  eligible before `listing_ts + warmup`.
- Overfit: highest-risk family (wide universe + grid); honest `n_trials`, DSR/PSR
  gates mandatory; params WF-selected, not hand-picked.
- Market impact: ADV floor + per-name cap; low (weekly) turnover.
- Regime break: momentum crashes (Daniel-Moskowitz) handled by crash filter +
  vol target.

## Promotion Gate

- Minimum validation status: walk_forward (CPCV for final)
- Required DSR/PSR or equivalent: DSR ≥ 0.95 and PSR ≥ 0.95
- Required reviewer: Claude (per `docs/REVIEW_QUESTIONS.md` / `CRITIQUE_PROTOCOL.md`)
- Live trading status: forbidden at this lab stage

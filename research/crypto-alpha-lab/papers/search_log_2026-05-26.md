# Paper Search Log - 2026-05-26

## Goal

Find papers that can produce alpha candidates compatible with the parent
backtesting architecture without touching live trading code.

## Search Queries

- `cryptocurrency market microstructure order flow imbalance bitcoin futures 2024 paper`
- `crypto perpetual futures funding rate arbitrage risk return 2024 2025 paper`
- `cryptocurrency factor momentum returns 2024 paper`
- `cryptocurrency pairs trading cointegration 2024 paper`
- `perpetual futures market quality funding settlement informed trading`

## Inclusion Criteria

- Maps to existing or near-existing parent backtest paths: event replay,
  vectorized scan, walk-forward, or CPCV.
- Uses crypto spot, crypto perpetual futures, or directly transferable order
  book methods.
- Has explicit data requirements.
- Discusses costs, funding, spread, fill logic, or validation methodology.

## Exclusion Criteria

- Pure live trading systems.
- Exchange API integration papers without alpha logic.
- Strategies requiring private data that cannot be approximated locally.
- Papers with unverifiable claims and no useful negative evidence.

## Initial Finding

The best immediate candidates are not generic daily technical indicators. The
most compatible areas are:

1. LOB/order-flow features that can be tested through event replay.
2. Funding/basis models that can be tested through existing funding carry paths.
3. Pairs/stat-arb ideas that can be stress-tested with walk-forward and CPCV.
4. Negative evidence on naive OHLCV/funding cross-sectional screens, useful as a
   baseline guardrail.

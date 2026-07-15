---
status: current
type: design
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Mechanism Taxonomy 004 — cross-venue funding frontier

This is the bounded B-taxonomy input for the 2026-07-15 strategy-idea round.
It deliberately contains one candidate. The previous taxonomy_003 candidates
have already been tested, and retrying them without a new ex-ante rationale
would be gate chasing. `research/deribit_data_strategy_research.md` C4 is now
eligible because its stated prerequisite is satisfied: C1/H-013 is shelved and
C2/H-015 is refuted.

| Family ID | 機制 | 經濟理由 | 資料 | status / 裁決 | distinctness 鄰居 | crowding/decay |
|---|---|---|---|---|---|---|
| F-XVENUE-FUNDING-SPREAD | Same-symbol Deribit-versus-Binance funding divergence; long the cheaper-funding perp and short the richer-funding perp with equal USD delta | Venue-specific positioning pressure should converge, allowing the lower-funding leg to finance the higher-funding short if persistence exceeds two-leg turnover cost | **available for funding proxy / partial for full PnL**: hourly Deribit BTC/ETH funding plus Binance 8h funding; venue-scoped Deribit perpetual mark/OHLC and the inverse-collateral contract are absent | frontier / untested; C4 prerequisite met | F-FUNDING-CARRY; F-FUNDING-XS-DISPERSION; F-XVENUE-LEADLAG | high; two-leg costs and venue crowding |

## Batch constraints

- Candidate cap: 1; ordered candidate: `F-XVENUE-FUNDING-SPREAD` only.
- Runtime cap: 300 seconds for the local Stage-2 pipeline run.
- Data tier: local TimescaleDB only; no network fetch or proxy substitution.
- Stage 3 must not run unless Stage 2 passes and real Deribit perpetual price,
  instrument, fee, and inverse-collateral accounting inputs exist.

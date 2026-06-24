---
status: draft
type: design
owner: human
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Design: Cross-Sectional Momentum (Market-Neutral) + Universe Data Infrastructure

## 1. Summary

Add a new high-return alpha family to the OKX/Binance research system: a
**dollar-neutral cross-sectional momentum** strategy traded over a **wide
liquid USDT-perp universe**, plus the **point-in-time universe + 1m data
infrastructure** it depends on.

This is OHLCV-only (order-book data is not maintained). The backtest base is
**1m OHLCV**; coarser bars (daily / weekly) used by the momentum signal are
derived on the fly by `backtesting/data_loader.py::_aggregate_1m_to_bar` — no
separate `candles_1H.parquet` is built.

Claude owns the research specs and the Codex implementation handoff. Codex owns
all implementation (data scripts, config, strategy module, portfolio
construction, backtest wiring).

## 2. Locked decisions (from 2026-06-23 brainstorm)

| Decision | Choice |
|---|---|
| Selection objective | **Maximize standalone risk-adjusted return** (highest Sharpe/DSR candidate family). |
| Instrument scope | **Wide cross-sectional universe** (20–50+ liquid USDT perps). |
| Direction | **Dollar-neutral long-short** (long top quantile / short bottom quantile). |
| Data base | **1m OHLCV**; daily/weekly bars derived. Bulk 1m download required for the universe. |
| Ownership | **Claude = spec + handoff; Codex = implementation.** |
| Scope this round | **Sub-project 0 (universe + data) + Sub-project 1 (XS momentum)** only. |

**Explicit tension (recorded by Claude as review/risk owner):** "maximize
standalone return" over a wide universe with a parameter search is the highest
overfitting-risk request in this project, and the harness governance
(DSR≥0.95, CPCV, honest `n_trials`) exists precisely to resist it. The
anti-overfit gates in §6 are therefore **non-negotiable** and bound into the
acceptance criteria; reported returns are not credible without them.

## 3. Goals / Non-goals

**Goals**
- A regenerable, point-in-time liquid-perp universe that excludes survivorship
  bias by construction.
- Bulk 1m OHLCV (+ funding) for the universe in both parquet and the canonical
  DB, venue-tagged.
- A dollar-neutral cross-sectional momentum strategy with vol-targeting and a
  momentum-crash regime filter.
- A validation path that can produce promotion-grade evidence (WF/CPCV + DSR)
  or fail honestly.

**Non-goals (this round)**
- Cross-sectional carry, factor-residual reversion (deferred sub-projects 2/3).
- Intraday / sub-daily momentum; order-book signals; paid data feeds.
- Any live/shadow promotion claim. This round produces research evidence only.

## 4. Architecture & decomposition

Two sub-projects, sequenced. Sub-project 0 is a hard prerequisite.

```
Sub-project 0: Universe + data infra (Codex)
  raw 1m klines (Binance)  ->  parquet + canonical_candles (source=binance)
  funding history          ->  funding store
  liquidity + listing data ->  universe_membership artifact (point-in-time)

Sub-project 1: XS momentum (Claude spec -> Codex impl)
  universe_membership + derived daily closes
    -> momentum score (vol-normalized trailing return)
    -> cross-sectional rank -> long/short quantiles
    -> dollar-neutral, inverse-vol, vol-targeted weights
    -> momentum-crash regime scaler
    -> weekly rebalance -> orders (maker-first)
  validation: vectorbt sweep -> walk_forward -> cpcv (DSR/PSR/n_trials)
```

### Component boundaries

| Unit | Does | Used by | Depends on |
|---|---|---|---|
| Universe builder (script) | Emits point-in-time `universe_membership` from ADV + listing/delisting data | Strategy, validation | Raw 1m candles, instrument specs |
| Data download (script) | Bulk 1m + funding into parquet + canonical DB, venue-tagged | Everything | `download_binance_data.py`, DB |
| `xs_momentum` strategy | Turns eligible universe + derived daily closes into dollar-neutral target weights at each weekly rebalance | Replay/backtest | data_loader, regime signal, allocation |
| Portfolio construction | Inverse-vol leg weighting, dollar-neutral scaling, vol target, per-name caps | Strategy | `portfolio/allocation.py`, `portfolio/sizing.py` |
| Regime/crash scaler | Global exposure multiplier in high-vol/drawdown regimes | Strategy | `signals/regime.py` |

## 5. Sub-project 0 — Universe + data infrastructure (Codex)

### Universe rules
- Candidates: USDT-margined perpetual swaps on the primary research venue
  (Binance), normalized to `<BASE>-USDT-SWAP`.
- Eligibility at rebalance date `t`:
  - listed and actively trading at `t` (delisted/halted symbols drop out when
    their candle data ends — **no backfill, no forward-fill across gaps**),
  - has ≥ `warmup_bars` of history before `t` (covers the momentum lookback),
  - rolling dollar ADV (e.g. 30-day median daily quote volume) ≥ `min_adv_usd`.
- Selection: rank eligible candidates by ADV, take **top N (default 30)**.
- Exclusions: USD-stable/wrapped/leveraged tokens (USDC, DAI, FDUSD, BTCDOM,
  *UP/*DOWN, *3L/*3S, etc.) via an explicit deny-list.

### Point-in-time membership (the survivorship guard)
- Output artifact `universe_membership` (parquet/csv), columns:
  `[date, symbol, eligible, adv_usd, listing_ts]`.
- Deterministic and regenerable from raw candles by a single script.
- A symbol must **never** appear eligible before `listing_ts + warmup`.

### Data
- Bulk **1m** klines for the universe via `download_binance_data.py` into
  `data/ticks/<SYM>/candles_1m.parquet` **and** `canonical_candles`
  (`source_primary=binance`).
- Funding history per symbol (needed to charge short-leg funding in §6, and
  reused by later carry work).
- BTC/ETH/SOL/MEME 1m already exist; the rest of the universe must be
  downloaded.
- Derived daily/weekly bars are produced at read time; optionally cache 1D via
  `write_candles_parquet` only if wide-universe runs are too slow (optimization,
  not required).

## 6. Sub-project 1 — XS momentum (market-neutral)

### Signal
- At weekly rebalance `t`, for each eligible symbol compute trailing return over
  lookback `L` (default **28 days**) on derived daily closes, optionally
  skipping the most recent `skip` days (short-term-reversal gap).
- **Vol-normalize**: divide by trailing realized vol → risk-adjusted momentum.
- Cross-sectionally rank scores across the eligible set.

### Portfolio construction
- Long top quantile `q`, short bottom quantile `q` (default **q = 0.30**).
- Within each leg: inverse-vol weights (default) or equal weight.
- Scale legs to **equal gross notional → dollar-neutral**.
- Apply a portfolio **vol target** (default annualized 15–20%) by scaling total
  gross exposure.
- Caps: per-name notional cap, total gross/net exposure cap, liquidation buffer.

### Rebalance & execution
- **Weekly** rebalance (default; e.g. Monday 00:00 UTC on the daily close) for
  low turnover.
- Maker-first; taker only for risk exits if live policy ever allows.
- Closest existing analog is `strategies/ohlcv_rotation.py`; Codex decides
  whether to extend the rotation framework or add a dedicated module. Long-short
  requires short legs (perps support this).

### Momentum-crash filter
- In high-vol / market-drawdown regimes, scale total exposure down (Daniel-
  Moskowitz crash risk). Vol-targeting handles part of this; add a
  drawdown-state multiplier from `signals/regime.py`.

### Default parameters (chosen, not hand-tuned)
`universe N=30`, `lookback L=28d`, `skip=0`, `q=0.30`, weekly rebalance,
inverse-vol legs, vol target 15–20%. These are literature-standard starting
points; final parameters are selected **programmatically by walk-forward**, not
by picking the best backtest.

## 7. Validation & anti-overfit gates (non-negotiable)

- Flow: `backtesting/vectorbt_scanner.py` sweep → `backtesting/walk_forward.py`
  → `backtesting/cpcv.py`.
- **Honest `n_trials`**: every `(L, skip, q, rebalance, vol-target, N)`
  combination tried is counted; the best grid cell is **not** relabeled as a
  naive baseline.
- **DSR ≥ 0.95 and PSR ≥ 0.95** before any promotion discussion.
- **Survivorship attestation**: results cite the point-in-time
  `universe_membership` artifact; a test asserts no pre-listing eligibility.
- **Realistic fills**: `fill_all_signals` / `idealized_fill` artifacts are
  capacity-analysis only, never edge/promotion evidence.
- **ct_val provenance** per venue; **venue-scoped canonical DB reads** for
  promotion-grade runs (parquet-only runs are research-tier).
- **Short-leg funding**: short perp legs pay/receive funding every 8h; PnL must
  include funding cashflows with correct sign.
- **Baseline comparison**: net-of-cost return/Sharpe vs equal-weight universe
  basket and BTC buy-hold. XS momentum must beat the naive market basket after
  costs to be worth promoting.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Overfitting (objective tension) | DSR/PSR + honest `n_trials`; WF-selected params. |
| Survivorship/delisting bias | Point-in-time membership; no backfill across delisting. |
| Momentum crashes (tail) | Vol target + regime crash scaler. |
| Crowding / limited capacity | ADV floor, per-name cap, low turnover. |
| Short funding drag | Explicit funding cashflows on short legs. |
| Cross-coin data quality | `quality_status` filter, min-coverage gate per symbol. |
| No portable-validation contract yet | Add an `xs_momentum` reference contract (future gate; does not block research). |

## 9. Deliverables & ownership

**Claude (research / docs)**
- This design doc.
- `research/strategy_synthesis.md`: new **Strategy 11 — Cross-Sectional
  Momentum (market-neutral)** hypothesis entry.
- `research/crypto-alpha-lab/alpha_specs/`: XS-momentum alpha candidate record.
- `docs/HYPOTHESIS_LEDGER.md` + `docs/EXPERIMENT_REGISTRY.md`: register the
  hypothesis and the planned experiment (Intelligence harness).
- Codex implementation handoff (PERMITTED / FORBIDDEN files, exact test/backtest
  commands, binary acceptance criteria, rollback) via the writing-plans step.
- Risk analysis (this §8) and review notes.

**Codex (implementation)**
- Universe builder + bulk 1m/funding download scripts; config for the universe.
- `strategies/xs_momentum.py` (or rotation extension); `portfolio/allocation.py`
  long-short construction; backtest wiring.
- Because implementation touches sizing/portfolio/PnL (funding on shorts), it
  requires a **Change Manifest** + `docs/DOC_IMPACT_MATRIX.md` rows, and a new
  strategy of this size likely needs an **ADR**.

## 10. Acceptance criteria (binary)

**Sub-project 0**
- [ ] `universe_membership` is regenerable by one script and deterministic.
- [ ] ≥ 25 symbols have ≥ 12 months of 1m coverage in both parquet and
      canonical DB (`source_primary=binance`).
- [ ] A test asserts a symbol is not eligible before `listing_ts + warmup`
      (no look-ahead).

**Sub-project 1**
- [ ] `xs_momentum` emits dollar-neutral weekly long-short target weights over
      the point-in-time universe.
- [ ] A `walk_forward` run completes and writes an artifact with
      `validation_status = walk_forward` and `idealized_fill = false`.
- [ ] DSR/PSR + honest `n_trials` reported; survivorship attestation present;
      short-leg funding included.
- [ ] Net-of-cost return/Sharpe reported against equal-weight and BTC baselines.

## 11. Out of scope (deferred)

Cross-sectional carry (sub-project 2), factor-residual reversion (sub-project
3), intraday/order-book signals, paid data feeds, live/shadow promotion.

## 12. Open defaults (override anytime)

`N=30`, daily-derived signal with weekly rebalance, `L=28d`, `q=0.30`,
inverse-vol legs, vol target 15–20%, no pre-cached 1D bars initially. SOL/MEME
existing 1m can seed the first smoke run before the full universe is downloaded.

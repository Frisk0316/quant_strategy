# Cross-Sectional Momentum + Universe Data Infra — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Ownership note (read first):** Per the 2026-06-23 decision, **Codex implements all trading-core / data / config tasks**; **Claude owns the research + governance docs tasks** (tagged `[Claude]`). Trading-core tasks are tagged `[Codex]`. Claude must not write code under `src/okx_quant/strategies/`, `portfolio/`, `risk/`, `execution/`, `signals/`. This plan therefore gives Codex exact files, interfaces, tests (acceptance specs), and behavioral specs — not finished strategy code.

**Goal:** Add a dollar-neutral cross-sectional momentum strategy over a wide point-in-time liquid USDT-perp universe, OHLCV-only on a 1m base, with promotion-capable validation.

**Architecture:** Reuse the existing `ohlcv_rotation.py` vectorised cross-sectional engine and its pure feature helpers; add a market-neutral long-short construction, a point-in-time universe membership layer (survivorship guard), short-leg funding accounting, and a WF/CPCV validation path with honest `n_trials`. Leave existing rotation behavior and artifacts untouched.

**Tech Stack:** Python, pandas/numpy, pyarrow parquet, PostgreSQL canonical_candles, pytest, existing `backtesting/{data_loader,walk_forward,cpcv}.py`.

## Global Constraints

- OHLCV-only; **no order-book data**. Backtest base bar = **1m**; daily/weekly bars are derived via `backtesting/data_loader.py::_aggregate_1m_to_bar` — do **not** create `candles_1H.parquet`.
- Direction = **dollar-neutral long-short** (long top quantile / short bottom quantile, equal gross notional).
- **Point-in-time universe only**; no backfill / forward-fill across delisting gaps. A symbol is never eligible before `listing_ts + warmup`.
- Anti-overfit gates are non-negotiable: honest `n_trials`, **DSR ≥ 0.95 and PSR ≥ 0.95**, WF-selected params (never relabel the best grid cell as naive).
- `fill_all_signals` / `idealized_fill: true` artifacts are capacity-analysis only — never edge/promotion evidence.
- Promotion-grade runs read **venue-scoped canonical DB** (`source_primary=binance`); parquet-only runs are research-tier.
- Short perp legs must charge **funding cashflows** with correct sign.
- Spec source of truth: `docs/superpowers/specs/2026-06-23-xs-momentum-universe-design.md`. Strategy assumptions only from spec/`research/`, never chat memory.

## Plan-level PERMITTED / FORBIDDEN

**PERMITTED (create/modify):**
- `config/universe.yaml` (new), `config/strategies.yaml` (add `xs_momentum` block), `config/instrument_specs.yaml` (universe symbols)
- `scripts/build_universe_membership.py` (new), reuse `scripts/download_binance_data.py`
- `src/okx_quant/strategies/xs_momentum.py` (new), `src/okx_quant/portfolio/allocation.py` (add long-short helper)
- `backtesting/xs_momentum_backtest.py` (new, mirror `ohlcv_rotation_backtest.py`)
- `tests/unit/test_xs_momentum*.py`, `tests/unit/test_universe_membership.py` (new)
- Governance docs (see Phase D)

**FORBIDDEN (do not touch):**
- Existing `ohlcv_rotation.py` behavior, its tests, or any existing `results/` artifact (reuse its pure helpers by import only).
- `src/okx_quant/risk/` sizing/PnL semantics beyond reading, `config/risk.yaml`, deployment/shadow/live gates.
- DB schema/migrations beyond approved 0011/0012 on the current branch.
- Differential-validation implementation owned by another session.

## File Structure

| File | Responsibility |
|---|---|
| `config/universe.yaml` | Universe rules: `min_adv_usd`, `top_n`, `warmup_bars`, deny-list, venue. |
| `scripts/build_universe_membership.py` | Emit deterministic point-in-time `universe_membership` artifact from candles + listing data. |
| `src/okx_quant/portfolio/allocation.py` | Add `dollar_neutral_long_short_weights(...)` pure helper. |
| `src/okx_quant/strategies/xs_momentum.py` | XS momentum params + vol-normalized score (reusing rotation helpers) + market-neutral target weights. |
| `backtesting/xs_momentum_backtest.py` | Vectorised backtest runner (mirror of `ohlcv_rotation_backtest.py`) with short-leg funding + cost. |
| `tests/unit/test_universe_membership.py` | Survivorship / no-lookahead tests. |
| `tests/unit/test_xs_momentum.py` | Score, ranking, dollar-neutral weights, funding-sign tests. |

---

## Phase A — Universe + data infrastructure  [Codex]

### Task A1: Universe config + symbol specs

**Files:**
- Create: `config/universe.yaml`
- Modify: `config/instrument_specs.yaml` (add any universe symbols missing from the current 14)

**Interfaces:**
- Produces: `config/universe.yaml` with keys `venue: binance`, `quote: USDT`, `instrument_type: SWAP`, `top_n: 30`, `min_adv_usd: <float>`, `adv_window_days: 30`, `warmup_bars: <int ≥ lookback>`, `deny_list: [...]` (stable/wrapped/leveraged), `rebalance: weekly`.

- [ ] **Step 1:** Write `config/universe.yaml` with the keys above; `deny_list` includes USDC/DAI/FDUSD/TUSD/BTCDOM and `*UP/*DOWN/*3L/*3S/*BULL/*BEAR` patterns.
- [ ] **Step 2:** Add to `config/instrument_specs.yaml` any candidate symbols not already present (per-venue `ct_val` resolves structurally for Binance USDT-M, but list them so backtests don't fail loudly).
- [ ] **Step 3:** Run `make check-config` (or the repo's config validation). Expected: PASS.
- [ ] **Step 4:** Commit. `git add config/universe.yaml config/instrument_specs.yaml && git commit -m "feat(universe): add cross-sectional perp universe config" --trailer "AI-Origin: Codex"`

### Task A2: Bulk 1m + funding download for the universe

**Files:** Reuse `scripts/download_binance_data.py` (no new code unless a batch wrapper helps).

- [ ] **Step 1:** For each universe candidate, download **1m** klines and funding into `data/ticks/<SYM>/candles_1m.parquet` and `canonical_candles` (`source=binance`), e.g. `python scripts/download_binance_data.py --inst <SYM> --bar 1m --start 2022-01-01 --end 2026-04-30`.
- [ ] **Step 2:** Verify coverage: a symbol counts as covered if it has ≥ 12 months of 1m rows in **both** parquet and canonical DB. Record per-symbol coverage to `results/universe_coverage_<date>.json`.
- [ ] **Step 3:** Confirm ≥ 25 symbols pass coverage. If fewer, widen the window or candidate list and rerun.
- [ ] **Step 4:** Commit the coverage report only (not the raw parquet, per repo data conventions). `git commit -m "chore(universe): record 1m+funding coverage report" --trailer "AI-Origin: Codex"`

### Task A3: Point-in-time universe membership builder  (survivorship guard)

**Files:**
- Create: `scripts/build_universe_membership.py`, `tests/unit/test_universe_membership.py`
- Output artifact: `data/universe/universe_membership.parquet` (columns `[date, symbol, eligible, adv_usd, listing_ts]`)

**Interfaces:**
- Produces: `build_membership(candles_by_symbol: dict[str, pd.DataFrame], cfg: dict) -> pd.DataFrame` — deterministic; `eligible[t, s]` is True iff `s` has ≥ `warmup_bars` history before `t`, is still trading at `t` (candle data present, not ended), and `adv_usd[t, s] ≥ min_adv_usd`; then top-`top_n` by ADV that date.

- [ ] **Step 1: Write the failing test** (`tests/unit/test_universe_membership.py`):

```python
import pandas as pd
from scripts.build_universe_membership import build_membership

def _ramp(start, periods, price=100.0):
    idx = pd.date_range(start, periods=periods, freq="D")
    return pd.DataFrame({"open": price, "high": price, "low": price,
                         "close": price, "vol": 1e6}, index=idx)

def test_symbol_not_eligible_before_listing_plus_warmup():
    cfg = {"top_n": 10, "min_adv_usd": 0.0, "warmup_days": 30}
    # NEW listed 2024-02-01; on 2024-02-10 it has <30d history -> ineligible
    candles = {"OLD-USDT-SWAP": _ramp("2024-01-01", 60),
               "NEW-USDT-SWAP": _ramp("2024-02-01", 30)}
    m = build_membership(candles, cfg)
    row = m[(m.date == pd.Timestamp("2024-02-10")) & (m.symbol == "NEW-USDT-SWAP")]
    assert bool(row.eligible.iloc[0]) is False

def test_delisted_symbol_drops_out_when_data_ends():
    cfg = {"top_n": 10, "min_adv_usd": 0.0, "warmup_days": 5}
    candles = {"DEAD-USDT-SWAP": _ramp("2024-01-01", 20)}  # ends 2024-01-20
    m = build_membership(candles, cfg)
    after = m[(m.date > pd.Timestamp("2024-01-20")) & (m.symbol == "DEAD-USDT-SWAP")]
    assert (after.eligible == False).all() if len(after) else True
```

- [ ] **Step 2:** Run `python -m pytest tests/unit/test_universe_membership.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3:** Implement `build_universe_membership.py` per the interface above (pure pandas; derive daily ADV from 1m via the data_loader resample; no forward-fill across gaps). Add a CLI that loads universe candles and writes the parquet artifact.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Generate the artifact: `python scripts/build_universe_membership.py --config config/universe.yaml --out data/universe/universe_membership.parquet`.
- [ ] **Step 6:** Commit. `git add scripts/build_universe_membership.py tests/unit/test_universe_membership.py && git commit -m "feat(universe): point-in-time membership builder with survivorship test" --trailer "AI-Origin: Codex"`

---

## Phase B — XS momentum strategy  [Codex]

### Task B1: Dollar-neutral long-short weight helper

**Files:**
- Modify: `src/okx_quant/portfolio/allocation.py` (add one pure function)
- Test: `tests/unit/test_xs_momentum.py`

**Interfaces:**
- Produces: `dollar_neutral_long_short_weights(scores: pd.Series, q: float, inverse_vol: pd.Series | None, gross: float) -> pd.Series` — selects top-`q` (long, +) and bottom-`q` (short, −); within each leg weights are equal or inverse-vol; **each leg scaled to `gross/2`** so `sum(weights)==0` (dollar-neutral) and `sum(abs(weights))==gross`.

- [ ] **Step 1: Write the failing test:**

```python
import numpy as np, pandas as pd
from okx_quant.portfolio.allocation import dollar_neutral_long_short_weights

def test_weights_are_dollar_neutral_and_gross_normalized():
    scores = pd.Series({"a": 5, "b": 4, "c": 0, "d": -4, "e": -5})
    w = dollar_neutral_long_short_weights(scores, q=0.4, inverse_vol=None, gross=1.0)
    assert abs(w.sum()) < 1e-9               # market neutral
    assert abs(w.abs().sum() - 1.0) < 1e-9   # gross = 1.0
    assert (w[["a", "b"]] > 0).all() and (w[["d", "e"]] < 0).all()
    assert w.get("c", 0.0) == 0.0            # middle excluded
```

- [ ] **Step 2:** Run `python -m pytest tests/unit/test_xs_momentum.py::test_weights_are_dollar_neutral_and_gross_normalized -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `dollar_neutral_long_short_weights` per interface. Follow existing `allocation.py` style.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit. `git commit -am "feat(portfolio): dollar-neutral long-short weight helper" --trailer "AI-Origin: Codex"`

### Task B2: XS momentum params + vol-normalized score

**Files:**
- Create: `src/okx_quant/strategies/xs_momentum.py`
- Test: `tests/unit/test_xs_momentum.py`

**Interfaces:**
- Consumes: `ohlcv_rotation.build_feature_panel` helpers by import (do not copy).
- Produces: `@dataclass XSMomentumParams` (`universe: list[str]`, `bar="1m"`, `rebalance="weekly"`, `lookback_days=28`, `skip_days=0`, `quantile=0.30`, `vol_window_days=28`, `inverse_vol=True`, `vol_target_annual=0.175`, `max_name_weight=0.10`, `fee_bps=2.0`, `slippage_bps=2.0`, `long_only=False`); and `vol_normalized_momentum(close_daily: pd.DataFrame, lookback: int, skip: int, vol_window: int) -> pd.DataFrame` returning per-date per-symbol risk-adjusted momentum (trailing return over `lookback` skipping last `skip`, divided by trailing realized vol).

- [ ] **Step 1: Write the failing test:**

```python
import numpy as np, pandas as pd
from okx_quant.strategies.xs_momentum import vol_normalized_momentum

def test_higher_steady_trend_scores_above_noisier_trend():
    idx = pd.date_range("2024-01-01", periods=40, freq="D")
    steady = pd.Series(np.linspace(100, 140, 40), index=idx)          # smooth up
    noisy = pd.Series(np.linspace(100, 140, 40) +
                      np.tile([5, -5], 20), index=idx)                # same drift, more vol
    close = pd.DataFrame({"STEADY": steady, "NOISY": noisy})
    score = vol_normalized_momentum(close, lookback=28, skip=0, vol_window=28)
    last = score.iloc[-1]
    assert last["STEADY"] > last["NOISY"]    # vol-normalization rewards steadiness
```

- [ ] **Step 2:** Run that test `-v`. Expected: FAIL (module/function missing).
- [ ] **Step 3:** Implement `XSMomentumParams` and `vol_normalized_momentum` reusing rotation helpers where they fit.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit. `git commit -am "feat(strategy): xs_momentum params + vol-normalized score" --trailer "AI-Origin: Codex"`

### Task B3: Market-neutral target-weight assembly

**Files:** `src/okx_quant/strategies/xs_momentum.py`, `tests/unit/test_xs_momentum.py`

**Interfaces:**
- Produces: `target_weights(score_panel: pd.DataFrame, membership: pd.DataFrame, params: XSMomentumParams, realized_vol: pd.DataFrame) -> pd.DataFrame` — for each weekly rebalance date: restrict to eligible symbols (membership), rank scores, call `dollar_neutral_long_short_weights`, apply `max_name_weight` cap and `vol_target_annual` gross scaling. Non-rebalance dates carry forward prior weights.

- [ ] **Step 1: Write the failing test** asserting: (a) only `membership.eligible` symbols get nonzero weight; (b) each rebalance date is dollar-neutral (`|sum|<1e-9`); (c) no single `|weight| > max_name_weight`.
- [ ] **Step 2:** Run `-v`. Expected: FAIL.
- [ ] **Step 3:** Implement `target_weights` per interface (weekly resample of the daily-derived panel).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit. `git commit -am "feat(strategy): xs_momentum market-neutral target weights" --trailer "AI-Origin: Codex"`

### Task B4: Momentum-crash regime scaler

**Files:** `src/okx_quant/strategies/xs_momentum.py` (consume `signals/regime.py` read-only), `tests/unit/test_xs_momentum.py`

**Interfaces:**
- Produces: a gross-exposure multiplier ∈ [0,1] applied in `target_weights` driven by market drawdown / high-vol state from `signals/regime.py`. In a flagged crash regime gross shrinks; in calm regime gross = full vol-target.

- [ ] **Step 1: Write the failing test:** feed a synthetic crash window (large market drawdown) and assert gross exposure on the post-crash rebalance is strictly less than on a calm rebalance.
- [ ] **Step 2:** Run `-v`. Expected: FAIL.
- [ ] **Step 3:** Implement the scaler reusing `signals/regime.py` (read-only).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit. `git commit -am "feat(strategy): xs_momentum crash-regime exposure scaler" --trailer "AI-Origin: Codex"`

### Task B5: `on_market`/`on_fill` stub + config block

**Files:** `src/okx_quant/strategies/xs_momentum.py`, `config/strategies.yaml`

**Interfaces:**
- `XSMomentum(Strategy)` implements `on_market` (no-op stub, mirroring `ohlcv_rotation.py` Phase 1 — vectorised backtest only) and `on_fill`. RiskGuard `size_multiplier` respected.

- [ ] **Step 1:** Implement the `Strategy` subclass skeleton (`on_market` returns `None`, `on_fill` no-op) so the module loads via the strategy registry.
- [ ] **Step 2:** Add an `xs_momentum:` block to `config/strategies.yaml` with `enabled: false` and the `XSMomentumParams` defaults.
- [ ] **Step 3:** Run `make check-config`. Expected: PASS.
- [ ] **Step 4:** Commit. `git commit -am "feat(strategy): register xs_momentum (disabled by default)" --trailer "AI-Origin: Codex"`

---

## Phase C — Vectorised backtest + validation  [Codex]

### Task C1: Vectorised backtest runner with short-leg funding

**Files:**
- Create: `backtesting/xs_momentum_backtest.py` (mirror `backtesting/ohlcv_rotation_backtest.py`)
- Test: `tests/unit/test_xs_momentum_backtest.py`

**Interfaces:**
- Produces: `run_xs_momentum_backtest(close, high, low, vol, funding, membership, params) -> result` with an equity curve, turnover, fee+slippage cost per rebalance, and **funding cashflow charged on short legs** (short pays positive funding, receives negative). Emits an artifact with `validation_status` and `idealized_fill: false` by default.

- [ ] **Step 1: Write the failing test:** construct a 2-symbol panel where the short leg has known positive funding; assert realized PnL is reduced by exactly the funding cashflow on the short notional (sign check). Spec invariant: funding sign must match `risk`/PnL conventions in `docs/DOMAIN_RULES.md`.
- [ ] **Step 2:** Run `-v`. Expected: FAIL.
- [ ] **Step 3:** Implement the runner mirroring the rotation backtest; add funding accounting; default realistic fills (no `fill_all_signals`).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Smoke** on existing 1m (BTC/ETH/SOL/MEME) as a 4-name mini-universe: produce one artifact. `git commit -am "feat(backtest): xs_momentum vectorised runner + funding" --trailer "AI-Origin: Codex"`

### Task C2: Parameter sweep with honest `n_trials`

**Files:** `backtesting/xs_momentum_backtest.py` (add a `scan_xs_momentum(grid)` like `vectorbt_scanner.scan_funding_carry`)

- [ ] **Step 1:** Implement `scan_xs_momentum` iterating the grid `{lookback_days, skip_days, quantile, vol_target_annual, top_n}`; record **every** cell and set `n_trials = len(grid)` in the output.
- [ ] **Step 2:** Add a test asserting `n_trials == product of grid dimensions` (no silent dropping).
- [ ] **Step 3:** Run `-v`. Expected: PASS.
- [ ] **Step 4:** Commit. `--trailer "AI-Origin: Codex"`

### Task C3: Walk-forward + CPCV + baselines

**Files:** reuse `backtesting/walk_forward.py::WalkForward.evaluate` and `backtesting/cpcv.py::CPCV.evaluate`; output reports under `results/`.

- [ ] **Step 1:** Wire `run_xs_momentum_backtest` as the per-window evaluator for `WalkForward.evaluate`; produce an artifact with `validation_status = walk_forward`, `idealized_fill = false`, and a survivorship attestation that cites `universe_membership.parquet`.
- [ ] **Step 2:** Run CPCV via `CPCV.evaluate` with the honest `n_trials` from C2; compute **DSR and PSR**; fail the report (not the run) if DSR<0.95 or PSR<0.95.
- [ ] **Step 3:** Add net-of-cost return/Sharpe comparison vs (a) equal-weight universe basket and (b) BTC buy-hold.
- [ ] **Step 4:** Save reports to `results/xs_momentum_wf_<date>.json` and `results/xs_momentum_cpcv_<date>.json`.
- [ ] **Step 5:** Commit reports. `--trailer "AI-Origin: Codex"`

---

## Phase D — Governance & research docs

### Task D1 [Codex]: Change Manifest + impact matrix + ADR

- [ ] **Step 1:** Create a Change Manifest from `docs/CHANGE_MANIFEST_TEMPLATE.md` (touches sizing/portfolio/PnL via short-leg funding).
- [ ] **Step 2:** Update the relevant `docs/DOC_IMPACT_MATRIX.md` rows; run `make docs-impact`.
- [ ] **Step 3:** Add an ADR under `docs/ADR/` for the new XS-momentum strategy family (major rule addition).
- [ ] **Step 4:** Add a **survivorship-bias** failure mode to `docs/FAILURE_MODES.md` and a guarding entry in `docs/INVARIANTS.md` (point-in-time membership; no pre-listing eligibility), linked to `test_universe_membership.py`.
- [ ] **Step 5:** Commit. `--trailer "AI-Origin: Codex"`

### Task D2 [Claude]: Research-layer specs

- [ ] **Step 1:** Add **Strategy 11 — Cross-Sectional Momentum (market-neutral)** to `research/strategy_synthesis.md` (signal, sizing, execution, risk controls, instruments, validation path).
- [ ] **Step 2:** Add an XS-momentum alpha candidate record under `research/crypto-alpha-lab/alpha_specs/`.
- [ ] **Step 3:** Register the hypothesis in `docs/HYPOTHESIS_LEDGER.md` and the planned experiment in `docs/EXPERIMENT_REGISTRY.md`.
- [ ] **Step 4:** Commit. `git commit -m "docs(research): add XS momentum strategy 11 + alpha candidate + ledger"`

### Task D3 [Claude]: Review the implementation

- [ ] **Step 1:** Review Codex PR against `docs/REVIEW_QUESTIONS.md` / `docs/CRITIQUE_PROTOCOL.md`: scope, survivorship guard, funding sign, honest `n_trials`, no `idealized_fill` in promotion claims, venue-scoped reads, ct_val provenance.
- [ ] **Step 2:** Record review notes; block promotion-readiness claims until DSR/PSR + WF/CPCV pass and the user approves.

---

## Self-Review

**Spec coverage:** universe rules → A1/A3; bulk 1m+funding → A2; point-in-time/survivorship → A3 + D1 invariant; vol-normalized momentum → B2; dollar-neutral long-short → B1/B3; vol target + caps → B3; crash filter → B4; 1m base / derived bars → Global Constraints + C1; honest n_trials → C2; WF/CPCV/DSR/PSR → C3; realistic fills → C1/C3; short-leg funding → C1; baselines → C3; ct_val/venue-scoped → Global Constraints + D3; research docs/ledger → D2; Change Manifest/ADR/failure-mode → D1. No uncovered spec section.

**Placeholder scan:** no TBD/TODO; each code step shows test or interface; behavioral specs for trading-core impl are intentional (Codex owns implementation per ownership note), not omissions.

**Type consistency:** `dollar_neutral_long_short_weights` (B1) is consumed by `target_weights` (B3); `vol_normalized_momentum` (B2) feeds `target_weights` (B3); `membership` columns `[date,symbol,eligible,adv_usd,listing_ts]` consistent across A3/B3/C3; `run_xs_momentum_backtest` (C1) reused by C2/C3.

---

## Execution Handoff

This plan splits by owner. **Phases A–C and D1 are Codex implementation tasks** (trading-core/data/config) — hand this file to a Codex session to execute task-by-task. **D2 is Claude-owned** research/docs and can be done immediately. **D3 is Claude review** after Codex's PR.

"""
Backtest runner using REAL OKX market data.

Data source: OKX public API, downloaded via scripts/fetch_okx_data.py
  - BTC-USDT-SWAP: 1H candles, 2024-01-01 → 2026-04-17
  - ETH-USDT-SWAP: 1H candles, 2024-01-01 → 2026-04-17
  - BTC-USDT-SWAP: funding rate history (~3 months available via public API)

Strategies backtested:
  1. Avellaneda-Stoikov Market Maker (1H bars)
  2. Funding Rate Carry (8h settlements)
  3. BTC-ETH Pairs Trading (1H bars, Kalman + OU z-score)

Run:
    python scripts/fetch_okx_data.py        # download data first
    python scripts/run_backtest.py          # then run backtest
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "backtesting"))

RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)
DATA_DIR = PROJECT_ROOT / "data" / "ticks"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from okx_quant.analytics.performance import sharpe, summary
from okx_quant.analytics.dsr import psr
from okx_quant.strategies.as_market_maker import as_quote
from okx_quant.strategies.pairs_trading import estimate_ou
from okx_quant.signals.vpin import classify_bvc
from data_loader import load_candles, load_funding
from walk_forward import WalkForward


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  LOAD REAL MARKET DATA
# ═══════════════════════════════════════════════════════════════════════════════
print("[1/8] Loading real OKX market data …")


def _load_candles(inst_id: str, bar: str = "1H") -> pd.DataFrame:
    return load_candles(inst_id=inst_id, bar=bar, data_dir=str(DATA_DIR))


def _load_funding(inst_id: str) -> pd.DataFrame:
    return load_funding(inst_id=inst_id, data_dir=str(DATA_DIR))


btc_df    = _load_candles("BTC-USDT-SWAP", "1H")
eth_df    = _load_candles("ETH-USDT-SWAP", "1H")
funding_df = _load_funding("BTC-USDT-SWAP")

# Align BTC/ETH to common index (inner join on timestamps)
common_idx = btc_df.index.intersection(eth_df.index)
btc_df = btc_df.loc[common_idx]
eth_df = eth_df.loc[common_idx]

START_DATE = str(btc_df.index[0].date())
END_DATE   = str(btc_df.index[-1].date())
FUND_START = str(funding_df.index[0].date())
FUND_END   = str(funding_df.index[-1].date())

print(f"    BTC: {len(btc_df):,} hourly bars  ({START_DATE} → {END_DATE})")
print(f"    ETH: {len(eth_df):,} hourly bars  ({START_DATE} → {END_DATE})")
print(f"    Funding: {len(funding_df):,} settlements  ({FUND_START} → {FUND_END})")

# ═══════════════════════════════════════════════════════════════════════════════
# 2.  FIGURE 1 — Market Data Overview
# ═══════════════════════════════════════════════════════════════════════════════
print("[2/8] Saving Figure 1 — market data overview …")

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=False)
fig.suptitle(
    f"Real OKX Market Data  ({START_DATE} → {END_DATE})",
    fontsize=14, fontweight="bold",
)

axes[0].plot(btc_df.index, btc_df["close"], linewidth=0.7, color="#1565C0")
axes[0].set_ylabel("BTC Price (USDT)")
axes[0].set_title("BTC-USDT-SWAP  (1H close)")
axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))

axes[1].plot(eth_df.index, eth_df["close"], linewidth=0.7, color="#6A1B9A")
axes[1].set_ylabel("ETH Price (USDT)")
axes[1].set_title("ETH-USDT-SWAP  (1H close)")
axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))

apr_pct = funding_df["apr"] * 100
axes[2].fill_between(funding_df.index, apr_pct, 0,
                     where=(apr_pct >= 0), color="#43A047", alpha=0.55, label="Positive APR")
axes[2].fill_between(funding_df.index, apr_pct, 0,
                     where=(apr_pct < 0),  color="#E53935", alpha=0.55, label="Negative APR")
axes[2].axhline(12, color="navy", linestyle="--", linewidth=1.0, label="12% entry threshold")
axes[2].axhline(0,  color="black", linewidth=0.6)
axes[2].set_ylabel("Funding APR (%)")
axes[2].set_title(f"BTC-USDT-SWAP Funding Rate  ({FUND_START} → {FUND_END})")
axes[2].legend(fontsize=8)

plt.tight_layout()
fig.savefig(RESULTS_DIR / "01_market_data.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# 3.  STRATEGY 1: AS MARKET MAKER (1H bars)
# ═══════════════════════════════════════════════════════════════════════════════
print("[3/8] Running AS Market Maker backtest …")

LOT_SIZE   = 0.001
COMM_MAKER = 0.0002
GAMMA   = 0.1
KAPPA   = 1.5
C_ALPHA = 100.0
BETA_VPIN = 2.0
MAX_POS = 10
TICK    = 0.1
ALPHA_SIGMA = 1 - np.exp(-np.log(2) / 5)   # half-life = 5 bars

closes_btc = btc_df["close"].values
highs_btc  = btc_df["high"].values
lows_btc   = btc_df["low"].values
vols_btc   = btc_df["vol"].values

inventory  = 0.0
sigma_ewma = 0.003
vpin_cdf   = 0.3
prev_close = float(closes_btc[0])
prev_inv_sign = 0
vpin_buf = deque(maxlen=50)

returns_asmm  = []
inventory_hist = []
spread_hist   = []

for i in range(1, len(btc_df)):
    c = closes_btc[i];  h = highs_btc[i];  l = lows_btc[i];  v = vols_btc[i]
    mid = (h + l) / 2.0
    bar_ret = float(np.log(c / max(prev_close, 1e-8)))
    prev_close = c

    sigma_ewma = ALPHA_SIGMA * abs(bar_ret) + (1 - ALPHA_SIGMA) * sigma_ewma
    alpha_signal = bar_ret * 0.001

    if sigma_ewma > 0:
        vb, vs = classify_bvc(bar_ret, sigma_ewma, float(v))
        imb_frac = abs(vb - vs) / (float(v) + 1e-8)
    else:
        imb_frac = 0.5
    vpin_buf.append(imb_frac)
    if len(vpin_buf) >= 5:
        buf_arr = np.array(vpin_buf)
        vpin_cdf = float(np.searchsorted(np.sort(buf_arr), imb_frac)) / len(buf_arr)

    bid, ask = as_quote(
        mid=mid, inventory=inventory, alpha_signal=alpha_signal, vpin=vpin_cdf,
        gamma=GAMMA, sigma=sigma_ewma, kappa=KAPPA, T_minus_t=1.0,
        tick=TICK, max_pos=MAX_POS, c_alpha=C_ALPHA, beta_vpin=BETA_VPIN,
    )

    if bid == -np.inf or ask == np.inf:
        returns_asmm.append(0.0)
        inventory_hist.append(inventory)
        spread_hist.append(float(np.nan))
        continue

    spread_AS  = (ask - bid) / mid
    spread_mkt = (h - l) / mid if mid > 0 else 1e-6
    fill_prob  = min(1.0, spread_AS / max(spread_mkt, 1e-8))

    pnl_spread = fill_prob * spread_AS / 2.0
    pnl_inv    = inventory * bar_ret * LOT_SIZE

    delta = fill_prob * LOT_SIZE
    inventory = float(np.clip(
        inventory + (-delta if bar_ret > 0 else delta),
        -MAX_POS, MAX_POS,
    ))

    commission = 0.0
    inv_sign = int(np.sign(inventory))
    if inv_sign != 0 and inv_sign != prev_inv_sign and prev_inv_sign != 0:
        commission = COMM_MAKER
    prev_inv_sign = inv_sign

    pnl_bar = pnl_spread + pnl_inv - commission
    returns_asmm.append(pnl_bar)
    inventory_hist.append(inventory)
    spread_hist.append(spread_AS)

returns_asmm   = np.array(returns_asmm, dtype=float)
inventory_hist  = np.array(inventory_hist, dtype=float)
spread_hist    = np.array(spread_hist, dtype=float)
asmm_equity    = (1 + returns_asmm).cumprod()
asmm_dd        = (asmm_equity - np.maximum.accumulate(asmm_equity)) / np.maximum.accumulate(asmm_equity)
PERIODS_1H     = 365 * 24
asmm_summary   = summary(returns_asmm, periods=PERIODS_1H)
asmm_psr       = psr(returns_asmm, sr_benchmark=0.0)

print(f"    AS MM  | Sharpe={asmm_summary['sharpe']:.2f}  MDD={asmm_summary['max_drawdown']*100:.1f}%  "
      f"TotalRet={asmm_summary['total_return']*100:.1f}%  PSR={asmm_psr:.3f}")

# ── Figure 2 ─────────────────────────────────────────────────────────────────
print("[4/8] Saving Figure 2 — AS Market Maker …")

dates_asmm = btc_df.index[1:]
SAMPLE = 50

fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=False)
fig.suptitle("Strategy 1: Avellaneda-Stoikov Market Maker  (Real BTC-USDT-SWAP, 1H)",
             fontsize=13, fontweight="bold")

axes[0].plot(dates_asmm, asmm_equity, linewidth=0.8, color="#1565C0")
axes[0].axhline(1, color="gray", linewidth=0.6, linestyle="--")
axes[0].set_ylabel("Equity (×)")
axes[0].set_title(f"Equity  Sharpe={asmm_summary['sharpe']:.2f}  "
                  f"TotalRet={asmm_summary['total_return']*100:.1f}%  PSR={asmm_psr:.3f}")

sp_roll = pd.Series(spread_hist, index=dates_asmm).rolling(24).mean()
axes[1].plot(dates_asmm, sp_roll, linewidth=0.7, color="#00897B")
axes[1].set_ylabel("Rel. Spread (×)")
axes[1].set_title("AS Spread / Mid (24-bar rolling mean)")

axes[2].fill_between(dates_asmm[::SAMPLE], inventory_hist[::SAMPLE], 0,
                     where=(inventory_hist[::SAMPLE] >= 0), color="#42A5F5", alpha=0.6, label="Long")
axes[2].fill_between(dates_asmm[::SAMPLE], inventory_hist[::SAMPLE], 0,
                     where=(inventory_hist[::SAMPLE] < 0),  color="#EF5350", alpha=0.6, label="Short")
axes[2].axhline(0, color="black", linewidth=0.5)
axes[2].set_ylabel("Inventory (lots)")
axes[2].set_title("Inventory")
axes[2].legend(fontsize=8)

axes[3].fill_between(dates_asmm, asmm_dd * 100, 0, color="#E53935", alpha=0.5)
axes[3].set_ylabel("Drawdown (%)")
axes[3].set_title(f"Drawdown  Max={asmm_summary['max_drawdown']*100:.1f}%")

plt.tight_layout()
fig.savefig(RESULTS_DIR / "02_as_market_maker.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# 4.  STRATEGY 2: FUNDING CARRY (real 8h funding data)
# ═══════════════════════════════════════════════════════════════════════════════
print("[5/8] Running Funding Carry backtest …")

FEE_ENTRY = 0.001
FEE_EXIT  = 0.001

in_pos = False
returns_carry = []
position_state = []

for _, row in funding_df.iterrows():
    apr     = float(row["apr"])
    rate_8h = float(row["rate"])
    pnl = 0.0

    if not in_pos and apr > 0.12:
        in_pos = True;  pnl -= FEE_ENTRY
    elif in_pos and apr < 0:
        in_pos = False; pnl -= FEE_EXIT
    if in_pos:
        pnl += rate_8h

    returns_carry.append(pnl)
    position_state.append(1 if in_pos else 0)

returns_carry  = np.array(returns_carry, dtype=float)
position_state = np.array(position_state, dtype=float)
carry_equity   = (1 + returns_carry).cumprod()
carry_dd       = (carry_equity - np.maximum.accumulate(carry_equity)) / np.maximum.accumulate(carry_equity)
PERIODS_8H     = 3 * 365
carry_summary  = summary(returns_carry, periods=PERIODS_8H)
carry_psr      = psr(returns_carry, sr_benchmark=0.0)

print(f"    Carry  | Sharpe={carry_summary['sharpe']:.2f}  MDD={carry_summary['max_drawdown']*100:.1f}%  "
      f"TotalRet={carry_summary['total_return']*100:.1f}%  PSR={carry_psr:.3f}")

# ── Figure 3 ─────────────────────────────────────────────────────────────────
print("[5/8] Saving Figure 3 — Funding Carry …")

fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=False)
fig.suptitle(
    f"Strategy 2: Funding Rate Carry  (Real BTC-USDT-SWAP, {FUND_START} → {FUND_END})",
    fontsize=13, fontweight="bold",
)

axes[0].plot(funding_df.index, carry_equity, linewidth=1.0, color="#2E7D32")
axes[0].axhline(1, color="gray", linewidth=0.6, linestyle="--")
axes[0].set_ylabel("Equity (×)")
axes[0].set_title(f"Equity  Sharpe={carry_summary['sharpe']:.2f}  "
                  f"TotalRet={carry_summary['total_return']*100:.1f}%  PSR={carry_psr:.3f}")

axes[1].plot(funding_df.index, apr_pct.values, linewidth=0.8, color="#558B2F")
axes[1].axhline(12,  color="navy",  linestyle="--", linewidth=1.0, label="12% entry")
axes[1].axhline(0,   color="black", linewidth=0.6)
axes[1].fill_between(funding_df.index, apr_pct.values, 0,
                     where=(apr_pct.values < 0), color="#E53935", alpha=0.3, label="Negative APR")
axes[1].set_ylabel("Funding APR (%)")
axes[1].set_title("Real Funding APR vs Entry Threshold")
axes[1].legend(fontsize=8)

axes[2].step(funding_df.index, position_state, where="post", linewidth=1.0, color="#1565C0")
axes[2].set_ylabel("In Position")
axes[2].set_ylim(-0.1, 1.3)
axes[2].set_yticks([0, 1])
axes[2].set_yticklabels(["Flat", "Active"])
axes[2].set_title("Position State")

axes[3].fill_between(funding_df.index, carry_dd * 100, 0, color="#E53935", alpha=0.5)
axes[3].set_ylabel("Drawdown (%)")
axes[3].set_title(f"Drawdown  Max={carry_summary['max_drawdown']*100:.1f}%")

plt.tight_layout()
fig.savefig(RESULTS_DIR / "03_funding_carry.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# 5.  STRATEGY 3: PAIRS TRADING (real BTC-ETH, 1H bars)
# ═══════════════════════════════════════════════════════════════════════════════
print("[6/8] Running Pairs Trading backtest …")

log_btc_h = np.log(btc_df["close"].values)
log_eth_h = np.log(eth_df["close"].values)
N_H = len(log_btc_h)

# ── Kalman filter (replicates PairsTradingStrategy._kalman_update) ────────────
Ve   = 1e-4 / (1 - 1e-4)
beta_kf = 1.0; P_kf = 1.0; R_kf = 0.001

spreads_kf = np.empty(N_H)
betas_kf   = np.empty(N_H)

for i in range(N_H):
    y = log_eth_h[i];  x = log_btc_h[i]
    P_pred  = P_kf + Ve
    innov   = y - beta_kf * x
    S       = P_pred * x ** 2 + R_kf
    K       = P_pred * x / S if S != 0 else 0.0
    beta_kf += K * innov
    P_kf     = (1 - K * x) * P_pred
    spreads_kf[i] = innov
    betas_kf[i]   = beta_kf

# Z-score: rolling 200-bar window
ZSCORE_WINDOW = 200
sp_series = pd.Series(spreads_kf, index=btc_df.index)
sp_mean   = sp_series.rolling(ZSCORE_WINDOW).mean()
sp_std    = sp_series.rolling(ZSCORE_WINDOW).std()
z_score   = ((sp_series - sp_mean) / sp_std.clip(lower=1e-10)).values

ou_params = estimate_ou(sp_series.iloc[ZSCORE_WINDOW:ZSCORE_WINDOW + 500])

log_btc_ret = np.diff(log_btc_h, prepend=log_btc_h[0])
log_eth_ret = np.diff(log_eth_h, prepend=log_eth_h[0])

ENTRY_Z = 2.0;  EXIT_Z = 0.3;  STOP_Z = 4.0
COMM_PAIR = 0.0002

in_pos_pairs   = False
pos_side_pairs = 0
returns_pairs  = []

for i in range(ZSCORE_WINDOW, N_H):
    zi   = z_score[i]
    pnl_p = 0.0

    if in_pos_pairs:
        pair_ret = log_eth_ret[i] - betas_kf[i] * log_btc_ret[i]
        pnl_p += pos_side_pairs * pair_ret

    if in_pos_pairs and abs(zi) > STOP_Z:
        in_pos_pairs = False; pos_side_pairs = 0
        pnl_p -= 2 * COMM_PAIR * 1.5
    elif in_pos_pairs and abs(zi) < EXIT_Z:
        in_pos_pairs = False; pos_side_pairs = 0
        pnl_p -= 2 * COMM_PAIR
    elif not in_pos_pairs and abs(zi) > ENTRY_Z and not np.isnan(zi):
        in_pos_pairs   = True
        pos_side_pairs = -1 if zi > 0 else +1
        pnl_p -= 2 * COMM_PAIR

    returns_pairs.append(pnl_p)

returns_pairs = np.array(returns_pairs, dtype=float)
pairs_equity  = (1 + returns_pairs).cumprod()
pairs_dd      = (pairs_equity - np.maximum.accumulate(pairs_equity)) / np.maximum.accumulate(pairs_equity)
pairs_summary = summary(returns_pairs, periods=PERIODS_1H)
pairs_psr     = psr(returns_pairs, sr_benchmark=0.0)

print(f"    Pairs  | Sharpe={pairs_summary['sharpe']:.2f}  MDD={pairs_summary['max_drawdown']*100:.1f}%  "
      f"TotalRet={pairs_summary['total_return']*100:.1f}%  PSR={pairs_psr:.3f}")
print(f"    OU params → theta={ou_params['theta']:.4f}  half_life={ou_params['half_life']:.1f}h  "
      f"mu={ou_params['mu']:.5f}")

# ── Figure 4 ─────────────────────────────────────────────────────────────────
print("[6/8] Saving Figure 4 — Pairs Trading …")

pair_dates = btc_df.index[ZSCORE_WINDOW:]

fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=False)
fig.suptitle(
    f"Strategy 3: BTC-ETH Pairs Trading  (Real data, {START_DATE} → {END_DATE})",
    fontsize=13, fontweight="bold",
)

axes[0].plot(pair_dates, pairs_equity, linewidth=0.9, color="#AD1457")
axes[0].axhline(1, color="gray", linewidth=0.6, linestyle="--")
axes[0].set_ylabel("Equity (×)")
axes[0].set_title(f"Equity  Sharpe={pairs_summary['sharpe']:.2f}  "
                  f"TotalRet={pairs_summary['total_return']*100:.1f}%  PSR={pairs_psr:.3f}")

z_plot = z_score[ZSCORE_WINDOW:]
axes[1].plot(pair_dates, z_plot, linewidth=0.5, color="#5C6BC0", alpha=0.8)
for thresh, ls in [(2.0, "--"), (4.0, ":")]:
    axes[1].axhline( thresh, color="orange", linestyle=ls, linewidth=1.0)
    axes[1].axhline(-thresh, color="orange", linestyle=ls, linewidth=1.0)
axes[1].axhline( EXIT_Z,  color="green", linestyle=":", linewidth=0.8)
axes[1].axhline(-EXIT_Z,  color="green", linestyle=":", linewidth=0.8)
axes[1].axhline(0, color="black", linewidth=0.5)
axes[1].set_ylabel("Z-Score")
axes[1].set_title(f"Kalman Spread Z-Score  (OU half-life={ou_params['half_life']:.0f}h)")

axes[2].plot(btc_df.index, betas_kf, linewidth=0.7, color="#F57F17")
axes[2].set_ylabel("Kalman β")
axes[2].set_title("Dynamic Hedge Ratio (Kalman Filter)")

axes[3].fill_between(pair_dates, pairs_dd * 100, 0, color="#E53935", alpha=0.5)
axes[3].set_ylabel("Drawdown (%)")
axes[3].set_title(f"Drawdown  Max={pairs_summary['max_drawdown']*100:.1f}%")

plt.tight_layout()
fig.savefig(RESULTS_DIR / "04_pairs_trading.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# 6.  WALK-FORWARD VALIDATION — Funding Carry
# ═══════════════════════════════════════════════════════════════════════════════
print("[7/8] Running Walk-Forward validation (Funding Carry) …")

APR_THRESHOLDS = np.linspace(0.05, 0.30, 6)

def _sim_carry(data: pd.DataFrame, thresh: float) -> list:
    ip = False; rets = []
    for _, row in data.iterrows():
        p = 0.0
        if not ip and float(row["apr"]) > thresh:
            ip = True;  p -= FEE_ENTRY
        elif ip and float(row["apr"]) < 0:
            ip = False; p -= FEE_EXIT
        if ip:
            p += float(row["rate"])
        rets.append(p)
    return rets

def funding_carry_strategy_fn(is_data: pd.DataFrame, oos_data: pd.DataFrame) -> pd.Series:
    best_thresh = 0.12; best_sr = -np.inf
    for thr in APR_THRESHOLDS:
        is_r = np.array(_sim_carry(is_data, thr))
        if is_r.std() > 1e-9:
            s = sharpe(is_r, periods=PERIODS_8H)
            if s > best_sr:
                best_sr, best_thresh = s, thr
    return pd.Series(_sim_carry(oos_data, best_thresh))

# Adjust WF window sizes to fit the available funding data (~93 days)
wf = WalkForward(is_days=14, oos_days=7)
wf_results = wf.evaluate(funding_df, funding_carry_strategy_fn, periods=PERIODS_8H)
n_windows = len(wf_results)
mean_oos = float(wf_results["oos_sharpe"].mean()) if n_windows else float("nan")
print(f"    WF windows={n_windows}  mean OOS Sharpe={mean_oos:.2f}")

# ── Figure 5 ─────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 5))
fig.suptitle("Walk-Forward Validation — Funding Carry OOS Sharpe", fontsize=14, fontweight="bold")

if n_windows > 0:
    colors_wf = ["#1565C0" if s >= 0 else "#E53935" for s in wf_results["oos_sharpe"]]
    ax.bar(wf_results["window"], wf_results["oos_sharpe"],
           color=colors_wf, edgecolor="white", linewidth=0.4)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axhline(mean_oos, color="#2E7D32", linestyle="--", linewidth=1.2,
               label=f"Mean OOS Sharpe = {mean_oos:.2f}")
    ax.set_title(f"IS=14d / OOS=7d  |  {n_windows} windows  |  Mean OOS Sharpe = {mean_oos:.2f}")
    ax.legend(fontsize=9)
else:
    ax.text(0.5, 0.5, "Insufficient data for walk-forward", ha="center", va="center",
            transform=ax.transAxes, fontsize=12)

ax.set_xlabel("Walk-Forward Window")
ax.set_ylabel("OOS Annualised Sharpe")
plt.tight_layout()
fig.savefig(RESULTS_DIR / "05_walk_forward.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# 7.  FIGURE 6 — Performance Summary Table
# ═══════════════════════════════════════════════════════════════════════════════
print("[8/8] Saving Figure 6 — performance summary table …")

METRIC_KEYS   = ["total_return", "sharpe", "sortino", "max_drawdown",
                 "calmar", "profit_factor", "win_rate", "omega"]
METRIC_LABELS = ["Total Return", "Sharpe", "Sortino", "Max Drawdown",
                 "Calmar", "Profit Factor", "Win Rate", "Omega"]
STRAT_NAMES   = [f"AS Market Maker\n({START_DATE}→{END_DATE})",
                 f"Funding Carry\n({FUND_START}→{FUND_END})",
                 f"Pairs Trading\n({START_DATE}→{END_DATE})"]

summaries = [asmm_summary, carry_summary, pairs_summary]
psrs_list = [asmm_psr,     carry_psr,     pairs_psr]

def _fmt(key: str, val: float) -> str:
    if key in ("total_return", "max_drawdown", "win_rate"):
        return f"{val * 100:.2f}%"
    elif val in (float("inf"), float("-inf")):
        return "∞"
    else:
        return f"{val:.3f}"

cell_text = []
for mk in METRIC_KEYS:
    cell_text.append([_fmt(mk, s[mk]) for s in summaries])
cell_text.append([f"{p:.3f}" for p in psrs_list])

fig, ax = plt.subplots(figsize=(13, 7))
fig.suptitle(
    f"Strategy Performance Summary  (Real OKX Data)",
    fontsize=13, fontweight="bold", y=0.98,
)
ax.axis("off")

table = ax.table(
    cellText=cell_text,
    rowLabels=METRIC_LABELS + ["PSR(SR>0)"],
    colLabels=STRAT_NAMES,
    loc="center", cellLoc="center",
)
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.1, 1.8)

for j in range(len(STRAT_NAMES)):
    cell = table[0, j]
    cell.set_facecolor("#1565C0")
    cell.set_text_props(color="white", fontweight="bold")
for i in range(len(METRIC_KEYS) + 1):
    cell = table[i + 1, -1]
    cell.set_facecolor("#E3F2FD")
for i in range(len(METRIC_KEYS) + 1):
    for j in range(len(STRAT_NAMES)):
        if i % 2 == 0:
            table[i + 1, j].set_facecolor("#FAFAFA")

plt.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(RESULTS_DIR / "06_performance_summary.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# 8.  STDOUT SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
SEP = "=" * 82
print(f"\n{SEP}")
print(f"  PERFORMANCE SUMMARY  (Real OKX Data)")
print(f"  BTC/ETH candles: {START_DATE} → {END_DATE}")
print(f"  Funding rates  : {FUND_START} → {FUND_END}")
print(SEP)
print(f"  {'Metric':<18} {'AS Market Maker':>20} {'Funding Carry':>16} {'Pairs Trading':>16}")
print(f"  {'-'*18} {'-'*20} {'-'*16} {'-'*16}")
for mk, ml in zip(METRIC_KEYS, METRIC_LABELS):
    vals = [_fmt(mk, s[mk]) for s in summaries]
    print(f"  {ml:<18} {vals[0]:>20} {vals[1]:>16} {vals[2]:>16}")
print(f"  {'PSR(SR>0)':<18} {asmm_psr:>20.3f} {carry_psr:>16.3f} {pairs_psr:>16.3f}")
print(SEP)
print(f"\n  Output → {RESULTS_DIR}/")
for f in sorted(RESULTS_DIR.glob("0*.png")):
    print(f"    {f.name}")
print()

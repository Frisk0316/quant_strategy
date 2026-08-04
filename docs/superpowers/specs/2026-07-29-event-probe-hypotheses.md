---
status: current
type: spec
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Event-design probe — H-028 (registered, data-blocked) + H-029 (executable)

**Positioning (ADR-0016):** limited probe (1 executable candidate + 1
registered-awaiting-data), NOT a complete round. Motivated by the H-024..H-027
batch post-mortem: four of five recent Stage-2 deaths were statistical-power
fails on daily breadth-2 books (floors 0.85-1.26). Event designs raise
observation counts ~8x (thousands of pooled settlement events), lowering the
honest floor to ~0.55-0.65 annualized — a material but not magical improvement;
the mechanism still has to be real.

**AUTHORIZATION (2026-07-29, user, "照你的方向做" after the direction proposal
that explicitly included Codex execution):** H-029 Stage 2 and, on four-check
PASS, its frozen Stage-3 grid. H-028 is registration-only (no probe possible on
26 days of data); its future probe needs fresh authorization when data
suffices.

## H-028 F-LIQUIDATION-REVERSAL — registered, awaiting data accrual

**Design space.** Problem: do liquidation cascades (forced flow) overshoot and
revert? Options: (a) do nothing — leaves the only structural forced-flow
mechanism untested; (b) probe now on 26 days — statistically meaningless,
burns a registry entry on noise; (c) **register now, accrue, probe when ≥ ~12
months of events exist** — chosen. Axis: immediacy vs statistical honesty.
Flip condition: discovery of a free historical liquidation source (none known;
paid sources out of scope per standing rule).

**Data reality (measured 2026-07-29):** `liq_okx_btc`/`liq_okx_eth` are
per-event with side/pos_side/price/size/notional, but coverage starts
2026-07-02 (forward-accumulating recent-window endpoint; 2026-07-08/09 gap
from host downtime). The `quant_liq_okx_ingest` 2-hourly task must stay
healthy — every downtime day is lost forever (same class as optsurf).

**Hypothesis (falsifiable, frozen for the future probe).** After a liquidation
cascade event (rolling 30-min same-direction liquidation notional z ≥ z_cut vs
trailing 90d), an hourly-horizon position AGAINST the cascade direction on the
affected symbol earns positive net-of-cost Sharpe surviving fold-refit WF/CPCV
with DSR >= 0.95 and PSR >= 0.95. **Mechanism distinction from shelved
H-012/F-OI-POSITIONING:** liquidation events are realized forced FLOW at
minute resolution; H-012 faded price moves on falling open-interest STOCK at
daily resolution. Does not reuse H-012's cost path (F36 does not carry over).

**Earliest probe:** ~2027-07 (12 months of events), or earlier only if the
user accepts a lower-power preliminary read.

## H-029 F-FUNDING-SETTLEMENT-DRIFT — executable now

**Design space.** Problem: is there predictable drift around funding
settlements when funding is extreme? Options: (a) do nothing; (b) carry-style
holding (dead: F-FUNDING-CARRY refuted E-026); (c) cross-sectional funding
level (dead: F-FUNDING-XS-DISPERSION shelved E-063); (d) **event-window
contrarian drift at settlement timestamps** — chosen: mechanism is
positioning-flow at a known clock time (crowded side de-risks into/out of the
payment), which neither dead family tested — they held multi-day carry or
weekly cross-sections; this trades a bounded post-settlement window only.
Axis: mechanism novelty vs proximity to two dead funding families —
distinctness gates decide, thresholds unchanged. Flip condition: return-stream
correlation ≥ MINT threshold with E-026 or E-031/E-063 kills the "different
mechanism" claim — stop at distinctness.

**Hypothesis (falsifiable).** On Binance BTC/ETH-USDT-SWAP, entering at
settlement time t+1min AGAINST the crowded side — SHORT for the holding
window when the settling funding rate z-scores >= +z_cut vs its trailing 90d
distribution, LONG when <= −z_cut, flat otherwise — and exiting at entry+hold,
earns positive net-of-cost Sharpe (8 bps round trip per traded event, costs at
trade time) surviving fold-refit WF/CPCV with DSR >= 0.95 and PSR >= 0.95.

**Frozen contract:**
- Window: 2020-01-01 → 2026-07-02 (full available funding+candle overlap; 90d
  z warmup → formal window from 2020-04-01; end frozen at funding-data max).
- Events: every 8h settlement timestamp with a valid z (≈6,850 per symbol).
- Grid (4 cells, ex-ante): z_cut ∈ {1.5, 2.0} × hold ∈ {2h, 6h}. Stage-2
  proxy = first cell (z_cut 1.5, hold 2h).
- Power inputs (honest event convention per `min_detectable_sharpe`):
  n_obs = pooled traded-eligible settlement timestamps in the formal window;
  breadth = 1.5 (BTC/ETH settle simultaneously and correlate — NOT 2.0);
  periods_per_year = 1095 (3 settlements/day) so the annualization matches the
  per-event return units; n_trials = 4 prospective.
- Distinctness (|corr| < 0.30 on daily-aggregated event PnL, ≥365 common
  days): E-031/E-063 F-FUNDING-XS-DISPERSION dated series (mandatory);
  E-026 F-FUNDING-CARRY series if a dated artifact exists — if none does,
  that is an I49 contract report to Claude, not a fail; F-VOL-REGIME-OPT
  (standard reference).
- Stop rules, no-retune, one registry entry, artifact + SHA-256: identical to
  the E-064..E-067 conventions.

---
status: current
type: review
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Claude review: H-030…H-037 Stage-2 slate (E-069…E-076)

Delivery: commits `69fae10`, `1f5f8df`, `d482a17`, `9f3023d`, `c3cb982`.
Method: primary-evidence read of all eight artifacts by the reviewing session,
plus a fresh-context verifier that ran every check independently.

## Verdict: ACCEPT — delivery is correct and honest

Verifier (all 8 checks PASS): 31/31 targeted tests, 996 passed / 1 skipped full
unit suite, ledger + metadata checks pass, **no Stage-3 leakage** (only
`stage2_feasibility.json` + `sha256.json` per dir, `grid_trials_evaluated=0`
everywhere), K-budgets and trials correctly unchanged for pre-existing families
and zero for the new ones, all eight SHA-256 hashes independently recomputed
and matched to their registry rows, and the 35-file diff matches the permitted
list exactly.

**The five data-blocked verdicts were independently confirmed against the live
DB, not taken on trust:**
- `optflow_deribit_*` rows are **hourly aggregates**; `raw_payload` retains only
  a `sample` array capped at 20 trades/hour (`sample_rule:
  first_20_inverse_trades_in_hour`), 895,928 sample trades over 44,805 hourly
  rows. No per-trade option tape exists → H-031 and H-035 are genuinely
  unbuildable as specified.
- FRED: **0 rows** in `external_observations` → H-033 and H-036 unbuildable.
- Official CME: `cme_btc1_continuous` **0 rows**; only `cme_btc_yfinance`, an
  explicitly research-only proxy, exists. The artifact correctly refused the
  proxy rather than substituting it → H-037 unbuildable.

## Results

| ID | Result | Decisive number |
| --- | --- | --- |
| H-030 | refuted (cost + power) | **Distinctness PASSED cleanly — abs corr 0.0173 vs E-059/F-TAKER-FLOW over 777 days.** The mechanism is genuinely distinct; it dies on economics: mean event gross **0.152 bps against an 8 bps round trip**, a ~53× shortfall over 22,159 events. |
| H-032 | refuted (distinctness + cost + power) | abs corr **0.5615** vs E-067 (1,762 days) |
| H-034 | refuted (distinctness + cost + power) | abs corr **0.4948** vs E-062 (898 days) |
| H-031, H-033, H-035, H-036, H-037 | inconclusive / data-blocked | mechanisms untested; see confirmations above |

## Claude rulings

**1. I27 ASSIGN, H-032 → F-VRP-TIMING.** 0.5615 vs E-067 is above the 0.30
gate over ample common days, so the mint-apart claim is falsified: VoV and our
own conditional-VRP signal are the same bet. Inherits n_trials=4, K 0/2;
F-VOL-OF-VOL dissolved. Note the four E-050 cells correlated only 0.216–0.229 —
the binding reference was H-026's conditional signal, not the original VRP
level, which is a sharper result than a bare "it's VRP".

**2. I27 ASSIGN, H-034 → F-XS-IDIOVOL.** 0.4948 vs E-062 is above the gate, so
"decomposed jump components carry information residual vol averages away" is
falsified. Inherits n_trials=0, K 0/2; F-VARIANCE-DECOMP dissolved.

Both reassignments carry **zero trial/K impact** because both runs evaluated 0
grid cells. K-budget families drop 35 → 33.

**3. H-030's refutation is accepted as final for our cost structure**, and is
worth stating precisely: the Kim & Hansen effect appears to be real and
distinct, but at 0.15 bps per event it is invisible beneath an 8 bps round
trip. The paper never addressed transaction costs; this is the measurement of
why that omission mattered.

## Open finding (does not change any verdict)

H-030's reported annualized Sharpe of −97.3 implies a per-event return standard
deviation of ≈8 bps, which is low for a vol-targeted 4-hour BTC/ETH hold
(≈25–40 bps expected). The hold is implemented correctly (exit at
`ts + 241 minutes`), and the cost gate fails on the **gross** number alone, so
the verdict stands regardless. But the return-series scaling in
`intrabar_periodicity_probe.py` should be understood before that module is
reused for any other candidate. Also unexamined: with ~27 qualifying events per
day and a 4-hour hold, events overlap heavily, so `n_obs=22,159` overstates
independent bets — immaterial to a fail, material if a variant ever passes.

## Process failure to own (mine, not Codex's)

**Five of the eight specs were frozen against data I assumed existed and never
verified.** I scouted data availability before registering H-028/H-029 and
correctly caught the liquidation-history gap; I did not repeat that check for
the literature slate, and the "available data" inventory I fed into the
research prompt listed FRED and CME as present when neither is ingested. The
cost was a full Codex build-and-run cycle producing five untestable candidates.
Recorded in `docs/ai/LESSONS.md`.

## Next

- The five data-blocked candidates stay `inconclusive`, not refuted — their
  mechanisms are untested. Unblocking each needs an ingestion decision:
  per-trade Deribit tape retention (H-031/H-035), FRED series ingestion
  (H-033/H-036), official CME data (H-037). Each is a separate, user-authorized
  data task.
- No Stage 3 is authorized for anything in this batch, and nothing in it earned
  one.

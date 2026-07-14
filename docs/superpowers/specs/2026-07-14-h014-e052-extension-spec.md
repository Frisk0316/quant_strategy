---
status: accepted
type: design
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# H-014 E-052 robustness extension — pre-registration (user-authorized 2026-07-14)

User ratified checkpoint ① (E-051) and authorized a longer-history retest.
Requested 2017→now; **data floor is 2019-03/04** (Deribit options trade tape
availability and the ETH options launch; DVOL itself starts 2021-03-24; DB 1m
OHLCV starts 2020). This extension is a same-mechanism retry: **consumes K
(F-VOL-REGIME-OPT K 0/2 → 1/2 at run time)**, grid unchanged, all method
choices below fixed BEFORE the reconstruction runs.

## IV-proxy reconstruction (pre-DVOL signal input)

**v1 verdict (2026-07-14): RECONSTRUCTION-FAIL-CLOSED, no K consumed.** The
tenor 20–40d / ±10% filter left 28–38% carry days with consecutive stale runs
up to 16 (BTC) / 24 (ETH) days — a filter-design artifact of the
monthly-expiry-dominated 2019–2020 listing structure (post-roll weeks have no
expiry inside 20–40d), caught by the pre-registered staleness rule. v2 below
was re-registered BEFORE any v2 aggregation ran; only data-quality
statistics, never strategy returns, were inspected between v1 and v2.

- Source: official trade tape (`get_last_trades_by_currency_and_time`),
  BTC and ETH, 2019-04-01 → 2021-06-30.
- Trade filter per day D (v2): option trades with tenor 10–60 calendar days
  and strike within ±15% of the trade's index price; both calls and puts.
  The sweep also stores the raw qualifying-superset trades (tenor ≤ 90d,
  moneyness ≤ 30%) so future re-aggregations need no re-sweep.
- Staleness rule (v2, intent-matched): max consecutive carry run ≤ 5 days
  AND overall carry ratio ≤ 15% over the classified span; violation fails
  the reconstruction closed as before.
- Daily proxy IV_D = premium-amount-weighted mean of trade `iv`. Days with
  < 10 qualifying trades carry the previous day's value (counted; > 10%
  carry-days in any 90-day stretch flags that stretch unusable).
- **Splice calibration:** overlap window 2021-03-24 → 2021-06-30: bias :=
  mean(proxy − DVOL daily close). Pre-DVOL series := proxy − bias. From
  2021-03-24 on, the signal input remains actual DVOL (E-039 series
  unchanged). Overlap stats (bias, std, corr) are reported in the artifact;
  |corr| < 0.85 on the overlap fails the reconstruction closed.
- Underlying daily closes 2019-04 → 2021-03 from the same public perpetual
  history used by E-039.

## Signal, book, and validation — identical to E-051

The signal stays IVP(365d) AND VRP z(90d) exactly as in the E-039 series
construction, recomputed over the spliced IV series, so classified days begin
≈ 2020-04 (COVID-crash aftermath), adding the 2020-03 shock decay and the
2021-05 crash to the existing 2022 bear. Same pre-registered grid
`{ivp_min ∈ [75,85], z_min ∈ [0.5,1.0]}`, same ADR-0010/R8 accounting, same
t+1 entry / tranche ladder / fee / settlement rules, same collectors
(creation_timestamp filter mandatory), `refit_validation` with
family-cumulative `n_trials = 8` (prior 4 + retry grid 4, I23).

## Outcome rules (fixed ex-ante)

- PASS (DSR ≥ 0.95 AND PSR ≥ 0.95 on the extended window): H-014 stays
  `supported` with materially stronger evidence.
- FAIL: H-014 reverts to `testing` with the conflict recorded; no further
  retry without user escalation (K would be 1/2; a second retry exhausts it).
- RECONSTRUCTION-FAIL-CLOSED (overlap corr < 0.85 or unusable stretches):
  E-052 records a data verdict only, consumes no K, and the extension is
  re-scoped or dropped.

## Artifacts

`results/h014_e052_extension_<date>/` (iv proxy series + overlap stats +
entries/marks/delivery extensions + summary.json). Experiment id E-052.

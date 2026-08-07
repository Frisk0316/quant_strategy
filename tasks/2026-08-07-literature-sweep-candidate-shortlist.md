---
status: current
type: task
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# 2026-08-07 literature sweep — candidate shortlist (track 2 of 雙軌並進)

Four parallel axis sweeps (OHLCV-XS, derivatives, macro, intraday-derived),
predictive-evidence-only, burned families excluded ex ante. Full agent
reports in the session transcript; this file records verdicts + identities.
Next step per candidate: full Candidate Admission Form packet
(`tasks/2026-08-05-candidate-input-quality-review.md` gates A1–E).

## ADMISSION-WORTHY (build packets next)

### S-001 Multi-week cross-sectional reversal (8–10 week formation)

- Signal: rank on trailing 8–10wk return; long losers/short winners; weekly
  overlapping portfolios (Jegadeesh-Titman). LOW turnover (~1/8 book/wk).
- Evidence: Kiefer & Nowotny 2026, SSRN 6703978 — 70 USDT Binance tokens,
  2021-01→2026-03 (venue/universe/period ≈ ours). Baseline Sharpe 0.96
  (NW t 2.10); high-vol subset 1.37 (t 3.19). Corroboration: Dobrynskaya
  SSRN 3913263 (2014–2020); Zaremba IRFA 2021 (1-day reversal is an
  illiquidity artifact — multi-week horizon only).
- Risks: working paper (not refereed); baseline 0.96 < 1.05 floor (boosted
  variants are small-cap-tilted); shares ranking machinery with refuted
  F-XS-MOMENTUM — distinctness gate vs momentum trials is decisive and must
  be pre-registered as such.

### S-002 Positive-jump variance / signed-jump XS short (weekly)

- Signal: from intraday returns, decompose RV into jump-robust + signed
  jump variances (or RSJ from semivariances); short high-JV+/RSJ names
  weekly. Computable from held 1m bars today.
- Evidence: Lee & Wang, JFQA 60(4) 2025 (doi:10.1017/S002210902400022X) —
  100 coins, 15-min data, 2015-10→2023-06 (includes Terra/FTX). H−L
  −3.7%/wk EW, −3.0%/wk VW at 1%, LTW-3-factor robust; effect loads on
  JV+ and jump-robust variance, NOT JV−. Zhang & Zhao IRFA 2023
  (SSRN 3910202) independently confirm RSJ.
- Risks: strongest in small/retail coins — top-30 attenuation is THE test;
  no cost analysis in paper (gross spreads); mechanism-cousin of
  F-XS-IDIOVOL (H-023/E-062) — distinctness check vs E-062 decisive.
  Perp shorting removes the paper's borrow constraint (our edge).

## BORDERLINE (hold, do not packet yet)

- S-003 CTREND trend factor (Fieberg et al., JFQA 60(7) 2025, SSRN
  4601972): peer-reviewed, cost-robust in big coins, but sample ends
  2022-05 and adjacency to refuted F-XS-MOMENTUM makes the distinctness
  gate a coin flip. Only revisit if S-001 passes and leaves K appetite.

## DATA-BLOCKED LOG (no timer; revisit conditions stated)

- 25Δ risk-reversal skew → returns: strongest equity pedigree (Xing/
  Zhang/Zhao JFQA 2010; Cremers & Weinbaum JFQA 2010), zero clean crypto
  test; needs 18–24mo of surface history (ours starts 2026-08) or a
  purchase. Revisit ≈2028-02 or on user-approved data buy.
- BVRP (BTC implied-minus-realized variance): mechanism distinct from
  burned VRP-timing, but no in-crypto predictive t-stats published
  (Atanasova SSRN 6771170 routes predictability through burned
  vol-of-vol). Do not buy data on current evidence.

## BARREN AXES (evidence recorded so we stop re-asking)

- Macro/cross-asset → crypto: BARREN at our bar. Liu & Tsyvinski RFS 2021
  anchor (no macro-factor exposure) still stands 2021–2026; dollar/rates/
  gold/liquidity leads are contemporaneous, practitioner-grade, or
  same-as-burned. Confirms H-040..H-046 closures from the literature side.
- Derivatives-implied direction: every candidate is equity-only,
  contemporaneous, data-blocked, or burned-adjacent.
- Calendar seasonality: dead post-2015 in recent samples (FRL 2024).
- Amihud/spread-proxy/volume premia: micro-cap artifacts; our universe has
  no cross-sectional variance in them.
- Intraday TS momentum (first→last half-hour): same-day horizon, single-
  digit-bps gross vs 16bps round trip — cost-dead for a daily book.

## Selection accounting (gate E, sweep level)

Sweep was literature-first (no repository outcome data consulted for
inclusion); burned-family exclusions used ledger status only. S-001/S-002
each become ONE prospective candidate; no variant screening occurred.
Admission packets must declare family linkage: S-001 → likely NEW family
(distinctness vs F-XS-MOMENTUM pre-registered); S-002 → NEW family with
pre-registered distinctness vs F-XS-IDIOVOL/E-062.

## Next actions

1. Claude: build S-001 and S-002 admission packets (A1 DB verification
   queries, B1 gross derivation from paper magnitudes to bps/event, B2
   cost model at maker/taker, B3 ≥ 2.0 check, E accounting). C1/C2 breadth
   needs a deterministic position series — pair each packet with a
   registered runner spec so phase 3 can bind it.
2. Codex: `tasks/2026-08-07-adr0016-phase3-round-runners-codex-tasks.md`
   (parallel track 1).
3. User: no decision needed until both packets pass/fail B3.

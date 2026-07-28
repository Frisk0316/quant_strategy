---
status: current
type: spec
owner: claude
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# Deribit moneyness/vol limited probe — H-024..H-027 Stage-1 spec

**Positioning (ADR-0016):** this is a **limited probe** (4 candidates), NOT a
complete strategy-finding round (which requires 10-15 frozen candidates with
the 8/2 mechanism/iteration mix). Registered before any results exist.
Trigger: the 2026-07-27 Deribit backfill (branch
`feature/deribit-vol-backfill-moneyness`, PR #17) made these datasets
available: DVOL 1h 2021-03+, RV30 1h 2018/2019+, optflow moneyness buckets
2024-01+ (see `config/external_data.yaml` notes for measured provenance).

**Shared constraints (all candidates):**
- Tradable book: OKX/Binance BTC/ETH-USDT-SWAP perps only (no options trading).
- All gates per existing contracts: Stage-2 four-check (data / distinctness /
  cost / power) with the frozen-contract discipline, then Stage-3 fold-refit
  WF/CPCV with family-cumulative `n_trials`, DSR >= 0.95 and PSR >= 0.95.
- No retune to chase gates; stop rules apply as in E-059/E-062.
- Optflow-based candidates: usable history starts 2024-01-01 (~2.5y hourly).
  The newest ~1 day lacks bucket fields until archive catch-up re-ingest —
  signals must tolerate a 1-day feature lag or exclude the live edge in
  backtests.
- Execution needs user authorization per candidate (or batch) before Stage 2.

---

## H-024 F-OPT-HEDGE-DEMAND — OTM put taker-buy surge

**Design space.** Problem: is bucketed OTM put taker-buy flow a tradable
risk-off signal where aggregate put/call flow (H-015, refuted) was not?
Options considered: (a) do nothing — leaves the only genuinely new backfilled
feature untested; (b) level signal (OTM put buy share high vs 90d) — closest
to refuted H-015 shape, weakest ex-ante separation; (c) **surge/acceleration
signal** (short-window OTM put buy premium vs its own trailing baseline,
long/flat de-risk) — chosen: Pan-Poteshman informed-trading evidence is
strongest in OTM contracts (leverage selection by informed traders), and E-044
showed the *aggregate* imbalance carries no signal, so the ex-ante claim is
specifically that moneyness bucketing isolates the informed component the
aggregate diluted. Axis: novelty-of-mechanism vs closeness-to-refuted-family.
Flip condition: if OTM-put-buy z-score return streams correlate > MINT
threshold with E-044 cells, the "bucketing isolates new information" premise
is false — stop at distinctness, do not reshape.

**Hypothesis (falsifiable).** A daily-rebalanced long/flat vol-targeted book
on BTC/ETH-USDT-SWAP that de-risks (flat) when the trailing 24h
`otm_put_buy_amt` share of total premium volume z-scores >= z_cut vs its 90d
distribution, long otherwise, earns positive net-of-cost Sharpe surviving
fold-refit WF/CPCV with DSR >= 0.95 and PSR >= 0.95.

**Distinctness targets:** E-044 (F-OPTFLOW-POSITIONING, refuted) — mandatory,
this is the nearest refuted neighbor; E-045 vol cells; F-VOL-REGIME-OPT
(E-051/E-052) since both de-risk in stress.

## H-025 F-OPT-MONEYNESS-STRUCTURE — OTM premium share regime

**Design space.** Problem: does the *composition* of option flow (OTM share of
premium) carry regime information beyond its *direction* (H-024)? Options:
(a) do nothing; (b) standalone signal book; (c) **conditioning overlay
evaluated as a standalone long/flat book first** — chosen: an overlay claim is
only meaningful if the conditioning variable predicts something; the cheapest
falsifiable form is a long/flat book on the variable itself. Axis: standalone
edge vs filter value. Flip condition: if Stage-2 power fails as a standalone
(like H-022), it may still be re-registered later as a filter on an existing
supported strategy — that would be a NEW hypothesis, not a retune of this one.

**Hypothesis (falsifiable).** A daily-rebalanced long/flat vol-targeted book
on BTC/ETH-USDT-SWAP that is flat when the trailing 24h
(`otm_premium`/(`atm_premium`+`itm_premium`+`otm_premium`)) z-scores >= z_cut
vs its 90d distribution and long otherwise earns positive net-of-cost Sharpe
surviving fold-refit WF/CPCV with DSR >= 0.95 and PSR >= 0.95.

**Distinctness targets:** H-024 return streams (same dataset, different
transform — if they mint as one family, they are one family and consume one
budget); E-044; E-045.

## H-026 F-VRP-TIMING retry 1 — regime-conditional VRP (family iteration)

**This is a retry of the shelved H-013 family, NOT a new family.** It consumes
F-VRP-TIMING K retry 1/2 and requires explicit user authorization on that
basis. Prior family grid: E-050's pre-registered 4 combos → next CPCV run uses
family-cumulative `n_trials` = 4 + new grid size.

**New ex-ante rationale (what E-050 did not test).** E-050 tested the
*unconditional* Bollerslev-Tauchen-Zhou VRP-return relation on 2024-2026 and
failed (WF 0.05, DSR 0.60). The new mechanism claim: VRP level is a mispricing
signal only in *calm* realized-vol regimes; in stressed regimes a high VRP is
fair compensation for jump risk, so the unconditional signal mixes two
populations and cancels. This conditioning was stated in vol literature
(VRP decomposition into diffusive/jump parts) and is testable now because the
backfilled window (2021-03 → now, ~5.3y) contains full stress cycles
(2021-05, 2022 bear, 2024-2026), unlike E-050's 2024-2026 window. Flip
condition: if conditional cells still fail, the family is shelved at K=2 —
terminal, no further VRP work without human escalation.

**Hypothesis (falsifiable).** A daily-rebalanced long/flat vol-targeted book
on BTC/ETH-USDT-SWAP that is long only when (VRP = hourly DVOL minus RV30 is
high vs its 90d distribution) AND (RV30 is below its rolling median regime
threshold), flat otherwise, earns positive net-of-cost Sharpe surviving
fold-refit WF/CPCV at family-cumulative `n_trials` with DSR >= 0.95 and
PSR >= 0.95.

**Distinctness targets:** E-050 cells (same family — expected related; the
gate here is the conditional cells adding information, judged by the standard
contract, not by relaxing MINT); F-VOL-REGIME-OPT (E-051/E-052) — mandatory,
both condition on vol regime.

## H-027 F-XVOL-RATIO — ETH/BTC implied-vol ratio mean reversion

**Design space.** Problem: is the relative implied-vol level between ETH and
BTC (both DVOL 1h now 2021-03+) a tradable relative-value signal? Options:
(a) do nothing; (b) vol-ratio as regime input to existing pair family — F-PAIRS-OU
is refuted (E-025), building on it inherits a dead family; (c) **standalone
dollar-neutral ETH-vs-BTC book signaled by DVOL-ratio z-score extremes** —
chosen: mechanism (relative risk-appetite reversion) is distinct from
price-spread OU (E-025 traded price cointegration, this trades vol-ratio
extremes). Axis: mechanism novelty vs proximity to refuted pair family. Flip
condition: return-stream correlation with E-025 cells above MINT threshold
kills the "different mechanism" claim — stop at distinctness.

**Hypothesis (falsifiable).** A dollar-neutral BTC/ETH-USDT-SWAP pair book
that goes long ETH / short BTC when the ETH/BTC hourly DVOL ratio z-scores
<= -z_cut vs its rolling distribution (and the mirror trade at >= +z_cut),
flat inside the band, daily-rebalanced and vol-targeted, earns positive
net-of-cost Sharpe surviving fold-refit WF/CPCV with DSR >= 0.95 and
PSR >= 0.95.

**Distinctness targets:** E-025 (F-PAIRS-OU, refuted) — mandatory; E-051/E-052
(vol-regime); H-021/E-056 (cross-venue pair mechanics, refuted).

---

## Execution notes

- Order (cheapest information first): H-024 → H-025 (shares H-024's feature
  pipeline) → H-027 → H-026 (consumes a scarce K retry; run last so the
  probe's feature-engineering lessons land first).
- Stage-2 power reality check: H-022 and H-023 both died at the power floor
  with breadth ~6-31; these are breadth-2 (BTC/ETH) time-series books like
  H-013/H-015, so the power floor computation must use the time-series
  convention of E-038/E-050, not the cross-sectional one.
- Each executed candidate gets its own EXPERIMENT_REGISTRY entry at run time;
  none are reserved here. No Stage 3 without Stage-2 four-check PASS.
- Implementation (feature extraction from `external_observations` JSONB
  fields, grid runner wiring) is Codex work per AGENTS.md ownership; this spec
  plus the ledger rows are the Claude-side deliverable.

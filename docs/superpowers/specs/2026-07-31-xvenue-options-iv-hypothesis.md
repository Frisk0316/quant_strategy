---
status: current
type: spec
owner: claude
created: 2026-07-31
last_reviewed: 2026-07-31
expires: none
superseded_by: null
---

# Cross-venue options IV/skew hypothesis (H-039) — design-space expansion

Status: Stage-0 implementation complete / persistence-blocked (forward
accumulation not activated).
Author: Claude, 2026-07-31; implementation: Codex, 2026-07-31.
Origin: user question "can we build strategies from Binance/OKX/Bybit options data?"

## Design-space expansion (per docs/DESIGN_SPACE.md)

### Cross-venue crypto options data as a new signal source — 2026-07-31

**Problem:** The only supported hypothesis (H-014) consumes Deribit options data;
no hypothesis uses the OKX/Bybit/Binance options surfaces, and we do not know if
cross-venue IV/skew divergence carries tradable information.

**Constraints:**
- Hard: no paid data purchases (2026-07-30 CME precedent); DSR/PSR >= 0.95
  gates; fail-closed Stage-2 data checks; family K/n_trials accounting;
  Claude does not implement collectors (Codex work).
- Soft: collector must be low-maintenance (cron snapshot like
  `quant_liq_okx_ingest`); avoid another first-20-samples trap (H-031/H-035).

**Data facts (researched 2026-07-31, sources in research log):**
- OKX: BTC/ETH European options; `GET /api/v5/public/opt-summary` returns mark
  IV + full greeks, free, no auth, ~20 req/2s. OI snapshot ~$3.2B.
- Bybit: USDC options BTC/ETH/SOL+; `GET /v5/market/tickers?category=option`
  returns markIv, bid1Iv/ask1Iv, greeks, OI, free. OI ~$1.3B.
- Binance: eapi European USDT options alive but marginal (~1% of Deribit OI);
  `eapi/v1/mark` public with mark/bid/ask IV + greeks.
- Deribit (reference venue, ~$46B OI): already ingested (H-014 stack).
- Free HISTORY does not exist: venue bulk archives exclude options;
  Tardis free tier = first-day-of-month CSVs only (12 days/yr — unusable for
  daily-horizon Stage 3). Forward collection is the only free path.

**Option A — buy Tardis history:** immediate 2020+/2023+ backfill for all
venues. Assumes budget approval. Wrong if edge is too small to justify spend —
which we cannot know ex ante. Blast radius: money + contradicts the
no-paid-data precedent. REJECTED for now.

**Option B — forward collector + deferred test (chosen):** Codex builds a cron
snapshot job (e.g. hourly) capturing, per venue (OKX, Bybit, Deribit; Binance
optional): 30d-tenor ATM mark IV, 25Δ risk-reversal (skew), total OI, and
top-of-book IV spread for the nearest-listed standard tenors. Register H-039 as
proposed/data-blocked like H-028; earliest honest Stage-2 probe after ~9-12
months of accumulation (>=270 daily observations). Assumes venue APIs stay
public. Wrong if OKX/Bybit IV is pure Deribit-follower noise — exactly what the
test will decide. Blast radius: one new ingest task + external_store table.

**Option C — smallest change:** do nothing; rely on Tardis free monthly samples
for a one-off descriptive study only. Rejected as a hypothesis path: 12
obs/year can never clear power gates; useful only as a schema/sanity reference
while building Option B.

**Axis:** money-now vs time-now (paid backfill vs free forward accumulation).
**Decision:** Option B — free, consistent with H-028 precedent, and the
collector cost is small; grab Tardis free samples once for schema calibration.
**Would change if:** user approves a data budget (flips to A), or 3 months of
collected data shows cross-venue 30d ATM IV gaps are always < fee floor
(kills the RV variant early) → ledger entry H-039.

## Hypothesis (falsifiable, primary variant)

H-039 / F-XVENUE-OPT-IV: A daily-rebalanced long/flat vol-targeted book on
BTC/ETH-USDT-SWAP that de-risks (flat) when cross-venue 30d ATM IV dispersion
(std of OKX/Bybit/Deribit mark IV, z-scored vs trailing 90d) >= z_cut and is
long otherwise earns positive net-of-cost Sharpe surviving fold-refit WF/CPCV
with DSR >= 0.95 and PSR >= 0.95.

Rationale for trading perps, not the options: OKX/Bybit option books are thin
(wide spreads) and would likely die at the Stage-2 cost gate; the information
variant follows the H-013/H-026 pattern (options-derived state variable, liquid
perp execution). A venue-RV variant (trade the IV gap directly on the options)
stays in the design space as a secondary cell, gated on observed spread width
from collected data.

Distinctness risk (I27): must mint apart from F-VRP-TIMING (E-050/E-067) and
F-VOL-REGIME-OPT (H-014) — dispersion-across-venues is a different state
variable than IV-level/VRP, but the 0.30 corr gate decides, not the story.

## Stage plan

0. (Codex, user-authorized 2026-07-31) Build collector on the existing
   `external_observations` store; one-off Tardis free-sample pull for schema
   calibration. Alert on gaps —
   downtime days are permanently lost (H-028 lesson).
1. After >=270 daily obs: Stage-2 four-check screen (data coverage,
   distinctness vs E-050/E-067/H-014 signals, cost, power). Fail-closed.
2. Only on Stage-2 PASS: pre-registered 4-combo grid {z_cut, dispersion
   window} fold-refit WF/CPCV at family-cumulative n_trials.

No trials consumed, K 0/2, no Stage 3, no promotion/demo/shadow/live claim.

## Stage-0 implementation record

- Reused the existing `external_datasets` / `external_observations` tables; no
  migration or new storage abstraction was needed.
- Registered six hourly datasets:
  `xvenue_opt_iv_{okx,bybit,deribit}_{btc,eth}`. For each expiry the collector
  selects the strike nearest the underlying/forward for ATM call/put IV and the
  call/put nearest +0.25/-0.25 delta. It brackets 30 calendar days with two
  valid expiries and linearly interpolates each leg in total variance; when
  only one side exists it uses the nearest expiry and records
  `interp = "nearest"`. `value_num` is `fields.atm_iv_30d`; `fields.rr_25d`
  is call IV minus put IV. Deribit percent IV is normalized to decimal.
- JSON fields also record full-chain venue-native OI and its unit. The complete
  normalized active instrument chain is retained in `raw_payload.instruments`
  so the derived metrics can be replayed. `observed_at` is the UTC snapshot
  hour bucket and `published_at` is the bucket end.
- `snapshot_xvenue_options.py` attempts all six datasets even when one venue
  fails, writes every successful current bucket, and exits non-zero after the
  attempts when a source failed or the prior-bucket gap exceeds 1.5 hours.
- Tardis free-sample schema calibration streamed only the CSV header for
  Deribit and OKX `options_chain` on 2020-09-01. Both returned:
  `exchange,symbol,timestamp,local_timestamp,type,strike_price,expiration,open_interest,last_price,bid_price,bid_amount,bid_iv,ask_price,ask_amount,ask_iv,mark_price,mark_iv,underlying_index,underlying_price,delta,gamma,vega,theta,rho`.
  Tardis does not document an equivalent Bybit options-chain dataset, so Bybit
  was calibrated against its public V5 option-tickers response.
- Public live source smoke passed all six datasets at 2026-07-31 09:00 UTC;
  every row used total-variance interpolation. BTC ATM IV was
  0.335363/0.341324/0.343866 for OKX/Bybit/Deribit and ETH was
  0.468888/0.478109/0.475948. The retained chains contained
  702/584/854 BTC and 644/474/708 ETH instruments respectively. These are
  in-memory source observations, not persisted row counts.
- First DB persistence is still blocked by the local TimescaleDB/Docker daemon
  refusing the configured connection (`ConnectionRefusedError`). The scheduled
  task is intentionally not registered; follow `docs/RUNBOOK.md` only after the
  DB is healthy and one six-dataset manual snapshot succeeds. Until then,
  H-039 remains data-blocked and no accumulation window has begun.

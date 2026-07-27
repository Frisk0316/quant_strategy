---
status: current
type: review
owner: claude
created: 2026-07-24
last_reviewed: 2026-07-24
expires: none
superseded_by: null
---

# Claude Review: E-058 F-TAKER-FLOW Stage-2 (H-022)

Fresh-context verifier + reviewer DB root-cause probe. Delivery commits
eb4a9db (preregister) → d9e89b7 (probe) → 0831013 (outcome).

## Verdict: APPROVE

- Registration-before-run provable in git; commit #1 contains only
  ledger/registry rows with the R6.6 ex-ante range declarations.
- Probe independently reproducible: power floor 0.7548964575664427 recomputed
  bit-for-bit; both gating-reference SHA-256s recomputed and matching; signal
  formula frozen (probe raises on any non-spec params); ts-bounded per
  symbol-year queries; malformed taker fields degrade to missing, never
  imputed. Full unit suite 954 passed / 1 skipped; ledger consistency,
  docs-impact --strict, Ruff PASS. Scope clean; no existing artifact touched.
- Outcome honesty: stage2_status FAIL on data_availability alone
  (coverage 0.932 < 0.95); H-022 recorded `inconclusive` (data-blocked), not
  refuted; n_trials 0 consumed, K 0/2.

## Reviewer root cause (direct DB evidence, read-only)

The 2,505,600 missing minutes are exactly ETH-USDT-SWAP (898d) +
SHIB-USDT-SWAP (842d) full member windows:

1. **ETH-USDT-SWAP:** Binance 1m raw rows are genuinely ABSENT from
   `market_klines` (sampled minute 2025-06-02 00:00 has 28 binance symbols
   with full 12-slot raw arrays; ETHUSDT is not among them). ETH's canonical
   coverage was populated via a path that did not persist raw kline arrays.
   Repair: free Binance Vision ETHUSDT-perp 1m re-ingestion into the raw
   layer for 2024-01-01→2026-06-17 (~1.29M rows), or an approved equivalent.
2. **SHIB-USDT-SWAP:** identity artifact — Binance lists only the
   1000SHIBUSDT perp; no native SHIBUSDT perp exists, so SHIB-USDT-SWAP can
   never have Binance taker rows. Moreover the PIT universe contains BOTH
   `SHIB-USDT-SWAP` and `1000SHIB-USDT-SWAP` as members — a potential
   double-weighting of the same economic asset in every XS book. This is a
   universe-integrity issue BEYOND this probe and needs its own scoped task.

## Notable preliminary signals (NOT evidence, window-limited)

On the 30 complete symbols: distinctness PASS (funding 0.059, vol-regime
0.100; advisory H-002 momentum 0.484), cost PASS with margin (52.8 bps weekly
gross vs 10.1 bps hurdle), power PASS (0.781 ≥ 0.755). These do not carry
evidentiary weight until data_availability passes on the full universe.

## User authorization 2026-07-24 ("批")

Steps 1 and 2 below are AUTHORIZED: the data-repair task and the E-059
reprobe of the same frozen contract. Task file:
`tasks/2026-07-24-e058-repair-e059-codex-tasks.md`. Step 3 (Stage-3) remains
a separate future decision.

## Repair-delivery review 2026-07-24 (commits 8fac3f7, aeb3443): APPROVE

- **T2 alias rule (`8fac3f7`): APPROVE.** `backtesting/universe_aliases.py`
  is minimal and order-preserving (alias map applied before dedup, so
  SHIB+1000SHIB collapse to one member); test 1/1 green; membership parquet
  byte-identical (SHA-256 `98228103...57c5` in the manifest); ADR-0015 +
  manifest + DOMAIN_RULES/INVARIANTS/KNOWN_ISSUES updated;
  docs-impact --strict and ledger consistency PASS. Ratified decisions:
  post-collapse universe does NOT refill rank-31 (conservative, no
  lookahead); helper deliberately NOT wired into the probe until T3 (the
  wiring is E-059's sole permitted code change). Collapse-day semantics
  (SHIB-only membership days map to the tradable 1000SHIB contract)
  accepted as economically correct consumption-time resolution.
- **T1: NEEDS-HUMAN, correctly fail-closed.** The sandbox preflight
  returned an EMPTY response and Codex refused to run ingest because the
  Binance client can swallow a network failure into an empty list — running
  would have risked a fake zero-row checkpoint. Right call; the client's
  swallow behavior is now recorded in FAILURE_MODES. Pre-ingest non-ETH
  baseline snapshot hash recorded for post-ingest invariance checking.
- **T3: correctly not started** (gated on verified T1). E-059 neither
  registered nor run; no artifact exists.

Next: the user runs the documented preflight + backward ingest on a
network-enabled host and returns both outputs; Codex then verifies T1
(898/898 days, 1,293,120 rows, 12-slot arrays, non-ETH baseline hash
unchanged) and proceeds to T3.

## Recommended next steps (need user authorization)

1. Data-repair task (Codex): ETH raw 1m backfill (Binance Vision, free;
   human/local network step) + SHIB-vs-1000SHIB universe identity resolution
   (scoped, PIT-preserving, with Claude review — do NOT silently rewrite
   membership history).
2. After repair verifies: E-059 reprobe of the SAME frozen contract
   (data-gap repair path, E-055→D6 precedent; not a gate-chasing retry;
   K unchanged; new experiment record with ex-ante note).
3. If E-059 passes all four checks, Stage-3 authorization is a separate user
   decision (grid n_trials=4 would then be consumed).

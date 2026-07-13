---
status: current
type: task
owner: claude
created: 2026-07-13
last_reviewed: 2026-07-13
expires: 2026-10-13
superseded_by: null
---

# Codex Task List: F-VOL-REGIME-OPT Stage-2 (H-014 / E-040)

Source spec: `docs/superpowers/specs/2026-07-13-f-vol-regime-opt-hypothesis.md`
(pre-registered grid + E-039 probe outcome). Claude-authored plan; **Codex
implements; Claude reviews every diff and report from here on** (user ruling
2026-07-13). User has authorized Stage-2 ONLY. T3 below is explicitly NOT
authorized yet.

## Context in two sentences

E-039 showed the IVP×VRP-z regime filter separates coin-denominated
short-premium payoffs (RICH covered call +2.35%/30d BTC vs −0.09% unfiltered)
under synthetic BS-on-DVOL pricing, and killed the cheap-bucket long-straddle
leg. Stage-2 must answer: **are real Deribit premiums close enough to the
synthetic prices that the RICH-bucket edge survives?**

## Global scope rules (apply to every task)

PERMITTED FILES:
- `research/probes/` (new scripts; do not edit `f_vol_regime_opt_probe.py`
  except to import/reuse — its E-039 output is an immutable artifact)
- `scripts/market_data/` new download helper only (no edits to existing
  ingestion scripts)
- `results/stage2_probe_*_f_vol_regime_opt/` (new artifacts)
- `docs/EXPERIMENT_REGISTRY.md` (E-040 row + note), `docs/HYPOTHESIS_LEDGER.md`
  (H-014 experiment link/notes only)
- `tests/unit/` new test files; docs per the AGENTS.md docs-update matrix

FORBIDDEN (do not touch in any task):
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`
- `config/risk.yaml`, any gate; `backtesting/` engine modules
- existing `results/**` artifacts (incl. E-039 outputs); `research/*.md`
- the other session's uncommitted PR #9 repair files

SCOPE LIMIT: no options backtest engine, no Deribit trade adapter, no
Change Manifest/ADR work — those are T3, not authorized.

## T1 — Real-premium calibration vs E-039 synthetic pricing (E-040)

Task: download Tardis.dev free first-of-month Deribit `options_chain` sample
days and measure how real quoted premiums compare to the probe's BS-on-DVOL
prices.

Required behavior:
1. Sample selection from `results/stage1_probe_20260713_f_vol_regime_opt/series_{btc,eth}.csv`:
   all month-first dates with a classified regime; pick ≥6 per symbol,
   stratified — ≥1 from the top IVP quartile and ≥1 from the bottom quartile
   per symbol when such month-firsts exist (they are data-given; no other
   selection freedom).
2. For each sampled day×symbol: fetch
   `https://datasets.tardis.dev/v1/deribit/options_chain/{yyyy}/{mm}/{dd}/OPTIONS.csv.gz`
   (no API key needed for first-of-month), take the snapshot nearest 08:00 UTC,
   select the expiry nearest 30d, and extract coin-denominated mid premiums +
   bid-ask spreads for: ~25Δ call, ~25Δ put, ~10Δ put, ATM call+put (nearest
   listed strikes; record actual delta/strike used).
3. Emit per-leg ratio `real_mid / synthetic_bs_on_dvol` and spread as % of mid;
   aggregate by leg and by IVP quartile. Write
   `results/stage2_probe_<date>_f_vol_regime_opt/stage2_feasibility.json`
   (+ per-day CSV) including a verdict field: PASS if the RICH-relevant legs'
   real premiums are ≥ 0.8× synthetic (i.e., the E-039 RICH edge is not a
   pricing artifact) — threshold stated here ex-ante, do not tune it.
4. Fail-closed on network/size problems per the E-035 precedent: record the
   exact command, error, and stop; no substitute data source, no fabrication.
5. Register `E-040` (0 trials, no K) linking H-014; update H-014's
   Experiment(s) column; run both docs checkers.

ACCEPTANCE CRITERIA (binary):
- [ ] ≥6 day×symbol pairs processed per symbol OR a fail-closed record exists
- [ ] Every extracted leg records strike, delta, mid, spread, and the matched
      synthetic price from the E-039 methodology (same formulas/haircut=0)
- [ ] `stage2_feasibility.json` exists with per-leg ratios by IVP quartile and
      the ex-ante PASS/FAIL verdict field
- [ ] E-040 row + H-014 link updated; `check_ledger_consistency.py` and
      `check_doc_metadata.py` both pass
- [ ] Diff contains only permitted files (`git diff --stat` in report)

## T2 — Chain-history acquisition options report (no purchase)

Task: one-page comparison (coverage window, granularity, delivery format,
price, license fit) of Tardis.dev vs Amberdata vs Laevitas for FULL Deribit
BTC/ETH option-chain history, ending in a recommendation. Report only —
**the user decides any purchase.** Record it in the T1 results directory as
`chain_data_options.md`.

ACCEPTANCE CRITERIA (binary):
- [ ] All three vendors covered with source URLs + retrieval dates
- [ ] Explicit "recommended / why / monthly cost" line
- [ ] No credentials created, nothing purchased

## T1-R — Authorized bounded rerun of E-040 (register as E-041)

USER AUTHORIZED 2026-07-13 ("是, 授權有界重跑") after Claude review
`tasks/2026-07-13-e040-stage2-claude-review.md`. Still a 0-trial probe, no K.

Required behavior — identical to T1 (same deterministic 12-pair sample, same
legs, same ex-ante 0.8 verdict threshold, same fail-closed discipline) with
EXACTLY three changes, all from the review findings, none tunable:
1. Replace the Content-Length pre-check with a **bytes-read guard** at the
   same fixed 2 GiB (streaming stops at the 08:00 snapshot, so reads are ~⅓
   of file size; do not raise the limit).
2. Synthetic denominator: sample **hourly DVOL** (`dvol_deribit_{btc,eth}_1h`
   in `external_observations`, `published_at` as-of ≤ the day's 08:00 UTC
   snapshot) instead of the E-039 daily close. If DB is unreachable, fail
   closed — do not fall back to daily DVOL silently; record it.
3. Split the status fields: `probe_status` (COMPLETE | FAIL_CLOSED) separate
   from `verdict.status` (PASS | FAIL, only when `evaluated=true`).

Register the run as `E-041` (supersedes E-040's fail-closed attempt; E-040
row stays immutable), link from H-014, artifacts in a NEW
`results/stage2_probe_<date>_f_vol_regime_opt_r1/` directory. T1's acceptance
criteria apply unchanged plus:
- [ ] E-040 artifacts untouched
- [ ] The three changes above are the ONLY behavior deltas vs T1 (state this
      in the report with the diff)

## T3 — NOT AUTHORIZED: options backtest MVP (listed for visibility only)

Single-leg expiry-settlement backtest with coin-denominated accounting is the
Stage-3 prerequisite. It is a business-rule change (new DOMAIN_RULES area):
requires Stage-2 PASS, a Change Manifest + ADR draft, Claude review, and
explicit user sign-off BEFORE any code. Do not start under this task file.

## Report and review protocol

On completion of T1+T2, Codex reports using the AGENTS.md end-of-task block
(implementation summary → deployment readiness) and hands off to Claude.
Claude reviews per `docs/REVIEW_QUESTIONS.md` + `docs/CRITIQUE_PROTOCOL.md`
with anchors in `docs/INVARIANTS.md`; checks I13 (no hidden trials — T1 must
contain zero parameter selection beyond the data-given stratification) and the
F26 class (all timestamps from the sampled snapshot, no lookahead). Claude
then drafts the Stage-3 authorization ask for the user only if T1's verdict
is PASS.

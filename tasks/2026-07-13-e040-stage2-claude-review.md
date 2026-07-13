---
status: current
type: review
owner: claude
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Claude Review: E-040 Stage-2 calibration (F-VOL-REGIME-OPT) — 2026-07-13

Scope: Codex deliverables under
`tasks/2026-07-13-f-vol-regime-opt-stage2-codex-tasks.md` (T1+T2).
Verdict: **ACCEPTED as fail-closed (T1) and complete (T2). Stage-2 itself did
NOT pass — verdict `evaluated=false` — so Stage 3 stays blocked.**

## Independently verified (not taken from the report)

- Unit test: `tests/unit/test_f_vol_regime_opt_stage2.py` — 1 passed (re-run).
- Ledger consistency + doc metadata checkers — pass (re-run; 15 H / 40 E / 14 K).
- `per_day_legs.csv`: 35 rows, 7 day×symbol pairs; **0 rows with
  `quote_local_timestamp > snapshot_timestamp`** (no lookahead, F26-class
  clean); all required leg fields populated; actual deltas near targets
  (0.249/−0.214/−0.093 …).
- Script review: as-of snapshot logic correct (monotonicity guard; keeps only
  rows ≤ snapshot batch); deterministic bottom-3/top-3 IVP sampling with no
  selection freedom (I13 clean); synthetic price imports E-039's `bs` — no
  formula drift; fail-closed path records exact URL/Content-Length, no
  substitute source.
- Diff scope: only permitted files; E-039 artifacts untouched; both Codex
  handoffs present.
- T1 acceptance boxes: all pass via the fail-closed branch. T2 boxes: all pass.

## Findings (none blocking acceptance)

1. **MINOR — DVOL timestamp mismatch:** synthetic uses the E-039 *daily close*
   DVOL while real quotes are at 08:00 UTC (~16 h gap) — adds noise to every
   ratio. Retry should sample `dvol_deribit_*_1h` as-of 08:00 instead.
2. **MINOR — status semantics:** on a completed run `stage2_status` would copy
   the pricing verdict (PASS/FAIL), conflating probe completion with pricing.
   Split the fields on retry. (This run's `FAIL_CLOSED` is unambiguous.)
3. **ECONOMICS (for Stage-3 design):** partial ratios say real 25Δ call ≈
   0.82× synthetic (Q4 mean 0.87) — hovering at the 0.8 bar — and the
   purchased 10Δ put wing costs ~1.7× synthetic. E-039's RICH-bucket edge is
   therefore overstated at the level; any Stage-3 net-credit computation must
   use real wing prices, not BS-on-DVOL.
4. **Guard design:** the 2 GiB Content-Length pre-check is stricter than
   needed — streaming stops at the 08:00 snapshot, so actual reads were only
   ~1/3 of file size (e.g. 325 MB of 995 MB). A bytes-read-only guard would
   likely have completed 2024-03-01 (3.05 GB × ⅓ ≈ 1.0 GiB < 2 GiB).
5. **Repo hygiene:** `research/probes/` and `results/` are gitignored; the
   registry references those paths. The eventual PR needs explicit force-adds
   or the record dangles.

## Recommendation to the user (decision required) — AUTHORIZED

User authorized the bounded rerun 2026-07-13; scoped as T1-R / E-041 in
`tasks/2026-07-13-f-vol-regime-opt-stage2-codex-tasks.md`.

Authorize a bounded E-040 rerun (still a 0-trial probe, no K): same
deterministic 12-pair sample, (a) replace the Content-Length pre-check with a
bytes-read guard at 2 GiB (finding 4), (b) synthetic denominator from hourly
DVOL as-of 08:00 (finding 1), (c) split status fields (finding 2). No
purchase needed for this step; the Tardis Business quote (T2 recommendation,
$3,000/mo) is only needed later for Stage-3 full-history backtests.

---
status: archived
type: plan
owner: ai
created: 2026-07-04
last_reviewed: 2026-07-04
expires: 2026-08-04
superseded_by: null
---

# Codex Dispatch: H-009 Retry-1 (breadth-restored checkpoint rerun)

Pre-registration (read first, it is binding):
`docs/superpowers/specs/2026-07-04-h009-retry1-preregistration.md`.

Precondition: funding backfill for the 4 missing symbols must have run
successfully (the user runs it in a networked terminal — Codex sandbox
network is blocked per E-035):

```
python scripts/market_data/backfill_universe_funding.py --start 2024-01-01 --end 2026-06-17
```

```text
Read AGENTS.md first, then execute:

Task: Rerun the F-FUNDING-XS-DISPERSION Stage-3 checkpoint (E-031 setup) on
the breadth-restored 32-symbol PIT universe with family n_trials=8, per the
binding pre-registration spec.
Strategy/spec source:
docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md +
docs/superpowers/specs/2026-07-04-h009-retry1-preregistration.md.
Required behavior: identical grid {lookback_days:[7,14], quantile:[0.20,0.30]}
= 4 combos, identical window 2024-01-01→2026-06-17, identical fold-refit
WF/CPCV harness and leak test as E-031 — the ONLY changes are (a) the symbol
set now includes CC/FIL/M/SHIB-USDT-SWAP if their backfilled funding passes
the same Stage-2 coverage/stale thresholds, and (b) caller-declared family
n_trials=8. Verify the backfill actually landed (Stage-2 probe or coverage
query) before running; if any of the 4 still fails coverage, run with
whatever subset passes and report the exclusion explicitly — do not relax
thresholds.

PERMITTED FILES (only edit these):
- scripts/run_funding_xs_dispersion_checkpoint.py (n_trials/universe wiring
  only; no harness redesign)
- backtesting/funding_xs_dispersion_backtest.py (only if symbol-set plumbing
  requires it)
- tests/unit/ (regression test updates for the above only)
- docs/EXPERIMENT_REGISTRY.md (new E-row)
- docs/HYPOTHESIS_LEDGER.md (H-009 row update: retry-1 result, n_trials=8,
  K 1/2 burned)
- results/ (new run artifacts only)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ , src/okx_quant/signals/ , src/okx_quant/risk/ ,
  src/okx_quant/portfolio/ , src/okx_quant/execution/ , config/risk.yaml
- research/ ; any existing results/** artifact (E-031 artifacts stay intact)
- backtesting/xs_momentum_backtest.py
- the grid, window, harness params, or thresholds (pre-registered; changing
  any of them voids the retry)

SCOPE LIMIT: fix only what is described; no adjacent refactoring.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run: pytest tests/unit -k "funding_xs" -q and paste the tail; then the
  checkpoint command and paste checkpoint1_auto.json contents.
- Update docs per the AGENTS.md docs-update matrix.
- Do not commit unless the user asks.

ACCEPTANCE CRITERIA (binary):
- [ ] Run used ≥29 symbols (28 + at least one restored) or explicitly reports
      which of the 4 failed coverage and why.
- [ ] n_trials declared as 8 in the CPCV artifact with provenance label.
- [ ] Leak test passed; idealized_fill false; ct_val authoritative;
      path_returns retained.
- [ ] New E-row + H-009 ledger update recording K 1/2 regardless of outcome.
- [ ] Diff contains only permitted files; E-031 artifacts unmodified.
- [ ] Stop at checkpoint①: report DSR/PSR/WF/CPCV numbers, make NO
      promotion/refutation verdict — that is Claude/user review per the
      pre-committed decision rule.

REPORT: changed files, test tail, checkpoint numbers, assumptions made,
anything UNCONFIRMED or skipped.

Also read docs/ai/JUDGMENT_RUBRICS.md §2 (definition of done) and §5
(quality floor) before reporting completion.
```

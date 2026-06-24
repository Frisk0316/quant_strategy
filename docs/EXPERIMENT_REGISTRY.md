---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Experiment Registry

Append-only log of experiments and research runs. Its job is to make results
**reproducible** and to keep an honest **trial count** (R6.3): every search over
parameters or strategies is a trial that inflates the best observed result.

Every experiment must link a hypothesis in [[HYPOTHESIS_LEDGER]]. Do not delete
rows — supersede them. A refuted or disappointing result is as valuable as a
positive one and must stay in the log.

## Registry

| ID | Date | Hypothesis | Setup (data range, config, seed) | Trials | Artifact / run_id | Outcome | Notes |
|---|---|---|---|---|---|---|---|
| E-000 | 2026-06-12 | H-000 | _example: BTC-SWAP 1H, config/strategies.yaml@<sha>, seed=0_ | 1 | _results/<run_id>_ | template | replace; do not delete |
| E-001 | 2026-06-17 | H-001 | BTC-USDT-SWAP MA crossover on synthetic 1H parquet fixture in `tests/unit/test_multi_venue_convergence.py`; two fixed venue configs (`okx`, `binance`); `instrument_specs` overrides; no DB/network; seed N/A | 1 | `tests/unit/test_multi_venue_convergence.py::test_swap_ct_val_cancels_under_notional_sizing` | supported | Unit golden case passed: 1 passed; validates convergence only, not deployability. |
| E-002 | 2026-06-23 | H-002 | XS momentum, point-in-time top-30 Binance USDT-perp universe, 1m-derived daily closes; config `config/strategies.yaml::xs_momentum` (pending) + `config/universe.yaml` (pending); grid over `{lookback, skip, quantile, vol_target, top_n}` via `scan_xs_momentum` (Phase C2); WF/CPCV via `backtesting/{walk_forward,cpcv}.py` | TBD (honest count from C2) | pending — `results/xs_momentum_wf_<date>.json`, `results/xs_momentum_cpcv_<date>.json` (Phase C3) | planned (not yet run) | Registered at plan time per [[HYPOTHESIS_LEDGER]] linkage; not evidence until the WF/CPCV artifacts exist and DSR/PSR are reported. Supersede this row with the run-time entry when produced. |
| E-003 | 2026-06-23 | H-002 | XS momentum validation on Binance USDT-perp canonical DB: 27 non-stable symbols, start floor 2024-01-01, common validation end 2026-06-16T16:00Z, `1H` bars aggregated from canonical `1m` with `source_primary='binance'`, funding from `funding_rates source='binance'`, `config/universe.yaml` warmup/deny-list, BTC market-close proxy, WF 365/90 and CPCV N=6/k=2/embargo=2%/purge=1 | 8 | `results/xs_momentum_validation_20260623/summary.json` | invalid / superseded | Superseded by E-004/E-005. Original WF combined OOS Sharpe 2.879, CPCV OOS Sharpe 1.592, DSR 1.000, PSR 0.992, and `promotion_gate_passed:true` were built on a lookahead leak; `scripts/recheck_dsr.py` also flags the stored CPCV DSR as untrusted because `DSR > PSR(0)`. Do not cite as evidence. `ETH-USDT-SWAP` was skipped by the source-scoped validation query. |

| E-004 | 2026-06-24 | H-002 | Same XS momentum setup as E-003, with daily target weights shifted one full day before intraday expansion; 27 Binance USDT-perp symbols; WF 365/90 and CPCV N=6/k=2/embargo=2%/purge=1 | 8 | `results/xs_momentum_validation_20260624_leakfix/summary.json` | refuted | Supersedes E-003: leak-free rerun had WF OOS Sharpe 0.8825, CPCV OOS Sharpe 0.5577, PSR 0.7961. Reported DSR 1.0 later proved to be a harness defect and is flagged untrusted by `scripts/recheck_dsr.py` (`DSR > PSR(0)`), so promotion remained blocked. |
| E-005 | 2026-06-24 | H-002 | Same XS momentum leak-free setup as E-004, with portfolio book-vol gross sizing and max gross leverage 2.0; DB-side Binance 1m-to-1H aggregation; fixed DSR basis and honest `n_trials=8` | 8 | `results/xs_momentum_validation_20260624_portfoliovol/summary.json` | refuted | Correctness-only sizing rerun: WF OOS Sharpe 1.2412, CPCV OOS Sharpe 0.6027, DSR 0.7823, PSR 0.8234, `promotion_gate_passed:false`. `scripts/recheck_dsr.py` confirms the saved DSR passes `DSR <= PSR(0)` but cannot independently recompute it because raw path returns were not saved. PSR remains below 0.95; no promotion support. |

## Required fields

- **Setup** must be enough to reproduce: instrument, date range, config
  reference (path + commit or hash), seed, and data source (DB vs parquet).
- **Trials** is the cumulative count of parameter/strategy combinations searched
  to produce this result. Hidden trials are a leakage bug (I13).
- **Artifact** points to the reproducible output (a `results/` run_id or file).
  Idealized-fill / in-sample artifacts must be labelled as such (R7.1).
- **Outcome** states the measured result and whether it supported the hypothesis.

## Rules

- Append, never rewrite. To correct an entry, add a new row and note "supersedes
  E-NNN".
- An experiment with no reproducible artifact is anecdote, not evidence.
- Promotion requires walk-forward / CPCV evidence and the
  `docs/ai_collaboration.md` gates, not a single positive row here.

Related: [[HYPOTHESIS_LEDGER]] · [[GOLDEN_CASES]] · `research/strategy_synthesis.md`.

---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Invariants

Properties that must hold for the system to be correct. Each invariant should be
**checkable** — ideally by a test, otherwise by an explicit review step. When you
add or change a business rule in [[DOMAIN_RULES]], add or update the matching
invariant here and point to the test that enforces it.

Columns: **ID**, the invariant, the [[DOMAIN_RULES]] rule it derives from, and
the enforcing test or check (or `REVIEW` if only human-checkable today).

| ID | Invariant | Rule | Enforced by |
|---|---|---|---|
| I1 | SWAP PnL scales by `ct_val`; a ct_val change moves PnL proportionally | R1.1 | `tests/unit/` PnL accounting tests |
| I2 | Closing a position moves unrealized → realized exactly, net of fees/funding | R1.3 | replay/portfolio tests |
| I3 | Maker-only strategy is never charged taker fees | R2.1 | execution/fee tests |
| I4 | Funding sign: long pays positive funding, receives negative | R3.1 | funding cashflow tests, `tests/unit/test_xs_momentum_backtest.py::test_short_receives_positive_funding` |
| I5 | Funding settlement count > 0 over a full settlement window | R3.2 | ADR-0005 Gate 4 |
| I6 | No exposure-increasing order exceeds configured per-instrument / per-portfolio caps | R4.3 | risk tests |
| I7 | Reduce-only orders cannot increase absolute exposure; fat-finger bypass is allowed only up to current position notional | R4.2 | ADR-0006, `tests/unit/test_risk_guard.py` |
| I8 | A fill at bar *t* uses only data available at or before *t* | R5.3 | replay oracle/integration tests |
| I9 | No orphan or phantom positions after partial fills or pairs exits | R5.2 | `tests/unit/test_backtesting.py`, integration |
| I10 | Terminal positions are liquidated (or run flagged bankrupt) | R5.2 | ADR-0005 Gate 1 |
| I11 | Data coverage ≥ 80% before a dated replay starts | R6.2 | ADR-0005 Gate 3 |
| I12 | DB-backed source parity agrees on timestamped close values for the same instrument/range; OHLCV structure is checked separately | R6.2 | `validate-data`, `tests/unit/test_differential_validation.py` |
| I13 | Trial count is recorded; no hidden trials in selection | R6.3 | `tests/unit/test_xs_momentum_backtest.py::test_scan_xs_momentum_records_honest_n_trials`, differential validation |
| I14 | `naive_backtest` / `in_sample` / idealized output never used as promotion evidence | R7.1 | REVIEW, gate logic |
| I15 | No live/shadow/demo claim without all gates passed + human approval | R7.2 | `docs/ai_collaboration.md`, REVIEW |
| I16 | A SWAP run's authoritative `ct_val` source matches the run execution venue | R1.4, R7.2 | `tests/unit/test_replay_ct_val_resolution.py`, `tests/unit/test_replay_ct_val_provenance_tag.py`, `tests/unit/test_differential_validation.py`, `tests/unit/test_multi_venue_convergence.py` |
| I17 | `strategy_fill` artifacts are marked `idealized_fill` and never used as promotion evidence | R5.4, R7.1 | `tests/unit/test_backtesting.py`, API warning tests |
| I18 | Submitted strategy-order fill counts exclude `terminal_liquidation` fills | R5.4 | `tests/unit/test_backtesting.py` |
| I19 | A venue-tagged run loads candles only from that venue's provenance-tagged canonical series; source-less parquet or another venue cannot substitute missing bars | R6.4 | `tests/unit/test_data_loader.py` |
| I20 | Universe membership is point-in-time: no symbol is eligible before listing plus warmup, and ended candle history is not forward-filled into later eligibility | R6.1 | `tests/unit/test_universe_membership.py` |
| I21 | DSR is computed on the same per-observation return basis as PSR(0), and `DSR <= PSR(0)` for the same series when `n_trials > 1` | R7.4 | `tests/unit/test_dsr.py`, `tests/unit/test_cpcv.py` |
| I22 | XS momentum portfolio-vol targeting sizes gross from estimated book volatility and enforces the max-gross cap | R4.4 | `tests/unit/test_xs_momentum.py::test_vol_target_uses_portfolio_book_vol_and_cap` |
| I23 | Candidate CPCV `n_trials` must be at least the family-cumulative trial count recorded in `docs/EXPERIMENT_REGISTRY.md`; a per-run grid count alone is a violation | R6.3, R7.4 | `tests/unit/test_xs_momentum_backtest.py::test_scan_adds_prior_family_trials_to_n_trials`; review of `backtesting.replay.run_replay_validations` caller-provided `n_trials` passthrough |
| I24 | WF/CPCV evidence must select parameters inside each train fold and evaluate only on the held-out test fold; slicing one full-sample-selected return series is in-sample evidence | R6.3, R7.4 | `tests/unit/test_pipeline_refit.py`, `tests/unit/test_pipeline_batch1_checkpoint_runner.py` |
| I25 | Future CPCV artifacts must retain raw path returns, or the combined return series when path assembly is unavailable, plus periods/lengths and n_trials provenance so DSR can be recomputed offline | R6.3, R7.4 | `tests/unit/test_cpcv.py::test_cpcv_emits_path_returns_that_recompute_dsr`, `tests/unit/test_pipeline_batch1_contracts.py::test_pipeline_refit_summary_carries_cpcv_retention_fields` |

## Usage

- Adding a rule → add an invariant. If it is `REVIEW`-only, note it as a gap and
  consider a follow-up test in [[HYPOTHESIS_LEDGER]] or `docs/KNOWN_ISSUES.md`.
- A failing invariant is a release blocker, not a warning.
- When a Change Manifest lists affected invariants, cite these IDs.

Related: [[DOMAIN_RULES]] · [[GOLDEN_CASES]] · [[FAILURE_MODES]].

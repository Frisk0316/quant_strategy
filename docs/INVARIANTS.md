---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-07-15
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
| I20 | Universe membership is point-in-time: no symbol is eligible before listing plus warmup, ended candle history is not forward-filled into later eligibility, and timestamp storage precision does not change membership output | R6.1, R6.2 | `tests/unit/test_universe_membership.py` |
| I21 | DSR is computed on the same per-observation return basis as PSR(0), and `DSR <= PSR(0)` for the same series when `n_trials > 1` | R7.4 | `tests/unit/test_dsr.py`, `tests/unit/test_cpcv.py` |
| I22 | XS momentum portfolio-vol targeting sizes gross from estimated book volatility and enforces the max-gross cap | R4.4 | `tests/unit/test_xs_momentum.py::test_vol_target_uses_portfolio_book_vol_and_cap` |
| I23 | Candidate CPCV `n_trials` must be at least the family-cumulative trial count recorded in `docs/EXPERIMENT_REGISTRY.md`; a per-run grid count alone is a violation | R6.3, R7.4 | `tests/unit/test_xs_momentum_backtest.py::test_scan_adds_prior_family_trials_to_n_trials`; review of `backtesting.replay.run_replay_validations` caller-provided `n_trials` passthrough |
| I24 | WF/CPCV evidence must select parameters inside each train fold and evaluate only on the held-out test fold; slicing one full-sample-selected return series is in-sample evidence | R6.3, R7.4 | `tests/unit/test_pipeline_refit.py`, `tests/unit/test_pipeline_batch1_checkpoint_runner.py` |
| I25 | Future CPCV artifacts must retain raw path returns, or the combined return series when path assembly is unavailable, plus periods/lengths and n_trials provenance so DSR can be recomputed offline | R6.3, R7.4 | `tests/unit/test_cpcv.py::test_cpcv_emits_path_returns_that_recompute_dsr`, `tests/unit/test_pipeline_batch1_contracts.py::test_pipeline_refit_summary_carries_cpcv_retention_fields` |
| I26 | Stage 3 checkpoint summaries entering checkpoint review must have a machine-readable `checkpoint1_auto.json` from `scripts/run_pipeline_checkpoint1_check.py` with `checkpoint1_auto_status != FAIL`; the summary and CPCV `n_trials` must reconcile to `docs/EXPERIMENT_REGISTRY.md` for that artifact/family, including feedback-spawned ideas once they are ledgered. `PASS` is advisory only and does not remove the required human review items. | R6.3, R7.4 | `tests/unit/test_pipeline_checkpoint1_check.py` |
| I27 | Automated idea ingestion must read ledger family status and family-cumulative `n_trials` before minting a family; if a candidate signal has `abs(corr) >= HARD_ASSIGN_CORR` to any supplied occupied/reference family signal, it must ASSIGN to that family and inherit its trial/K budget rather than MINT. MINT is provisional and remains subject to human mechanism-novelty review. A family's retry budget `K_used` (limit `K_limit=2`) is read from the EXPERIMENT_REGISTRY *Family K-budget* table and is distinct from `n_trials`; the two must never be conflated, and a family at `K_used==K_limit` is shelved/escalated rather than retried. | R6.3, R7.4 | `tests/unit/test_pipeline_family_minting.py` |
| I28 | Automated B-taxonomy idea generation must use `docs/HYPOTHESIS_LEDGER.md` `Status` as the authoritative occupied-family verdict while `docs/EXPERIMENT_REGISTRY.md` remains the `n_trials`/K source. Refuted, shelved, or inconclusive occupied families without an explicit `twist`/`轉折` marker are skipped (`inconclusive_no_twist` for inconclusive; `refuted_no_twist` for refuted/shelved), and overlay families without deterministic base-family plumbing are skipped instead of drafted as standalone alpha. | R6.3, R7.4 | `tests/unit/test_pipeline_idea_generator.py` |
| I29 | Pipeline orchestration state (`orchestrator_state.json`) must be append-only per candidate: every status advance appends `status_history`, missing hypothesis IDs fail closed before state is written, unimplemented Stage2/Stage3 families including `family_id == "NEW"` move to `awaiting_stage2_implementation` or `awaiting_stage3_implementation` instead of being silently backtested, legacy Stage3 runners refuse non-legacy `batch_id` values, and the driver must not write `docs/HYPOTHESIS_LEDGER.md` or `docs/EXPERIMENT_REGISTRY.md`. | R6.3, R7.4 | `tests/unit/test_pipeline_orchestrator.py`, `tests/unit/test_pipeline_stage2_registry.py`, `tests/unit/test_pipeline_stage3_registry.py` |
| I30 | Pipeline feedback tags are advisory ranking inputs only: they may lower rank and mark `feedback_spawned`, but they must not change eligibility, cap, Stage2/Stage3 gates, checkpoint thresholds, or ledger writes. Any feedback-spawned candidate that reaches checkpoint review must reconcile to family-cumulative `n_trials` like any other candidate. | R6.3, R7.4 | `tests/unit/test_pipeline_idea_generator.py`, `tests/unit/test_pipeline_orchestrator.py`, `tests/unit/test_pipeline_checkpoint1_check.py` |
| I31 | Turtle S1/S2 reference semantics stay isolated to the research-only Turtle runner: shifted rolling thresholds, strict cash gate, S1 skip-after-win, and no forced end liquidation must not leak into replay/live semantics | R5.5, R7.1 | `tests/unit/test_turtle_backtest.py`, `tests/unit/test_routes_backtest_turtle.py` |
| I32 | Every caller-controlled artifact identifier is a safe single path component, and its resolved read/write target remains inside the intended artifact root | — | `tests/unit/test_artifact_rows.py`, `tests/unit/test_backtesting.py`, `tests/unit/test_differential_validation.py`, API/CLI regressions |
| I33 | An unknown execution venue fails closed; it is never silently substituted with Binance or another venue | R6.4 | `tests/unit/test_backtest_request_exchange.py` |
| I34 | Numeric `ct_val` validation rejects non-finite/non-positive values and values above `1e7` at every explicit input point (fill metadata, replay caller specs, DB/config paths); a missing fill value may reuse validated position state, while an invalid or incomplete explicit instrument spec must raise before entering positions, PnL, or an authoritative provenance label | R1.5 | `tests/unit/test_sizing.py`, `tests/unit/test_position_pnl_accounting.py`, `tests/unit/test_backtesting.py`, `tests/unit/test_replay_ct_val_resolution.py` |
| I35 | Both supported FastAPI app factories expose the documented Manual and Progress routes | — | `tests/unit/test_routes_manual.py`, `tests/unit/test_routes_progress.py` |
| I36 | Progress file reads serve only existing markdown paths explicitly listed in `config/workstreams.yaml` and resolved inside the repository | — | `tests/unit/test_routes_progress.py::test_progress_route_serves_only_configured_files` |
| I37 | A research artifact that claims t+1 execution must delay every signal-dependent return component, including turnover cost, until that execution point | R5.3, R6.1 | Known gap: E-037 spot-check; `docs/KNOWN_ISSUES.md` |
| I38 | Governance checks fail closed: H↔E links agree in both directions, only an explicit per-ID `reserved` annotation exempts a missing experiment, valid Markdown table spacing cannot hide rows, and every non-exempt task document has non-empty lifecycle metadata | — | `tests/unit/test_ledger_consistency.py`, `tests/unit/test_doc_metadata_tasks.py` |
| I39 | Coin-denominated options PnL settles on official Deribit delivery prices, allows bounded-coin-loss structures only, and every daily mark records its source. ADR-0011 additionally rejects naked short-put intents before fill handling, caps each symbol at 1.0 open unit, and journals chain failures/rejections without aborting the sibling currency cycle. | R8.1–R8.7 | `tests/unit/test_h014_options_accounting.py`, `tests/unit/test_h014_shadow.py` |
| I40 | H-014 shadow signals delegate to the research `build_series` definition, use hourly DVOL only after F26 `published_at`, align canonical closes to the research 08:00 UTC day, require the exact prior common day, and expose no private/order method. | R6.1, R8.7 | `tests/unit/test_h014_shadow.py`; five-day real-DB parity check |
| I41 | Funding settlement rows may be canonicalized to their nearest hourly boundary only when source jitter is at most one second; exact timestamp equality must not manufacture gaps, and larger offsets fail closed rather than being rounded into a valid event. | R6.1 | `tests/unit/test_xvenue_funding_spread_probe.py` |
| I42 | A quantitative family-distinctness check must fail closed when any required candidate/reference correlation is undefined because observations are insufficient or either series has zero variance; undefined is never equivalent to zero correlation. | R6.3 | `tests/unit/test_xvenue_funding_spread_probe.py` |
| I43 | A funding proxy that claims next-settlement execution must verify every adjacent evaluated event is exactly one contractual interval apart; missing intervals fail the cost gate instead of being compressed into a false t+1 transition. | R6.1, R6.3 | `tests/unit/test_xvenue_funding_spread_probe.py` |
| I44 | Inverse-perpetual research PnL uses the exact 1/P formula in coin, converts to USD at the same-bar venue-scoped mark for pair aggregation, and no Stage-3 grid may run before a hand-computed golden inverse-perp cycle test (entry, funding interval, basis move, exit, both cost scenarios) is green | R9.1–R9.5 | `tests/unit/test_h021_inverse_perp_accounting.py` (to land with the Stage-3 runner; REVIEW until then) |

## Usage

- Adding a rule → add an invariant. If it is `REVIEW`-only, note it as a gap and
  consider a follow-up test in [[HYPOTHESIS_LEDGER]] or `docs/KNOWN_ISSUES.md`.
- A failing invariant is a release blocker, not a warning.
- When a Change Manifest lists affected invariants, cite these IDs.

Related: [[DOMAIN_RULES]] · [[GOLDEN_CASES]] · [[FAILURE_MODES]].

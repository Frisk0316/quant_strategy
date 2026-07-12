---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Failure Modes

Catalogue of known ways this system produces **wrong-but-plausible** results —
the bugs that pass tests and look fine on a chart but corrupt money, risk, or
research conclusions. Every new bug *class* discovered should be added here with
its detection and the invariant/test that now guards it.

This is the inverted view of [[INVARIANTS]]: invariants say what must hold;
failure modes say how it silently breaks.

## Catalogue

| ID | Failure mode | Symptom | Detection / guard | Rule |
|---|---|---|---|---|
| F1 | Missing `ct_val` on SWAP PnL | PnL off by the contract multiplier (e.g. 100x) | I1 PnL tests with ct_val != 1 | R1.1 |
| F2 | Funding sign inverted | Strategy PnL flips sign vs. expectation | I4 funding tests | R3.1 |
| F3 | Funding window too short | Funding income understated, settlement count low | I5 Gate 4 | R3.2 |
| F4 | Lookahead / leakage | In-sample looks great, out-of-sample collapses | I8 oracle tests, review | R5.3, R6.1 |
| F5 | Hidden trial count | Best result is overfit; not reproducible | I13, differential validation | R6.3 |
| F6 | Orphan hedge / phantom position | Open leg after exit; phantom risk | I9 backtesting tests | R5.2 |
| F7 | Terminal position leak | Unrealized PnL excluded; results look better | I10 Gate 1 | R5.2 |
| F8 | Insufficient data coverage | Metrics computed on sparse data | I11 Gate 3 | R6.2 |
| F9 | DB/parquet mismatch | Different results from "same" data | I12 validate-data | R6.2 |
| F10 | Idealized-fill treated as evidence | Promotion on a best-case upper bound | I14, review | R7.1 |
| F11 | No-fill replay | Flat equity curve, run completes "clean" | Gate 2 fill-rate warning | R5.1 |
| F12 | Maker charged taker fees | Costs overstated, edge hidden | I3 fee tests | R2.1 |
| F13 | Stale doc treated as current | Implementing target behavior as if it exists | DOC_LIFECYCLE status check | — |
| F14 | Chat memory as source of truth | Strategy drift, untracked assumption | Read config/research, not memory | — |
| F15 | Close-flattened artifact OHLC treated as canonical OHLC | DB parity compares the right exchange but fails on O/H/L or volume even though every close matches | Close-only `db_parity` regression plus artifact-level OHLCV structural checks | R6.2, R7.2 |
| F16 | Reduce-only close blocked by entry fat-finger cap | Strategy remains in-position after a valid exit signal; later entry/re-entry behavior is distorted | `tests/unit/test_risk_guard.py::test_reduce_only_close_can_exceed_fat_finger_cap_up_to_current_position` | R4.2 |
| F17 | Queue-fraction lot rounding creates zero-fill exits | A small reduce-only close order repeatedly touches the L1 book but `remaining_sz * queue_fill_fraction` rounds below `lotSz`/`minSz`, so no fill row is emitted and the strategy stays in-position until cancellation or terminal liquidation | Gate 2 fill-rate warning, `orders.csv`/`fills.csv`/`cancel_log.csv` audit, and replay lot-rounding tests in `tests/unit/test_execution_flow.py` | R5.1, R5.2 |
| F18 | Terminal liquidation counted as submitted-order fill | `real_fill_count`/`orders_filled_count` include end-of-run liquidation rows whose `cl_ord_id` was never in `orders.csv`, slightly inflating fill-rate interpretation | Cross-check `fills.csv` `cl_ord_id` against `orders.csv` and `validation.terminal_liquidation_fill_count` | R5.1, R7.2 |
| F19 | Survivorship-biased universe membership | Delisted or newly listed symbols are treated as if they were tradable throughout history, inflating cross-sectional strategy results | I20 point-in-time membership tests and review of `data/universe/universe_membership.parquet` provenance | R6.1 |
| F20 | DSR unit/sample mismatch | Annualized Sharpe or overlapping CPCV paths are treated as thousands of independent per-bar observations, so DSR saturates to 1.0 even when PSR fails | I21 DSR/PSR invariant tests and CPCV `n_trials` checks | R7.4, R6.3 |
| F21 | Single-name vol proxy used for a market-neutral book target | A diversified long-short book realizes far below the intended vol target while appearing spec-compliant | I22 XS momentum portfolio-vol sizing test and artifact realized-vol review | R4.4 |
| F22 | Pseudo-OOS from full-sample parameter selection | WF/CPCV callback ignores the train fold, reuses one full-sample-selected return series, and reports in-sample selection as OOS evidence; CPCV paths may become identical or over-optimistic | I24 fold-refit tests and review of pipeline summary `validation_mode` / path dispersion | R6.3, R7.4 |
| F23 | Wrong verdict source or standalone overlay in B-taxonomy idea generation | A stale experiment outcome or taxonomy free text makes an occupied inconclusive/refuted family look eligible, or an overlay family is drafted as a standalone alpha, inflating trial/K-budget risk | I28 idea-generator verdict/overlay tests and review of `idea_batch.json` skipped reasons | R6.3, R7.4 |
| F24 | Timestamp precision drift in universe source parity | DB and parquet membership outputs represent the same calendar days but carry different `datetime64` units, breaking source-parity checks or downstream artifact comparisons | `tests/unit/test_universe_membership.py::test_build_membership_ignores_timestamp_storage_precision` and DB/parquet parity test | R6.2 |
| F25 | Artifact round-trip loses marker semantics | File-backed CSV fills/trades parse epoch `ts` as strings, or DB/file artifact symbol filtering runs before normalized marker construction, so chart marker fallback drops otherwise valid executions | `tests/unit/test_routes_backtest_turtle.py::test_turtle_csv_string_records_emit_execution_markers`; local artifact regression `test_existing_turtle_run_symbol_filtered_execution_marker_endpoint` is skip-gated when gitignored files are absent | R7.1 |
| F26 | Bucketed external aggregate published at bucket start | As-of joins can see up to one bucket of future DVOL or option-flow data while charts and gap scans look normal | Deribit hourly DVOL and option-flow tests assert `published_at = observed_at + 1h`; DB relabel scan checks no `_1h`/`optflow` rows publish at bucket start | R6.1 |
| F27 | Optional pre-step blocks primary action | A best-effort preparation step, such as external dataset refresh before export, hard-fails and prevents the actual DB-backed export/download even though usable data exists | `tests/unit/test_routes_data_export.py::test_refresh_external_datasets_skips_db_known_dataset_missing_from_yaml`, frontend `node --check`, and manual browser export check | R7.2 |
| F28 | Full-table coverage aggregation exceeds the UI timeout | Market Data Coverage reports `signal timed out` even though DB rows exist | `tests/unit/test_routes_data_delete.py::test_coverage_route_uses_instrument_bars_fast_path` requires per-dataset LATERAL aggregation over the existing external-observation index; real-DB timing check | R7.2 |
| F29 | Terminal private-WS authentication failure treated as reconnectable | Invalid demo credentials produce a connect/error loop and eventually trip the local WS reconnect breaker instead of exposing the OKX error once | `tests/unit/test_market_data_handler.py::test_private_auth_failure_does_not_reconnect_or_trip_breaker`; OKX login probe confirms error `60005 Invalid apiKey` | R7.2 |
| F30 | Unvalidated artifact identifier escapes the result root | A caller-controlled `run_id` or `validation_id` containing path separators writes or reads outside the intended result directory | Shared validate-and-resolve helper plus `test_artifact_rows.py`, API, writer, differential-validation and CLI regressions | — |
| F31 | Unknown execution venue silently normalizes to Binance | A typo selects plausible Binance data/specs instead of rejecting the request, invalidating venue provenance without an obvious error | `tests/unit/test_backtest_request_exchange.py` requires explicit unknown venue 400 before queueing | R6.4 |
| F32 | `ct_val` validation assumes multipliers are at most one or accepts non-finite values | Legitimate multiplier contracts are rejected while NaN can enter sizing/accounting and corrupt downstream values | `tests/unit/test_sizing.py` enforces finite `0 < ct_val <= 1e7`; ADR-0003 amendment | R1.2, R1.4, R1.5 |
| F33 | Parallel FastAPI app factories expose different UI routes | A feature passes direct-router tests and works under the trading engine but returns 404 from the RUNBOOK-recommended standalone server | `tests/unit/test_routes_manual.py::test_standalone_server_registers_manual_router` | — |
| F34 | Progress repo paths are sent through the frontend-only static mount | Every configured document exists, but clicking a card opens HTTP 404 | `tests/unit/test_routes_progress.py::test_progress_route_serves_only_configured_files` plus browser smoke | — |
| F35 | Documentation lifecycle frontmatter renders as manual prose | The manual opens but begins with internal `status`, owner, and review metadata | `tests/unit/test_routes_manual.py::test_chapter_markdown_returned` | — |
| F36 | Turnover cost is posted before the claimed execution lag | A day-t target affects day-t research returns through cost even though position PnL/funding begin at t+1, so leak checks can look green while return timing is inconsistent | E-037 manual leak-lag spot-check; known-gap review before reusing `oi_positioning_backtest.py` | R5.3, R6.1 |

## How to add a failure mode

When a bug is found that is a *new kind* of silent error:

1. Add a row: name, symptom, how it was/should be detected, and the rule it
   violates.
2. If no invariant guards it, add or strengthen one in [[INVARIANTS]] and, if
   possible, a regression test.
3. Note recurring operational failures in `docs/DEBUGGING_RUNBOOK.md` and
   durable backlog in `docs/KNOWN_ISSUES.md`.

Related: [[INVARIANTS]] · [[MENTAL_MODELS]] · [[CRITIQUE_PROTOCOL]] ·
`docs/KNOWN_ISSUES.md`.

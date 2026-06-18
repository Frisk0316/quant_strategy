# Session Handoff: DB parity close-only contract - 2026-06-18

## Implementation summary
Changed source-provenance `db_parity` to compare only timestamped `close` values
between replay `price_series.csv` and DB canonical candles. Added a regression
test for close-flattened artifacts whose DB O/H/L and volume differ while close
matches. Updated harness docs to record the close-only input contract and the
durable PASS evidence under `results/`.

## Diff scope
- Files added:
  - `tasks/2026-06-18-db-parity-close-only-context-handoff.md`
  - `tasks/2026-06-18-db-parity-close-only-session-handoff.md`
- Files changed:
  - `backtesting/differential_validation.py`
  - `tests/unit/test_differential_validation.py`
  - `docs/AI_HANDOFF.md`
  - `docs/CHANGELOG_AI.md`
  - `docs/CURRENT_STATE.md`
  - `docs/DATA_FLOW.md`
  - `docs/DOMAIN_RULES.md`
  - `docs/FAILURE_MODES.md`
  - `docs/INVARIANTS.md`
  - `docs/KNOWN_ISSUES.md`
  - `docs/RUNBOOK.md`
  - `docs/ai_collaboration.md`
  - `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`
  - `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/`
  - `results/adr0007_binance_btc_1h_db_pass_20260618/validation/adr0007_binance_btc_1h_db_pass_20260618_source_provenance/SUPERSEDED.md`
- Files deleted: none.

## Business-rule change?
- Yes. DOC_IMPACT rows reviewed: A5 backtesting and A9 validation/gates.
  Change Manifest updated at
  `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, no strategy assumption changed.
- config/: N/A, no runtime config changed.
- ADR: N/A, no new policy/schema decision; ADR-0005 and ADR-0007 reviewed.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- Direct DB close assertion - artifact rows 192, DB rows 192, matched rows 192,
  close mismatches 0.
- Red test:
  `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_uses_close_only_for_close_flattened_artifacts -q`
  - failed before implementation with `ohlcv_source_validation == "artifact_warn"`.
- Green slice:
  `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_compares_artifact_to_canonical_candles tests/unit/test_differential_validation.py::test_db_parity_uses_close_only_for_close_flattened_artifacts tests/unit/test_differential_validation.py::test_reference_replay_uses_db_canonical_prices_when_enabled -q`
  - 3 passed, 1 pytest cache permission warning.
- Teeth confirmation:
  `test_reference_replay_uses_db_canonical_prices_when_enabled` mutates only DB
  `close` and asserts `value_mismatches == 1`.
- Full target:
  `python -m pytest tests/unit/test_differential_validation.py -q` - 46 passed,
  1196 warnings.
- Temp source-provenance with output under `%TEMP%` and `--engines nautilus` -
  PASS for `source_data_validation`, `ct_val_provenance`, `db_parity`, and
  `ohlcv_source_validation`.
- Durable source-provenance with `--engines nautilus` and validation id
  `codex_close_only_db_parity_pass_20260618` - PASS and wrote
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`.
- Existing durable artifact gate:
  `python scripts/run_source_provenance_validation.py --validation-result results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`
  - PASS.
- Old FAIL artifact marker:
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/adr0007_binance_btc_1h_db_pass_20260618_source_provenance/SUPERSEDED.md`
  points reviewers to the durable PASS artifact.
- `python scripts/docs/check_doc_metadata.py` - passed with 12 pre-existing
  warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py --strict` with per-process
  `safe.directory` - passed: 13 changed files, no violations.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF
  normalization warnings only.

## Docs updated
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`,
  `docs/DATA_FLOW.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`,
  `docs/FAILURE_MODES.md`, `docs/KNOWN_ISSUES.md`, `docs/RUNBOOK.md`,
  `docs/ai_collaboration.md`, and the ADR-0007 Change Manifest.

## Known limitations / risks
- The older repo-local validation artifact still records the pre-fix FAIL and
  carries `SUPERSEDED.md`; it should not be cited as PASS.
- Durable source-provenance used `--engines nautilus` to verify source-data gate
  only; it is not a vectorbt/backtrader signal-quorum claim.
- `make` is not installed in this shell, so Makefile targets were verified by
  running their underlying scripts directly.

## Rollback plan
- Revert `backtesting/differential_validation.py`,
  `tests/unit/test_differential_validation.py`, the docs/handoff files, and the
  new `results/.../codex_close_only_db_parity_pass_20260618/` validation
  directory. No DB schema, config, strategy, risk, portfolio, execution, or
  pre-existing result artifact rollback is needed.

## Context Handoff
- See `tasks/2026-06-18-db-parity-close-only-context-handoff.md`.

## Questions for human review
- Should the next evidence run include vectorbt/backtrader, or is source-data
  PASS sufficient for this review slice?

## Next recommended task
- Ask Claude to review ADR-0007 P1 source-scoped DB parity PASS evidence.

## Human Learning Notes (required)
When an artifact is a derived representation, parity should compare the field
that actually preserves provenance. Here that is close; comparing flattened O/H/L
or quote-volume units created a false failure without adding source confidence.

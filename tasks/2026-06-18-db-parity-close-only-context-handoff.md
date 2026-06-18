# Context Handoff: DB parity close-only contract - 2026-06-18

## Goal (one sentence)
Fix source-provenance `db_parity` so replay `price_series.csv` proves DB source
agreement using timestamped close prices only.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: ADR-0007 P1 local branch with venue-scoped
  `db_parity` and `canonical_source_primary` already implemented.
- In-progress edits (files): `backtesting/differential_validation.py`,
  `tests/unit/test_differential_validation.py`, and source-provenance docs.
- What works right now: saved Binance run
  `adr0007_binance_btc_1h_db_pass_20260618` has 192/192 artifact closes matched
  to DB canonical Binance closes with zero close mismatches; durable
  source-provenance output under
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/`
  passed the source-data gate.
- What does not work / unfinished: the older repo-local validation artifact
  `adr0007_binance_btc_1h_db_pass_20260618_source_provenance` still records the
  pre-fix FAIL, carries `SUPERSEDED.md`, and should not be cited as PASS.

## Decisions made (and why)
- `db_parity` compares only `close` for `price_series.csv` because replay
  artifacts are close-flattened and volume is not in the same unit as DB
  canonical candles.
- O/H/L and volume remain artifact/data-quality checks, not DB source-provenance
  fields.
- No ADR-0002 schema change and no fake OHLC persistence.

## Open questions / unverified assumptions
- Whether Claude wants a vectorbt/backtrader rerun for signal-quorum evidence;
  this session's durable `nautilus` run proves source-data gate PASS only.

## Rules in play (preserve verbatim)
- Invariants touched: I12 - DB-backed source parity agrees on timestamped close
  values for the same instrument/range; OHLCV structure is checked separately.
- Domain rules touched: R6.2, R7.2.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`, DB schema, ADR-0002 result schema, existing
  `results/` artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/CURRENT_STATE.md`,
  `docs/AI_HANDOFF.md`, `docs/DOMAIN_RULES.md`, `docs/ai_collaboration.md`,
  ADR-0007.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Validation / Promotion
  Gates; `backtesting/differential_validation.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` for harness rules.

## Checks run
- Direct DB close assertion: artifact rows 192, DB rows 192, matched rows 192,
  close mismatches 0.
- Red test:
  `python -m pytest tests/unit/test_differential_validation.py::test_db_parity_uses_close_only_for_close_flattened_artifacts -q`
  failed before implementation with `ohlcv_source_validation == "artifact_warn"`.
- Green tests:
  `python -m pytest tests/unit/test_differential_validation.py -q` - 46 passed,
  1196 warnings.
- Temp source-provenance:
  `scripts/run_source_provenance_validation.py --run-id adr0007_binance_btc_1h_db_pass_20260618 --engines nautilus --validation-id codex_close_only_temp_validation --output-dir %TEMP%\codex_close_only_temp_validation`
  - PASS for source-data checks.
- Durable source-provenance:
  `scripts/run_source_provenance_validation.py --run-id adr0007_binance_btc_1h_db_pass_20260618 --engines nautilus --validation-id codex_close_only_db_parity_pass_20260618`
  - PASS for source-data checks and wrote
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`.
- Existing durable artifact gate:
  `scripts/run_source_provenance_validation.py --validation-result results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`
  - PASS.
- Old FAIL artifact marker:
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/adr0007_binance_btc_1h_db_pass_20260618_source_provenance/SUPERSEDED.md`
  points reviewers to the durable PASS artifact.
- Docs:
  `check_doc_metadata.py` - passed with 12 pre-existing warnings;
  `check_feature_map_links.py` - passed;
  `check_doc_impact.py --strict` with per-process safe.directory - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF
  normalization warnings only.

## Approvals
- Human approval needed / obtained: user explicitly asked Codex to implement
  Claude's close-only `db_parity` fix, then approved durable evidence under
  `results/<run_id>/validation/<validation_id>/`.

## Next action (single, concrete)
- Ask Claude to review the new durable source-data PASS artifact and decide
  whether vectorbt/backtrader signal-quorum evidence should be regenerated.

## Human Learning Notes
The 768 mismatches were exactly the misleading symptom: 192 bars times four
non-like-for-like fields. Close matched all rows, so the right fix was deleting
the bad comparisons, not manufacturing OHLC or relaxing tolerance.

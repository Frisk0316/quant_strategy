# Superseded Validation Artifact

This validation run is retained as historical diagnostic evidence only.

- Status: superseded
- Superseded by: `../codex_close_only_db_parity_pass_20260618/validation_result.json`
- Reason: this artifact was generated before `db_parity` was corrected to compare
  timestamped `close` values only for replay `price_series.csv` provenance. It
  failed on non-like-for-like flattened O/H/L and different-unit volume fields.
- Do not cite this artifact as ADR-0007 P1 source-provenance PASS evidence.

Use the superseding artifact for source-data evidence:

- `source_data_validation.status == "PASS"`
- `checks.ct_val_provenance.status == "PASS"`
- `checks.db_parity.status == "PASS"`
- `checks.db_parity.canonical_source_primary == "binance"`
- `ohlcv_source_validation == "db_parity_pass"`

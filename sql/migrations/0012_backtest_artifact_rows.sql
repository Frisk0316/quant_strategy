-- Derived read index for large backtest artifacts.
-- Source of truth remains backtest_artifacts.payload and result/file artifacts.

CREATE TABLE IF NOT EXISTS backtest_artifact_rows (
    run_id TEXT NOT NULL REFERENCES backtest_runs(run_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    inst_id TEXT NOT NULL DEFAULT '',
    ts_ms BIGINT,
    datetime_text TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, artifact_type, ordinal)
);

CREATE INDEX IF NOT EXISTS backtest_artifact_rows_symbol_ord_idx
    ON backtest_artifact_rows (run_id, artifact_type, inst_id, ordinal);

CREATE INDEX IF NOT EXISTS backtest_artifact_rows_symbol_ts_idx
    ON backtest_artifact_rows (run_id, artifact_type, inst_id, ts_ms);

CREATE INDEX IF NOT EXISTS backtest_artifact_rows_type_idx
    ON backtest_artifact_rows (run_id, artifact_type);

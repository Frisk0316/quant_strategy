CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id          TEXT PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategies      TEXT[] NOT NULL DEFAULT '{}',
    symbols         TEXT[] NOT NULL DEFAULT '{}',
    bar             TEXT NOT NULL DEFAULT '',
    start_date      DATE,
    end_date        DATE,
    artifact_dir    TEXT NOT NULL,
    total_return    FLOAT8,
    sharpe          FLOAT8,
    max_drawdown    FLOAT8,
    order_count     INT,
    real_fill_count INT,
    fill_rate       FLOAT8,
    bankrupt        BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS backtest_runs_created_at_idx ON backtest_runs (created_at DESC);

CREATE TABLE IF NOT EXISTS backtest_artifacts (
    run_id        TEXT NOT NULL REFERENCES backtest_runs(run_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_count     INT NOT NULL DEFAULT 0,
    payload       JSONB NOT NULL,
    PRIMARY KEY (run_id, artifact_type)
);

CREATE INDEX IF NOT EXISTS backtest_artifacts_run_id_idx ON backtest_artifacts (run_id);

import pytest
from pydantic import ValidationError

from crypto_alpha_lab.schemas import AlphaCandidate, BacktestConfig, PaperScoring


def test_paper_scoring_priority_score_penalizes_risk() -> None:
    scoring = PaperScoring(
        paper_id="ofi-2014",
        title="The Price Impact of Order Book Events",
        authors=("Cont", "Kukanov", "Stoikov"),
        year=2014,
        source_type="journal_article",
        url="https://example.com/ofi",
        doi="10.1093/jjfinec/nbt003",
        alpha_category="microstructure",
        expected_horizon="intraday",
        required_data=("l2_order_book", "trades"),
        evidence_quality=5,
        crypto_relevance=5,
        data_availability=4,
        implementation_fit=4,
        cost_awareness=4,
        novelty=3,
        leakage_risk=1,
        overfit_risk=2,
        known_failure_modes=("queue position not modeled",),
    )

    assert 0 <= scoring.priority_score() <= 5
    assert scoring.priority_score() == 3.83


def test_backtest_config_normalizes_symbols_and_rejects_live_mode() -> None:
    config = BacktestConfig(
        config_id="bt-ofi-smoke",
        strategy_id="ofi_research",
        paper_ids=("ofi-2014",),
        symbols=("btc-usdt-swap",),
        timeframe="5m",
        start="2024-01-01",
        end="2024-02-01",
        initial_cash=10000,
        fee_bps=2,
        slippage_bps=1,
        assumptions=("research smoke test",),
    )

    assert config.symbols == ("BTC-USDT-SWAP",)
    assert config.allow_live_trading is False
    assert config.artifact_contract == "ADR-0002-compatible"

    with pytest.raises(ValidationError, match="live trading"):
        BacktestConfig(
            config_id="bad-live",
            strategy_id="bad",
            symbols=("BTC-USDT-SWAP",),
            timeframe="5m",
            start="2024-01-01",
            end="2024-02-01",
            initial_cash=10000,
            allow_live_trading=True,
        )


def test_backtest_config_requires_forward_time_window() -> None:
    with pytest.raises(ValidationError, match="end must be after start"):
        BacktestConfig(
            config_id="bad-window",
            strategy_id="bad",
            symbols=("BTC-USDT-SWAP",),
            timeframe="1h",
            start="2024-02-01",
            end="2024-01-01",
            initial_cash=10000,
        )


def test_alpha_candidate_rejects_live_mode() -> None:
    with pytest.raises(ValidationError, match="live trading"):
        AlphaCandidate(
            candidate_id="bad-live-alpha",
            title="Bad Live Alpha",
            paper_ids=("paper-001",),
            hypothesis="Bad hypothesis",
            signal_definition="Bad signal",
            entry_rule="Enter",
            exit_rule="Exit",
            sizing_rule="Size",
            required_data=("ohlcv",),
            expected_horizon="daily",
            backtest_path="walk_forward",
            allow_live_trading=True,
        )

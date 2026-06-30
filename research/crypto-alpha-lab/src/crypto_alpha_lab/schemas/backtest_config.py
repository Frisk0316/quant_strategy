"""Schema for research backtest requests."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ExecutionMode = Literal["vectorized", "event_replay"]
DataSource = Literal["local_fixture", "local_parquet", "local_database"]
FillModel = Literal["next_bar_close", "next_bar_open", "maker_replay", "conservative"]
ValidationStatus = Literal["research_draft", "in_sample", "naive_backtest", "walk_forward", "cpcv"]


class BacktestConfig(BaseModel):
    """Research-only backtest configuration contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    paper_ids: tuple[str, ...] = Field(default_factory=tuple)
    symbols: tuple[str, ...] = Field(min_length=1)
    timeframe: str = Field(pattern=r"^\d+(m|h|d)$")
    start: date
    end: date
    initial_cash: float = Field(gt=0)
    fee_bps: float = Field(default=0.0, ge=0)
    slippage_bps: float = Field(default=0.0, ge=0)
    validation_status: ValidationStatus = "research_draft"
    execution_mode: ExecutionMode = "vectorized"
    data_source: DataSource = "local_fixture"
    fill_model: FillModel = "next_bar_close"
    artifact_contract: str = "ADR-0002-compatible"
    allow_live_trading: bool = False
    assumptions: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(symbol.strip().upper() for symbol in symbols)
        if any(not symbol for symbol in normalized):
            raise ValueError("symbols cannot contain empty values")
        return normalized

    @model_validator(mode="after")
    def validate_research_only_config(self) -> "BacktestConfig":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.allow_live_trading:
            raise ValueError("BacktestConfig cannot enable live trading")
        return self

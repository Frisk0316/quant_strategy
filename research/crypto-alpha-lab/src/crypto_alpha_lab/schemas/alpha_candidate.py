"""Schema for alpha candidates derived from scored papers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crypto_alpha_lab.schemas.paper_scoring import ExpectedHorizon

CandidateStatus = Literal["idea", "screened", "ready_for_backtest", "watchlist", "rejected"]
BacktestPath = Literal[
    "event_replay",
    "vectorized_scan",
    "walk_forward",
    "cpcv",
    "manual_review_only",
]


class AlphaCandidate(BaseModel):
    """Research alpha candidate with explicit backtest mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    paper_ids: tuple[str, ...] = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    signal_definition: str = Field(min_length=1)
    entry_rule: str = Field(min_length=1)
    exit_rule: str = Field(min_length=1)
    sizing_rule: str = Field(min_length=1)
    required_data: tuple[str, ...] = Field(min_length=1)
    target_symbols: tuple[str, ...] = Field(default_factory=tuple)
    expected_horizon: ExpectedHorizon
    backtest_path: BacktestPath
    validation_plan: tuple[str, ...] = Field(default_factory=tuple)
    risk_controls: tuple[str, ...] = Field(default_factory=tuple)
    expected_failure_modes: tuple[str, ...] = Field(default_factory=tuple)
    parent_framework_touchpoints: tuple[str, ...] = Field(default_factory=tuple)
    status: CandidateStatus = "idea"
    allow_live_trading: bool = False

    @model_validator(mode="after")
    def validate_research_only(self) -> "AlphaCandidate":
        if self.allow_live_trading:
            raise ValueError("AlphaCandidate cannot enable live trading")
        return self

"""Schema for ranking paper-derived crypto alpha ideas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["preprint", "working_paper", "journal_article", "review", "negative_evidence"]
AlphaCategory = Literal[
    "momentum",
    "mean_reversion",
    "microstructure",
    "carry",
    "stat_arb",
    "volatility",
    "alternative_data",
    "risk_filter",
    "execution",
]
ExpectedHorizon = Literal["tick", "intraday", "daily", "multi_day"]


class PaperScoring(BaseModel):
    """Literature scoring record for alpha prioritization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: tuple[str, ...] = Field(default_factory=tuple)
    year: int = Field(ge=1900, le=2100)
    venue: str | None = None
    source_type: SourceType = "working_paper"
    url: str | None = None
    doi: str | None = None
    alpha_category: AlphaCategory
    expected_horizon: ExpectedHorizon
    required_data: tuple[str, ...] = Field(default_factory=tuple)
    evidence_quality: int = Field(ge=0, le=5)
    crypto_relevance: int = Field(ge=0, le=5)
    data_availability: int = Field(ge=0, le=5)
    implementation_fit: int = Field(ge=0, le=5)
    cost_awareness: int = Field(ge=0, le=5)
    novelty: int = Field(ge=0, le=5)
    leakage_risk: int = Field(ge=0, le=5)
    overfit_risk: int = Field(ge=0, le=5)
    known_failure_modes: tuple[str, ...] = Field(default_factory=tuple)
    notes: str = ""

    def priority_score(self) -> float:
        """Return a 0-5 score after penalizing research risks."""

        benefit = (
            self.evidence_quality * 0.22
            + self.crypto_relevance * 0.18
            + self.data_availability * 0.16
            + self.implementation_fit * 0.16
            + self.cost_awareness * 0.16
            + self.novelty * 0.12
        )
        penalty = self.leakage_risk * 0.15 + self.overfit_risk * 0.15
        return round(max(0.0, min(5.0, benefit - penalty)), 2)

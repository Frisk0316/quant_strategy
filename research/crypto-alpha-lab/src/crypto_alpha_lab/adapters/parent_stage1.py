"""Adapters from lab candidates to parent Stage 1 drafts."""
from __future__ import annotations

from crypto_alpha_lab.schemas import AlphaCandidate

FAMILY_BY_CATEGORY = {
    "carry": "F-FUNDING-CARRY",
    "microstructure": "F-OFI-MAKER-SKEW",
    "stat_arb": "F-PAIRS-OU",
    "volatility": "F-VOL-REGIME",
    "risk_filter": "F-VOL-REGIME",
    "momentum": "F-XS-MOMENTUM",
    "mean_reversion": "F-S5-RESIDUAL-MEANREV",
    "alternative_data": "F-SENTIMENT",
    "execution": "F-OFI-MAKER-SKEW",
}


def to_parent_stage1_draft(candidate: AlphaCandidate, *, alpha_category: str | None = None) -> dict[str, object]:
    family_id = FAMILY_BY_CATEGORY.get(alpha_category or "", "NEW")
    return {
        "source": "A_literature",
        "provisional_candidate_id": candidate.candidate_id,
        "family_id_or_NEW": family_id,
        "mechanism": candidate.hypothesis,
        "signal_definition": candidate.signal_definition,
        "data_feasible": True,
        "prior_rank": 1,
        "planned_grid_size": 4,
        "draft_status": "drafted",
        "feedback_spawned": False,
        "required_data": candidate.required_data,
        "expected_horizon": candidate.expected_horizon,
        "backtest_path": candidate.backtest_path,
        "paper_ids": candidate.paper_ids,
    }

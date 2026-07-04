"""Probe Stage 2 data availability for taxonomy_002 frontier candidates."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.pipeline_stage2_registry import (
    BATCH_ID,
    CANDIDATES,
    DSN,
    END_EXCLUSIVE,
    FUNDING_SOURCE,
    OI_DATASETS,
    START,
    STAGE2_PROBES,
    UNIVERSE_PATH,
    VENUES,
    XVENUE_SYMBOLS,
    CandidateSpec,
    FundingThresholds,
    OIThresholds,
    Stage2Context,
    Stage2Probe,
    VenueThresholds,
    _candidate_list,
    _connect,
    _expected_1m_rows,
    _expected_8h_rows,
    _fetch_funding_timestamps,
    _fetch_venue_coverage,
    _iso_dt,
    _jsonable,
    _print_summary,
    _quantiles,
    _safe_ratio,
    _spec,
    _summarize_funding,
    _utc,
    _write_result,
    build_fail_closed_result,
    build_funding_data_check,
    build_oi_data_check,
    build_stage2_result,
    build_xvenue_data_check,
    load_point_in_time_universe,
    main,
    probe_funding,
    probe_oi,
    probe_xvenue,
    run_data_probe,
)

__all__ = [
    "BATCH_ID",
    "CANDIDATES",
    "DSN",
    "END_EXCLUSIVE",
    "FUNDING_SOURCE",
    "OI_DATASETS",
    "START",
    "STAGE2_PROBES",
    "UNIVERSE_PATH",
    "VENUES",
    "XVENUE_SYMBOLS",
    "CandidateSpec",
    "FundingThresholds",
    "OIThresholds",
    "Stage2Context",
    "Stage2Probe",
    "VenueThresholds",
    "build_fail_closed_result",
    "build_funding_data_check",
    "build_oi_data_check",
    "build_stage2_result",
    "build_xvenue_data_check",
    "load_point_in_time_universe",
    "main",
    "probe_funding",
    "probe_oi",
    "probe_xvenue",
    "run_data_probe",
]


if __name__ == "__main__":
    raise SystemExit(main())

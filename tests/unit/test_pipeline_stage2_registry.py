from datetime import datetime, timezone
from pathlib import Path

import pytest

from backtesting.pipeline_feasibility import FeasibilityResult
import backtesting.pipeline_stage2_registry as registry


@pytest.mark.asyncio
async def test_stage2_registry_uses_family_ids_and_uniform_probe_signature(monkeypatch):
    calls = []

    async def fake_funding(conn, *, universe_path, start, end, thresholds):
        calls.append(("funding", conn, universe_path, start, end, type(thresholds).__name__))
        return FeasibilityResult("batch", "candidate", "dir", "H-1", "F-FUNDING-XS-DISPERSION", ())

    async def fake_xvenue(conn, *, start, end, thresholds):
        calls.append(("xvenue", conn, start, end, type(thresholds).__name__))
        return FeasibilityResult("batch", "candidate", "dir", "H-2", "F-XVENUE-LEADLAG", ())

    monkeypatch.setattr(registry, "probe_funding", fake_funding)
    monkeypatch.setattr(registry, "probe_xvenue", fake_xvenue)

    ctx = {
        "universe_path": "universe.parquet",
        "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 1, 2, tzinfo=timezone.utc),
    }

    assert set(registry.STAGE2_PROBES) == {"F-FUNDING-XS-DISPERSION", "F-XVENUE-LEADLAG"}

    funding = await registry.STAGE2_PROBES["F-FUNDING-XS-DISPERSION"]("conn", ctx)
    xvenue = await registry.STAGE2_PROBES["F-XVENUE-LEADLAG"]("conn", ctx)

    assert funding.family_id == "F-FUNDING-XS-DISPERSION"
    assert xvenue.family_id == "F-XVENUE-LEADLAG"
    assert calls == [
        ("funding", "conn", Path("universe.parquet"), ctx["start"], ctx["end"], "FundingThresholds"),
        ("xvenue", "conn", ctx["start"], ctx["end"], "VenueThresholds"),
    ]

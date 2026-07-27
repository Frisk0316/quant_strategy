from __future__ import annotations

from datetime import datetime, timedelta, timezone

from okx_quant.data.external_clients.deribit_option_flow import DeribitOptionFlowClient
from scripts.market_data import ingest_external


def test_option_flow_endpoint_selection():
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    assert ingest_external._option_flow_endpoint(None, now) == DeribitOptionFlowClient.www_endpoint
    assert ingest_external._option_flow_endpoint(now - timedelta(hours=12), now) == DeribitOptionFlowClient.www_endpoint
    assert ingest_external._option_flow_endpoint(now - timedelta(days=30), now) == DeribitOptionFlowClient.history_endpoint

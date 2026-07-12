from __future__ import annotations

from scripts.market_data.snapshot_deribit_options import DEFAULT_DATASETS, _parse_args


def test_snapshot_deribit_options_dataset_override_does_not_append_defaults():
    assert _parse_args(["--dataset", "optsurf_deribit_btc"]).dataset == ["optsurf_deribit_btc"]
    assert _parse_args([]).dataset == list(DEFAULT_DATASETS)

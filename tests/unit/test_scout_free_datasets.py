import json

import scripts.scout_free_datasets as scout


def test_parse_binance_taker_fields_from_raw_kline_array():
    payload = {"exchange": "binance", "raw": [0, 1, 2, 3, 4, 5, 6, 7, 8, "12.5", "34.5", 11]}

    assert scout.parse_binance_taker_fields(payload) == (12.5, 34.5)
    assert scout.parse_binance_taker_fields({"raw": payload["raw"][:10]}) is None


def test_main_skips_without_dsn(monkeypatch, capsys):
    async def forbidden_scout(*_args):
        raise AssertionError("scout should not run without a DSN")

    monkeypatch.setattr(scout, "resolve_dsn", lambda _explicit=None: None)
    monkeypatch.setattr(scout, "scout", forbidden_scout)

    assert scout.main([]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "SKIP"

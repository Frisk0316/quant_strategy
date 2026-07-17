from datetime import datetime, timezone
from types import SimpleNamespace

import json

import scripts.audit_history_coverage as audit
import scripts.verify_okx_1m_backfill as verify


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def test_audit_skips_cleanly_without_dsn(tmp_path, monkeypatch, capsys):
    async def forbidden_connect(_dsn):
        raise AssertionError("DB connection attempted")

    monkeypatch.setattr(audit, "resolve_dsn", lambda _explicit=None: None)
    monkeypatch.setattr(audit, "_connect", forbidden_connect)
    json_out = tmp_path / "audit.json"
    markdown_out = tmp_path / "audit.md"

    assert audit.main(["--json-out", str(json_out), "--markdown-out", str(markdown_out)]) == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["status"] == "SKIP"
    assert "SKIP" in markdown_out.read_text(encoding="utf-8")
    assert "SKIP: no DSN" in capsys.readouterr().out


def test_audit_with_dsn_emits_ranked_json_and_markdown(tmp_path, monkeypatch):
    class FakeConnection:
        closed = False

        async def fetch(self, query):
            if "FROM canonical_candles" in query:
                return [
                    {
                        "inst_id": "BTC-USDT-SWAP",
                        "source_primary": "binance",
                        "bar": "1m",
                        "interval_ms": 60_000,
                        "earliest_ts": _dt("2020-01-01"),
                        "latest_ts": _dt("2020-01-01 00:02:00"),
                        "row_count": 2,
                    },
                    {
                        "inst_id": "ETH-USDT-SWAP",
                        "source_primary": "binance",
                        "bar": "1m",
                        "interval_ms": 60_000,
                        "earliest_ts": _dt("2021-01-01"),
                        "latest_ts": _dt("2021-01-01 00:01:00"),
                        "row_count": 2,
                    },
                ]
            if "FROM external_datasets" in query:
                return [
                    {
                        "dataset_id": "dvol_deribit_btc",
                        "provider": "deribit",
                        "frequency": "daily",
                        "earliest_ts": _dt("2021-01-01"),
                        "latest_ts": _dt("2021-01-03"),
                        "row_count": 2,
                    },
                    {
                        "dataset_id": "optsurf_deribit_btc",
                        "provider": "deribit",
                        "frequency": "event",
                        "earliest_ts": None,
                        "latest_ts": None,
                        "row_count": 0,
                    },
                ]
            raise AssertionError(query)

        async def close(self):
            self.closed = True

    conn = FakeConnection()

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(audit, "resolve_dsn", lambda explicit=None: explicit)
    monkeypatch.setattr(audit, "_connect", fake_connect)
    json_out = tmp_path / "audit.json"
    markdown_out = tmp_path / "audit.md"

    assert audit.main(
        [
            "--dsn",
            "postgresql://unit",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    ) == 0

    report = json.loads(json_out.read_text(encoding="utf-8"))
    btc = report["canonical_candles"][0]
    dvol = report["external_observations"][0]
    measured = [
        row["history_gap_years"]
        for row in report["ranked_history_gaps"]
        if row["history_gap_years"] is not None
    ]
    markdown = markdown_out.read_text(encoding="utf-8")

    assert report["status"] == "COMPLETE"
    assert btc["earliest_ts"] == "2020-01-01T00:00:00Z"
    assert btc["latest_ts"] == "2020-01-01T00:02:00Z"
    assert btc["row_count"] == 2
    assert btc["gap_vs_expected"]["missing_rows"] == 1
    assert dvol["gap_vs_expected"]["missing_rows"] == 1
    assert measured == sorted(measured, reverse=True)
    assert all(row["max_available_history_status"] == "UNCONFIRMED" for row in report["ranked_history_gaps"])
    assert all(label in markdown for label in ("P1", "P2", "P3", "H-010", "H-016/H-017"))
    assert conn.closed is True


def test_okx_verifier_returns_nonzero_below_threshold(monkeypatch, capsys):
    class FakeConnection:
        calls = 0

        async def fetch(self, _sql, *_params):
            self.calls += 1
            if self.calls == 1:
                return [
                    {
                        "inst_id": symbol,
                        "raw_rows": 100,
                        "venue_rows": 100,
                        "mismatch_rows": 0,
                    }
                    for symbol in verify.XVENUE_SYMBOLS
                ]
            return []

        async def close(self):
            pass

    async def fake_connect(_dsn):
        return FakeConnection()

    async def fake_probe(_conn, **_kwargs):
        return SimpleNamespace(
            checks=(
                SimpleNamespace(
                    reason="coverage failed",
                    details={
                        "venue_coverage": {
                            symbol: {
                                "okx": {"row_count": 100, "coverage_ratio": 0.94},
                                "aligned_rows": 100,
                                "alignment_ratio": 0.94,
                            }
                            for symbol in verify.XVENUE_SYMBOLS
                        }
                    },
                ),
            )
        )

    monkeypatch.setattr(verify, "resolve_dsn", lambda explicit=None: explicit)
    monkeypatch.setattr(verify, "_connect", fake_connect)
    monkeypatch.setattr(verify, "probe_xvenue", fake_probe)

    assert verify.main(["--dsn", "postgresql://unit"]) == 1
    assert '"status": "FAIL"' in capsys.readouterr().out

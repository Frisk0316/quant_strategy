from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from okx_quant.core.config import AppConfig, OKXSecrets, SystemConfig, load_config
from okx_quant.execution.binance_testnet import futures_client
from okx_quant.execution.deribit_live import private_client
from okx_quant.monitoring import telegram_alert
from scripts.market_data import ingest_external


class _FailingStore:
    def __init__(self) -> None:
        self.finished: list[dict] = []
        self.checkpoints: list[dict] = []

    async def upsert_dataset(self, dataset_id, cfg):
        pass

    async def start_fetch_job(self, dataset_id, provider, start, end):
        return "job-1"

    async def finish_fetch_job(self, job_id, **kwargs):
        self.finished.append(kwargs)

    async def update_checkpoint(self, dataset_id, **kwargs):
        self.checkpoints.append(kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dataset_id", "env_name", "cfg"),
    [
        (
            "fred_test",
            "FRED_API_KEY",
            {"provider": "fred", "adapter": "fred", "series_id": "DGS10"},
        ),
        (
            "nasdaq_test",
            "NASDAQ_DATA_LINK_API_KEY",
            {
                "provider": "nasdaq",
                "adapter": "nasdaq_data_link",
                "dataset_code": "TEST/DATA",
            },
        ),
    ],
)
async def test_external_4xx_api_key_is_redacted_before_persistence(
    dataset_id: str,
    env_name: str,
    cfg: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = f"{dataset_id}-secret"
    monkeypatch.setenv(env_name, secret)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(403, request=request)

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *args, **kwargs: real_client(*args, transport=transport, **kwargs),
    )
    store = _FailingStore()

    with pytest.raises(RuntimeError) as caught:
        await ingest_external._ingest_one(
            store,
            dataset_id,
            cfg,
            None,
            None,
            dry_run=False,
        )

    assert secret in str(requests[0].url)
    assert secret not in str(caught.value)
    assert secret not in store.finished[-1]["error_message"]
    assert secret not in store.checkpoints[-1]["last_error"]
    assert "api_key=***" in store.finished[-1]["error_message"]


def test_redact_error_masks_raw_api_key_query() -> None:
    error = RuntimeError("failed https://example.test/data?api_key=raw-secret&x=1")

    assert ingest_external._redact_error(error) == (
        "failed https://example.test/data?api_key=***&x=1"
    )


def test_config_secret_fields_do_not_leak_from_repr_or_dump() -> None:
    values = {
        "OKX_API_KEY": "api-key-value",
        "OKX_SECRET": "api-secret-value",
        "OKX_PASSPHRASE": "passphrase-value",
        "TELEGRAM_TOKEN": "telegram-token-value",
        "TELEGRAM_CHAT_ID": "telegram-chat-value",
    }
    secrets = OKXSecrets(**values, _env_file=None)
    cfg = AppConfig(system=SystemConfig(equity_usd=1), secrets=secrets)

    for field in (
        secrets.okx_api_key,
        secrets.okx_secret,
        secrets.okx_passphrase,
        secrets.telegram_token,
        secrets.telegram_chat_id,
    ):
        assert isinstance(field, SecretStr)
    rendered = f"{cfg!s}\n{cfg!r}\n{cfg.model_dump()}\n{cfg.model_dump(mode='json')}"
    for value in values.values():
        assert value not in rendered


def test_config_database_url_overrides_empty_yaml_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    dsn = "postgresql://configured-by-environment"
    monkeypatch.setenv("DATABASE_URL", dsn)

    assert load_config(require_secrets=False).storage.timescale_dsn == dsn


@pytest.mark.asyncio
async def test_telegram_failure_log_redacts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "telegram-sensitive-token"
    monitor = telegram_alert.TelegramMonitor(token=token, chat_id="42")
    await monitor._client.aclose()

    class FailingClient:
        async def post(self, url: str, json: dict) -> None:
            raise httpx.ConnectError(f"failed request to {url}")

    logs: list[str] = []
    monitor._client = FailingClient()  # type: ignore[assignment]
    monkeypatch.setattr(
        telegram_alert.logger,
        "warning",
        lambda message, *args: logs.append(message.format(*args)),
    )

    await monitor.send_alert("test")

    assert logs
    assert "ConnectError" in logs[0]
    assert token not in logs[0]
    assert "***" in logs[0]


def test_secret_from_env_defaults_to_repo_root_from_arbitrary_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "BINANCE_API_KEY",
        "BINANCE_SECRET",
        "BINANCE_FUTURES_API_KEY",
        "BINANCE_FUTURES_SECRET",
        "DERIBIT_API_KEY",
        "DERIBIT_API_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "exists", lambda _path: True)
    seen: list[Path] = []
    monkeypatch.setattr(
        futures_client,
        "dotenv_values",
        lambda path: (
            seen.append(Path(path))
            or {"BINANCE_API_KEY": "binance-key", "BINANCE_SECRET": "binance-secret"}
        ),
    )
    monkeypatch.setattr(
        private_client,
        "dotenv_values",
        lambda path: (
            seen.append(Path(path))
            or {"DERIBIT_API_KEY": "deribit-key", "DERIBIT_API_SECRET": "deribit-secret"}
        ),
    )

    binance = futures_client.BinanceFuturesTestnetClient.from_env(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    )
    deribit = private_client.DeribitPrivateClient.from_env(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    )
    binance.close()
    deribit.close()

    assert seen == [
        Path(futures_client.__file__).resolve().parents[4] / ".env",
        Path(private_client.__file__).resolve().parents[4] / ".env",
    ]

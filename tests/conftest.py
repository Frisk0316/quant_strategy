from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from okx_quant.core.bus import EventBus
from okx_quant.core.config import (  # noqa: E402
    AppConfig,
    BacktestConfig,
    OKXEndpoints,
    OKXSecrets,
    RiskConfig,
    StorageConfig,
    StrategiesConfig,
    SystemConfig,
    load_config,
)
from okx_quant.core.events import FillPayload  # noqa: E402
from okx_quant.execution.broker import Broker  # noqa: E402


class FilledBroker(Broker):
    def __init__(self) -> None:
        self.orders: list[dict] = []

    async def submit(self, order: dict):
        self.orders.append(order)
        return FillPayload(
            cl_ord_id=order["cl_ord_id"],
            ord_id="ord-1",
            inst_id=order["inst_id"],
            fill_px=float(order["px"]),
            fill_sz=float(order["sz"]),
            fee=0.0,
            fee_ccy="USDT",
            side=order["side"],
            ts=1,
            strategy=order["strategy"],
            state="filled",
            metadata=dict(order.get("metadata", {})),
        )

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        return True

    async def close_all(self) -> None:
        return None


class PendingBroker(Broker):
    def __init__(self) -> None:
        self.orders: list[dict] = []

    async def submit(self, order: dict):
        self.orders.append(order)
        return FillPayload(
            cl_ord_id=order["cl_ord_id"],
            ord_id="ord-pending",
            inst_id=order["inst_id"],
            fill_px=0.0,
            fill_sz=0.0,
            fee=0.0,
            fee_ccy="USDT",
            side=order["side"],
            ts=1,
            strategy=order["strategy"],
            state="pending",
            metadata=dict(order.get("metadata", {})),
        )

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        return True

    async def close_all(self) -> None:
        return None


@pytest.fixture
def minimal_cfg() -> AppConfig:
    strategies = StrategiesConfig()
    strategies.funding_carry.perp_symbol = "BTC-USDT-SWAP"
    strategies.funding_carry.spot_symbol = "BTC-USDT"
    return AppConfig(
        system=SystemConfig(
            mode="demo",
            symbols=["BTC-USDT-SWAP"],
            spot_symbols=["BTC-USDT"],
            equity_usd=10_000.0,
        ),
        okx=OKXEndpoints(),
        storage=StorageConfig(
            backend="parquet",
            parquet_dir="./data/ticks",
            timescale_dsn=None,
            candle_backend="parquet",
        ),
        strategies=strategies,
        risk=RiskConfig(
            max_order_notional_usd=10_000.0,
            max_pos_pct_equity=1.0,
            max_leverage=3.0,
            max_daily_loss_pct=0.05,
            soft_drawdown_pct=0.10,
            hard_drawdown_pct=0.15,
            stale_quote_pct=0.20,
        ),
        backtest=BacktestConfig(order_latency_ms=0, cancel_latency_ms=0, queue_fill_fraction=1.0),
        secrets=OKXSecrets.model_construct(
            okx_api_key="",
            okx_secret="",
            okx_passphrase="",
            telegram_token=None,
            telegram_chat_id=None,
        ),
    )


@pytest.fixture
def prod_risk_cfg() -> RiskConfig:
    return load_config(require_secrets=False).risk


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def filled_broker() -> FilledBroker:
    return FilledBroker()


@pytest.fixture
def pending_broker() -> PendingBroker:
    return PendingBroker()


@pytest.fixture
def synthetic_funding_frame() -> pd.DataFrame:
    ts = pd.to_datetime(
        [
            "2024-01-01 00:02:00Z",
            "2024-01-01 00:03:00Z",
            "2024-01-01 00:04:00Z",
        ],
        utc=True,
    )
    ts_ms = [int(pd.Timestamp(value).timestamp() * 1000) for value in ts]
    return pd.DataFrame(
        {
            "ts": ts,
            "rate": [0.0010, -0.0005, 0.00025],
            "nextFundingTime": [value + 60_000 for value in ts_ms],
            "funding_interval_hours": [1.0 / 60.0] * len(ts),
        }
    )


@pytest.fixture
def btc_parquet_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "ticks"
    inst_dir = data_dir / "BTC_USDT_SWAP"
    inst_dir.mkdir(parents=True)

    ts = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
    close = pd.Series([50_000 + i * 50 for i in range(24)], dtype=float)
    candles = pd.DataFrame(
        {
            "ts": ts,
            "open": close - 10,
            "high": close + 25,
            "low": close - 25,
            "close": close,
            "vol": [100 + i for i in range(24)],
        }
    )
    candles.to_parquet(inst_dir / "candles_1H.parquet", index=False)

    funding_ts = pd.to_datetime(
        ["2024-01-01 02:00:00Z", "2024-01-01 10:00:00Z", "2024-01-01 18:00:00Z"],
        utc=True,
    )
    funding = pd.DataFrame(
        {
            "ts": funding_ts,
            "rate": [0.001, 0.001, 0.001],
            "nextFundingTime": (funding_ts.view("int64") // 1_000_000) + 8 * 3600 * 1000,
            "funding_interval_hours": [8.0, 8.0, 8.0],
        }
    )
    funding.to_parquet(inst_dir / "funding.parquet", index=False)
    return data_dir

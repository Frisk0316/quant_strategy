"""
Configuration loader using Pydantic v2.
Reads secrets from environment (.env), structured config from YAML files.
Fails fast on startup if any required value is missing or invalid.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Secrets — from environment / .env file
# ---------------------------------------------------------------------------

class OKXSecrets(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    okx_api_key: str = Field(..., alias="OKX_API_KEY")
    okx_secret: str = Field(..., alias="OKX_SECRET")
    okx_passphrase: str = Field(..., alias="OKX_PASSPHRASE")
    telegram_token: Optional[str] = Field(None, alias="TELEGRAM_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, alias="TELEGRAM_CHAT_ID")


# ---------------------------------------------------------------------------
# System config — from settings.yaml
# ---------------------------------------------------------------------------

class OKXEndpoints(BaseModel):
    base_url: str = "https://www.okx.com"
    ws_public: str = "wss://ws.okx.com:8443/ws/v5/public"
    ws_private: str = "wss://ws.okx.com:8443/ws/v5/private"
    ws_business: str = "wss://ws.okx.com:8443/ws/v5/business"
    ws_demo_host: str = "wspap.okx.com"
    book_depth: int = 400


class StorageConfig(BaseModel):
    backend: Literal["parquet", "timescaledb"] = "parquet"
    parquet_dir: str = "./data/ticks"
    timescale_dsn: Optional[str] = None
    redis_url: str = "redis://localhost:6379"


class ClockConfig(BaseModel):
    sync_interval_secs: int = 300


class SystemConfig(BaseModel):
    mode: Literal["demo", "shadow", "live"] = "demo"
    symbols: list[str] = ["BTC-USDT-SWAP"]
    spot_symbols: list[str] = ["BTC-USDT"]
    equity_usd: float = Field(gt=0)
    log_level: str = "INFO"
    json_logs: bool = False


# ---------------------------------------------------------------------------
# Strategy params — from strategies.yaml
# ---------------------------------------------------------------------------

class OBIMarketMakerParams(BaseModel):
    enabled: bool = True
    symbols: list[str] = ["BTC-USDT-SWAP"]
    depth: int = 5
    alpha_decay: float = 0.5
    ewma_halflife_ms: float = 200.0
    obi_threshold: float = 0.15
    c_alpha: float = 100.0
    refresh_interval_ms: float = 500.0
    max_inventory: int = 50
    td_mode: str = "cross"


class ASMarketMakerParams(BaseModel):
    enabled: bool = True
    symbols: list[str] = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    gamma: float = 0.1
    sigma_lookback_min: int = 5
    kappa: float = 1.5
    max_pos_contracts: int = 50
    c_alpha: float = 100.0
    beta_vpin: float = 2.0
    vpin_bucket_divisor: int = 75
    vpin_window: int = 50
    refresh_interval_ms: float = 500.0
    kappa_recal_interval_secs: int = 3600
    td_mode: str = "cross"


class FundingCarryParams(BaseModel):
    enabled: bool = True
    perp_symbol: str = "BTC-USDT-SWAP"
    spot_symbol: str = "BTC-USDT"
    min_apr_threshold: float = 0.12
    rebalance_drift_threshold: float = 0.02
    funding_check_interval_secs: int = 300
    td_mode: str = "cross"


class PairsTradingParams(BaseModel):
    enabled: bool = False
    symbol_y: str = "ETH-USDT-SWAP"
    symbol_x: str = "BTC-USDT-SWAP"
    kalman_delta: float = 1e-4
    entry_z: float = 2.0
    exit_z: float = 0.3
    stop_z: float = 4.0
    lookback_hours: int = 168
    td_mode: str = "cross"


class StrategiesConfig(BaseModel):
    obi_market_maker: OBIMarketMakerParams = OBIMarketMakerParams()
    as_market_maker: ASMarketMakerParams = ASMarketMakerParams()
    funding_carry: FundingCarryParams = FundingCarryParams()
    pairs_trading: PairsTradingParams = PairsTradingParams()


# ---------------------------------------------------------------------------
# Risk config — from risk.yaml
# ---------------------------------------------------------------------------

class RiskConfig(BaseModel):
    max_order_notional_usd: float = 500.0
    max_pos_pct_equity: float = 0.30
    max_leverage: float = 3.0
    max_daily_loss_pct: float = 0.05
    soft_drawdown_pct: float = 0.10
    hard_drawdown_pct: float = 0.15
    stale_quote_pct: float = 0.02
    ws_reconnect_circuit_threshold: int = 3
    ws_reconnect_window_secs: int = 60
    rest_error_rate_circuit_threshold: float = 0.05
    rest_error_rate_window: int = 100
    hard_stop_cooldown_hours: int = 48

    @model_validator(mode="after")
    def validate_thresholds(self) -> "RiskConfig":
        assert self.soft_drawdown_pct < self.hard_drawdown_pct, (
            "soft_drawdown_pct must be less than hard_drawdown_pct"
        )
        assert self.max_leverage <= 10.0, "max_leverage seems dangerously high"
        return self


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    system: SystemConfig
    okx: OKXEndpoints = OKXEndpoints()
    storage: StorageConfig = StorageConfig()
    clock: ClockConfig = ClockConfig()
    strategies: StrategiesConfig = StrategiesConfig()
    risk: RiskConfig = RiskConfig()
    secrets: OKXSecrets = None  # type: ignore[assignment]

    def is_demo(self) -> bool:
        return self.system.mode == "demo"

    def is_live(self) -> bool:
        return self.system.mode == "live"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(
    settings_path: str = "config/settings.yaml",
    strategies_path: str = "config/strategies.yaml",
    risk_path: str = "config/risk.yaml",
    env_file: str = ".env",
) -> AppConfig:
    def _load(path: str) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(p) as f:
            return yaml.safe_load(f) or {}

    settings_raw = _load(settings_path)
    strategies_raw = _load(strategies_path)
    risk_raw = _load(risk_path)

    system = SystemConfig(**settings_raw.get("system", {}))
    okx_endpoints = OKXEndpoints(**settings_raw.get("okx", {}))
    storage = StorageConfig(**settings_raw.get("storage", {}))
    clock = ClockConfig(**settings_raw.get("clock", {}))
    strategies = StrategiesConfig(**strategies_raw)
    risk = RiskConfig(**risk_raw.get("risk", {}))

    # Load secrets — raises ValidationError if keys are missing
    if env_file and Path(env_file).exists():
        os.environ.setdefault("_dotenv_loaded", "1")
    secrets = OKXSecrets(_env_file=env_file)

    return AppConfig(
        system=system,
        okx=okx_endpoints,
        storage=storage,
        clock=clock,
        strategies=strategies,
        risk=risk,
        secrets=secrets,
    )

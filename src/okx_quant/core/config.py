"""
Configuration loader using Pydantic v2.
Reads secrets from environment (.env), structured config from YAML files.
Fails fast on startup if any required value is missing or invalid.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from okx_quant.core.symbols import normalize_spot_symbol, normalize_swap_symbol

FEAR_GREED_LABELS: dict[str, str] = {
    "extreme fear": "Extreme Fear",
    "fear": "Fear",
    "neutral": "Neutral",
    "greed": "Greed",
    "extreme greed": "Extreme Greed",
}


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
    # Default to TimescaleDB candles; run_replay_backtest.py + routes_backtest.py
    # auto-fall back to "parquet" when no DSN is reachable so the parquet flow
    # keeps working in environments without a DB.
    candle_backend: Literal["parquet", "postgres"] = "postgres"
    # Default exchange whose data is consumed by backtests. Strategies must
    # backtest on the same exchange's data they intend to trade on (see
    # docs/ai_collaboration.md deployment gates). Frontend can override per-run.
    primary_exchange: Literal["binance", "okx", "bybit", "coinbase", "kraken"] = "binance"


# ---------------------------------------------------------------------------
# Market data pipeline config — from settings.yaml market_data section
# ---------------------------------------------------------------------------

class MarketDataCanonicalConfig(BaseModel):
    base_bar: str = "1m"
    derived_bars: list[str] = ["5m", "15m", "1H"]


class MarketDataValidationConfig(BaseModel):
    manual_only: bool = True
    sigma_threshold: float = 3.0
    replace_outliers_default: bool = False
    sources: list[str] = ["binance", "bybit"]


class MarketDataIngestionConfig(BaseModel):
    default_concurrency: int = 1
    max_retries: int = 3
    retry_backoff_seconds: list[int] = [1, 3, 9]
    chunk_days: dict[str, int] = {
        "1m": 7,
        "5m": 30,
        "15m": 60,
        "1H": 180,
    }


class MarketDataConfig(BaseModel):
    source_primary: str = "okx"
    canonical: MarketDataCanonicalConfig = MarketDataCanonicalConfig()
    bars: list[str] = ["1m", "5m", "15m", "1H"]
    instruments: list[str] = []
    validation: MarketDataValidationConfig = MarketDataValidationConfig()
    ingestion: MarketDataIngestionConfig = MarketDataIngestionConfig()


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
    mlofi_weight: float = 1.0
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
    mlofi_depth: int = 5
    mlofi_decay: float = 0.5
    mlofi_weight: float = 1.0
    beta_vpin: float = 2.0
    elevated_size_multiplier: float = 0.5
    toxic_size_multiplier: float = 0.25
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
    max_abs_basis_z: float = 2.5
    max_crowding: float = 0.85
    funding_check_interval_secs: int = 300
    td_mode: str = "cross"

    @field_validator("perp_symbol")
    @classmethod
    def normalize_perp_symbol(cls, value: str) -> str:
        return normalize_swap_symbol(value)

    @field_validator("spot_symbol")
    @classmethod
    def normalize_spot_symbol(cls, value: str) -> str:
        return normalize_spot_symbol(value)


class PairsTradingParams(BaseModel):
    enabled: bool = False
    symbol_y: str = "ETH-USDT-SWAP"
    symbol_x: str = "BTC-USDT-SWAP"
    kalman_delta: float = 1e-4
    entry_z: float = 2.0
    exit_z: float = 0.3
    stop_z: float = 4.0
    lookback_hours: int = 168
    max_half_life_hours: float = Field(default=48.0, gt=0, description="Maximum OU half-life in hours")
    max_hedge_uncertainty: float = 10.0
    td_mode: str = "cross"

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_max_half_life(cls, values):
        if isinstance(values, dict) and "max_half_life" in values and "max_half_life_hours" not in values:
            values = dict(values)
            values["max_half_life_hours"] = values["max_half_life"]
        return values

    @property
    def max_half_life(self) -> float:
        return self.max_half_life_hours

    @field_validator("symbol_y", "symbol_x")
    @classmethod
    def normalize_pair_symbol(cls, value: str) -> str:
        return normalize_swap_symbol(value)


class MACrossoverParams(BaseModel):
    enabled: bool = True
    symbols: list[str] = ["BTC-USDT-SWAP"]
    fast_window: int = Field(default=20, gt=0)
    slow_window: int = Field(default=50, gt=0)
    indicator_db_warmup: bool = False
    td_mode: str = "cross"

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return [normalize_swap_symbol(symbol) for symbol in value]

    @model_validator(mode="after")
    def validate_windows(self) -> "MACrossoverParams":
        if self.fast_window >= self.slow_window:
            raise ValueError("ma_crossover fast_window must be smaller than slow_window")
        return self


class EMACrossoverParams(BaseModel):
    enabled: bool = True
    symbols: list[str] = ["BTC-USDT-SWAP"]
    fast_span: int = Field(default=20, gt=0)
    slow_span: int = Field(default=50, gt=0)
    indicator_db_warmup: bool = False
    td_mode: str = "cross"

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return [normalize_swap_symbol(symbol) for symbol in value]

    @model_validator(mode="after")
    def validate_spans(self) -> "EMACrossoverParams":
        if self.fast_span >= self.slow_span:
            raise ValueError("ema_crossover fast_span must be smaller than slow_span")
        return self


class MACDCrossoverParams(BaseModel):
    enabled: bool = True
    symbols: list[str] = ["BTC-USDT-SWAP"]
    fast_span: int = Field(default=12, gt=0)
    slow_span: int = Field(default=26, gt=0)
    signal_span: int = Field(default=9, gt=0)
    indicator_db_warmup: bool = False
    td_mode: str = "cross"

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return [normalize_swap_symbol(symbol) for symbol in value]

    @model_validator(mode="after")
    def validate_spans(self) -> "MACDCrossoverParams":
        if self.fast_span >= self.slow_span:
            raise ValueError("macd_crossover fast_span must be smaller than slow_span")
        return self


class FearGreedSentimentParams(BaseModel):
    enabled: bool = False
    symbol: str = "BTC-USDT-SWAP"
    dataset_id: str = "fear_greed_btc"
    max_age_seconds: int = Field(default=172800, gt=0)
    extreme_fear_label: str = "Extreme Fear"
    exit_labels: list[str] = ["Greed", "Extreme Greed"]
    extreme_fear_threshold: float = Field(default=25.0, ge=0.0, le=100.0)
    exit_value_threshold: float = Field(default=51.0, ge=0.0, le=100.0)
    max_missing_signal_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    max_stale_signal_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    td_mode: str = "cross"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_swap_symbol(value)

    @field_validator("extreme_fear_label")
    @classmethod
    def validate_extreme_fear_label(cls, value: str) -> str:
        return _canonical_fear_greed_label(value)

    @field_validator("exit_labels")
    @classmethod
    def validate_exit_labels(cls, value: list[str]) -> list[str]:
        labels = [_canonical_fear_greed_label(label) for label in value]
        if not labels:
            raise ValueError("fear_greed_sentiment exit_labels must not be empty")
        return labels


class CMEGapFillParams(BaseModel):
    enabled: bool = False
    symbol: str = "BTC-USDT-SWAP"
    dataset_id: str = "cme_btc1_continuous"
    max_age_seconds: int = Field(default=604800, gt=0)
    min_gap_bps: float = Field(default=10.0, ge=0)
    max_hold_days: float = Field(default=5.0, gt=0)
    roll_dates: list[str] = []
    max_missing_signal_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    max_stale_signal_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    td_mode: str = "cross"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_swap_symbol(value)

    @field_validator("roll_dates")
    @classmethod
    def validate_roll_dates(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in value:
            try:
                normalized.append(pd.Timestamp(raw).date().isoformat())
            except Exception as exc:
                raise ValueError(f"invalid cme_gap_fill roll date: {raw}") from exc
        return normalized


class StrategiesConfig(BaseModel):
    obi_market_maker: OBIMarketMakerParams = OBIMarketMakerParams()
    as_market_maker: ASMarketMakerParams = ASMarketMakerParams()
    funding_carry: FundingCarryParams = FundingCarryParams()
    pairs_trading: PairsTradingParams = PairsTradingParams()
    ma_crossover: MACrossoverParams = MACrossoverParams()
    ema_crossover: EMACrossoverParams = EMACrossoverParams()
    macd_crossover: MACDCrossoverParams = MACDCrossoverParams()
    fear_greed_sentiment: FearGreedSentimentParams = FearGreedSentimentParams()
    cme_gap_fill: CMEGapFillParams = CMEGapFillParams()


def _canonical_fear_greed_label(value: str) -> str:
    text = str(value or "").strip()
    canonical = FEAR_GREED_LABELS.get(text.casefold())
    if not canonical:
        allowed = ", ".join(FEAR_GREED_LABELS.values())
        raise ValueError(f"Unknown Fear & Greed label '{value}'. Allowed: {allowed}")
    return canonical


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


class BacktestConfig(BaseModel):
    order_latency_ms: int = Field(default=0, ge=0)
    cancel_latency_ms: int = Field(default=200, ge=0)
    queue_fill_fraction: float = Field(default=0.20, ge=0.0, le=1.0)
    liquidate_on_end: bool = True


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
    backtest: BacktestConfig = BacktestConfig()
    market_data: MarketDataConfig = MarketDataConfig()
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
    require_secrets: bool = True,
) -> AppConfig:
    def _load(path: str) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    settings_raw = _load(settings_path)
    strategies_raw = _load(strategies_path)
    risk_raw = _load(risk_path)

    system = SystemConfig(**settings_raw.get("system", {}))
    okx_endpoints = OKXEndpoints(**settings_raw.get("okx", {}))
    storage = StorageConfig(**settings_raw.get("storage", {}))
    # Bridge DATABASE_URL env var into storage config when YAML omits timescale_dsn.
    # This lets backtest scripts (which skip .env loading) still find the DSN via cfg.
    env_dsn = os.environ.get("DATABASE_URL")
    if env_dsn and not storage.timescale_dsn:
        storage = storage.model_copy(update={"timescale_dsn": env_dsn})
    clock = ClockConfig(**settings_raw.get("clock", {}))
    strategies = StrategiesConfig(**strategies_raw)
    risk = RiskConfig(**risk_raw.get("risk", {}))
    backtest = BacktestConfig(**risk_raw.get("backtest", {}))
    market_data_raw = settings_raw.get("market_data", {})
    market_data = MarketDataConfig(**market_data_raw) if market_data_raw else MarketDataConfig()

    # Load secrets — live/demo engine keeps fail-fast behavior, offline
    # backtests can opt out because they do not call authenticated APIs.
    if require_secrets:
        if env_file and Path(env_file).exists():
            os.environ.setdefault("_dotenv_loaded", "1")
        secrets = OKXSecrets(_env_file=env_file)
    else:
        secrets = OKXSecrets.model_construct(
            okx_api_key="",
            okx_secret="",
            okx_passphrase="",
            telegram_token=None,
            telegram_chat_id=None,
        )

    return AppConfig(
        system=system,
        okx=okx_endpoints,
        storage=storage,
        clock=clock,
        strategies=strategies,
        risk=risk,
        backtest=backtest,
        market_data=market_data,
        secrets=secrets,
    )

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Callable

import pandas as pd
import pyarrow.parquet as pq
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    status: str
    message: str


def _result(name: str, status: str, message: str) -> CheckResult:
    return CheckResult(name=name, status=status, message=message)


def _inst_dir(data_dir: str | Path, inst_id: str) -> Path:
    return Path(data_dir) / inst_id.replace("-", "_")


def _candle_path(data_dir: str | Path, inst_id: str, bar: str) -> Path:
    return _inst_dir(data_dir, inst_id) / f"candles_{bar}.parquet"


def _load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return pq.read_table(path).to_pandas()


def _bar_timedelta(bar: str) -> pd.Timedelta:
    normalized = bar.lower()
    if normalized.endswith("m"):
        return pd.Timedelta(minutes=int(normalized[:-1]))
    if normalized.endswith("h"):
        return pd.Timedelta(hours=int(normalized[:-1]))
    if normalized.endswith("d"):
        return pd.Timedelta(days=int(normalized[:-1]))
    raise ValueError(f"Unsupported bar: {bar}")


def check_candle_gaps(data_dir: str | Path, inst_id: str, bar: str) -> CheckResult:
    name = "candle_gaps"
    try:
        df = _load_parquet(_candle_path(data_dir, inst_id, bar))
        if len(df) < 2:
            return _result(name, "WARN", "fewer than two candles")
        ts = pd.to_datetime(df["ts"], utc=True).sort_values()
        expected = _bar_timedelta(bar)
        gaps = ts.diff().dropna()
        gap_count = int((gaps > expected * 1.5).sum())
        if gap_count:
            return _result(name, "WARN", f"{gap_count} gap(s) larger than {expected}")
        return _result(name, "PASS", f"{len(df)} candles, no material gaps")
    except Exception as exc:
        return _result(name, "FAIL", str(exc))


def check_candle_ohlcv_sanity(data_dir: str | Path, inst_id: str, bar: str = "1H") -> CheckResult:
    name = "candle_ohlcv_sanity"
    try:
        df = _load_parquet(_candle_path(data_dir, inst_id, bar))
        required = {"open", "high", "low", "close", "vol"}
        missing = required - set(df.columns)
        if missing:
            return _result(name, "FAIL", f"missing columns: {sorted(missing)}")
        bad_ohlc = df[
            (df["high"] < df[["open", "close"]].max(axis=1))
            | (df["low"] > df[["open", "close"]].min(axis=1))
            | (df["vol"] < 0)
        ]
        if not bad_ohlc.empty:
            return _result(name, "FAIL", f"{len(bad_ohlc)} invalid OHLCV row(s)")
        return _result(name, "PASS", "OHLCV invariants hold")
    except Exception as exc:
        return _result(name, "FAIL", str(exc))


def check_funding_timestamps(data_dir: str | Path, inst_id: str) -> CheckResult:
    name = "funding_timestamps"
    try:
        df = _load_parquet(_inst_dir(data_dir, inst_id) / "funding.parquet")
        if len(df) < 2:
            return _result(name, "WARN", "fewer than two funding rows")
        ts = pd.to_datetime(df["ts"], utc=True).sort_values()
        diffs = ts.diff().dropna()
        tolerance = pd.Timedelta(minutes=5)
        ok = diffs.apply(
            lambda d: abs(d - pd.Timedelta(hours=4)) <= tolerance
            or abs(d - pd.Timedelta(hours=8)) <= tolerance
        )
        if not bool(ok.all()):
            return _result(name, "WARN", "funding interval outside 4h/8h +/-5m")
        return _result(name, "PASS", "funding intervals look regular")
    except Exception as exc:
        return _result(name, "FAIL", str(exc))


def check_parquet_schema(data_dir: str | Path, inst_id: str, bar: str) -> CheckResult:
    name = "parquet_schema"
    try:
        df = _load_parquet(_candle_path(data_dir, inst_id, bar))
        required = {"ts", "open", "high", "low", "close", "vol"}
        missing = required - set(df.columns)
        if missing:
            return _result(name, "FAIL", f"missing columns: {sorted(missing)}")
        return _result(name, "PASS", "required candle columns present")
    except Exception as exc:
        return _result(name, "FAIL", str(exc))


def check_data_staleness(data_dir: str | Path, inst_id: str, bar: str) -> CheckResult:
    name = "data_staleness"
    try:
        df = _load_parquet(_candle_path(data_dir, inst_id, bar))
        if df.empty:
            return _result(name, "FAIL", "no candle rows")
        last_ts = pd.to_datetime(df["ts"], utc=True).max()
        now = pd.Timestamp.now(tz=timezone.utc)
        age = now - last_ts
        if age > pd.Timedelta(hours=48):
            return _result(name, "FAIL", f"last candle is stale: {age}")
        return _result(name, "PASS", f"last candle age {age}")
    except Exception as exc:
        return _result(name, "FAIL", str(exc))


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def check_config_thresholds() -> CheckResult:
    name = "config_thresholds"
    try:
        strategies = _load_yaml(PROJECT_ROOT / "config" / "strategies.yaml")
        offenders = []
        for strategy_name, cfg in strategies.items():
            c_alpha = cfg.get("c_alpha") if isinstance(cfg, dict) else None
            if c_alpha is not None and float(c_alpha) > 100.0:
                offenders.append(f"{strategy_name}.c_alpha={c_alpha}")
        if offenders:
            return _result(name, "WARN", ", ".join(offenders))
        return _result(name, "PASS", "strategy thresholds within configured warning bands")
    except Exception as exc:
        return _result(name, "FAIL", str(exc))


def check_strategy_symbol_overlap() -> CheckResult:
    name = "strategy_symbol_overlap"
    try:
        settings = _load_yaml(PROJECT_ROOT / "config" / "settings.yaml")
        strategies = _load_yaml(PROJECT_ROOT / "config" / "strategies.yaml")
        system = settings.get("system", {})
        allowed = set(system.get("symbols", [])) | set(system.get("spot_symbols", []))
        missing: set[str] = set()
        for cfg in strategies.values():
            if not isinstance(cfg, dict):
                continue
            for key in ("symbols",):
                missing.update(s for s in cfg.get(key, []) if s not in allowed)
            for key in ("perp_symbol", "spot_symbol", "symbol_x", "symbol_y"):
                symbol = cfg.get(key)
                if symbol and symbol not in allowed:
                    missing.add(symbol)
        if missing:
            return _result(name, "FAIL", f"strategy symbols not in settings.yaml: {sorted(missing)}")
        return _result(name, "PASS", "strategy symbols are covered by settings.yaml")
    except Exception as exc:
        return _result(name, "FAIL", str(exc))


def _print_results(results: list[CheckResult]) -> None:
    for item in results:
        print(f"{item.status:4} {item.name}: {item.message}")


def _exit_code(results: list[CheckResult]) -> int:
    return 1 if any(item.status == "FAIL" for item in results) else 0


def run_checks(args: argparse.Namespace) -> list[CheckResult]:
    config_checks = [check_config_thresholds, check_strategy_symbol_overlap]
    if args.check_config_only:
        return [check() for check in config_checks]

    if args.all:
        settings = _load_yaml(PROJECT_ROOT / "config" / "settings.yaml")
        instruments = settings.get("market_data", {}).get("instruments") or settings.get("system", {}).get("symbols", [])
    else:
        instruments = [args.inst]

    results: list[CheckResult] = []
    for inst_id in instruments:
        checks: list[Callable[[], CheckResult]] = [
            lambda inst_id=inst_id: check_parquet_schema(args.data_dir, inst_id, args.bar),
            lambda inst_id=inst_id: check_candle_gaps(args.data_dir, inst_id, args.bar),
            lambda inst_id=inst_id: check_candle_ohlcv_sanity(args.data_dir, inst_id, args.bar),
            lambda inst_id=inst_id: check_funding_timestamps(args.data_dir, inst_id),
            lambda inst_id=inst_id: check_data_staleness(args.data_dir, inst_id, args.bar),
        ]
        for check in checks:
            result = check()
            result.name = f"{inst_id}.{result.name}"
            results.append(result)
    results.extend(check() for check in config_checks)
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Parquet/config validation pre-flight.")
    parser.add_argument("--data-dir", default="data/ticks")
    parser.add_argument("--inst", default="BTC-USDT-SWAP")
    parser.add_argument("--bar", default="1H")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--check-config-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    results = run_checks(args)
    _print_results(results)
    return _exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())

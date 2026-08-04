"""Deterministic seven-candidate paper/data limited research probe.

This is intentionally a ``limited_probe``.  It is not an ADR-0016 complete
strategy-finding round and never authorizes promotion, portable validation,
shadow, demo, or live use.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from backtesting.cpcv import CPCV
from backtesting.macro_state_probe import load_fomc_dates
from backtesting.pipeline_feasibility import (
    FeasibilityCheck,
    FeasibilityResult,
    evaluate_stage2_result,
    result_to_dict,
)
from backtesting.pipeline_power_screen import min_detectable_sharpe
from backtesting.universe_aliases import collapse_same_asset_aliases
from backtesting.walk_forward import WalkForward


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BATCH_ID = "paper_data_limited_probe_20260802"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results/paper_data_limited_probe_20260802"
SPEC_PATH = PROJECT_ROOT / "docs/superpowers/specs/2026-08-02-paper-data-limited-probe.md"
RECEIPT_PATH = PROJECT_ROOT / "tasks/2026-08-02-paper-data-limited-probe-preregistration-receipt.md"
LEDGER_PATH = PROJECT_ROOT / "docs/HYPOTHESIS_LEDGER.md"
REGISTRY_PATH = PROJECT_ROOT / "docs/EXPERIMENT_REGISTRY.md"
MEMBERSHIP_PATH = PROJECT_ROOT / "data/universe/universe_membership.parquet"
E031_REFERENCE = PROJECT_ROOT / "results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/family_minting_candidate.json"
E045_REFERENCE = PROJECT_ROOT / "results/idea_batch_20260713_taxonomy_003/f_xs_illiquidity/combo_daily_returns.csv"

FORMAL_START = pd.Timestamp("2020-01-01", tz="UTC")
FORMAL_END = pd.Timestamp("2026-07-29", tz="UTC")
XS_START = pd.Timestamp("2024-01-01", tz="UTC")
XS_END = pd.Timestamp("2026-06-17", tz="UTC")
WARMUP_DAYS = 120
ONE_WAY_COST = 4.0 / 10_000.0
CORRELATION_LIMIT = 0.70
MIN_REFERENCE_DAYS = 365
BTC = "BTC-USDT-SWAP"
ETH = "ETH-USDT-SWAP"


@dataclass(frozen=True)
class CandidateSpec:
    hypothesis_id: str
    experiment_id: str
    signal_ref: str
    family_id: str
    candidate_dir: str
    power_breadth: float
    existing_iteration: bool = False


CANDIDATES = (
    CandidateSpec("H-040", "E-077", "wiki_attention_trend", "F-WIKI-ATTENTION-TREND", "f_wiki_attention_trend", power_breadth=1.0),
    CandidateSpec("H-041", "E-078", "network_adoption", "F-NETWORK-ADOPTION", "f_network_adoption", power_breadth=1.0),
    CandidateSpec("H-042", "E-079", "usdt_depeg_reversal", "F-STABLECOIN-DEPEG-REVERSAL", "f_stablecoin_depeg_reversal", power_breadth=1.0),
    CandidateSpec("H-043", "E-080", "xs_salience", "F-XS-SALIENCE", "f_xs_salience", power_breadth=1.0),
    CandidateSpec("H-044", "E-081", "cftc_participant_regime", "F-CFTC-PARTICIPANT-REGIME", "f_cftc_participant_regime", power_breadth=1.0),
    CandidateSpec("H-045", "E-082", "fomc_yield_published_iteration", "F-MACRO-EVENT-DRIFT", "f_macro_event_drift", power_breadth=1.0, existing_iteration=True),
    CandidateSpec("H-046", "E-083", "macro_state_yieldcurve_iteration", "F-XASSET-MACRO-LEAD", "f_xasset_macro_lead", power_breadth=1.0, existing_iteration=True),
)
CANDIDATE_BY_ID = {candidate.hypothesis_id: candidate for candidate in CANDIDATES}

EXTERNAL_DATASETS = (
    "wiki_pageviews_bitcoin_en",
    "cm_btc_active_addresses",
    "cm_eth_active_addresses",
    "cm_usdt_price_usd",
    "cot_cme_btc",
    "cot_cme_eth",
    "dgs2",
    "dgs10",
    "vixcls",
    "dtwexbgs",
)


@dataclass
class ProbeInputs:
    close: pd.DataFrame
    funding: pd.DataFrame
    external: pd.DataFrame
    membership: pd.DataFrame
    references: dict[str, pd.Series]
    reference_errors: dict[str, str]


@dataclass
class CandidateEvaluation:
    spec: CandidateSpec
    stage2: FeasibilityResult
    targets: pd.DataFrame
    pnl: pd.DataFrame
    evidence: dict[str, Any]


@dataclass
class CandidateOutcome:
    spec: CandidateSpec
    evaluation: CandidateEvaluation | None
    stage3: dict[str, Any] | None
    error: BaseException | None


def _utc_index(index: Any) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(index, utc=True)).normalize()


def _normalise_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.astype(float).copy()
    result.index = _utc_index(result.index)
    return result[~result.index.duplicated(keep="last")].sort_index()


def _normalise_series(series: pd.Series) -> pd.Series:
    result = series.astype(float).copy()
    result.index = _utc_index(result.index)
    return result[~result.index.duplicated(keep="last")].sort_index()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sharpe(series: pd.Series, periods: float = 365.0) -> float:
    clean = series.dropna().astype(float)
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    return float(clean.mean() / std * math.sqrt(periods)) if std > 0.0 else 0.0


def available_scalar(rows: pd.DataFrame, dataset_id: str) -> pd.Series:
    """Return values indexed by the day they became available, not observed day."""

    if rows.empty:
        return pd.Series(dtype=float)
    selected = rows[
        (rows["dataset_id"] == dataset_id)
        & rows["published_at"].notna()
        & rows["value_num"].notna()
        & (rows["quality_status"].astype(str).str.lower() != "suspect")
    ].copy()
    if selected.empty:
        return pd.Series(dtype=float)
    selected["available_day"] = _utc_index(selected["published_at"])
    selected = selected.sort_values(["available_day", "observed_at"]).drop_duplicates(
        "available_day", keep="last"
    )
    return pd.Series(
        selected["value_num"].astype(float).to_numpy(),
        index=pd.DatetimeIndex(selected["available_day"]),
        dtype=float,
    ).sort_index()


def central_pnl(
    target_weights: pd.DataFrame,
    closes: pd.DataFrame,
    daily_funding: pd.DataFrame,
    *,
    one_way_cost: float = ONE_WAY_COST,
) -> pd.DataFrame:
    """Apply the frozen t+1, SUM-funding and one-way cost accounting contract."""

    prices = _normalise_frame(closes)
    target = _normalise_frame(target_weights).reindex(index=prices.index, columns=prices.columns).fillna(0.0)
    funding = _normalise_frame(daily_funding).reindex(index=prices.index, columns=prices.columns)
    positions = target.shift(1).fillna(0.0)
    returns = prices.pct_change(fill_method=None)
    active = positions.abs() > 0.0
    valid = ((~active) | returns.notna()).all(axis=1) & ((~active) | funding.notna()).all(axis=1)
    gross = (positions * returns.fillna(0.0)).sum(axis=1)
    funding_pnl = -(positions * funding.fillna(0.0)).sum(axis=1)
    turnover = positions.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = positions.iloc[0].abs().sum()
    cost = turnover * float(one_way_cost)
    net = gross + funding_pnl - cost
    gross, funding_pnl, net = gross.where(valid), funding_pnl.where(valid), net.where(valid)
    position_payload = positions.apply(
        lambda row: json.dumps(
            {key: float(value) for key, value in row.items() if abs(float(value)) > 0.0},
            sort_keys=True,
            separators=(",", ":"),
        ),
        axis=1,
    )
    return pd.DataFrame(
        {
            "gross": gross,
            "funding": funding_pnl,
            "cost": cost,
            "net": net,
            "positions": position_payload,
            "turnover": turnover,
        },
        index=prices.index,
    )


def salience_statistic(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    *,
    theta: float = 0.1,
    delta: float = 0.7,
) -> float:
    pair = pd.concat({"ri": asset_returns, "rm": market_returns}, axis=1).dropna()
    if pair.empty or theta <= 0.0 or not 0.0 < delta <= 1.0:
        return float("nan")
    sigma = (pair["ri"] - pair["rm"]).abs() / (
        pair["ri"].abs() + pair["rm"].abs() + theta
    )
    rank = sigma.rank(ascending=False, method="first")
    weights = delta ** (rank - 1.0)
    weights = weights / weights.sum()
    return float((weights * pair["ri"]).sum() - pair["ri"].mean())


def build_salience_targets(
    closes: pd.DataFrame,
    membership: pd.DataFrame,
    *,
    formation_days: int = 7,
    quantile: float = 0.2,
    theta: float = 0.1,
    delta: float = 0.7,
) -> pd.DataFrame:
    prices = _normalise_frame(closes)
    eligible = membership.reindex(index=prices.index, columns=prices.columns).fillna(False).astype(bool)
    returns = prices.pct_change(fill_method=None)
    market = returns.where(eligible).mean(axis=1)
    targets = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns, dtype=float)
    for day in prices.index[prices.index.weekday == 0]:
        symbols = eligible.columns[eligible.loc[day]].tolist()
        window = returns.loc[:day].tail(formation_days)
        if len(window) < formation_days or len(symbols) < 5:
            targets.loc[day] = 0.0
            continue
        scores = pd.Series(
            {
                symbol: salience_statistic(
                    window[symbol], market.reindex(window.index), theta=theta, delta=delta
                )
                for symbol in symbols
            },
            dtype=float,
        ).dropna().sort_values()
        n_leg = int(math.floor(len(scores) * quantile))
        if n_leg < 2 or len(scores) < 2 * n_leg:
            targets.loc[day] = 0.0
            continue
        targets.loc[day] = 0.0
        targets.loc[day, scores.index[:n_leg]] = 0.5 / n_leg
        targets.loc[day, scores.index[-n_leg:]] = -0.5 / n_leg
    return targets.ffill().fillna(0.0)


def _weekly_targets(signals: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    daily = signals.reindex(index).ffill(limit=7)
    targets = pd.DataFrame(np.nan, index=index, columns=signals.columns, dtype=float)
    monday = index.weekday == 0
    targets.loc[monday] = daily.loc[monday].to_numpy()
    return targets.ffill().fillna(0.0)


def _equal_asset_signs(signals: pd.DataFrame) -> pd.DataFrame:
    result = np.sign(signals.astype(float))
    return result * (1.0 / max(1, result.shape[1]))


def _membership_matrix(frame: pd.DataFrame, columns: Sequence[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    required = {"date", "symbol", "eligible"}
    if required.difference(frame.columns):
        raise ValueError(f"universe membership missing columns: {sorted(required.difference(frame.columns))}")
    selected = frame.copy()
    selected["date"] = _utc_index(selected["date"])
    selected = selected[selected["eligible"].astype(bool)]
    alias_rows = [
        {"date": day, "symbol": symbol, "value": True}
        for day, group in selected.groupby("date", sort=True)
        for symbol in collapse_same_asset_aliases(group["symbol"].astype(str), exchange="binance")
    ]
    collapsed = pd.DataFrame(alias_rows, columns=["date", "symbol", "value"])
    matrix = collapsed.pivot_table(
        index="date", columns="symbol", values="value", aggfunc="max", fill_value=False
    )
    return matrix.reindex(index=index, columns=list(columns), fill_value=False).astype(bool)


def _window(spec: CandidateSpec) -> tuple[pd.Timestamp, pd.Timestamp]:
    return (XS_START, XS_END) if spec.hypothesis_id == "H-043" else (FORMAL_START, FORMAL_END)


def _clip_book(
    targets: pd.DataFrame,
    close: pd.DataFrame,
    funding: pd.DataFrame,
    spec: CandidateSpec,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = _window(spec)
    index = close.index[(close.index >= start) & (close.index < end)]
    target = targets.reindex(index=index, columns=close.columns).fillna(0.0)
    pnl = central_pnl(target, close.reindex(index), funding.reindex(index))
    return target, pnl


def _wiki_book(inputs: ProbeInputs, spec: CandidateSpec) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    close = inputs.close[[BTC]].dropna(how="all")
    views = available_scalar(inputs.external, "wiki_pageviews_bitcoin_en")
    aligned = views.reindex(close.index).ffill(limit=3)
    attention_up = np.log(aligned.where(aligned > 0.0)).diff() > 0.0
    trend = np.sign(close[BTC] / close[BTC].rolling(7, min_periods=7).mean() - 1.0)
    targets = pd.DataFrame({BTC: trend.where(attention_up, 0.0)}, index=close.index).fillna(0.0)
    target, pnl = _clip_book(targets, close, inputs.funding[[BTC]], spec)
    return target, pnl, {"required_datasets": {"wiki_pageviews_bitcoin_en": 365}, "signal_input_active_days": int(aligned.notna().sum())}


def _network_book(inputs: ProbeInputs, spec: CandidateSpec) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    close = inputs.close[[BTC, ETH]].dropna(how="all")
    available = pd.DataFrame(
        {
            BTC: available_scalar(inputs.external, "cm_btc_active_addresses"),
            ETH: available_scalar(inputs.external, "cm_eth_active_addresses"),
        }
    ).reindex(close.index).ffill(limit=3)
    growth = np.log(available.where(available > 0.0)).diff(7)
    targets = _weekly_targets(_equal_asset_signs(growth), close.index)
    target, pnl = _clip_book(targets, close, inputs.funding[[BTC, ETH]], spec)
    return target, pnl, {
        "required_datasets": {"cm_btc_active_addresses": 365, "cm_eth_active_addresses": 365},
        "signal_input_active_days": int(available.dropna(how="any").shape[0]),
    }


def _depeg_book(inputs: ProbeInputs, spec: CandidateSpec) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    close = inputs.close[[BTC, ETH]].dropna(how="all")
    price = available_scalar(inputs.external, "cm_usdt_price_usd").reindex(close.index).ffill(limit=3)
    prior = price.shift(1)
    mean = prior.rolling(60, min_periods=60).mean()
    std = prior.rolling(60, min_periods=60).std().replace(0.0, np.nan)
    severe = ((price < 0.99) & ((price - mean) / std <= -3.0)).astype(float)
    targets = pd.DataFrame({BTC: severe * 0.5, ETH: severe * 0.5}, index=close.index)
    target, pnl = _clip_book(targets, close, inputs.funding[[BTC, ETH]], spec)
    return target, pnl, {
        "required_datasets": {"cm_usdt_price_usd": 365},
        "signal_input_active_days": int(price.notna().sum()),
        "severe_event_days": int(severe.sum()),
    }


def _salience_book(inputs: ProbeInputs, spec: CandidateSpec) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    start = XS_START - pd.Timedelta(days=14)
    close = inputs.close.loc[(inputs.close.index >= start) & (inputs.close.index < XS_END)].copy()
    membership = _membership_matrix(inputs.membership, close.columns, close.index)
    targets = build_salience_targets(close, membership)
    target, pnl = _clip_book(targets, close, inputs.funding.reindex(columns=close.columns), spec)
    return target, pnl, {
        "required_datasets": {},
        "signal_input_active_days": int(membership.any(axis=1).sum()),
        "median_pit_breadth": float(membership.sum(axis=1).median()),
    }


def _cot_ratio(rows: pd.DataFrame, dataset_id: str) -> pd.Series:
    if rows.empty:
        return pd.Series(dtype=float)
    selected = rows[
        (rows["dataset_id"] == dataset_id)
        & rows["published_at"].notna()
        & (rows["quality_status"].astype(str).str.lower() != "suspect")
    ].copy()
    values: list[tuple[pd.Timestamp, float]] = []
    for row in selected.sort_values(["published_at", "observed_at"]).to_dict("records"):
        fields = row.get("fields") or {}
        if isinstance(fields, str):
            fields = json.loads(fields)
        try:
            net, oi = float(fields["net_position"]), float(fields["open_interest"])
        except (KeyError, TypeError, ValueError):
            continue
        if oi > 0.0:
            values.append((pd.Timestamp(row["published_at"]).tz_convert("UTC").normalize(), net / oi))
    if not values:
        return pd.Series(dtype=float)
    series = pd.Series(dict(values), dtype=float).sort_index()
    return series[~series.index.duplicated(keep="last")]


def _cot_book(inputs: ProbeInputs, spec: CandidateSpec) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    close = inputs.close[[BTC, ETH]].dropna(how="all")
    releases = pd.DataFrame(
        {
            BTC: np.sign(_cot_ratio(inputs.external, "cot_cme_btc").diff(4)) * 0.5,
            ETH: np.sign(_cot_ratio(inputs.external, "cot_cme_eth").diff(4)) * 0.5,
        }
    )
    targets = releases.reindex(close.index).ffill(limit=14).fillna(0.0)
    target, pnl = _clip_book(targets, close, inputs.funding[[BTC, ETH]], spec)
    return target, pnl, {
        "required_datasets": {"cot_cme_btc": 52, "cot_cme_eth": 52},
        "signal_input_active_days": int(targets.abs().sum(axis=1).gt(0.0).sum()),
    }


def _fomc_book(inputs: ProbeInputs, spec: CandidateSpec) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    close = inputs.close[[BTC, ETH]].dropna(how="all")
    targets = pd.DataFrame(0.0, index=close.index, columns=[BTC, ETH])
    dgs = inputs.external[
        (inputs.external["dataset_id"] == "dgs2")
        & inputs.external["published_at"].notna()
        & inputs.external["value_num"].notna()
        & (inputs.external["quality_status"].astype(str).str.lower() != "suspect")
    ].copy()
    if not dgs.empty:
        dgs["observed_day"] = _utc_index(dgs["observed_at"])
        dgs["published_day"] = _utc_index(dgs["published_at"])
        dgs = dgs.sort_values(["observed_day", "published_at"]).drop_duplicates("observed_day", keep="last")
    usable_post = 0
    usable_pre = 0
    for decision in load_fomc_dates():
        day = pd.Timestamp(decision).tz_convert("UTC").normalize()
        if not FORMAL_START <= day < FORMAL_END:
            continue
        position = close.index.searchsorted(day)
        if 0 < position < len(close.index) and close.index[position] == day:
            prior_day = close.index[position - 1]
            targets.loc[prior_day, [BTC, ETH]] = 0.5
            usable_pre += 1
        observed = dgs[dgs.get("observed_day", pd.Series(dtype="datetime64[ns, UTC]")) == day]
        previous = dgs[dgs.get("observed_day", pd.Series(dtype="datetime64[ns, UTC]")) < day].tail(1)
        if observed.empty or previous.empty:
            continue
        change = float(observed.iloc[-1]["value_num"]) - float(previous.iloc[-1]["value_num"])
        direction = -float(np.sign(change)) * 0.5
        publication = pd.Timestamp(observed.iloc[-1]["published_day"])
        post_days = close.index[close.index > publication][:2]
        # Targets are set on publication day and the next day; central shift executes after publication.
        target_days = close.index[close.index >= publication][:2]
        if len(post_days) == 2 and len(target_days) == 2:
            targets.loc[target_days, [BTC, ETH]] = direction
            usable_post += 1
    target, pnl = _clip_book(targets, close, inputs.funding[[BTC, ETH]], spec)
    return target, pnl, {
        "required_datasets": {"dgs2": 365},
        "signal_input_active_days": usable_pre + 2 * usable_post,
        "usable_pre_events": usable_pre,
        "usable_post_events": usable_post,
        "calendar_source": _repo_path(PROJECT_ROOT / "tests/fixtures/fomc_decision_dates_2020_2026.csv"),
    }


def _macro_book(inputs: ProbeInputs, spec: CandidateSpec) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    close = inputs.close[[BTC, ETH]].dropna(how="all")
    state = pd.DataFrame(
        {
            "vix": available_scalar(inputs.external, "vixcls"),
            "dollar": available_scalar(inputs.external, "dtwexbgs"),
            "dgs10": available_scalar(inputs.external, "dgs10"),
            "dgs2": available_scalar(inputs.external, "dgs2"),
        }
    ).reindex(close.index).ffill(limit=7)
    state["curve"] = state["dgs10"] - state["dgs2"]
    factors = state[["vix", "dollar", "curve"]]
    prior = factors.shift(1)
    mean = prior.rolling(60, min_periods=60).mean()
    std = prior.rolling(60, min_periods=60).std().replace(0.0, np.nan)
    z = (factors - mean) / std
    risk_off_votes = (z["vix"] >= 1.0).astype(int) + (z["dollar"] >= 1.0).astype(int) + (z["curve"] <= -1.0).astype(int)
    complete = z.notna().all(axis=1)
    long_state = ((risk_off_votes < 2) & complete).astype(float)
    targets = pd.DataFrame({BTC: long_state * 0.5, ETH: long_state * 0.5}, index=close.index)
    target, pnl = _clip_book(targets, close, inputs.funding[[BTC, ETH]], spec)
    return target, pnl, {
        "required_datasets": {"vixcls": 365, "dtwexbgs": 365, "dgs10": 365, "dgs2": 365},
        "signal_input_active_days": int(complete.sum()),
        "risk_off_days": int((risk_off_votes.ge(2) & complete).sum()),
    }


BOOK_BUILDERS: dict[str, Callable[[ProbeInputs, CandidateSpec], tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]]] = {
    "H-040": _wiki_book,
    "H-041": _network_book,
    "H-042": _depeg_book,
    "H-043": _salience_book,
    "H-044": _cot_book,
    "H-045": _fomc_book,
    "H-046": _macro_book,
}


def _dataset_stats(rows: pd.DataFrame, dataset_id: str) -> dict[str, Any]:
    selected = rows[rows["dataset_id"] == dataset_id].copy() if not rows.empty else pd.DataFrame()
    if selected.empty:
        return {
            "rows": 0,
            "usable_rows": 0,
            "active_days": 0,
            "observed_start": None,
            "observed_end": None,
            "published_start": None,
            "published_end": None,
            "suspect_rows_excluded": 0,
        }
    suspect = selected["quality_status"].astype(str).str.lower() == "suspect"
    usable = selected[~suspect & selected["published_at"].notna()]
    return {
        "rows": int(len(selected)),
        "usable_rows": int(len(usable)),
        "active_days": int(_utc_index(usable["published_at"]).nunique()),
        "observed_start": pd.Timestamp(selected["observed_at"].min()).isoformat(),
        "observed_end": pd.Timestamp(selected["observed_at"].max()).isoformat(),
        "published_start": pd.Timestamp(usable["published_at"].min()).isoformat() if not usable.empty else None,
        "published_end": pd.Timestamp(usable["published_at"].max()).isoformat() if not usable.empty else None,
        "suspect_rows_excluded": int(suspect.sum()),
    }


def _data_check(
    spec: CandidateSpec,
    inputs: ProbeInputs,
    targets: pd.DataFrame,
    pnl: pd.DataFrame,
    evidence: Mapping[str, Any],
) -> FeasibilityCheck:
    requirements = dict(evidence.get("required_datasets", {}))
    datasets = {dataset: _dataset_stats(inputs.external, dataset) for dataset in requirements}
    deficient = [
        dataset
        for dataset, minimum in requirements.items()
        if datasets[dataset]["usable_rows"] < int(minimum)
    ]
    held = targets.shift(1).fillna(0.0).abs().sum(axis=1) > 0.0
    held_days = int(held.sum())
    valid_held_days = int((held & pnl["net"].notna()).sum())
    funding_coverage = valid_held_days / held_days if held_days else 0.0
    market_active_days = int(targets.index.nunique())
    signal_days = int(evidence.get("signal_input_active_days", 0))
    minimum_signal_days = 20 if spec.hypothesis_id == "H-045" else 365
    status = "PASS"
    reasons: list[str] = []
    if deficient:
        status = "FAIL"
        reasons.append(f"dataset minimum not met: {', '.join(deficient)}")
    if market_active_days < 365:
        status = "FAIL"
        reasons.append(f"market active days {market_active_days} < 365")
    if signal_days < minimum_signal_days:
        status = "FAIL"
        reasons.append(f"signal input active days {signal_days} < {minimum_signal_days}")
    if held_days == 0 or funding_coverage < 0.80:
        status = "FAIL"
        reasons.append(f"held-day price/funding coverage {funding_coverage:.6f} < 0.80")
    reason = "; ".join(reasons) if reasons else "required source, market, signal, and held-day funding coverage pass"
    return FeasibilityCheck(
        "data_availability",
        status,
        reason,
        {
            "formal_window": {"start": _window(spec)[0].isoformat(), "end_exclusive": _window(spec)[1].isoformat()},
            "datasets": datasets,
            "market_active_days": market_active_days,
            "signal_input_active_days": signal_days,
            "held_days": held_days,
            "valid_held_days": valid_held_days,
            "held_day_price_and_funding_coverage": funding_coverage,
            "candle_contract": "Binance source_primary canonical 1m daily last close; suspect excluded",
            "funding_contract": "funding_rates source=binance daily SUM; never AVG",
            **{key: value for key, value in evidence.items() if key != "required_datasets"},
        },
    )


def _correlation(candidate: pd.Series, reference: pd.Series) -> tuple[int, float | None]:
    joined = pd.concat({"candidate": candidate, "reference": reference}, axis=1).dropna()
    if len(joined) < MIN_REFERENCE_DAYS:
        return len(joined), None
    if joined["candidate"].nunique() < 2 or joined["reference"].nunique() < 2:
        return len(joined), None
    corr = float(joined["candidate"].corr(joined["reference"]))
    return len(joined), corr if math.isfinite(corr) else None


def _market_references(inputs: ProbeInputs, index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    close = inputs.close.reindex(index=index, columns=[BTC, ETH])
    returns = close.pct_change(fill_method=None)
    return {
        "btc_buy_hold": returns[BTC],
        "btc_eth_equal_weight_buy_hold": returns.mean(axis=1),
    }


def _distinctness_check(
    spec: CandidateSpec,
    inputs: ProbeInputs,
    candidate_returns: pd.Series,
) -> FeasibilityCheck:
    references = {**_market_references(inputs, candidate_returns.index), **inputs.references}
    comparisons: dict[str, Any] = {}
    invalid = dict(inputs.reference_errors)
    for name, reference in references.items():
        overlap, corr = _correlation(candidate_returns, reference)
        comparisons[name] = {"overlap_days": overlap, "correlation": corr}
        if corr is None or overlap < MIN_REFERENCE_DAYS:
            invalid[name] = f"reference overlap {overlap} < {MIN_REFERENCE_DAYS} or correlation unavailable"
    finite = [abs(float(row["correlation"])) for row in comparisons.values() if row["correlation"] is not None]
    max_abs = max(finite) if finite else None
    if spec.existing_iteration:
        return FeasibilityCheck(
            "distinctness",
            "PASS",
            "same-family iteration; correlation is advisory and cannot mint a new family",
            {
                "same_family": True,
                "advisory_max_abs_correlation": max_abs,
                "comparisons": comparisons,
                "reference_errors": invalid,
            },
        )
    passed = not invalid and max_abs is not None and max_abs < CORRELATION_LIMIT
    reason = (
        f"all frozen references available and max abs correlation {max_abs:.6f} < {CORRELATION_LIMIT:.2f}"
        if passed
        else "frozen reference missing/short or correlation threshold not cleared; fail closed"
    )
    return FeasibilityCheck(
        "distinctness",
        "PASS" if passed else "FAIL",
        reason,
        {
            "same_family": False,
            "correlation_limit": CORRELATION_LIMIT,
            "minimum_common_days": MIN_REFERENCE_DAYS,
            "max_abs_correlation": max_abs,
            "comparisons": comparisons,
            "reference_errors": invalid,
        },
    )


def _cost_check(pnl: pd.DataFrame) -> FeasibilityCheck:
    clean = pnl["net"].dropna().astype(float)
    net_sharpe = _sharpe(clean)
    weekly_mean = float(clean.resample("W-MON", label="right", closed="right").sum().mean()) if not clean.empty else 0.0
    passed = net_sharpe > 0.0 and weekly_mean > 0.0
    return FeasibilityCheck(
        "cost_after_edge",
        "PASS" if passed else "FAIL",
        f"net Sharpe={net_sharpe:.6f}; mean weekly net={weekly_mean:.8f}",
        {
            "annualized_net_sharpe": net_sharpe,
            "mean_weekly_net_return": weekly_mean,
            "one_way_fee_plus_slippage_bps": ONE_WAY_COST * 10_000.0,
            "full_entry_exit_cost_bps": ONE_WAY_COST * 20_000.0,
            "gross_sum": float(pnl["gross"].dropna().sum()),
            "funding_sum": float(pnl["funding"].dropna().sum()),
            "cost_sum": float(pnl["cost"].sum()),
            "net_sum": float(clean.sum()),
        },
    )


def _power_check(spec: CandidateSpec, targets: pd.DataFrame, pnl: pd.DataFrame) -> FeasibilityCheck:
    executed = targets.shift(1).fillna(0.0)
    active = executed.abs().sum(axis=1) > 0.0
    clean = pnl.loc[active, "net"].dropna().astype(float)
    years = max(1e-9, (_window(spec)[1] - _window(spec)[0]).days / 365.0)
    periods = max(1.0, len(clean) / years)
    breadth = spec.power_breadth
    plausible = _sharpe(clean, periods)
    skew = float(clean.skew()) if len(clean) >= 3 else 0.0
    kurtosis = float(clean.kurt()) + 3.0 if len(clean) >= 4 else 3.0
    if not math.isfinite(skew):
        skew = 0.0
    if not math.isfinite(kurtosis):
        kurtosis = 3.0
    floor: float | None = None
    error: str | None = None
    try:
        floor = min_detectable_sharpe(
            breadth=breadth,
            n_obs=len(clean),
            n_trials=1,
            skew=skew,
            kurtosis=kurtosis,
            periods_per_year=periods,
        )
    except ValueError as exc:
        error = str(exc)
    passed = floor is not None and plausible >= floor
    return FeasibilityCheck(
        "statistical_power",
        "PASS" if passed else "FAIL",
        (
            f"plausible net Sharpe {plausible:.6f} {'>=' if passed else '<'} minimum detectable {floor:.6f}"
            if floor is not None
            else f"power screen unavailable: {error}"
        ),
        {
            "breadth": breadth,
            "n_obs": len(clean),
            "n_trials": 1,
            "periods_per_year": periods,
            "sample_skew": skew,
            "sample_kurtosis": kurtosis,
            "plausible_net_sharpe": plausible,
            "min_detectable_sharpe": floor,
            "error": error,
        },
    )


def _validate_power_contract(specs: Sequence[CandidateSpec]) -> None:
    invalid = [spec.hypothesis_id for spec in specs if not math.isfinite(spec.power_breadth) or spec.power_breadth <= 0.0]
    if invalid:
        raise ValueError(f"candidate power_breadth must be finite and positive: {invalid}")


def evaluate_candidate(spec: CandidateSpec, inputs: ProbeInputs) -> CandidateEvaluation:
    targets, pnl, evidence = BOOK_BUILDERS[spec.hypothesis_id](inputs, spec)
    checks = (
        _data_check(spec, inputs, targets, pnl, evidence),
        _distinctness_check(spec, inputs, pnl["net"]),
        _cost_check(pnl),
        _power_check(spec, targets, pnl),
    )
    stage2 = FeasibilityResult(
        BATCH_ID,
        spec.signal_ref,
        spec.candidate_dir,
        spec.hypothesis_id,
        spec.family_id,
        checks,
    )
    return CandidateEvaluation(spec, stage2, targets, pnl, evidence)


def stage3_gate_checks(
    *,
    dsr: float,
    psr: float,
    nonzero_activity: bool,
    n_trials: Any,
    n_trials_provenance: Any,
) -> dict[str, bool]:
    checks = {
        "dsr_gate_passed": bool(dsr >= 0.95),
        "psr_gate_passed": bool(psr >= 0.95),
        "dsr_le_psr": bool(dsr <= psr + 1e-12),
        "nonzero_activity": bool(nonzero_activity),
        "n_trials_reconciled": bool(
            n_trials == 1 and n_trials_provenance == "caller_declared"
        ),
    }
    checks["statistical_gate_passed"] = all(checks.values())
    return checks


def run_stage3(evaluation: CandidateEvaluation) -> dict[str, Any]:
    """Run the fixed, no-grid Stage-3 protocol and retain raw CPCV returns."""

    returns = evaluation.pnl["net"].dropna().astype(float)
    if len(returns) < 6:
        raise ValueError("Stage 3 requires at least six valid daily returns")
    frame = pd.DataFrame({"fold_marker": 0.0}, index=returns.index)

    def fixed_returns(_train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        return returns.reindex(test.index).fillna(0.0)

    wf = WalkForward(is_days=365, oos_days=90).evaluate(frame, fixed_returns, periods=365)
    cpcv = CPCV(n_splits=6, k_test=2, embargo_pct=0.02, purge_size=1).evaluate(
        frame,
        fixed_returns,
        periods=365,
        n_trials=1,
        n_trials_provenance="caller_declared",
    )
    wf_sharpe = float(wf["oos_sharpe"].mean()) if not wf.empty else 0.0
    dsr = float(cpcv.get("dsr") or 0.0)
    psr = float(cpcv.get("psr") or 0.0)
    executed = evaluation.targets.shift(1).fillna(0.0)
    gate_checks = stage3_gate_checks(
        dsr=dsr,
        psr=psr,
        nonzero_activity=bool(executed.abs().sum(axis=1).gt(0.0).any()),
        n_trials=cpcv.get("n_trials"),
        n_trials_provenance=cpcv.get("n_trials_provenance"),
    )
    return {
        "schema_version": 1,
        "validation_mode": "fixed_signal_no_parameter_refit",
        "wf_oos_sharpe": wf_sharpe,
        "cpcv_oos_sharpe": float(cpcv.get("overall_oos_sharpe") or 0.0),
        "dsr": dsr,
        "psr": psr,
        **gate_checks,
        "n_trials": 1,
        "n_trials_provenance": cpcv.get("n_trials_provenance"),
        "cpcv": {
            "n_splits": 6,
            "k_test": 2,
            "embargo_pct": 0.02,
            "purge_size": 1,
            "n_combinations": cpcv.get("n_combinations"),
            "n_paths": cpcv.get("n_paths"),
            "path_sharpes": cpcv.get("path_sharpes", []),
            "path_return_periods": cpcv.get("path_return_periods"),
            "path_return_lengths": cpcv.get("path_return_lengths", []),
            "path_returns": cpcv.get("path_returns", []),
            "combined_return_periods": cpcv.get("combined_return_periods"),
            "combined_return_length": cpcv.get("combined_return_length"),
            "combined_returns": cpcv.get("combined_returns", []),
        },
        "promotion_gate_passed": False,
        "portable_validation_gate": False,
        "live_trading_authorized": False,
    }


def run_isolated_candidates(
    specs: Sequence[CandidateSpec],
    stage2_runner: Callable[[CandidateSpec], CandidateEvaluation],
    stage3_runner: Callable[[CandidateEvaluation], dict[str, Any]],
) -> list[CandidateOutcome]:
    """Run candidates independently; Stage-2 FAIL is a terminal Stage-3 stop."""

    outcomes: list[CandidateOutcome] = []
    for spec in specs:
        try:
            evaluation = stage2_runner(spec)
            if evaluate_stage2_result(evaluation.stage2) != "PASS":
                outcomes.append(CandidateOutcome(spec, evaluation, None, None))
                continue
            try:
                stage3 = stage3_runner(evaluation)
                outcomes.append(CandidateOutcome(spec, evaluation, stage3, None))
            except Exception as exc:  # per-candidate terminal isolation
                outcomes.append(CandidateOutcome(spec, evaluation, None, exc))
        except Exception as exc:  # per-candidate terminal isolation
            outcomes.append(CandidateOutcome(spec, None, None, exc))
    return outcomes


def _error_stage2(spec: CandidateSpec, exc: BaseException) -> FeasibilityResult:
    error = {"error_type": type(exc).__name__, "error": str(exc), "policy": "fail_closed_no_proxy_no_fabrication"}
    checks = (
        FeasibilityCheck("data_availability", "FAIL", "candidate evaluation error", error),
        FeasibilityCheck("distinctness", "FAIL", "not evaluated after candidate error", {"max_abs_correlation": None}),
        FeasibilityCheck("cost_after_edge", "FAIL", "not evaluated after candidate error", {"annualized_net_sharpe": None}),
        FeasibilityCheck("statistical_power", "FAIL", "not evaluated after candidate error", {"n_obs": 0, "n_trials": 1}),
    )
    return FeasibilityResult(BATCH_ID, spec.signal_ref, spec.candidate_dir, spec.hypothesis_id, spec.family_id, checks)


_RECEIPT_ROW = re.compile(r"\|\s*`?([^|`]+?)`?\s*\|\s*`?([0-9a-fA-F]{64})`?\s*\|")


def validate_preregistration(
    *,
    project_root: Path = PROJECT_ROOT,
    receipt_path: Path = RECEIPT_PATH,
) -> dict[str, Any]:
    """Verify frozen design/registry/source hashes before any output or DB read."""

    receipt = receipt_path.read_text(encoding="utf-8")
    recorded: dict[str, str] = {}
    for match in _RECEIPT_ROW.finditer(receipt):
        recorded[match.group(1).strip().replace("\\", "/")] = match.group(2).lower()
    required = (
        "docs/superpowers/specs/2026-08-02-paper-data-limited-probe.md",
        "docs/HYPOTHESIS_LEDGER.md",
        "docs/EXPERIMENT_REGISTRY.md",
        "backtesting/paper_signal_probe.py",
        "scripts/run_paper_signal_limited_probe.py",
    )
    missing = sorted(set(required).difference(recorded))
    if missing:
        raise ValueError(f"pre-registration receipt missing required hashes: {missing}")
    for relative in required:
        actual = file_sha256(project_root / relative)
        if actual != recorded[relative]:
            raise ValueError(f"pre-registration hash mismatch: {relative}")

    spec = (project_root / required[0]).read_text(encoding="utf-8").lower()
    ledger = (project_root / required[1]).read_text(encoding="utf-8")
    registry = (project_root / required[2]).read_text(encoding="utf-8")
    required_tokens = [
        "limited_probe",
        "complete_round",
        "false",
        "[2020-01-01, 2026-07-29)",
        "[2024-01-01, 2026-06-17)",
        *[candidate.hypothesis_id.lower() for candidate in CANDIDATES],
        *[candidate.experiment_id.lower() for candidate in CANDIDATES],
        *[candidate.signal_ref.lower() for candidate in CANDIDATES],
    ]
    if any(token not in spec for token in required_tokens):
        raise ValueError("limited-probe spec is missing a frozen identity, window, or incomplete-round token")
    for candidate in CANDIDATES:
        token = f"| {candidate.hypothesis_id} |"
        registry_rows = [
            line
            for line in registry.splitlines()
            if f"| {candidate.experiment_id} |" in line
        ]
        registered_path = f"results/paper_data_limited_probe_20260802/{candidate.candidate_dir}/"
        if token not in ledger or not registry_rows:
            raise ValueError(f"{candidate.hypothesis_id} must be pre-registered in ledger and registry")
        if candidate.hypothesis_id not in registry_rows[0] or registered_path not in registry_rows[0]:
            raise ValueError(
                f"{candidate.experiment_id} must bind {candidate.hypothesis_id} to {registered_path}"
            )
    return {
        "validated": True,
        "receipt_path": _repo_path(receipt_path),
        "receipt_sha256": file_sha256(receipt_path),
        "frozen_file_sha256": recorded,
    }


def _load_references() -> tuple[dict[str, pd.Series], dict[str, str]]:
    references: dict[str, pd.Series] = {}
    errors: dict[str, str] = {}
    try:
        payload = json.loads(E031_REFERENCE.read_text(encoding="utf-8"))
        signal = payload.get("signal")
        if not isinstance(signal, Mapping):
            raise ValueError("signal mapping missing")
        references["E031_funding_xs"] = _normalise_series(pd.Series(signal, dtype=float))
    except Exception as exc:
        errors["E031_funding_xs"] = f"{type(exc).__name__}: {exc}"
    try:
        frame = pd.read_csv(E045_REFERENCE, index_col="day")
        frame.index = _utc_index(frame.index)
        for column in frame.columns:
            references[f"E045_xs_illiquidity:{column}"] = _normalise_series(frame[column])
    except Exception as exc:
        errors["E045_xs_illiquidity"] = f"{type(exc).__name__}: {exc}"
    return references, errors


async def _load_inputs(conn: Any) -> ProbeInputs:
    membership = pd.read_parquet(MEMBERSHIP_PATH)
    required = {"date", "symbol", "eligible"}
    if required.difference(membership.columns):
        raise ValueError(f"universe membership missing columns: {sorted(required.difference(membership.columns))}")
    raw_symbols = membership.loc[
        membership["eligible"].astype(bool), "symbol"
    ].dropna().astype(str)
    symbols = sorted(
        set(collapse_same_asset_aliases(raw_symbols, exchange="binance")) | {BTC, ETH}
    )
    load_start = (FORMAL_START - pd.Timedelta(days=WARMUP_DAYS)).to_pydatetime()
    load_end = FORMAL_END.to_pydatetime()
    candle_rows = await conn.fetch(
        """
        SELECT inst_id, date_trunc('day', ts) AS day,
               (array_agg(close ORDER BY ts DESC))[1]::double precision AS close
        FROM canonical_candles
        WHERE inst_id=ANY($1::text[])
          AND bar='1m'
          AND source_primary='binance'
          AND quality_status!='suspect'
          AND ts >= $2 AND ts < $3
        GROUP BY inst_id, day
        ORDER BY day, inst_id
        """,
        symbols,
        load_start,
        load_end,
    )
    close_frame = pd.DataFrame([dict(row) for row in candle_rows])
    if close_frame.empty:
        raise ValueError("Binance source_primary canonical 1m query returned no daily closes")
    close_frame["day"] = pd.to_datetime(close_frame["day"], utc=True)
    close = close_frame.pivot(index="day", columns="inst_id", values="close").astype(float).sort_index()

    funding_rows = await conn.fetch(
        """
        SELECT inst_id, date_trunc('day', ts) AS day,
               SUM(funding_rate)::double precision AS funding_rate
        FROM funding_rates
        WHERE source='binance'
          AND inst_id=ANY($1::text[])
          AND ts >= $2 AND ts < $3
        GROUP BY inst_id, day
        ORDER BY day, inst_id
        """,
        symbols,
        load_start,
        load_end,
    )
    funding_frame = pd.DataFrame([dict(row) for row in funding_rows])
    if funding_frame.empty:
        funding = pd.DataFrame(index=close.index, columns=close.columns, dtype=float)
    else:
        funding_frame["day"] = pd.to_datetime(funding_frame["day"], utc=True)
        funding = funding_frame.pivot(index="day", columns="inst_id", values="funding_rate").astype(float).sort_index()
    funding = funding.reindex(index=close.index, columns=close.columns)

    external_rows = await conn.fetch(
        """
        SELECT dataset_id, observed_at, published_at, value_num, fields, quality_status
        FROM external_observations
        WHERE dataset_id=ANY($1::text[])
          AND published_at >= $2 AND published_at < $3
        ORDER BY dataset_id, published_at, observed_at
        """,
        list(EXTERNAL_DATASETS),
        load_start,
        load_end,
    )
    external = pd.DataFrame(
        [dict(row) for row in external_rows],
        columns=["dataset_id", "observed_at", "published_at", "value_num", "fields", "quality_status"],
    )
    if not external.empty:
        external["observed_at"] = pd.to_datetime(external["observed_at"], utc=True)
        external["published_at"] = pd.to_datetime(external["published_at"], utc=True)
    references, reference_errors = _load_references()
    return ProbeInputs(close, funding, external, membership, references, reference_errors)


def _write_outcome(output_root: Path, outcome: CandidateOutcome) -> dict[str, Any]:
    candidate_root = output_root / outcome.spec.candidate_dir
    candidate_root.mkdir(parents=True, exist_ok=False)
    stage2 = outcome.evaluation.stage2 if outcome.evaluation is not None else _error_stage2(outcome.spec, outcome.error or RuntimeError("unknown candidate error"))
    stage2_path = candidate_root / "stage2_feasibility.json"
    _write_json(stage2_path, result_to_dict(stage2))
    artifacts: dict[str, str] = {"stage2_feasibility": _repo_path(stage2_path)}

    if outcome.evaluation is not None:
        weights_path = candidate_root / "target_weights.csv"
        pnl_path = candidate_root / "daily_pnl.csv"
        weights = outcome.evaluation.targets.copy()
        weights.index.name = "day"
        weights.to_csv(weights_path)
        pnl = outcome.evaluation.pnl.copy()
        pnl.index.name = "day"
        pnl.to_csv(pnl_path)
        artifacts.update(target_weights=_repo_path(weights_path), daily_pnl=_repo_path(pnl_path))

    if outcome.stage3 is not None:
        stage3 = dict(outcome.stage3)
        cpcv = dict(stage3.pop("cpcv"))
        raw_path = candidate_root / "cpcv_path_returns.json"
        stage3_path = candidate_root / "stage3_validation.json"
        _write_json(
            raw_path,
            {
                "schema_version": 1,
                "batch_id": BATCH_ID,
                "hypothesis_id": outcome.spec.hypothesis_id,
                **cpcv,
            },
        )
        stage3["cpcv"] = {
            key: value
            for key, value in cpcv.items()
            if key not in {"path_returns", "combined_returns"}
        }
        stage3["raw_cpcv_returns_artifact"] = _repo_path(raw_path)
        _write_json(stage3_path, stage3)
        artifacts.update(stage3_validation=_repo_path(stage3_path), cpcv_path_returns=_repo_path(raw_path))

    stage2_status = evaluate_stage2_result(stage2)
    if outcome.error is not None:
        terminal_status, reason = "ERROR", f"{type(outcome.error).__name__}: {outcome.error}"
    elif stage2_status != "PASS":
        terminal_status, reason = "FAIL", "stage2_fail_stop_stage3_not_run"
    elif outcome.stage3 and outcome.stage3.get("statistical_gate_passed"):
        terminal_status, reason = "PASS", "stage3_dsr_psr_gate_pass_research_only"
    else:
        terminal_status, reason = "FAIL", "stage3_statistical_gate_fail"
    terminal = {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "round_type": "limited_probe",
        "complete_round": False,
        "hypothesis_id": outcome.spec.hypothesis_id,
        "experiment_id": outcome.spec.experiment_id,
        "signal_ref": outcome.spec.signal_ref,
        "family_id": outcome.spec.family_id,
        "existing_iteration": outcome.spec.existing_iteration,
        "stage2_status": stage2_status,
        "stage3_executed": outcome.stage3 is not None,
        "terminal_status": terminal_status,
        "terminal_reason": reason,
        "statistical_gate_passed": bool(outcome.stage3 and outcome.stage3.get("statistical_gate_passed")),
        "promotion_gate_passed": False,
        "portable_validation_gate": False,
        "live_trading_authorized": False,
        "artifacts": artifacts,
    }
    terminal_path = candidate_root / "terminal.json"
    _write_json(terminal_path, terminal)
    artifacts["terminal"] = _repo_path(terminal_path)
    hashes = {
        path.relative_to(candidate_root).as_posix(): file_sha256(path)
        for path in sorted(candidate_root.rglob("*"))
        if path.is_file() and path.name != "sha256.json"
    }
    hash_path = candidate_root / "sha256.json"
    _write_json(hash_path, hashes)
    terminal["artifacts"] = artifacts
    terminal["artifacts"]["sha256"] = _repo_path(hash_path)
    return terminal


async def run_limited_probe(*, dsn: str, output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"immutable output root already exists: {output_root}")
    _validate_power_contract(CANDIDATES)
    preregistration = validate_preregistration()
    output_root.mkdir(parents=True, exist_ok=False)

    load_error: BaseException | None = None
    inputs: ProbeInputs | None = None
    conn = None
    try:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        await conn.execute("SET default_transaction_read_only = on")
        await conn.execute("SET statement_timeout = '20min'")
        inputs = await _load_inputs(conn)
    except Exception as exc:
        load_error = exc
    finally:
        if conn is not None:
            await conn.close()

    def evaluate(spec: CandidateSpec) -> CandidateEvaluation:
        if load_error is not None:
            raise load_error
        if inputs is None:
            raise RuntimeError("probe inputs unavailable")
        return evaluate_candidate(spec, inputs)

    outcomes = run_isolated_candidates(CANDIDATES, evaluate, run_stage3)
    terminals = [_write_outcome(output_root, outcome) for outcome in outcomes]
    report = {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "round_type": "limited_probe",
        "complete_round": False,
        "incomplete_round_reason": "seven-candidate user-authorized limited probe; ADR-0016 complete-round quota and autonomous phases are not claimed",
        "pre_registration": preregistration,
        "formal_windows": {
            "default": {"start": FORMAL_START.isoformat(), "end_exclusive": FORMAL_END.isoformat()},
            "H-043": {"start": XS_START.isoformat(), "end_exclusive": XS_END.isoformat()},
        },
        "candidate_count": len(terminals),
        "terminal_counts": {
            status: sum(row["terminal_status"] == status for row in terminals)
            for status in ("PASS", "FAIL", "ERROR")
        },
        "candidates": terminals,
        "promotion_gate_passed": False,
        "portable_validation_gate": False,
        "live_trading_authorized": False,
    }
    _write_json(output_root / "limited_probe_report.json", report)
    return report

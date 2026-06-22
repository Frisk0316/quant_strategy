# Backtest Execution Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two user-selectable backtest execution choices, Strategy Fill and Dual Output, so strategy research is separated from realistic maker-execution stress.

**Architecture:** Reuse the existing research-only `fill_all_signals` and `fill_all_on_submit` path as the named `strategy_fill` profile. Keep the current maker replay as internal `realistic_execution`, and add a small dual-run wrapper that writes two normal run directories plus one comparison JSON. This avoids a new fill engine and keeps live, shadow, demo, and promotion gates unchanged.

**Tech Stack:** Python 3.12, pandas, Pydantic, FastAPI, Preact/HTM frontend, pytest, existing replay/artifact harness.

---

## Source Design

Implement the approved design in `docs/superpowers/specs/2026-06-22-backtest-execution-profiles-design.md`.

## Locate Before Edit

User-facing behavior changed:

- Backtest entrypoint exposes `Strategy Fill` and `Dual Output`.
- Artifacts explicitly say whether a run is idealized strategy research or realistic execution stress.
- Fill metrics distinguish submitted strategy-order fills from terminal liquidation fills.

Files permitted for this task:

- `backtesting/research_controls.py`
- `backtesting/replay.py`
- `scripts/run_replay_backtest.py`
- `scripts/run_validation_lab_signal_order_check.py`
- `src/okx_quant/api/routes_backtest.py`
- `frontend/view-config.js`
- `tests/unit/test_parameter_sweep.py`
- `tests/unit/test_backtesting.py`
- `tests/unit/test_backtest_request_exchange.py`
- `tests/integration/test_api_endpoints.py`
- `docs/change_manifests/2026-06-22-backtest-execution-profiles.md`
- `docs/DOMAIN_RULES.md`
- `docs/INVARIANTS.md`
- `docs/FEATURE_MAP.md`
- `docs/UI_MAP.md`
- `docs/DATA_FLOW.md`
- `docs/RUNBOOK.md`
- `docs/ai_collaboration.md`
- `docs/CURRENT_STATE.md`
- `docs/AI_HANDOFF.md`
- `docs/CHANGELOG_AI.md`
- `tasks/2026-06-22-validation-lab-report-context-handoff.md`
- `tasks/2026-06-22-validation-lab-report-session-handoff.md`

Files forbidden for this task:

- `research/`
- `src/okx_quant/strategies/`
- Existing `results/` artifact directories
- Live, shadow, demo, and deployment gate code except additive warning text in docs
- Differential-validation implementation

Rollback path:

- Revert the implementation commits for the files above.
- Existing historical artifacts remain untouched.
- Legacy `fill_all_signals` stays backward compatible during rollout.

Verification floor:

- Targeted pytest for research controls, replay metrics, CLI, API request handling.
- Frontend static check.
- Doc metadata/link/doc-impact checks.
- One BTC-USDT-SWAP Binance 1H Validation Lab rerun for `strategy_fill`.
- One dual-output replay smoke for MACD 12/26/9.

## File Responsibilities

- `backtesting/research_controls.py`: owns execution profile names, normalization, and profile-to-config controls.
- `backtesting/replay.py`: owns replay metrics and excludes terminal liquidation from submitted strategy-order fill counts.
- `scripts/run_replay_backtest.py`: owns CLI profile selection, dual-run orchestration, and comparison JSON.
- `scripts/run_validation_lab_signal_order_check.py`: owns report-specific BTC 1H signal-order validation runs with profile selection.
- `src/okx_quant/api/routes_backtest.py`: owns public API request field, validation, subprocess command construction, and dual-output job status.
- `frontend/view-config.js`: owns the two-choice UI picker and request payload.
- Docs and manifest files: own business-rule auditability and user interpretation.

---

### Task 1: Execution Profile Controls

**Files:**

- Modify: `tests/unit/test_parameter_sweep.py`
- Modify: `backtesting/research_controls.py`

- [ ] **Step 1: Add failing tests for profile normalization and controls**

In `tests/unit/test_parameter_sweep.py`, extend the `backtesting.research_controls` import block:

```python
from backtesting.research_controls import (
    EXECUTION_PROFILE_DUAL_OUTPUT,
    EXECUTION_PROFILE_REALISTIC,
    EXECUTION_PROFILE_STRATEGY_FILL,
    FILL_ALL_HARD_DRAWDOWN_PCT,
    FILL_ALL_MAX_DAILY_LOSS_PCT,
    FILL_ALL_SOFT_DRAWDOWN_PCT,
    ResearchControlError,
    apply_execution_profile_controls,
    apply_fill_all_signal_controls,
    apply_research_risk_overrides,
    normalize_execution_profile,
)
```

Add these tests after `test_fill_all_signal_controls_copy_config_without_mutating_base`:

```python
def test_normalize_execution_profile_defaults_to_strategy_fill():
    assert normalize_execution_profile(None) == EXECUTION_PROFILE_STRATEGY_FILL
    assert normalize_execution_profile("") == EXECUTION_PROFILE_STRATEGY_FILL
    assert normalize_execution_profile(" Strategy_Fill ") == EXECUTION_PROFILE_STRATEGY_FILL


def test_normalize_execution_profile_rejects_internal_realistic_for_public_surface():
    with pytest.raises(ResearchControlError):
        normalize_execution_profile(EXECUTION_PROFILE_REALISTIC)

    assert (
        normalize_execution_profile(EXECUTION_PROFILE_REALISTIC, allow_internal=True)
        == EXECUTION_PROFILE_REALISTIC
    )


def test_normalize_execution_profile_allows_public_dual_output():
    assert normalize_execution_profile("dual_output") == EXECUTION_PROFILE_DUAL_OUTPUT


def test_apply_execution_profile_strategy_fill_uses_existing_fill_all_controls():
    cfg = load_config(require_secrets=False)

    updated, controls = apply_execution_profile_controls(cfg, EXECUTION_PROFILE_STRATEGY_FILL)

    assert controls["execution_profile"] == EXECUTION_PROFILE_STRATEGY_FILL
    assert controls["idealized_fill"] is True
    assert controls["research_fill_all_signals"]["enabled"] is True
    assert updated.backtest.fill_all_signals is True
    assert updated.backtest.queue_fill_fraction == 1.0
    assert updated.risk.max_order_notional_usd >= cfg.risk.max_order_notional_usd
    assert cfg.backtest.fill_all_signals is False


def test_apply_execution_profile_realistic_keeps_config_unchanged():
    cfg = load_config(require_secrets=False)

    updated, controls = apply_execution_profile_controls(
        cfg,
        EXECUTION_PROFILE_REALISTIC,
        allow_internal=True,
    )

    assert updated is cfg
    assert controls == {
        "execution_profile": EXECUTION_PROFILE_REALISTIC,
        "idealized_fill": False,
    }


def test_apply_execution_profile_dual_must_be_orchestrated_by_runner():
    cfg = load_config(require_secrets=False)

    with pytest.raises(ResearchControlError):
        apply_execution_profile_controls(cfg, EXECUTION_PROFILE_DUAL_OUTPUT)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/unit/test_parameter_sweep.py::test_normalize_execution_profile_defaults_to_strategy_fill tests/unit/test_parameter_sweep.py::test_apply_execution_profile_strategy_fill_uses_existing_fill_all_controls -q
```

Expected: fails because `EXECUTION_PROFILE_STRATEGY_FILL`, `normalize_execution_profile`, and `apply_execution_profile_controls` do not exist.

- [ ] **Step 3: Add the minimal profile helpers**

In `backtesting/research_controls.py`, add `Literal` to the import:

```python
from typing import Any, Literal
```

Add this block after `RISK_OVERRIDE_KEYS`:

```python
EXECUTION_PROFILE_STRATEGY_FILL = "strategy_fill"
EXECUTION_PROFILE_REALISTIC = "realistic_execution"
EXECUTION_PROFILE_DUAL_OUTPUT = "dual_output"

ExecutionProfile = Literal["strategy_fill", "realistic_execution", "dual_output"]

PUBLIC_EXECUTION_PROFILES = {
    EXECUTION_PROFILE_STRATEGY_FILL,
    EXECUTION_PROFILE_DUAL_OUTPUT,
}

INTERNAL_EXECUTION_PROFILES = {
    EXECUTION_PROFILE_STRATEGY_FILL,
    EXECUTION_PROFILE_REALISTIC,
    EXECUTION_PROFILE_DUAL_OUTPUT,
}
```

Add these functions after `apply_fill_all_signal_controls`:

```python
def normalize_execution_profile(
    value: Any,
    *,
    allow_internal: bool = False,
    default: str = EXECUTION_PROFILE_STRATEGY_FILL,
) -> ExecutionProfile:
    """Normalize a backtest execution profile name.

    Public users choose Strategy Fill or Dual Output. The realistic profile is
    kept as an internal target so dual-output orchestration can run the current
    maker replay without exposing another end-user mode.
    """
    raw = str(value or default).strip().lower()
    profile = EXECUTION_PROFILE_STRATEGY_FILL if raw == "fill_all_signals" else raw
    allowed = INTERNAL_EXECUTION_PROFILES if allow_internal else PUBLIC_EXECUTION_PROFILES
    if profile not in allowed:
        public = ", ".join(sorted(allowed))
        raise ResearchControlError(f"unsupported execution profile: {profile}; expected one of {public}")
    return profile  # type: ignore[return-value]


def apply_execution_profile_controls(
    cfg: Any,
    profile: Any,
    *,
    allow_internal: bool = False,
) -> tuple[Any, dict[str, Any]]:
    """Apply config controls for a single replay execution profile."""
    normalized = normalize_execution_profile(profile, allow_internal=allow_internal)
    if normalized == EXECUTION_PROFILE_DUAL_OUTPUT:
        raise ResearchControlError("dual_output must be orchestrated by the runner")
    if normalized == EXECUTION_PROFILE_STRATEGY_FILL:
        updated, fill_all_controls = apply_fill_all_signal_controls(cfg, True)
        return updated, {
            "execution_profile": EXECUTION_PROFILE_STRATEGY_FILL,
            "idealized_fill": True,
            "research_fill_all_signals": fill_all_controls,
        }
    return cfg, {
        "execution_profile": EXECUTION_PROFILE_REALISTIC,
        "idealized_fill": False,
    }
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
python -m pytest tests/unit/test_parameter_sweep.py::test_normalize_execution_profile_defaults_to_strategy_fill tests/unit/test_parameter_sweep.py::test_normalize_execution_profile_rejects_internal_realistic_for_public_surface tests/unit/test_parameter_sweep.py::test_normalize_execution_profile_allows_public_dual_output tests/unit/test_parameter_sweep.py::test_apply_execution_profile_strategy_fill_uses_existing_fill_all_controls tests/unit/test_parameter_sweep.py::test_apply_execution_profile_realistic_keeps_config_unchanged tests/unit/test_parameter_sweep.py::test_apply_execution_profile_dual_must_be_orchestrated_by_runner -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git -c safe.directory=C:/quant_strategy add backtesting/research_controls.py tests/unit/test_parameter_sweep.py
git -c safe.directory=C:/quant_strategy commit -m "feat(backtest): add execution profile controls"
```

Expected: commit succeeds and stages only the two listed files.

---

### Task 2: Submitted Fill Metrics Exclude Terminal Liquidation

**Files:**

- Modify: `tests/unit/test_backtesting.py`
- Modify: `backtesting/replay.py`

- [ ] **Step 1: Add the failing metric regression test**

In `tests/unit/test_backtesting.py`, add this test near the other `ReplayRecorder` tests:

```python
def test_execution_metrics_exclude_terminal_liquidation_from_submitted_order_fill_count():
    recorder = ReplayRecorder(initial_equity=10_000.0)
    recorder.order_log.append({
        "ts": 1,
        "cl_ord_id": "strategy-entry",
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "px": 100.0,
        "sz": "1",
        "strategy": "unit",
        "notional_usd": 100.0,
    })
    recorder.fill_log.append({
        "ts": 2,
        "cl_ord_id": "terminal-close",
        "ord_id": "terminal-close",
        "inst_id": "BTC-USDT-SWAP",
        "side": "sell",
        "fill_px": 101.0,
        "fill_sz": 1.0,
        "fee": 0.0,
        "notional_usd": 101.0,
        "strategy": "terminal_liquidation",
        "state": "filled",
        "metadata": {"action": "terminal_liquidation"},
    })

    metrics = recorder._execution_metrics(pd.Series([0.0, 0.01], index=[1, 2]))

    assert metrics["real_fill_count"] == 1
    assert metrics["terminal_liquidation_fill_count"] == 1
    assert metrics["submitted_order_fill_count"] == 0
    assert metrics["orders_filled_count"] == 0
    assert metrics["fill_rate"] == 0.0
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
python -m pytest tests/unit/test_backtesting.py::test_execution_metrics_exclude_terminal_liquidation_from_submitted_order_fill_count -q
```

Expected: fails because `submitted_order_fill_count` is missing or `orders_filled_count` includes the terminal liquidation fill.

- [ ] **Step 3: Update replay execution metrics**

In `backtesting/replay.py`, add this helper method inside `ReplayRecorder`, before `_execution_metrics`:

```python
    @staticmethod
    def _is_terminal_liquidation_fill(row: dict[str, Any]) -> bool:
        metadata = row.get("metadata")
        return isinstance(metadata, dict) and metadata.get("action") == "terminal_liquidation"
```

In `ReplayRecorder._execution_metrics`, replace the current filled-id block:

```python
        real_fill_count = len(real_fills)
        filled_order_ids = {row.get("cl_ord_id") for row in real_fills if row.get("cl_ord_id")}
        orders_filled_count = len(filled_order_ids)
```

with:

```python
        real_fill_count = len(real_fills)
        submitted_order_ids = {
            row.get("cl_ord_id")
            for row in self.order_log
            if row.get("cl_ord_id")
        }
        terminal_liquidation_fills = [
            row for row in real_fills
            if self._is_terminal_liquidation_fill(row)
        ]
        submitted_fill_ids = {
            row.get("cl_ord_id")
            for row in real_fills
            if row.get("cl_ord_id") in submitted_order_ids
            and not self._is_terminal_liquidation_fill(row)
        }
        orders_filled_count = len(submitted_fill_ids)
        terminal_liquidation_fill_count = len(terminal_liquidation_fills)
```

In the returned metrics dict, add:

```python
            "submitted_order_fill_count": orders_filled_count,
            "terminal_liquidation_fill_count": terminal_liquidation_fill_count,
```

Keep the existing `real_fill_count` as total real fill rows, including terminal liquidation, because existing artifact readers already use it that way.

- [ ] **Step 4: Run replay metric tests**

Run:

```powershell
python -m pytest tests/unit/test_backtesting.py::test_execution_metrics_exclude_terminal_liquidation_from_submitted_order_fill_count tests/unit/test_backtesting.py::test_replay_terminal_liquidation_closes_open_swap_position -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git -c safe.directory=C:/quant_strategy add backtesting/replay.py tests/unit/test_backtesting.py
git -c safe.directory=C:/quant_strategy commit -m "fix(backtest): exclude terminal liquidation from submitted fill metrics"
```

Expected: commit succeeds and stages only the two listed files.

---

### Task 3: CLI Profiles, Dual Output, And Validation Lab Runner

**Files:**

- Modify: `tests/unit/test_backtesting.py`
- Modify: `scripts/run_replay_backtest.py`
- Modify: `scripts/run_validation_lab_signal_order_check.py`

- [ ] **Step 1: Add CLI tests for Strategy Fill and Dual Output**

In `tests/unit/test_backtesting.py`, add these tests after `test_run_replay_backtest_cli_enables_fill_all_signals`:

```python
def test_run_replay_backtest_cli_strategy_fill_profile_marks_result(monkeypatch, minimal_cfg, tmp_path):
    from scripts import run_replay_backtest as cli

    calls = {}
    saved = {}

    def fake_run_replay_backtest(**kwargs):
        calls.update(kwargs)
        return ReplayBacktestResult(
            returns=pd.Series([0.0], index=[1]),
            equity_curve=pd.Series([10_000.0], index=[1]),
            metrics={"total_return": 0.0, "fill_rate": 1.0, "real_fill_count": 1},
            order_log=pd.DataFrame([{"cl_ord_id": "o1"}]),
            fill_log=pd.DataFrame([{"cl_ord_id": "o1", "fill_sz": 1.0, "state": "filled", "fee": 0.0}]),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    def fake_save_backtest_artifacts(**kwargs):
        saved["validation"] = dict(kwargs["result"].validation)
        run_dir = tmp_path / kwargs["run_id"]
        run_dir.mkdir()
        return run_dir

    monkeypatch.setattr(cli, "load_config", lambda require_secrets=False: minimal_cfg)
    monkeypatch.setattr(cli, "run_replay_backtest", fake_run_replay_backtest)
    monkeypatch.setattr(cli, "save_backtest_artifacts", fake_save_backtest_artifacts)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_replay_backtest.py",
            "--strategy",
            "ma_crossover",
            "--execution-profile",
            "strategy_fill",
            "--save-artifacts",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "unit_profile",
        ],
    )

    cli.main()

    assert calls["cfg"].backtest.fill_all_signals is True
    assert saved["validation"]["execution_profile"] == "strategy_fill"
    assert saved["validation"]["idealized_fill"] is True


def test_run_replay_backtest_cli_dual_output_saves_two_runs_and_comparison(monkeypatch, minimal_cfg, tmp_path):
    from scripts import run_replay_backtest as cli

    saved_run_ids = []

    def fake_run_replay_backtest(**kwargs):
        is_strategy_fill = bool(kwargs["cfg"].backtest.fill_all_signals)
        total_return = 0.20 if is_strategy_fill else 0.05
        fill_rate = 1.0 if is_strategy_fill else 0.25
        return ReplayBacktestResult(
            returns=pd.Series([0.0, total_return], index=[1, 2]),
            equity_curve=pd.Series([10_000.0, 10_000.0 * (1 + total_return)], index=[1, 2]),
            metrics={
                "total_return": total_return,
                "max_drawdown": -0.01,
                "fill_rate": fill_rate,
                "submitted_order_count": 4,
                "real_fill_count": 4 if is_strategy_fill else 1,
                "submitted_order_fill_count": 4 if is_strategy_fill else 1,
                "terminal_liquidation_fill_count": 0,
            },
            order_log=pd.DataFrame([{"cl_ord_id": "o1"}]),
            fill_log=pd.DataFrame([{"cl_ord_id": "o1", "fill_sz": 1.0, "state": "filled", "fee": 0.0}]),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    def fake_save_backtest_artifacts(**kwargs):
        saved_run_ids.append(kwargs["run_id"])
        run_dir = tmp_path / kwargs["run_id"]
        run_dir.mkdir()
        return run_dir

    monkeypatch.setattr(cli, "load_config", lambda require_secrets=False: minimal_cfg)
    monkeypatch.setattr(cli, "run_replay_backtest", fake_run_replay_backtest)
    monkeypatch.setattr(cli, "save_backtest_artifacts", fake_save_backtest_artifacts)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_replay_backtest.py",
            "--strategy",
            "macd_crossover",
            "--execution-profile",
            "dual_output",
            "--save-artifacts",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "unit_dual",
        ],
    )

    cli.main()

    assert saved_run_ids == ["unit_dual_strategy_fill", "unit_dual_realistic_execution"]
    comparison = json.loads((tmp_path / "unit_dual_execution_comparison.json").read_text(encoding="utf-8"))
    assert comparison["execution_profile"] == "dual_output"
    assert comparison["strategy_fill_run_id"] == "unit_dual_strategy_fill"
    assert comparison["realistic_execution_run_id"] == "unit_dual_realistic_execution"
    assert comparison["deltas"]["strategy_minus_realistic_return"] == pytest.approx(0.15)
    assert comparison["deltas"]["strategy_minus_realistic_fill_rate"] == pytest.approx(0.75)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/unit/test_backtesting.py::test_run_replay_backtest_cli_strategy_fill_profile_marks_result tests/unit/test_backtesting.py::test_run_replay_backtest_cli_dual_output_saves_two_runs_and_comparison -q
```

Expected: fails because `--execution-profile`, module-level `save_backtest_artifacts`, and dual comparison output are not implemented.

- [ ] **Step 3: Refactor `scripts/run_replay_backtest.py` imports and parser**

In `scripts/run_replay_backtest.py`, replace the `backtesting.research_controls` import with:

```python
from backtesting.artifacts import build_run_id, save_backtest_artifacts
from backtesting.replay import run_replay_backtest, run_replay_validations
from backtesting.research_controls import (
    EXECUTION_PROFILE_DUAL_OUTPUT,
    EXECUTION_PROFILE_REALISTIC,
    EXECUTION_PROFILE_STRATEGY_FILL,
    apply_execution_profile_controls,
    apply_research_risk_overrides,
    normalize_execution_profile,
    summarize_risk_events,
)
```

Add this parser argument after `--fill-all-signals`:

```python
    parser.add_argument("--execution-profile", default=None,
                        choices=[
                            EXECUTION_PROFILE_STRATEGY_FILL,
                            EXECUTION_PROFILE_DUAL_OUTPUT,
                            EXECUTION_PROFILE_REALISTIC,
                        ],
                        help="Backtest execution profile. UI exposes strategy_fill and dual_output; realistic_execution is internal/debug.")
```

- [ ] **Step 4: Add CLI helper functions**

In `scripts/run_replay_backtest.py`, add this block after `BAR_PERIODS`:

```python
COMPARISON_KEYS = [
    "signal_count",
    "submitted_order_count",
    "real_fill_count",
    "submitted_order_fill_count",
    "terminal_liquidation_fill_count",
    "fill_rate",
    "total_return",
    "max_drawdown",
]


def _profile_from_args(args: argparse.Namespace) -> str:
    if args.execution_profile:
        return normalize_execution_profile(args.execution_profile, allow_internal=True)
    if args.fill_all_signals:
        return EXECUTION_PROFILE_STRATEGY_FILL
    return EXECUTION_PROFILE_STRATEGY_FILL


def _comparison_metrics(result) -> dict[str, float | int | None]:
    metrics = dict(getattr(result, "metrics", {}) or {})
    signal_log = getattr(result, "signal_log", []) or []
    out = {key: metrics.get(key) for key in COMPARISON_KEYS}
    out["signal_count"] = len(signal_log)
    return out


def _delta(left: dict, right: dict, key: str) -> float | None:
    try:
        return float(left.get(key)) - float(right.get(key))
    except (TypeError, ValueError):
        return None


def _write_execution_comparison(
    *,
    output_dir: str,
    base_run_id: str,
    strategy_fill_run_id: str,
    realistic_run_id: str,
    strategy_fill_result,
    realistic_result,
) -> Path:
    strategy_metrics = _comparison_metrics(strategy_fill_result)
    realistic_metrics = _comparison_metrics(realistic_result)
    payload = {
        "base_run_id": base_run_id,
        "execution_profile": EXECUTION_PROFILE_DUAL_OUTPUT,
        "strategy_fill_run_id": strategy_fill_run_id,
        "realistic_execution_run_id": realistic_run_id,
        "metrics": {
            EXECUTION_PROFILE_STRATEGY_FILL: strategy_metrics,
            EXECUTION_PROFILE_REALISTIC: realistic_metrics,
        },
        "deltas": {
            "strategy_minus_realistic_return": _delta(strategy_metrics, realistic_metrics, "total_return"),
            "strategy_minus_realistic_fill_rate": _delta(strategy_metrics, realistic_metrics, "fill_rate"),
        },
    }
    path = Path(output_dir) / f"{base_run_id}_execution_comparison.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
```

- [ ] **Step 5: Move the single-run body into `_run_profile_once`**

In `scripts/run_replay_backtest.py`, add this helper before `main()`:

```python
def _run_profile_once(
    *,
    args: argparse.Namespace,
    cfg,
    profile: str,
    output_dir: str,
    run_id: str | None,
    strategy_params: dict,
    instrument_specs: dict | None,
) -> tuple[object, Path | None]:
    profile_cfg, profile_controls = apply_execution_profile_controls(
        cfg,
        profile,
        allow_internal=True,
    )
    result = run_replay_backtest(
        strategy_names=args.strategy,
        cfg=profile_cfg,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
        bar=args.bar,
        periods=args.periods or BAR_PERIODS.get(args.bar, 365 * 24),
        instrument_specs=instrument_specs,
        liquidate_on_end=args.liquidate_on_end,
    )
    result.validation["execution_profile"] = profile
    result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)
    if profile_controls.get("idealized_fill"):
        result.validation["idealized_fill"] = True
        result.validation["research_fill_all_signals"] = profile_controls.get("research_fill_all_signals", {})

    validation_results = None
    if args.save_artifacts and args.validate:
        validation_results = run_replay_validations(
            strategy_names=args.strategy,
            cfg=profile_cfg,
            data_dir=args.data_dir,
            start=args.start,
            end=args.end,
            bar=args.bar,
            periods=args.periods or BAR_PERIODS.get(args.bar, 365 * 24),
            mode=args.validate,
            instrument_specs=instrument_specs,
            liquidate_on_end=args.liquidate_on_end,
            progress_callback=lambda update: print(
                f"PROGRESS:{int(update.get('progress', 85))}:{str(update.get('message') or 'Running replay validation')}",
                flush=True,
            ),
        )
        print("PROGRESS:99:Saving replay artifacts", flush=True)

    run_dir = None
    if args.save_artifacts:
        artifact_args = argparse.Namespace(**vars(args))
        artifact_args.execution_profile = profile
        artifact_args.strategy_params = strategy_params
        run_dir = save_backtest_artifacts(
            result=result,
            cfg=profile_cfg,
            args=artifact_args,
            output_dir=output_dir,
            run_id=run_id,
            strategy_names=args.strategy,
            start=args.start,
            end=args.end,
            bar=args.bar,
            validation_results=validation_results,
        )
    return result, run_dir
```

Then adjust `main()` so after strategy and instrument config are parsed it does:

```python
    profile = _profile_from_args(args)
    output_dir = str(PROJECT_ROOT / args.output_dir) if not Path(args.output_dir).is_absolute() else args.output_dir
    base_run_id = build_run_id(args.strategy, args.start, args.end, args.bar, args.run_id)

    print("PROGRESS:20:Running replay backtest", flush=True)
    if profile == EXECUTION_PROFILE_DUAL_OUTPUT:
        strategy_run_id = f"{base_run_id}_{EXECUTION_PROFILE_STRATEGY_FILL}"
        realistic_run_id = f"{base_run_id}_{EXECUTION_PROFILE_REALISTIC}"
        strategy_result, strategy_dir = _run_profile_once(
            args=args,
            cfg=cfg,
            profile=EXECUTION_PROFILE_STRATEGY_FILL,
            output_dir=output_dir,
            run_id=strategy_run_id,
            strategy_params=strategy_params,
            instrument_specs=instrument_specs,
        )
        realistic_result, realistic_dir = _run_profile_once(
            args=args,
            cfg=cfg,
            profile=EXECUTION_PROFILE_REALISTIC,
            output_dir=output_dir,
            run_id=realistic_run_id,
            strategy_params=strategy_params,
            instrument_specs=instrument_specs,
        )
        if args.save_artifacts:
            comparison_path = _write_execution_comparison(
                output_dir=output_dir,
                base_run_id=base_run_id,
                strategy_fill_run_id=strategy_run_id,
                realistic_run_id=realistic_run_id,
                strategy_fill_result=strategy_result,
                realistic_result=realistic_result,
            )
            print(f"Saved execution comparison to {comparison_path}")
        result = strategy_result
        run_dir = strategy_dir
    else:
        result, run_dir = _run_profile_once(
            args=args,
            cfg=cfg,
            profile=profile,
            output_dir=output_dir,
            run_id=args.run_id,
            strategy_params=strategy_params,
            instrument_specs=instrument_specs,
        )
```

Keep the existing summary printing after this block. Remove the old inline `from backtesting.artifacts import save_backtest_artifacts` import inside `main()` because the module-level import is now patched by tests.

- [ ] **Step 6: Add Validation Lab profile support**

In `scripts/run_validation_lab_signal_order_check.py`, replace the research-controls import with:

```python
from backtesting.research_controls import (
    EXECUTION_PROFILE_REALISTIC,
    EXECUTION_PROFILE_STRATEGY_FILL,
    apply_execution_profile_controls,
    summarize_risk_events,
)
```

In `_parse_args()`, add:

```python
    parser.add_argument(
        "--execution-profile",
        choices=[EXECUTION_PROFILE_STRATEGY_FILL, EXECUTION_PROFILE_REALISTIC],
        default=EXECUTION_PROFILE_STRATEGY_FILL,
    )
```

In `main()`, after `case_cfg = _case_config(cfg, strategy, params)`, add:

```python
        case_cfg, profile_controls = apply_execution_profile_controls(
            case_cfg,
            args.execution_profile,
            allow_internal=True,
        )
```

After `result = run_replay_backtest(...)`, add:

```python
        result.validation["execution_profile"] = args.execution_profile
        if profile_controls.get("idealized_fill"):
            result.validation["idealized_fill"] = True
            result.validation["research_fill_all_signals"] = profile_controls.get("research_fill_all_signals", {})
```

In `artifact_args = SimpleNamespace(...)`, add:

```python
            execution_profile=args.execution_profile,
```

In the final `report` dict, add:

```python
        "execution_profile": args.execution_profile,
```

- [ ] **Step 7: Run CLI tests**

Run:

```powershell
python -m pytest tests/unit/test_backtesting.py::test_run_replay_backtest_cli_strategy_fill_profile_marks_result tests/unit/test_backtesting.py::test_run_replay_backtest_cli_dual_output_saves_two_runs_and_comparison tests/unit/test_backtesting.py::test_run_replay_backtest_cli_enables_fill_all_signals -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit Task 3**

Run:

```powershell
git -c safe.directory=C:/quant_strategy add scripts/run_replay_backtest.py scripts/run_validation_lab_signal_order_check.py tests/unit/test_backtesting.py
git -c safe.directory=C:/quant_strategy commit -m "feat(backtest): add execution profile CLI modes"
```

Expected: commit succeeds and stages only the three listed files.

---

### Task 4: API Request And Job Status Support

**Files:**

- Modify: `tests/unit/test_backtest_request_exchange.py`
- Modify: `tests/integration/test_api_endpoints.py`
- Modify: `src/okx_quant/api/routes_backtest.py`

- [ ] **Step 1: Add request validation tests**

In `tests/unit/test_backtest_request_exchange.py`, add imports:

```python
import pytest
from fastapi import HTTPException
from okx_quant.api.routes_backtest import (
    RunBacktestRequest,
    _normalize_backtest_request,
    _normalize_exchange,
    _validate_backtest_request,
)
```

Add these tests:

```python
def test_backtest_request_defaults_execution_profile_to_strategy_fill():
    req = RunBacktestRequest(strategy="ma_crossover", symbols=["BTC-USDT-SWAP"])

    normalized = _normalize_backtest_request(req)
    _validate_backtest_request(normalized)

    assert normalized.execution_profile == "strategy_fill"


def test_backtest_request_accepts_public_dual_output_profile():
    req = RunBacktestRequest(
        strategy="ma_crossover",
        symbols=["BTC-USDT-SWAP"],
        execution_profile="dual_output",
    )

    normalized = _normalize_backtest_request(req)
    _validate_backtest_request(normalized)

    assert normalized.execution_profile == "dual_output"


def test_backtest_request_rejects_public_realistic_execution_profile():
    req = RunBacktestRequest(
        strategy="ma_crossover",
        symbols=["BTC-USDT-SWAP"],
        execution_profile="realistic_execution",
    )

    with pytest.raises(HTTPException) as exc:
        _validate_backtest_request(req)

    assert exc.value.status_code == 400
    assert "execution profile" in str(exc.value.detail)
```

- [ ] **Step 2: Add subprocess command test**

In `tests/integration/test_api_endpoints.py`, add this test after `test_parameter_sweep_endpoint_marks_job_done`:

```python
@pytest.mark.asyncio
async def test_backtest_run_passes_execution_profile_to_subprocess(client, monkeypatch, tmp_path):
    from okx_quant.api import routes_backtest

    seen_cmd = {}

    class FakeProc:
        returncode = 0
        stdout = iter(["PROGRESS:50:unit\n"])
        stderr = iter([])

        def wait(self):
            return 0

    def fake_popen(cmd, **kwargs):
        seen_cmd["cmd"] = cmd
        run_id = cmd[cmd.index("--run-id") + 1]
        out_dir = tmp_path / "results" / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.json").write_text(
            json.dumps({
                "run_id": run_id,
                "metrics": {},
                "validation": {"execution_profile": "dual_output"},
            }),
            encoding="utf-8",
        )
        return FakeProc()

    monkeypatch.setattr(routes_backtest, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(routes_backtest.subprocess, "Popen", fake_popen)

    response = await client.post(
        "/api/backtest/run",
        json={
            "strategy": "ma_crossover",
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1H",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "execution_profile": "dual_output",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = await client.get(f"/api/backtest/run/status/{job_id}")
    assert status.json()["status"] == "done"
    assert "--execution-profile" in seen_cmd["cmd"]
    assert seen_cmd["cmd"][seen_cmd["cmd"].index("--execution-profile") + 1] == "dual_output"
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/unit/test_backtest_request_exchange.py::test_backtest_request_defaults_execution_profile_to_strategy_fill tests/unit/test_backtest_request_exchange.py::test_backtest_request_accepts_public_dual_output_profile tests/unit/test_backtest_request_exchange.py::test_backtest_request_rejects_public_realistic_execution_profile tests/integration/test_api_endpoints.py::test_backtest_run_passes_execution_profile_to_subprocess -q
```

Expected: fails because API request model and command construction do not support `execution_profile`.

- [ ] **Step 4: Update API imports and request model**

In `src/okx_quant/api/routes_backtest.py`, replace the research-controls import with:

```python
from backtesting.research_controls import ResearchControlError, normalize_execution_profile, sanitize_risk_overrides
```

In `RunBacktestRequest`, add:

```python
    execution_profile: str = "strategy_fill"
```

- [ ] **Step 5: Normalize and validate the profile**

In `_normalize_backtest_request`, before `return normalized`, add:

```python
    if normalized.fill_all_signals:
        normalized.execution_profile = "strategy_fill"
```

In `_validate_backtest_request`, after `_resolve_data_dir(req.data_dir)`, add:

```python
    try:
        req.execution_profile = normalize_execution_profile(req.execution_profile)
    except ResearchControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

In `_request_parameters`, update the `"backtest"` dict to:

```python
        "backtest": {
            "execution_profile": req.execution_profile,
            "fill_all_signals": bool(req.fill_all_signals),
        },
```

- [ ] **Step 6: Pass the profile to the subprocess and surface dual status**

In `_run_backtest_job`, add to `cmd` after `--run-id`:

```python
            "--execution-profile",
            req.execution_profile,
```

After subprocess success, replace:

```python
        result_path = results_dir / run_id / "result.json"
```

with:

```python
        effective_run_id = run_id
        comparison_path = results_dir / f"{Path(run_id).name}_execution_comparison.json"
        comparison_payload: dict[str, Any] = {}
        if req.execution_profile == "dual_output" and comparison_path.exists():
            try:
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                effective_run_id = str(comparison_payload.get("strategy_fill_run_id") or f"{run_id}_strategy_fill")
            except Exception:
                effective_run_id = f"{run_id}_strategy_fill"
        result_path = results_dir / effective_run_id / "result.json"
```

In the final `_run_jobs[job_id].update({...})` success dict, add:

```python
            "run_id": effective_run_id,
            "base_run_id": run_id if req.execution_profile == "dual_output" else None,
            "execution_profile": req.execution_profile,
            "execution_comparison": str(comparison_path) if comparison_payload else None,
            "comparison_run_ids": {
                "strategy_fill": comparison_payload.get("strategy_fill_run_id"),
                "realistic_execution": comparison_payload.get("realistic_execution_run_id"),
            } if comparison_payload else None,
```

- [ ] **Step 7: Run API tests**

Run:

```powershell
python -m pytest tests/unit/test_backtest_request_exchange.py tests/integration/test_api_endpoints.py::test_backtest_run_passes_execution_profile_to_subprocess -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit Task 4**

Run:

```powershell
git -c safe.directory=C:/quant_strategy add src/okx_quant/api/routes_backtest.py tests/unit/test_backtest_request_exchange.py tests/integration/test_api_endpoints.py
git -c safe.directory=C:/quant_strategy commit -m "feat(api): expose backtest execution profiles"
```

Expected: commit succeeds and stages only the three listed files.

---

### Task 5: Frontend Two-Choice Picker

**Files:**

- Modify: `frontend/view-config.js`

- [ ] **Step 1: Add execution profile constants**

In `frontend/view-config.js`, after `RISK_OVERRIDE_SPECS`, add:

```javascript
const EXECUTION_PROFILE_OPTIONS = [
  {
    value: "strategy_fill",
    label: "Strategy Fill",
    hint: "Evaluate the strategy after signals become fills.",
  },
  {
    value: "dual_output",
    label: "Dual Output",
    hint: "Run Strategy Fill and realistic execution side by side.",
  },
];
```

- [ ] **Step 2: Replace fill-all state with profile state for run requests**

In `RunBacktestView`, replace:

```javascript
  const [fillAllSignals, setFillAllSignals] = useConfigState(false);
```

with:

```javascript
  const [executionProfile, setExecutionProfile] = useConfigState("strategy_fill");
  const fillAllSignals = executionProfile === "strategy_fill";
```

In `triggerBacktest()`, replace:

```javascript
      fill_all_signals: fillAllSignals,
```

with:

```javascript
      execution_profile: executionProfile,
      fill_all_signals: executionProfile === "strategy_fill",
```

In `triggerParameterSweep()`, keep the legacy sweep payload but derive it from the profile:

```javascript
        fill_all_signals: executionProfile === "strategy_fill",
```

- [ ] **Step 3: Replace the checkbox with a two-option select**

In the Research risk overrides field, replace the `<label>` block for `Fill all signals` with:

```javascript
              <div class="field" style=${{ marginTop: 10 }}>
                <div class="field-label">Execution profile</div>
                <select class="select" value=${executionProfile} onChange=${(e) => setExecutionProfile(e.target.value)}>
                  ${EXECUTION_PROFILE_OPTIONS.map((opt) => html`<option key=${opt.value} value=${opt.value}>${opt.label}</option>`)}
                </select>
                <div class="field-hint">
                  ${(EXECUTION_PROFILE_OPTIONS.find((opt) => opt.value === executionProfile) || EXECUTION_PROFILE_OPTIONS[0]).hint}
                </div>
              </div>
```

Do the same replacement in `ParameterSweepPanel`: remove the `fillAllSignals` and `setFillAllSignals` props from the component call and from the function argument list, then show this read-only hint before the estimate line:

```javascript
      <div class="field-hint">
        Sweep finalists use ${executionProfile === "strategy_fill" ? "Strategy Fill" : "realistic execution"} for reruns.
      </div>
```

Pass `executionProfile=${executionProfile}` into `ParameterSweepPanel`.

- [ ] **Step 4: Static-check the frontend**

Run:

```powershell
make frontend-check
```

Expected: frontend check passes. If `make` is unavailable on the machine, run the repo's documented fallback from `docs/RUNBOOK.md` and record the unavailable `make` command in the final report.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git -c safe.directory=C:/quant_strategy add frontend/view-config.js
git -c safe.directory=C:/quant_strategy commit -m "feat(frontend): add execution profile picker"
```

Expected: commit succeeds and stages only `frontend/view-config.js`.

---

### Task 6: Docs, Manifest, And Handoff Updates

**Files:**

- Create: `docs/change_manifests/2026-06-22-backtest-execution-profiles.md`
- Modify: `docs/DOMAIN_RULES.md`
- Modify: `docs/INVARIANTS.md`
- Modify: `docs/FEATURE_MAP.md`
- Modify: `docs/UI_MAP.md`
- Modify: `docs/DATA_FLOW.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/ai_collaboration.md`
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/AI_HANDOFF.md`
- Modify: `docs/CHANGELOG_AI.md`
- Modify: `tasks/2026-06-22-validation-lab-report-context-handoff.md`
- Modify: `tasks/2026-06-22-validation-lab-report-session-handoff.md`

- [ ] **Step 1: Create the Change Manifest**

Create `docs/change_manifests/2026-06-22-backtest-execution-profiles.md`:

```markdown
---
status: current
type: manifest
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Change Manifest: Backtest Execution Profiles

## Summary
Backtest runs now separate idealized strategy research from realistic maker-execution stress through named execution profiles. The change preserves existing realistic replay behavior internally and makes idealized artifacts explicit research-only evidence.

## Business rule(s) affected
R5 execution/fill semantics, R7 validation and promotion evidence, R8 risk and sizing interpretation for research-only runs.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A2 portfolio/execution, A5 backtesting, A8 API/UI behavior, A9 validation/reporting.

## Files changed
- backtesting/research_controls.py - adds profile names and profile-to-config controls.
- backtesting/replay.py - excludes terminal liquidation from submitted-order fill metrics.
- scripts/run_replay_backtest.py - adds profile CLI and dual-output orchestration.
- scripts/run_validation_lab_signal_order_check.py - runs report validation under a selected execution profile.
- src/okx_quant/api/routes_backtest.py - accepts the public profile field and maps dual output to job status.
- frontend/view-config.js - exposes Strategy Fill and Dual Output as the two user choices.
- tests/ - guards profile controls, metrics, CLI, and API behavior.
- docs/ - records business-rule and user-interpretation changes.

## Behavior delta
- Before: The main replay path mixed strategy signal quality with maker queue, cancel, lot/min rounding, and terminal liquidation effects unless users found the low-level `fill_all_signals` switch.
- After: Users select `Strategy Fill` for signal-to-position research or `Dual Output` for paired strategy-vs-realistic diagnostics.
- Money/risk impact: Research PnL can increase under `strategy_fill` because execution caps and queue constraints are intentionally bypassed. Such artifacts are marked `idealized_fill` and are not promotion evidence.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - live, shadow, demo, and default config files are unchanged.
- ADR: N/A - additive profile metadata and UI/API naming do not replace an existing architecture decision.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [ ] docs/DOMAIN_RULES.md - execution profile semantics.
- [ ] docs/INVARIANTS.md - idealized-fill and terminal-liquidation metric invariants.
- [ ] docs/FEATURE_MAP.md - backtest entrypoint ownership.
- [ ] docs/UI_MAP.md - two-choice execution profile picker.
- [ ] docs/DATA_FLOW.md - dual-output artifact flow.
- [ ] docs/RUNBOOK.md - CLI examples and verification.
- [ ] docs/ai_collaboration.md - promotion evidence caveat.

## Invariants / golden cases
- Invariants checked: idealized artifacts cannot be promotion evidence; terminal liquidation does not count as submitted strategy-order fill.
- Golden cases affected: BTC-USDT-SWAP Binance 1H Validation Lab signal-order checks.

## Tests / checks run
- python -m pytest tests/unit/test_parameter_sweep.py tests/unit/test_backtesting.py tests/unit/test_backtest_request_exchange.py tests/integration/test_api_endpoints.py -q
- make frontend-check
- make docs-impact
- python scripts/run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1 --run-suffix maxord250_pospct1_strategyfill --execution-profile strategy_fill

## Risks and rollback
- Risks: UI users may compare idealized and realistic runs without reading caveats; dual output doubles replay runtime; parameter sweep remains single-profile and does not produce paired comparisons.
- Rollback: Revert the implementation commits and remove the new manifest/docs entries. Historical results remain valid because no artifact migration occurs.

## Approval
- Human approval required: yes - approved in chat on 2026-06-22 after reviewing the design direction.
```

- [ ] **Step 2: Update domain and invariant docs**

Add or update rules in `docs/DOMAIN_RULES.md`:

```markdown
### Execution Profiles

- `strategy_fill` is a research-only execution profile that uses immediate full fills for submitted signal orders and lifts research-only caps through copied config objects.
- `realistic_execution` is the current maker replay with queue, cancel latency, lot/min rounding, post-only behavior, and terminal liquidation.
- `dual_output` runs both profiles with the same data, symbols, strategy parameters, and exchange, then writes a small comparison artifact.
- `strategy_fill` and `dual_output` are not live-readiness or promotion evidence.
```

Add or update invariants in `docs/INVARIANTS.md`:

```markdown
### Backtest Execution Profiles

- Any artifact with `validation.idealized_fill = true` must also identify its execution profile as `strategy_fill` or be nested under a `dual_output` comparison.
- Submitted strategy-order fill counts exclude fills whose metadata action is `terminal_liquidation`.
- Dual-output comparison metrics must include both run IDs and must not overwrite either child run's normal artifacts.
```

- [ ] **Step 3: Update feature, UI, data-flow, runbook, and collaboration docs**

Update `docs/FEATURE_MAP.md` under the backtesting/API/UI areas with:

```markdown
- Execution profiles: `backtesting/research_controls.py`, `scripts/run_replay_backtest.py`, `src/okx_quant/api/routes_backtest.py`, and `frontend/view-config.js` own the Strategy Fill / Dual Output path.
```

Update `docs/UI_MAP.md` near the backtest configuration view:

```markdown
- Run Backtest execution profile picker shows only `Strategy Fill` and `Dual Output`.
- `Strategy Fill` sends `execution_profile=strategy_fill`.
- `Dual Output` sends `execution_profile=dual_output`; the job opens the strategy-fill child run by default and carries comparison metadata.
```

Update `docs/DATA_FLOW.md` in the backtest artifact flow:

```markdown
Backtest profile flow:
UI/API -> scripts/run_replay_backtest.py -> apply_execution_profile_controls -> replay -> save_backtest_artifacts.
For `dual_output`, the script writes `<base>_strategy_fill/`, `<base>_realistic_execution/`, and `<base>_execution_comparison.json`.
```

Update `docs/RUNBOOK.md` with:

```markdown
Strategy Fill:
python scripts/run_replay_backtest.py --strategy macd_crossover --symbol BTC-USDT-SWAP --exchange binance --bar 1H --strategy-params "{\"fast_span\":12,\"slow_span\":26,\"signal_span\":9}" --execution-profile strategy_fill --save-artifacts --run-id manual_macd_strategy_fill

Dual Output:
python scripts/run_replay_backtest.py --strategy macd_crossover --symbol BTC-USDT-SWAP --exchange binance --bar 1H --strategy-params "{\"fast_span\":12,\"slow_span\":26,\"signal_span\":9}" --execution-profile dual_output --save-artifacts --run-id manual_macd_dual
```

Update `docs/ai_collaboration.md` deployment gate language:

```markdown
Artifacts marked `idealized_fill`, `strategy_fill`, or `dual_output` are research diagnostics only. They cannot be used as edge, promotion, or live-readiness evidence without the normal realistic replay, differential validation, shadow/demo, and human approval gates.
```

- [ ] **Step 4: Update handoff and current-state docs**

Append a concise entry to `docs/CHANGELOG_AI.md`:

```markdown
## 2026-06-22 - Backtest Execution Profiles

- Added implementation plan for Strategy Fill and Dual Output execution profiles.
- Planned Strategy Fill as a first-class name for the existing research-only fill-all path.
- Planned Dual Output as paired Strategy Fill plus realistic maker replay artifacts.
```

Update `docs/CURRENT_STATE.md` and `docs/AI_HANDOFF.md` with:

```markdown
Backtest execution profiles are being implemented from `docs/superpowers/specs/2026-06-22-backtest-execution-profiles-design.md` and `docs/superpowers/plans/2026-06-22-backtest-execution-profiles.md`. The intended user choices are `Strategy Fill` and `Dual Output`; live/demo/shadow gates remain unchanged.
```

Update both task handoff files with:

```markdown
Human Learning Notes:
- `Strategy Fill` answers whether strategy signals perform after becoming positions.
- `realistic_execution` answers how much of that signal stream survives the current maker replay assumptions.
- `dual_output` compares both; passing it is diagnostic, not live-readiness approval.
```

- [ ] **Step 5: Run docs checks**

Run:

```powershell
python scripts/docs/check_doc_metadata.py
python scripts/docs/check_feature_map_links.py
python scripts/docs/check_doc_impact.py
```

Expected: commands pass or report only pre-existing warnings. If `make` is available, also run:

```powershell
make docs-impact
```

Expected: advisory or strict impact check recognizes the manifest in the changeset.

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git -c safe.directory=C:/quant_strategy add docs/change_manifests/2026-06-22-backtest-execution-profiles.md docs/DOMAIN_RULES.md docs/INVARIANTS.md docs/FEATURE_MAP.md docs/UI_MAP.md docs/DATA_FLOW.md docs/RUNBOOK.md docs/ai_collaboration.md docs/CURRENT_STATE.md docs/AI_HANDOFF.md docs/CHANGELOG_AI.md tasks/2026-06-22-validation-lab-report-context-handoff.md tasks/2026-06-22-validation-lab-report-session-handoff.md
git -c safe.directory=C:/quant_strategy commit -m "docs(backtest): document execution profile semantics"
```

Expected: commit succeeds and stages only listed docs/task files.

---

### Task 7: End-To-End Verification And User Evidence

**Files:**

- Read generated artifacts under `results/`
- No source modifications in this task unless a test exposes a defect

- [ ] **Step 1: Run targeted test suite**

Run:

```powershell
python -m pytest tests/unit/test_parameter_sweep.py tests/unit/test_backtesting.py tests/unit/test_backtest_request_exchange.py tests/integration/test_api_endpoints.py -q
```

Expected: tests pass. If unrelated pre-existing tests fail, isolate the new tests listed in Tasks 1-4 and report the unrelated failures separately.

- [ ] **Step 2: Run frontend and docs checks**

Run:

```powershell
make frontend-check
python scripts/docs/check_doc_metadata.py
python scripts/docs/check_feature_map_links.py
python scripts/docs/check_doc_impact.py
git diff --check
```

Expected: checks pass or report only pre-existing warnings.

- [ ] **Step 3: Run BTC-USDT-SWAP Binance 1H Strategy Fill validation**

Run:

```powershell
python scripts/run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1 --run-suffix maxord250_pospct1_strategyfill --execution-profile strategy_fill
```

Expected:

- The JSON output path is `results/validation_lab_signal_order_check_20260622_maxord250_pospct1_strategyfill.json`.
- Each case has `execution_profile = strategy_fill` in child artifact `result.json`.
- MA/EMA/MACD submitted orders and fills are no longer dominated by maker queue or fat-finger research caps.
- `validation.idealized_fill = true` appears in Strategy Fill artifacts.

- [ ] **Step 4: Run MACD Dual Output smoke**

Run:

```powershell
python scripts/run_replay_backtest.py --strategy macd_crossover --symbol BTC-USDT-SWAP --exchange binance --bar 1H --strategy-params "{\"fast_span\":12,\"slow_span\":26,\"signal_span\":9}" --risk-overrides "{\"max_order_notional_usd\":250,\"max_pos_pct_equity\":1}" --execution-profile dual_output --save-artifacts --run-id validation_lab_macd_btc_binance_1h_20260622_dual
```

Expected generated artifacts:

- `results/validation_lab_macd_btc_binance_1h_20260622_dual_strategy_fill/result.json`
- `results/validation_lab_macd_btc_binance_1h_20260622_dual_realistic_execution/result.json`
- `results/validation_lab_macd_btc_binance_1h_20260622_dual_execution_comparison.json`

Expected comparison JSON fields:

```json
{
  "execution_profile": "dual_output",
  "strategy_fill_run_id": "validation_lab_macd_btc_binance_1h_20260622_dual_strategy_fill",
  "realistic_execution_run_id": "validation_lab_macd_btc_binance_1h_20260622_dual_realistic_execution",
  "metrics": {
    "strategy_fill": {},
    "realistic_execution": {}
  },
  "deltas": {
    "strategy_minus_realistic_return": 0.0,
    "strategy_minus_realistic_fill_rate": 0.0
  }
}
```

The numeric delta values may differ from the example, but the keys must exist.

- [ ] **Step 5: Summarize evidence for the user**

Report:

```text
Strategy Fill answers signal-to-position research PnL and is idealized.
Realistic execution answers maker replay fillability and execution friction.
Dual Output compares both with the same strategy/data/symbol window.
Passing Strategy Fill means signals can be transformed into positions under idealized research assumptions.
Passing Dual Output means the gap between idealized strategy behavior and the current realistic execution model is measured, not that the strategy is live-ready.
```

- [ ] **Step 6: Commit verification handoff updates if source/docs changed during verification**

If verification produced only `results/` artifacts and no tracked source/doc changes, do not commit. If defects required tracked fixes, commit only those files:

```powershell
git -c safe.directory=C:/quant_strategy status --short
git -c safe.directory=C:/quant_strategy add <tracked files changed by the fix>
git -c safe.directory=C:/quant_strategy commit -m "fix(backtest): stabilize execution profile verification"
```

Expected: no unrelated dirty files are staged.

---

## Self-Review

Spec coverage:

- User two-choice control: Task 5.
- `strategy_fill` using existing fill-all path: Tasks 1 and 3.
- Internal `realistic_execution`: Tasks 1 and 3.
- `dual_output` paired artifacts and comparison JSON: Task 3.
- Terminal liquidation excluded from submitted fill count: Task 2.
- API/UI shape: Tasks 4 and 5.
- Validation Lab rerun: Task 7.
- Research-only caveats and manifest: Task 6.

Placeholder scan:

- No red-flag placeholder strings are intentionally used in implementation instructions.
- Every code-changing step includes concrete code or exact replacement text.

Type and name consistency:

- Public values are `strategy_fill` and `dual_output`.
- Internal value is `realistic_execution`.
- Comparison keys match the approved design: `signal_count`, `submitted_order_count`, `real_fill_count`, `submitted_order_fill_count`, `terminal_liquidation_fill_count`, `fill_rate`, `total_return`, `max_drawdown`, `strategy_minus_realistic_return`, and `strategy_minus_realistic_fill_rate`.


import { h, Fragment } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
const useConfigState = useState;
const useConfigEffect = useEffect;

const { Sparkline } = window.Charts;

const BAR_PERIODS = {
  "1m": 525600, "3m": 175200, "5m": 105120, "15m": 35040,
  "30m": 17520, "1H": 8760, "2H": 4380, "4H": 2190, "1D": 365,
};
const TECHNICAL_STRATEGIES = new Set(["ma_crossover", "ema_crossover", "macd_crossover"]);
const EXTERNAL_STRATEGIES = new Set(["fear_greed_sentiment", "cme_gap_fill"]);
const PARAMETERIZED_STRATEGIES = new Set([...TECHNICAL_STRATEGIES, ...EXTERNAL_STRATEGIES]);
const STRATEGY_PARAM_DEFAULTS = {
  ma_crossover: { fast_window: 20, slow_window: 50 },
  ema_crossover: { fast_span: 20, slow_span: 50 },
  macd_crossover: { fast_span: 12, slow_span: 26, signal_span: 9 },
  fear_greed_sentiment: { dataset_id: "fear_greed_btc", max_age_seconds: 172800, extreme_fear_label: "Extreme Fear", extreme_fear_threshold: 25, exit_value_threshold: 51 },
  cme_gap_fill: {
    dataset_id: "cme_btc_yfinance",
    max_age_seconds: 604800,
    min_gap_bps: 25,
    max_hold_days: 2,
    stop_loss_bps_mult: 1.5,
    max_gap_bps: 0,
    allow_direction: "long_only",
  },
};
const SWEEP_PARAM_DEFAULTS = {
  ma_crossover: { fast_window: "7~20", slow_window: "21~100" },
  ema_crossover: { fast_span: "7~20", slow_span: "21~100" },
  macd_crossover: { fast_span: "8, 12", slow_span: "21, 26, 50", signal_span: "9" },
};
const RISK_OVERRIDE_DEFAULTS = {
  max_order_notional_usd: "",
  max_pos_pct_equity: "",
  max_leverage: "",
};
const RISK_OVERRIDE_SPECS = [
  {
    key: "max_order_notional_usd",
    label: "Max order USD",
    placeholder: "e.g. 5000",
    step: "50",
    help: "Per-order notional cap in USD. Orders above this amount are blocked as fat_finger; raising it can allow high-price exits and rebalances.",
  },
  {
    key: "max_pos_pct_equity",
    label: "Max pos pct",
    placeholder: "e.g. 0.75",
    step: "0.05",
    help: "Max position notional as a fraction of equity. 0.30 means current position plus the new order cannot exceed 30% of equity, except reduce-only exits.",
  },
  {
    key: "max_leverage",
    label: "Max leverage",
    placeholder: "e.g. 3",
    step: "0.5",
    help: "Research leverage ceiling, expressed as gross notional divided by equity. Kept with the copied risk config and dashboard parity; order blocking is mainly driven by max order USD and max pos pct.",
  },
];
const SWEEP_PARAM_SPECS = {
  ma_crossover: [
    ["fast_window", "fast"],
    ["slow_window", "slow"],
  ],
  ema_crossover: [
    ["fast_span", "fast"],
    ["slow_span", "slow"],
  ],
  macd_crossover: [
    ["fast_span", "fast"],
    ["slow_span", "slow"],
    ["signal_span", "signal"],
  ],
};
const SWEEP_ROWS_PER_DAY = {
  "1m": 1440, "3m": 480, "5m": 288, "15m": 96,
  "30m": 48, "1H": 24, "2H": 12, "4H": 6, "1D": 1,
};
const SWEEP_SECONDS_PER_EVENT = {
  ma_crossover: 0.0018,
  ema_crossover: 0.00020,
  macd_crossover: 0.00025,
};
const DERIVABLE_FROM_1M_BARS = new Set(["3m", "5m", "15m", "30m", "1H", "2H", "4H", "6H", "12H", "1D"]);

const todayUtc = new Date();
todayUtc.setUTCHours(0, 0, 0, 0);
const yesterday = new Date(todayUtc - 86400000).toISOString().slice(0, 10);
const FETCH_QUERY_INPUT_ID = "market-data-fetch-query";
const FETCH_EXCHANGE_SELECT_ID = "market-data-fetch-exchange";
const FETCH_BAR_SELECT_ID = "market-data-fetch-bar";
const FETCH_START_INPUT_ID = "market-data-fetch-start";
const FETCH_END_INPUT_ID = "market-data-fetch-end";
let marketDataInstrumentSearchSeq = 0;
const FETCH_TERMINAL_STATUSES = new Set(["done", "error", "cancelled"]);

const fmtPct = (v, d = 2) => (v == null || !isFinite(v) ? "-" : `${(v * 100).toFixed(d)}%`);
const fmtNum = (v, d = 2) => (v == null || !isFinite(v) ? "-" : v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }));
const fmtUSD = (v, d = 2) => (v == null || !isFinite(v) ? "-" : `$${fmtNum(v, d)}`);
const fmtTs = (value) => {
  if (!value) return "-";
  const d = typeof value === "number" ? new Date(value) : new Date(value);
  return isNaN(d.getTime()) ? String(value) : d.toISOString().replace("T", " ").slice(0, 16);
};
const fmtDate = (value) => {
  if (!value) return "-";
  const d = typeof value === "number" ? new Date(value) : new Date(value);
  return isNaN(d.getTime()) ? String(value).slice(0, 10) : d.toISOString().slice(0, 10);
};
const fmtDuration = (seconds) => {
  const s = Number(seconds);
  if (!isFinite(s)) return "-";
  if (s < 60) return `${s.toFixed(1)}s`;
  if (s < 3600) return `${(s / 60).toFixed(1)}m`;
  return `${(s / 3600).toFixed(1)}h`;
};
const clampProgress = (value) => {
  const n = Number(value);
  if (!isFinite(n)) return 0;
  return Math.max(0, Math.min(100, n));
};
function ProgressStage({ job, style = {} }) {
  if (!job || job.progress == null) return null;
  const pct = clampProgress(job.progress);
  const pctLabel = `${Math.round(pct)}%`;
  const stage = job.message || (job.status === "done" ? "Complete" : job.status === "error" ? "Failed" : "Working");
  const tone = job.status === "done" ? "profit" : job.status === "error" ? "loss" : "";
  const timingParts = [];
  if (job.elapsed_seconds != null) timingParts.push(`elapsed ${fmtDuration(job.elapsed_seconds)}`);
  if (job.estimated_remaining_seconds != null && job.status === "running") {
    timingParts.push(`remaining ${fmtDuration(job.estimated_remaining_seconds)}`);
  }
  if (job.completed_trials != null && job.total_trials != null) {
    timingParts.push(`${job.completed_trials}/${job.total_trials} trials`);
  }
  return html`
    <div style=${{ flex: 1, minWidth: 180, ...style }}>
      <div class="row" style=${{ justifyContent: "space-between", gap: 10, alignItems: "baseline", marginBottom: 6 }}>
        <div class="field-hint" style=${{ minWidth: 0, overflowWrap: "anywhere" }}>
          <span style=${{ color: "var(--text-muted)" }}>Stage:</span> ${stage}
        </div>
        <span class="mono" style=${{ fontSize: 11, color: "var(--text)", whiteSpace: "nowrap" }}>${pctLabel}</span>
      </div>
      <div class=${`bar ${tone}`} style=${{ height: 6 }}>
        <i style=${{ width: `${pct}%` }}></i>
      </div>
      ${timingParts.length > 0 && html`
        <div class="field-hint mono" style=${{ marginTop: 4, fontSize: 11 }}>${timingParts.join(" - ")}</div>
      `}
    </div>
  `;
}
function parseSweepValues(raw) {
  const out = [];
  String(raw || "").split(",").map((p) => p.trim()).filter(Boolean).forEach((part) => {
    const m = part.match(/^(\d+(?:\.\d+)?)\s*(?:\.\.|~|-)\s*(\d+(?:\.\d+)?)(?::(\d+(?:\.\d+)?))?$/);
    if (m) {
      const start = Number(m[1]);
      const end = Number(m[2]);
      const step = Number(m[3] || 1);
      if (!Number.isInteger(start) || !Number.isInteger(end) || !Number.isInteger(step) || start <= 0 || end < start || step <= 0) {
        throw new Error(`Invalid range: ${part}`);
      }
      for (let v = start; v <= end; v += step) out.push(v);
    } else {
      const v = Number(part);
      if (!Number.isInteger(v) || v <= 0) throw new Error(`Invalid value: ${part}`);
      out.push(v);
    }
  });
  return [...new Set(out)];
}
function buildSweepGrid(strategy, inputs) {
  const specs = SWEEP_PARAM_SPECS[strategy] || [];
  const grid = {};
  specs.forEach(([key]) => {
    const values = parseSweepValues(inputs?.[key]);
    if (!values.length) throw new Error(`${key} cannot be empty`);
    grid[key] = values;
  });
  return grid;
}
function countValidSweepCombos(strategy, grid) {
  const keys = Object.keys(grid || {});
  const total = keys.reduce((acc, key) => acc * (grid[key]?.length || 0), 1);
  const fastKey = strategy === "ma_crossover" ? "fast_window" : "fast_span";
  const slowKey = strategy === "ma_crossover" ? "slow_window" : "slow_span";
  if (!grid?.[fastKey] || !grid?.[slowKey]) return { total, valid: total };
  let valid = 0;
  grid[fastKey].forEach((fast) => {
    grid[slowKey].forEach((slow) => {
      if (fast < slow) valid += keys
        .filter((key) => key !== fastKey && key !== slowKey)
        .reduce((acc, key) => acc * (grid[key]?.length || 0), 1);
    });
  });
  return { total, valid };
}
function estimateSweepSeconds(strategy, grid, bar, start, end, symbols) {
  const { valid } = countValidSweepCombos(strategy, grid);
  const days = Math.max(1, (new Date(end) - new Date(start)) / 86_400_000);
  const rows = days * (SWEEP_ROWS_PER_DAY[bar] || 24) * Math.max(1, symbols.length);
  const perEvent = SWEEP_SECONDS_PER_EVENT[strategy] || 0.00025;
  return Math.max(0.6, 0.35 + rows * perEvent) * Math.max(1, valid);
}
function estimateValidationMultiplier(start, end, validation) {
  if (!validation || validation === "none") return 1;
  const days = Math.max(1, (new Date(end) - new Date(start)) / 86_400_000);
  const wfWindows = Math.max(0, Math.floor(Math.max(0, days - 30) / 7) + 1);
  const cpcvCombos = 15;
  return 1
    + (validation === "wf" || validation === "both" ? wfWindows : 0)
    + (validation === "cpcv" || validation === "both" ? cpcvCombos : 0);
}
function cleanRiskOverrides(raw = {}) {
  const out = {};
  Object.entries(raw || {}).forEach(([key, value]) => {
    if (value === "" || value == null) return;
    const num = Number(value);
    if (Number.isFinite(num) && num > 0) out[key] = num;
  });
  return out;
}
function isDbOhlcvTradingPairRow(row) {
  return (row?.data_kind || "ohlcv") === "ohlcv"
    && Number(row?.row_count || 0) > 0
    && typeof row?.inst_id === "string"
    && row.inst_id.includes("SWAP");
}
function coverageSupportsBar(rowBar, targetBar) {
  return rowBar === targetBar || (rowBar === "1m" && DERIVABLE_FROM_1M_BARS.has(targetBar));
}
function dbTradingPairsForBar(coverageRows, targetBar) {
  return [...new Set((coverageRows || [])
    .filter((row) => isDbOhlcvTradingPairRow(row) && coverageSupportsBar(row.bar, targetBar))
    .map((row) => row.inst_id))]
    .sort();
}
function dbTradingPairStartMap(coverageRows, targetBar) {
  const out = {};
  (coverageRows || [])
    .filter((row) => isDbOhlcvTradingPairRow(row) && coverageSupportsBar(row.bar, targetBar))
    .forEach((row) => {
      const date = fmtDate(row.first_ts);
      if (!date || date === "-") return;
      if (!out[row.inst_id] || date < out[row.inst_id]) out[row.inst_id] = date;
    });
  return out;
}

window.fmt = { pct: fmtPct, num: fmtNum, usd: fmtUSD, ts: fmtTs, date: fmtDate };

function KPI({ label, value, sub, tone, spark, sparkMode = "area", hint }) {
  const toneClass = tone === "up" ? "up" : tone === "down" ? "down" : "";
  return html`
    <div class="kpi">
      <div class="kpi-label">
        ${label}
        ${hint && html`<span class="chip" style=${{ fontSize: 10, padding: "1px 6px" }}>${hint}</span>`}
      </div>
      <div class="kpi-value">${value}</div>
      ${sub && html`<div class=${`kpi-delta ${toneClass}`}>${sub}</div>`}
      ${spark && html`
        <div class="kpi-spark">
          <${Sparkline} values=${spark} color=${tone === "down" ? "var(--loss)" : tone === "up" ? "var(--profit)" : "var(--accent)"} mode=${sparkMode} height=${32} />
        </div>
      `}
    </div>
  `;
}

function RunBacktestView({ setView, setSelectedRunId }) {
  const [dataCoverage, setDataCoverage] = useConfigState(null);
  const [strategy, setStrategy] = useConfigState("funding_carry");
  const [symbol, setSymbol] = useConfigState("BTC-USDT-SWAP");
  const [spotSymbol, setSpotSymbol] = useConfigState("BTC-USDT");
  const [symbolX, setSymbolX] = useConfigState("BTC-USDT-SWAP");
  const [symbolY, setSymbolY] = useConfigState("ETH-USDT-SWAP");
  const [exchange, setExchange] = useConfigState("binance");
  const [bar, setBar] = useConfigState("1H");
  const [periodsOverride, setPeriodsOverride] = useConfigState(null);
  const [start, setStart] = useConfigState("2024-01-01");
  const [end, setEnd] = useConfigState(yesterday);
  const [equity, setEquity] = useConfigState(5000);
  const [validation, setValidation] = useConfigState("both");
  const [runJob, setRunJob] = useConfigState(null);
  const [rotUniverse, setRotUniverse] = useConfigState(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]);
  const [technicalSymbols, setTechnicalSymbols] = useConfigState(["BTC-USDT-SWAP"]);
  const [rotBenchmark, setRotBenchmark] = useConfigState("BTC-USDT-SWAP");
  const [rotRebalanceMin, setRotRebalanceMin] = useConfigState(60);
  const [rotTopK, setRotTopK] = useConfigState(3);
  const [rotRankExitBuffer, setRotRankExitBuffer] = useConfigState(6);
  const [strategyParams, setStrategyParams] = useConfigState(STRATEGY_PARAM_DEFAULTS);
  const [sweepParams, setSweepParams] = useConfigState(SWEEP_PARAM_DEFAULTS);
  const [riskOverrides, setRiskOverrides] = useConfigState(RISK_OVERRIDE_DEFAULTS);
  const [fillAllSignals, setFillAllSignals] = useConfigState(false);
  const [sweepFinalistValidation, setSweepFinalistValidation] = useConfigState("none");
  const [sweepTopPct, setSweepTopPct] = useConfigState(10);
  const [sweepMaxFinalists, setSweepMaxFinalists] = useConfigState(20);
  const [sweepJob, setSweepJob] = useConfigState(null);
  const periods = periodsOverride ?? BAR_PERIODS[bar] ?? 8760;
  const strat = MOCK.STRATEGIES.find((s) => s.id === strategy) || {};
  const isRotation = strategy === "ohlcv_rotation";
  const isDailyWinner = strategy === "daily_winner";
  const isTechnical = TECHNICAL_STRATEGIES.has(strategy);
  const hasStrategyParams = PARAMETERIZED_STRATEGIES.has(strategy);
  const isBasketStrategy = isRotation || isDailyWinner || isTechnical;
  const selectedBar = isDailyWinner ? "1D" : bar;
  const tradingPairOptions = dbTradingPairsForBar(dataCoverage || [], selectedBar);
  const tradingPairOptionsKey = tradingPairOptions.join("|");
  const tradingPairSet = new Set(tradingPairOptions);
  const tradingPairStartMap = dbTradingPairStartMap(dataCoverage || [], selectedBar);
  const selectedSwapSymbols = strategy === "pairs_trading"
    ? [symbolX, symbolY]
    : isTechnical
    ? technicalSymbols
    : isBasketStrategy
    ? rotUniverse
    : [symbol].filter((s) => s && s.includes("SWAP"));
  const selectedTradingPairsValid = tradingPairOptions.length > 0
    && selectedSwapSymbols.length > 0
    && selectedSwapSymbols.every((s) => tradingPairSet.has(s));
  const selectedCoverageWarnings = [...new Set(selectedSwapSymbols)]
    .map((s) => ({ instId: s, firstDate: tradingPairStartMap[s] }))
    .filter((row) => row.instId && row.firstDate && start && start < row.firstDate)
    .sort((a, b) => a.firstDate.localeCompare(b.firstDate) || a.instId.localeCompare(b.instId));
  const estimateDays = Math.max(1, (new Date(end) - new Date(start)) / 86_400_000);
  const estimateEvents = estimateDays * (SWEEP_ROWS_PER_DAY[isDailyWinner ? "1D" : bar] || 24) * Math.max(1, selectedSwapSymbols.length);
  const singleReplaySeconds = Math.max(0.6, 0.35 + estimateEvents * 0.00008);
  const fullBacktestEstimate = singleReplaySeconds * estimateValidationMultiplier(start, end, isRotation ? "none" : validation);

  useConfigEffect(() => {
    window.API.fetchDataCoverage()
      .then((rows) => setDataCoverage(rows || []))
      .catch(() => setDataCoverage([]));
  }, []);

  useConfigEffect(() => {
    if (dataCoverage == null) return;
    if (!tradingPairOptions.length) {
      setSymbol("");
      setSymbolX("");
      setSymbolY("");
      setRotBenchmark("");
      setRotUniverse([]);
      setTechnicalSymbols([]);
      return;
    }
    const first = tradingPairOptions[0];
    const currentX = tradingPairSet.has(symbolX) ? symbolX : first;
    const second = tradingPairOptions.find((s) => s !== currentX) || currentX;

    if (!tradingPairSet.has(symbol)) setSymbol(first);
    if (!tradingPairSet.has(symbolX)) setSymbolX(first);
    if (!tradingPairSet.has(symbolY) || (strategy === "pairs_trading" && tradingPairOptions.length > 1 && symbolY === currentX)) {
      setSymbolY(second);
    }
    if (!tradingPairSet.has(rotBenchmark)) setRotBenchmark(first);
    setRotUniverse((current) => {
      const values = current || [];
      if (!values.length) return current;
      const valid = values.filter((s) => tradingPairSet.has(s));
      if (valid.length === values.length) return current;
      return valid.length ? valid : tradingPairOptions.slice(0, Math.min(3, tradingPairOptions.length));
    });
    setTechnicalSymbols((current) => {
      const values = current || [];
      if (!values.length) return current;
      const valid = values.filter((s) => tradingPairSet.has(s));
      if (valid.length === values.length) return current;
      return valid.length ? valid : [first];
    });
  }, [dataCoverage, selectedBar, strategy, symbol, symbolX, symbolY, rotBenchmark, tradingPairOptionsKey]);

  // Reconnect to any in-progress job after page refresh
  useConfigEffect(() => {
    const savedJobId = localStorage.getItem("activeBacktestJobId");
    if (!savedJobId) return;
    window.API.fetchBacktestRunStatus(savedJobId).then((s) => {
      if (s && s.status === "running") {
        setRunJob(s);
        const iv = setInterval(() => {
          window.API.fetchBacktestRunStatus(savedJobId).then((st) => {
            setRunJob(st);
            if (st.status === "done" || st.status === "error") {
              clearInterval(iv);
              localStorage.removeItem("activeBacktestJobId");
            }
          }).catch(() => { clearInterval(iv); localStorage.removeItem("activeBacktestJobId"); });
        }, 2000);
      } else {
        localStorage.removeItem("activeBacktestJobId");
      }
    }).catch(() => localStorage.removeItem("activeBacktestJobId"));
  }, []);

  useConfigEffect(() => {
    const savedJobId = localStorage.getItem("activeSweepJobId");
    if (!savedJobId) return;
    window.API.fetchBacktestSweepStatus(savedJobId).then((s) => {
      if (s && s.status === "running") {
        setSweepJob(s);
        const iv = setInterval(() => {
          window.API.fetchBacktestSweepStatus(savedJobId).then((st) => {
            setSweepJob(st);
            if (st.status === "done" || st.status === "error") {
              clearInterval(iv);
              localStorage.removeItem("activeSweepJobId");
            }
          }).catch((err) => {
            setSweepJob({ status: "error", progress: 100, message: err.message });
            clearInterval(iv);
            localStorage.removeItem("activeSweepJobId");
          });
        }, 2000);
      } else if (s && (s.status === "done" || s.status === "error")) {
        setSweepJob(s);
        localStorage.removeItem("activeSweepJobId");
      } else {
        localStorage.removeItem("activeSweepJobId");
      }
    }).catch(() => localStorage.removeItem("activeSweepJobId"));
  }, []);

  useConfigEffect(() => {
    if (isDailyWinner && bar !== "1D") {
      setBar("1D");
      setPeriodsOverride(null);
    }
  }, [isDailyWinner, bar]);

  function onBarChange(newBar) {
    setBar(newBar);
    setPeriodsOverride(null);
  }

  function triggerBacktest() {
    const body = {
      strategy,
      exchange,
      bar: isDailyWinner ? "1D" : bar,
      periods: isDailyWinner ? BAR_PERIODS["1D"] : periods,
      start,
      end,
      symbols: strategy === "pairs_trading" ? [symbolY, symbolX] : isTechnical ? technicalSymbols : isBasketStrategy ? [] : [symbol],
      symbol_x: strategy === "pairs_trading" ? symbolX : null,
      symbol_y: strategy === "pairs_trading" ? symbolY : null,
      perp_symbol: strategy === "funding_carry" ? symbol : null,
      spot_symbol: strategy === "funding_carry" ? spotSymbol : null,
      validate: isRotation ? null : (validation === "none" ? null : validation),
      universe: (isRotation || isDailyWinner) ? rotUniverse : [],
      benchmark: isRotation ? rotBenchmark : undefined,
      rebalance_minutes: isRotation ? rotRebalanceMin : undefined,
      top_k: isRotation ? rotTopK : undefined,
      rank_exit_buffer: isRotation ? rotRankExitBuffer : undefined,
      initial_equity: +equity || 5000,
      strategy_params: hasStrategyParams ? (strategyParams[strategy] || {}) : {},
      risk_overrides: cleanRiskOverrides(riskOverrides),
      fill_all_signals: fillAllSignals,
    };
    setRunJob({ status: "running", progress: 0, message: "Submitting backtest..." });
    window.API.triggerBacktestRun(body).then((job) => {
      setRunJob(job);
      localStorage.setItem("activeBacktestJobId", job.job_id);
      const iv = setInterval(() => {
        window.API.fetchBacktestRunStatus(job.job_id).then((s) => {
          setRunJob(s);
          if (s.status === "done" || s.status === "error") {
            clearInterval(iv);
            localStorage.removeItem("activeBacktestJobId");
          }
        }).catch((err) => {
          setRunJob({ status: "error", message: err.message });
          clearInterval(iv);
          localStorage.removeItem("activeBacktestJobId");
        });
      }, 2000);
    }).catch((err) => setRunJob({ status: "error", message: err.message }));
  }

  function triggerParameterSweep() {
    try {
      const parameterGrid = buildSweepGrid(strategy, sweepParams[strategy] || {});
      const body = {
        strategy,
        exchange,
        bar,
        periods,
        start,
        end,
        symbols: technicalSymbols,
        initial_equity: +equity || 5000,
        parameter_grid: parameterGrid,
        max_combinations: 5000,
        risk_overrides: cleanRiskOverrides(riskOverrides),
        fill_all_signals: fillAllSignals,
        run_finalists: true,
        finalist_top_pct: Math.max(1, Math.min(100, Number(sweepTopPct) || 10)) / 100,
        max_finalists: Math.max(0, Math.min(100, Number(sweepMaxFinalists) || 20)),
        finalist_validation: sweepFinalistValidation === "none" ? null : sweepFinalistValidation,
      };
      setSweepJob({ status: "running", progress: 0, message: "Submitting parameter sweep..." });
      window.API.triggerBacktestSweep(body).then((job) => {
        setSweepJob(job);
        localStorage.setItem("activeSweepJobId", job.job_id);
        const iv = setInterval(() => {
          window.API.fetchBacktestSweepStatus(job.job_id).then((s) => {
            setSweepJob(s);
            if (s.status === "done" || s.status === "error") {
              clearInterval(iv);
              localStorage.removeItem("activeSweepJobId");
            }
          }).catch((err) => {
            setSweepJob({ status: "error", message: err.message });
            clearInterval(iv);
            localStorage.removeItem("activeSweepJobId");
          });
        }, 2000);
      }).catch((err) => {
        setSweepJob({ status: "error", message: err.message });
        localStorage.removeItem("activeSweepJobId");
      });
    } catch (err) {
      setSweepJob({ status: "error", message: err.message });
    }
  }

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="row" style=${{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
        <div class="card" style=${{ flex: 2 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Backtest configuration</div>
              <div class="card-sub">strategy, trading pair, bar, and date window</div>
            </div>
            <div class="row" style=${{ gap: 8 }}>
              <button class="btn ghost sm">Save preset</button>
              <button class="btn primary sm" disabled=${runJob?.status === "running" || tradingPairOptions.length < 1 || !selectedTradingPairsValid || (strategy === "pairs_trading" && symbolX === symbolY) || ((isRotation || isDailyWinner) && rotUniverse.length < 2) || (isTechnical && technicalSymbols.length < 1)} onClick=${triggerBacktest}>Run backtest</button>
            </div>
          </div>

          <div class="grid" style=${{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div class="field">
              <div class="field-label">Strategy</div>
              <select class="select" value=${strategy} onChange=${(e) => setStrategy(e.target.value)}>
                ${MOCK.STRATEGIES.map((s) => html`<option key=${s.id} value=${s.id}>${s.name}</option>`)}
              </select>
              <div class="field-hint">${strat.desc}</div>
            </div>
            <div class="field">
              <div class="field-label">Exchange</div>
              <select class="select mono" value=${exchange} onChange=${(e) => setExchange(e.target.value)}>
                <option value="binance">Binance</option>
                <option value="okx">OKX</option>
              </select>
            </div>
            ${isDailyWinner ? html`
              <${Fragment}>
                <div class="field" style=${{ gridColumn: "1 / -1" }}>
                  <div class="field-label">Trading Pairs (DB OHLCV)</div>
                  <div class="tbl-wrap" style=${{ maxHeight: 120 }}>
                    <table class="tbl" style=${{ fontSize: 12 }}>
                      <tbody>
                        ${tradingPairOptions.length ? tradingPairOptions.map((s) => html`
                          <tr key=${s} style=${{ cursor: "pointer" }}
                              onClick=${() => setRotUniverse((u) => u.includes(s) ? u.filter((x) => x !== s) : [...u, s])}>
                            <td style=${{ width: 28 }}>
                              <input type="checkbox" checked=${rotUniverse.includes(s)} onChange=${() => {}} />
                            </td>
                            <td class="mono">${s}</td>
                          </tr>
                        `) : html`<tr><td colSpan=${2} class="field-hint" style=${{ padding: 12 }}>No DB trading pairs available for ${selectedBar}.</td></tr>`}
                      </tbody>
                    </table>
                  </div>
                  <div class="field-hint">${rotUniverse.length} trading pairs selected - one round trip per complete day.</div>
                </div>
              <//>
            ` : strategy === "ohlcv_rotation" ? html`
              <${Fragment}>
                <div class="field" style=${{ gridColumn: "1 / -1" }}>
                  <div class="field-label">Trading Pairs (DB OHLCV)</div>
                  <div class="tbl-wrap" style=${{ maxHeight: 120 }}>
                    <table class="tbl" style=${{ fontSize: 12 }}>
                      <tbody>
                        ${tradingPairOptions.length ? tradingPairOptions.map((s) => html`
                          <tr key=${s} style=${{ cursor: "pointer" }}
                              onClick=${() => setRotUniverse((u) => u.includes(s) ? u.filter((x) => x !== s) : [...u, s])}>
                            <td style=${{ width: 28 }}>
                              <input type="checkbox" checked=${rotUniverse.includes(s)} onChange=${() => {}} />
                            </td>
                            <td class="mono">${s}</td>
                          </tr>
                        `) : html`<tr><td colSpan=${2} class="field-hint" style=${{ padding: 12 }}>No DB trading pairs available for ${selectedBar}.</td></tr>`}
                      </tbody>
                    </table>
                  </div>
                  <div class="field-hint">${rotUniverse.length} trading pairs selected — re-ranked every ${rotRebalanceMin} bars, top-${rotTopK} held</div>
                </div>
                <div class="field">
                  <div class="field-label">Benchmark</div>
                  <select class="select mono" value=${rotBenchmark} onChange=${(e) => setRotBenchmark(e.target.value)}>
                    ${tradingPairOptions.length ? tradingPairOptions.map((s) => html`<option key=${s}>${s}</option>`) : html`<option value="">No DB trading pairs</option>`}
                  </select>
                  <div class="field-hint">Regime filter: go flat when benchmark is below its 240-min EMA.</div>
                </div>
                <div class="field">
                  <div class="field-label">Rebalance interval (min)</div>
                  <input class="input mono" value=${rotRebalanceMin} onChange=${(e) => setRotRebalanceMin(+e.target.value)} />
                  <div class="field-hint">Re-rank universe every N minutes. Default: 60.</div>
                </div>
                <div class="field">
                  <div class="field-label">Top-k positions</div>
                  <input class="input mono" value=${rotTopK} onChange=${(e) => setRotTopK(+e.target.value)} />
                  <div class="field-hint">Max simultaneous positions. Equal weight, capped at 35%.</div>
                </div>
                <div class="field">
                  <div class="field-label">Exit rank buffer</div>
                  <input class="input mono" value=${rotRankExitBuffer} onChange=${(e) => setRotRankExitBuffer(+e.target.value)} />
                  <div class="field-hint">Exit when rank falls below this threshold.</div>
                </div>
              <//>
            ` : isTechnical ? html`
              <${Fragment}>
                <div class="field" style=${{ gridColumn: "1 / -1" }}>
                  <div class="field-label">Trading Pairs (DB OHLCV)</div>
                  <button class="btn sm" style=${{ marginBottom: 4 }}
                    onClick=${() => {
                      const all = tradingPairOptions;
                      const allSelected = all.length > 0 && technicalSymbols.length === all.length;
                      setTechnicalSymbols(allSelected ? [] : [...all]);
                    }}>
                    ${tradingPairOptions.length > 0 && technicalSymbols.length === tradingPairOptions.length ? "Deselect All" : "Select All"}
                  </button>
                  <div class="tbl-wrap" style=${{ maxHeight: 120 }}>
                    <table class="tbl" style=${{ fontSize: 12 }}>
                      <tbody>
                        ${tradingPairOptions.length ? tradingPairOptions.map((s) => html`
                          <tr key=${s} style=${{ cursor: "pointer" }}
                              onClick=${() => setTechnicalSymbols((u) => u.includes(s) ? u.filter((x) => x !== s) : [...u, s])}>
                            <td style=${{ width: 28 }}>
                              <input type="checkbox" checked=${technicalSymbols.includes(s)} onChange=${() => {}} />
                            </td>
                            <td class="mono">${s}</td>
                          </tr>
                        `) : html`<tr><td colSpan=${2} class="field-hint" style=${{ padding: 12 }}>No DB trading pairs available for ${selectedBar}.</td></tr>`}
                      </tbody>
                    </table>
                  </div>
                  <div class="field-hint">${technicalSymbols.length} trading pairs selected - long/flat crossover backtest.</div>
                </div>
              <//>
            ` : strategy === "pairs_trading" ? html`
              <${Fragment}>
                <div class="field">
                  <div class="field-label">Reference Trading Pair (X)</div>
                  <select class="select mono" value=${symbolX} onChange=${(e) => setSymbolX(e.target.value)}>
                    ${tradingPairOptions.length ? tradingPairOptions.map((s) => html`<option key=${s}>${s}</option>`) : html`<option value="">No DB trading pairs</option>`}
                  </select>
                  <div class="field-hint">Reference leg for hedge ratio and spread signal, e.g. BTC-USDT-SWAP.</div>
                </div>
                <div class="field">
                  <div class="field-label">Trade/spread Trading Pair (Y)</div>
                  <select class="select mono" value=${symbolY} onChange=${(e) => setSymbolY(e.target.value)}>
                    ${tradingPairOptions.length ? tradingPairOptions.map((s) => html`<option key=${s}>${s}</option>`) : html`<option value="">No DB trading pairs</option>`}
                  </select>
                  <div class="field-hint">Dependent leg traded against X, e.g. ETH, LTC, SOL, or other available swaps.</div>
                </div>
                ${symbolX === symbolY && html`
                  <div class="field-hint" style=${{ gridColumn: "1 / -1", color: "var(--loss)" }}>
                    Pair Trading requires two different trading pairs.
                  </div>
                `}
              <//>
            ` : html`
              <div class="field">
                <div class="field-label">${strategy === "funding_carry" ? "Perp Trading Pair" : "Trading Pair"}</div>
                <select class="select mono" value=${symbol} onChange=${(e) => setSymbol(e.target.value)}>
                  ${tradingPairOptions.length ? tradingPairOptions.map((s) => html`<option key=${s}>${s}</option>`) : html`<option value="">No DB trading pairs</option>`}
                </select>
                <div class="field-hint">OKX instrument id</div>
              </div>
            `}
            ${strategy === "funding_carry" && html`
              <div class="field">
                <div class="field-label">Spot hedge trading pair</div>
                <input class="input mono" value=${spotSymbol} onChange=${(e) => setSpotSymbol(e.target.value)} />
                <div class="field-hint">Spot leg used for delta-neutral funding carry.</div>
              </div>
            `}
            <div class="field">
              <div class="field-label">Bar size</div>
              <select class="select mono" value=${isDailyWinner ? "1D" : bar} disabled=${isDailyWinner} onChange=${(e) => onBarChange(e.target.value)}>
                ${Object.keys(BAR_PERIODS).map((b) => html`<option key=${b}>${b}</option>`)}
              </select>
              ${isDailyWinner && html`<div class="field-hint">Daily Winner always uses 1D candles derived from DB 1m OHLCV when needed.</div>`}
            </div>
            <div class="field">
              <div class="field-label">
                Annualization periods
                <span
                  class="chip"
                  style=${{ marginLeft: 6, fontSize: 10 }}
                  title="Sharpe = mean_bar_return / std x sqrt(periods). Use 8,760 for 1H bars so metrics are annual. Changing bar size resets this automatically."
                >?</span>
              </div>
              <input
                class="input mono"
                value=${periods}
                onChange=${(e) => setPeriodsOverride(+e.target.value)}
              />
              <div class="field-hint">
                auto: ${BAR_PERIODS[isDailyWinner ? "1D" : bar]?.toLocaleString()} - <span style=${{ color: periodsOverride ? "var(--accent)" : "var(--text-muted)" }}>${periodsOverride ? "overridden" : "synced"}</span>
              </div>
            </div>
            <div class="field">
              <div class="field-label">Start</div>
              <input class="input mono" type="date" value=${start} onChange=${(e) => setStart(e.target.value)} />
              ${selectedCoverageWarnings.length > 0 && html`
                <div class="field-hint" style=${{ color: "var(--warn)", marginTop: 6 }}>
                  No DB data before first candle:
                  ${selectedCoverageWarnings.map((row) => `${row.instId} starts ${row.firstDate}`).join("; ")}
                </div>
              `}
            </div>
            <div class="field">
              <div class="field-label">End</div>
              <input
                class="input mono"
                type="date"
                value=${end}
                max=${yesterday}
                onChange=${(e) => setEnd(e.target.value > yesterday ? yesterday : e.target.value)}
              />
              <div class="field-hint">max: ${yesterday} (data through yesterday)</div>
            </div>
            <div class="field">
              <div class="field-label">Initial equity (USD)</div>
              <input class="input mono" value=${equity} onChange=${(e) => setEquity(+e.target.value)} />
            </div>
            ${(() => {
              // Warm-up clock-time per strategy (minutes)
              const warmupMin = {
                funding_carry: 0,
                pairs_trading: 168 * 60,
                ohlcv_rotation: 240,
                daily_winner: 24 * 60,
              };
              const wm = warmupMin[strategy] || 0;
              if (!wm || !start || !end) return null;
              const days = (new Date(end) - new Date(start)) / 86400000;
              const warmupDays = wm / 60 / 24;
              if (days < warmupDays * 3) {
                const warmupLabel = warmupDays >= 1 ? `${warmupDays.toFixed(1)} days` : `${(wm / 60).toFixed(1)} h`;
                return html`<div class="field-hint" style=${{ color: "var(--warn, #d97706)" }}>
                  ⚠ Warm-up: ~${warmupLabel}. Backtest window (${days.toFixed(0)} d) may have limited active trading.
                </div>`;
              }
              return null;
            })()}
            ${!isRotation && html`
              <div class="field">
                <div class="field-label">Validation</div>
                <select class="select" value=${validation} onChange=${(e) => setValidation(e.target.value)}>
                  <option value="both">Both (WF + CPCV)</option>
                  <option value="wf">Walk-Forward</option>
                  <option value="cpcv">CPCV</option>
                  <option value="none">None</option>
                </select>
              </div>
            `}
            <div class="field" style=${{ gridColumn: "1 / -1" }}>
              <div class="field-label">Research risk overrides</div>
              <div class="grid" style=${{ gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10 }}>
                ${RISK_OVERRIDE_SPECS.map((spec) => html`
                  <div key=${spec.key} class="col" style=${{ gap: 4, minWidth: 0 }}>
                    <div class="field-label" title=${spec.help} style=${{ fontSize: 11 }}>${spec.label}</div>
                    <input class="input mono" type="number" min="0" step=${spec.step}
                      value=${riskOverrides[spec.key]}
                      placeholder=${spec.placeholder}
                      title=${spec.help}
                      aria-label=${spec.label}
                      onChange=${(e) => setRiskOverrides((v) => ({ ...v, [spec.key]: e.target.value }))} />
                    <div class="field-hint" title=${spec.help} style=${{ lineHeight: 1.35 }}>${spec.help}</div>
                  </div>
                `)}
              </div>
              <label class="row" style=${{ gap: 8, marginTop: 10, alignItems: "flex-start" }}>
                <input type="checkbox" checked=${fillAllSignals}
                  onChange=${(e) => setFillAllSignals(e.target.checked)}
                  style=${{ marginTop: 2 }} />
                <span>
                  <span class="field-label" style=${{ display: "block", fontSize: 12 }}>Fill all signals</span>
                  <span class="field-hint">Research-only idealized execution: bypasses capacity caps and fills every submitted signal order.</span>
                </span>
              </label>
              <div class="field-hint" style=${{ marginTop: 6 }}>Blank means use config default. Research-only; live risk config is unchanged.</div>
            </div>
          </div>
          <div class="field-hint" style=${{ marginTop: 10 }}>
            Est. full backtest: ${fmtDuration(fullBacktestEstimate)} (${fmtDuration(singleReplaySeconds)} single replay × ${estimateValidationMultiplier(start, end, isRotation ? "none" : validation)} passes)
          </div>
          ${runJob && html`
            <div class="col" style=${{ gap: 8, marginTop: 16 }}>
              <div class="row" style=${{ gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                <span class=${`chip ${runJob.status === "done" ? "profit" : runJob.status === "error" ? "loss" : "warn"}`}>${runJob.status}</span>
                ${runJob.run_id && html`<span class="mono" style=${{ fontSize: 11, color: "var(--text-muted)", overflowWrap: "anywhere" }}>${runJob.run_id}</span>`}
                ${runJob.status === "done" && runJob.run_id && setView && html`
                  <button class="btn primary sm" onClick=${() => {
                    setSelectedRunId?.(runJob.run_id);
                    setView("backtest");
                  }}>View Results →</button>
                `}
              </div>
              <${ProgressStage} job=${runJob} />
            </div>
            ${runJob.status === "error" && runJob.output && html`
              <pre style=${{ marginTop: 8, padding: "8px 12px", background: "var(--surface-2)", borderRadius: 6, fontSize: 11, color: "var(--loss)", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 200, overflowY: "auto" }}>${runJob.output}</pre>
            `}
          `}
        </div>

        <div class="card" style=${{ flex: 1, minWidth: 280 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Strategy parameters</div>
              <div class="card-sub mono">${strategy}</div>
            </div>
          </div>
          <${StrategyParams} id=${strategy} params=${strategyParams[strategy] || {}} riskOverrides=${riskOverrides} fillAllSignals=${fillAllSignals} setParams=${(next) => setStrategyParams((all) => ({ ...all, [strategy]: next }))} />
          ${isTechnical && html`
            <div class="sep" style=${{ margin: "12px 0" }}></div>
            <${ParameterSweepPanel}
              id=${strategy}
              inputs=${sweepParams[strategy] || {}}
              setInputs=${(next) => setSweepParams((all) => ({ ...all, [strategy]: next }))}
              bar=${bar}
              start=${start}
              end=${end}
              symbols=${technicalSymbols}
              job=${sweepJob}
              onRun=${triggerParameterSweep}
              finalistValidation=${sweepFinalistValidation}
              setFinalistValidation=${setSweepFinalistValidation}
              finalistTopPct=${sweepTopPct}
              setFinalistTopPct=${setSweepTopPct}
              maxFinalists=${sweepMaxFinalists}
              setMaxFinalists=${setSweepMaxFinalists}
              fillAllSignals=${fillAllSignals}
              setFillAllSignals=${setFillAllSignals}
              setView=${setView}
              setSelectedRunId=${setSelectedRunId}
            />
          `}
        </div>
      </div>

      <${MarketDataCard} />
    </div>
  `;
}

function StrategyParams({ id, params: activeParams = {}, riskOverrides = {}, fillAllSignals = false, setParams = () => {} }) {
  const specs = {
    funding_carry: [
      ["min_apr_threshold", "0.12", "min APR to enter", "Minimum annualized funding rate (APR) required to open a carry position. Filters out low-yield periods. 0.12 = 12% APR."],
      ["rebalance_drift_threshold", "0.02", "spot/perp drift", "Max allowed deviation between spot and perp position sizes before rebalancing. Keeps delta-neutral exposure."],
      ["funding_check_interval_secs", "300", "poll cadence (s)", "How often (seconds) the strategy re-checks the funding rate via REST. Lower = more reactive, higher = fewer API calls."],
    ],
    pairs_trading: [
      ["kalman_delta", "0.0001", "process noise", "Kalman filter process variance. Lower = hedge ratio changes slowly, more stable but lags regime shifts."],
      ["entry_z", "2.0", "entry z-score", "Open a position when the OU spread z-score crosses +/-entry_z. Higher = fewer but higher-conviction entries, lower fill rate."],
      ["exit_z", "0.3", "exit z-score", "Close the position when z-score reverts to +/-exit_z. Lower = exit close to mean, capturing full reversion."],
      ["stop_z", "4.0", "stop-loss z-score", "Force-close if z-score reaches +/-stop_z. Protects against spread divergence and non-stationary regimes."],
      ["lookback_hours", "168", "OU estimator window (h)", "Rolling window for estimating Ornstein-Uhlenbeck parameters. 168 h = 1 week. Shorter = adapts faster, noisier estimates."],
    ],
    ma_crossover: [
      ["fast_window", "20", "fast MA window", "Number of selected-bar closes used for the fast simple moving average. Must be smaller than slow_window."],
      ["slow_window", "50", "slow MA window", "Number of selected-bar closes used for the slow simple moving average. Default: 50."],
    ],
    ema_crossover: [
      ["fast_span", "20", "fast EMA span", "Exponential moving average span for the fast trend line. Must be smaller than slow_span."],
      ["slow_span", "50", "slow EMA span", "Exponential moving average span for the slow trend line. Default: 50."],
    ],
    macd_crossover: [
      ["fast_span", "12", "MACD fast EMA", "Fast EMA span used in MACD. Must be smaller than slow_span."],
      ["slow_span", "26", "MACD slow EMA", "Slow EMA span used in MACD. Default: 26."],
      ["signal_span", "9", "signal EMA", "EMA span applied to the MACD line. Default: 9."],
    ],
    fear_greed_sentiment: [
      ["dataset_id", "fear_greed_btc", "external dataset", "External feature dataset id. Missing or stale observations suppress trading signals."],
      ["max_age_seconds", "172800", "feature TTL", "Maximum age for the as-of Fear & Greed value. Older values are treated as stale and generate no signal."],
      ["extreme_fear_label", "Extreme Fear", "entry label", "Classification label that opens a long position when the feature is fresh."],
      ["extreme_fear_threshold", "25", "numeric entry", "Numeric Fear & Greed value at or below this threshold also opens a long position."],
      ["exit_value_threshold", "51", "numeric exit", "Numeric Fear & Greed value at or above this threshold exits an existing position."],
    ],
    cme_gap_fill: [
      ["dataset_id", "cme_btc_yfinance", "external dataset", "External BTC futures dataset id. cme_btc_yfinance is research-only proxy; cme_btc1_continuous requires official data ingest."],
      ["max_age_seconds", "604800", "feature TTL", "Maximum age for the as-of CME observation before it is treated as stale."],
      ["min_gap_bps", "25", "gap threshold", "Minimum weekend CME gap size in basis points before the strategy considers an entry."],
      ["max_hold_days", "2", "max hold", "Maximum holding time in days before a gap-fill position exits by timeout."],
      ["stop_loss_bps_mult", "1.5", "stop multiple", "Stop-loss distance as a multiple of gap_bps from the OKX entry anchor. 0 disables stop-loss."],
      ["max_gap_bps", "0", "upper gap filter", "Optional upper bound for oversized gaps. 0 disables the upper-bound filter."],
      ["allow_direction", "long_only", "direction filter", "long_only trades only down-gaps. This default is regime-fitted to BTC 2024-26 and needs bear-regime walk-forward."],
    ],
    ohlcv_rotation: [
      ["top_k", "3", "max simultaneous positions", "Max instruments held at once. Each gets equal weight (1/n), capped at max_position_weight=0.35."],
      ["rebalance_minutes", "60", "rebalance cadence (min)", "Re-rank universe every N minutes. Lower = more reactive, higher turnover cost."],
      ["atr_stop_multiple", "2.0", "ATR stop loss", "Close position if price drops more than N × ATR below entry price."],
      ["max_holding_minutes", "480", "max holding time (min)", "Force-exit if held longer than this and composite score ≤ 0."],
      ["min_volume_z", "1.0", "volume z-score (diagnostic)", "Diagnostic threshold shown in backtest report. Not a hard entry filter; volume enters selection via composite score weight. Controls the vol_filter_pass_pct diagnostic metric."],
    ],
    daily_winner: [
      ["selection", "yesterday_return", "ranking signal", "Ranks the selected universe by yesterday's daily close/open return, then trades the strongest trading pair today."],
      ["holding_period", "1 day", "forced round trip", "Buys today's open and exits at today's daily close, producing one expected trade per complete day."],
      ["purpose", "validation", "backtest smoke test", "Designed to verify DB daily aggregation, trade generation, metrics, and frontend artifacts. Not a live trading candidate."],
    ],
  }[id] || [];
  const editable = PARAMETERIZED_STRATEGIES.has(id);
  const riskMaxOrder = Number(riskOverrides.max_order_notional_usd);
  const riskMaxPos = Number(riskOverrides.max_pos_pct_equity);
  const riskMaxLeverage = Number(riskOverrides.max_leverage);
  const hasRiskOverride = fillAllSignals || [riskMaxOrder, riskMaxPos, riskMaxLeverage].some((v) => Number.isFinite(v) && v > 0);
  const riskSummary = [
    `max_order_notional: ${Number.isFinite(riskMaxOrder) && riskMaxOrder > 0 ? fmtUSD(riskMaxOrder, 0) : "$500"}`,
    `max_pos_pct: ${Number.isFinite(riskMaxPos) && riskMaxPos > 0 ? fmtPct(riskMaxPos, 0) : "30%"}`,
    `max_leverage: ${Number.isFinite(riskMaxLeverage) && riskMaxLeverage > 0 ? `${fmtNum(riskMaxLeverage, 1)}x` : "3.0x"}`,
    `fill_all_signals: ${fillAllSignals ? "on" : "off"}`,
  ].join(" - ");
  function parseParam(value) {
    const num = Number(value);
    return value !== "" && Number.isFinite(num) ? num : value;
  }
  return html`
    <div class="col" style=${{ gap: 12 }}>
      ${specs.map(([k, v, short, full]) => html`
        <div key=${k} class="col" style=${{ gap: 4 }}>
          <div style=${{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(88px, 120px)", alignItems: "center", gap: 8 }}>
            <div style=${{ minWidth: 0, fontSize: 12, overflowWrap: "anywhere" }} class="mono" title=${short}>${k}</div>
            <input class="input mono" value=${editable ? (activeParams[k] ?? v) : v} disabled=${!editable}
              onChange=${(e) => setParams({ ...activeParams, [k]: parseParam(e.target.value) })}
              style=${{ width: "100%", maxWidth: 120, padding: "4px 8px", fontSize: 12, textAlign: "right" }} />
          </div>
          <div class="field-hint" style=${{ fontSize: 11 }}>${full}</div>
        </div>
      `)}
      <div class="sep"></div>
      <div class="field-hint">td_mode: cross - post_only: true - ${riskSummary}${hasRiskOverride ? " - research override active" : ""}${editable ? " - parameters are sent with this run" : ""}</div>
    </div>
  `;
}

function ParameterSweepPanel({
  id,
  inputs = {},
  setInputs = () => {},
  bar,
  start,
  end,
  symbols = [],
  job,
  onRun,
  finalistValidation = "none",
  setFinalistValidation = () => {},
  finalistTopPct = 10,
  setFinalistTopPct = () => {},
  maxFinalists = 20,
  setMaxFinalists = () => {},
  fillAllSignals = false,
  setFillAllSignals = () => {},
  setView,
  setSelectedRunId,
}) {
  const specs = SWEEP_PARAM_SPECS[id] || [];
  const [rangeDrafts, setRangeDrafts] = useConfigState({});
  let grid = {};
  let parseError = "";
  try {
    grid = buildSweepGrid(id, inputs);
  } catch (err) {
    parseError = err.message;
  }
  const counts = parseError ? { total: 0, valid: 0 } : countValidSweepCombos(id, grid);
  const screeningSeconds = parseError ? null : estimateSweepSeconds(id, grid, bar, start, end, symbols);
  const finalistCount = counts.valid
    ? Math.min(Number(maxFinalists) || 0, Math.max(1, Math.ceil(counts.valid * ((Number(finalistTopPct) || 10) / 100))))
    : 0;
  const finalistSeconds = screeningSeconds == null || !counts.valid
    ? null
    : (screeningSeconds / Math.max(1, counts.valid)) * finalistCount * estimateValidationMultiplier(start, end, finalistValidation);
  const estimateSeconds = screeningSeconds == null || finalistSeconds == null ? null : screeningSeconds + finalistSeconds;
  const topRows = job?.top_results || [];
  const finalistRows = job?.finalist_results || [];
  function updateDraft(key, field, value) {
    setRangeDrafts((all) => ({ ...all, [key]: { ...(all[key] || {}), [field]: value } }));
  }
  function applyRange(key) {
    const draft = rangeDrafts[key] || {};
    const startV = Number(draft.start);
    const endV = Number(draft.end);
    const stepV = Number(draft.step || 1);
    if (!Number.isInteger(startV) || !Number.isInteger(endV) || !Number.isInteger(stepV) || startV <= 0 || endV < startV || stepV <= 0) return;
    setInputs({ ...inputs, [key]: `${startV}~${endV}${stepV > 1 ? `:${stepV}` : ""}` });
  }
  return html`
    <div class="col" style=${{ gap: 10 }}>
      <div>
        <div class="card-title" style=${{ fontSize: 13 }}>Parameter sweep</div>
        <div class="card-sub">compact screening, then full artifacts for top Sharpe finalists</div>
      </div>
      ${specs.map(([key, label]) => html`
        <div key=${key} class="field">
          <div class="field-label">${label} values</div>
          <input class="input mono" value=${inputs[key] || ""}
            onChange=${(e) => setInputs({ ...inputs, [key]: e.target.value })}
            placeholder="7~100"
            style=${{ fontSize: 12 }} />
          <div class="row" style=${{ gap: 6, marginTop: 6 }}>
            <input class="input mono" type="number" min="1" placeholder="start"
              value=${rangeDrafts[key]?.start || ""}
              onChange=${(e) => updateDraft(key, "start", e.target.value)}
              style=${{ minWidth: 0, fontSize: 11, padding: "4px 6px" }} />
            <input class="input mono" type="number" min="1" placeholder="end"
              value=${rangeDrafts[key]?.end || ""}
              onChange=${(e) => updateDraft(key, "end", e.target.value)}
              style=${{ minWidth: 0, fontSize: 11, padding: "4px 6px" }} />
            <input class="input mono" type="number" min="1" placeholder="step"
              value=${rangeDrafts[key]?.step || ""}
              onChange=${(e) => updateDraft(key, "step", e.target.value)}
              style=${{ width: 54, fontSize: 11, padding: "4px 6px" }} />
            <button class="btn sm" onClick=${() => applyRange(key)} style=${{ padding: "4px 8px" }}>Apply</button>
          </div>
        </div>
      `)}
      <div class="grid" style=${{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div class="field">
          <div class="field-label">Top percent</div>
          <input class="input mono" type="number" min="1" max="100" value=${finalistTopPct}
            onChange=${(e) => setFinalistTopPct(e.target.value)} />
        </div>
        <div class="field">
          <div class="field-label">Max finalists</div>
          <input class="input mono" type="number" min="0" max="100" value=${maxFinalists}
            onChange=${(e) => setMaxFinalists(e.target.value)} />
        </div>
      </div>
      <div class="field">
        <div class="field-label">Finalist validation</div>
        <select class="select" value=${finalistValidation} onChange=${(e) => setFinalistValidation(e.target.value)}>
          <option value="none">None</option>
          <option value="wf">Walk-Forward</option>
          <option value="cpcv">CPCV</option>
          <option value="both">Both (WF + CPCV)</option>
        </select>
      </div>
      <label class="row" style=${{ gap: 8, alignItems: "flex-start" }}>
        <input type="checkbox" checked=${fillAllSignals}
          onChange=${(e) => setFillAllSignals(e.target.checked)}
          style=${{ marginTop: 2 }} />
        <span>
          <span class="field-label" style=${{ display: "block", fontSize: 12 }}>Fill all signals</span>
          <span class="field-hint">Ignore market/risk caps for this sweep; research-only idealized execution.</span>
        </span>
      </label>
      <div class="field-hint">
        ${parseError
          ? html`<span style=${{ color: "var(--loss)" }}>${parseError}</span>`
          : html`${counts.valid}/${counts.total} valid combos - screening ${fmtDuration(screeningSeconds)} - finalists ${finalistCount} / ${fmtDuration(finalistSeconds)} - total ${fmtDuration(estimateSeconds)}`}
      </div>
      <button class="btn sm" disabled=${!!parseError || !counts.valid || !symbols.length || job?.status === "running"} onClick=${onRun}>
        Run sweep
      </button>
      ${job && html`
        <div class="row" style=${{ gap: 8, alignItems: "center" }}>
          <span class=${`chip ${job.status === "done" ? "profit" : job.status === "error" ? "loss" : "warn"}`}>${job.status}</span>
        </div>
        <${ProgressStage} job=${job} style=${{ marginTop: 6 }} />
        ${job.estimate && html`
          <div class="field-hint">
            ${job.combination_count || 0} combos - screening ${fmtDuration(job.estimate.estimated_screening_seconds)} - finalist reruns ${fmtDuration(job.estimate.estimated_full_rerun_seconds)}
          </div>
        `}
        ${job.status === "error" && html`
          <pre style=${{ marginTop: 4, padding: "8px 10px", background: "var(--surface-2)", borderRadius: 6, fontSize: 11, color: "var(--loss)", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 160, overflowY: "auto" }}>${job.message || ""}</pre>
        `}
      `}
      ${topRows.length > 0 && html`
        <div class="tbl-wrap" style=${{ maxHeight: 240 }}>
          <table class="tbl" style=${{ fontSize: 11 }}>
            <thead>
              <tr>
                <th>#</th>
                <th>params</th>
                <th>Sharpe</th>
                <th>Return</th>
                <th>MDD</th>
                <th>Full</th>
              </tr>
            </thead>
            <tbody>
              ${topRows.slice(0, 8).map((row) => html`
                <tr key=${row.trial}>
                  <td>${row.rank}</td>
                  <td class="mono">${Object.entries(row.params || {}).map(([k, v]) => `${k.replace("_window", "").replace("_span", "")}:${v}`).join(" ")}</td>
                  <td>${fmtNum(row.sharpe, 2)}</td>
                  <td>${fmtPct(row.total_return, 2)}</td>
                  <td>${fmtPct(row.max_drawdown, 2)}</td>
                  <td>
                    ${row.finalist_run_id && html`
                      <button class="btn sm" onClick=${() => {
                        setSelectedRunId?.(row.finalist_run_id);
                        setView?.("backtest");
                      }}>Open</button>
                    `}
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      `}
      ${job?.artifacts?.summary_csv && html`
        <div class="field-hint mono">${job.artifacts.summary_csv}</div>
      `}
      ${finalistRows.length > 0 && html`
        <div class="field-hint">${finalistRows.filter((r) => r.status === "ok").length}/${finalistRows.length} finalist full backtests saved.</div>
      `}
    </div>
  `;
}

function MarketDataCard() {
  const [coverage, setCoverage] = useConfigState(null);
  const [instruments, setInstruments] = useConfigState([]);
  const [fetchJob, setFetchJob] = useConfigState(null);
  const [exportJob, setExportJob] = useConfigState(null);
  const [showFetchPanel, setShowFetchPanel] = useConfigState(false);
  const [showExportPanel, setShowExportPanel] = useConfigState(false);
  const [fetchForm, setFetchForm] = useConfigState({ exchange: "okx", symbols: [], bar: "1m", start: "2024-01-01", end: yesterday });
  const [instrumentQuery, setInstrumentQuery] = useConfigState("");
  const [instrumentSearch, setInstrumentSearch] = useConfigState({ status: "idle", exchange: "okx", query: "", message: "" });
  const [fetchStartPending, setFetchStartPending] = useConfigState(false);
  const [fetchCancelPending, setFetchCancelPending] = useConfigState(false);
  const [exportForm, setExportForm] = useConfigState({ kind: "ohlcv", symbols: [], datasets: ["cme_btc_yfinance"], bar: "1H", start: "2024-01-01", end: yesterday, format: "xlsx" });
  const listingMap = Object.fromEntries(instruments.map((i) => [i.inst_id, i.list_date]));
  const latestSelectedListing = (fetchForm.symbols || [])
    .map((s) => listingMap[s])
    .filter(Boolean)
    .sort()
    .at(-1) || "";
  const exportKind = exportForm.kind || "ohlcv";
  const exportCoverageBar = exportForm.bar === "1H" ? "1m" : exportForm.bar;
  const ROWS_PER_DAY = { "1H": 24, "1m": 1440, "5m": 288, "15m": 96, funding: 3, external: 1 };
  const estDays = Math.max(0, (new Date(exportForm.end) - new Date(exportForm.start)) / 86_400_000);
  function fmtBytes(b) {
    if (b < 1024) return b + " B";
    if (b < 1_048_576) return (b / 1024).toFixed(1) + " KB";
    if (b < 1_073_741_824) return (b / 1_048_576).toFixed(1) + " MB";
    return (b / 1_073_741_824).toFixed(1) + " GB";
  }
  const coverageSymbols = [...new Set((coverage || [])
    .filter((r) => exportKind === "funding" ? r.data_kind === "funding" : r.data_kind === "ohlcv" && r.bar === exportCoverageBar)
    .map((r) => r.inst_id)
    .filter(Boolean))]
    .sort();
  const exportSymbols = coverageSymbols.length
    ? coverageSymbols
    : [];
  const exportDatasets = [...new Set((coverage || [])
    .filter((r) => r.data_kind === "external")
    .map((r) => r.inst_id)
    .filter(Boolean))]
    .sort();
  const externalOptions = exportDatasets.length ? exportDatasets : ["cme_btc_yfinance"];
  const selectedExportSymbols = (exportForm.symbols || []).filter((s) => exportSymbols.includes(s));
  const selectedExportDatasets = (exportForm.datasets || []).filter((d) => externalOptions.includes(d));
  const selectedExportCount = exportKind === "external" ? selectedExportDatasets.length : selectedExportSymbols.length;
  const estRows = selectedExportCount * estDays * (ROWS_PER_DAY[exportKind === "ohlcv" ? exportForm.bar : exportKind] || 24);
  const estBytes = estRows * (exportForm.format === "xlsx" ? 60 : 80);
  const existingDbFetchSymbols = [...new Set((coverage || [])
    .filter((row) => (row.data_kind || "ohlcv") === "ohlcv" && row.bar === fetchForm.bar)
    .map((row) => row.inst_id)
    .filter(Boolean))]
    .sort();
  const fetchSearchQuery = String(instrumentQuery || "").trim();
  const searchResultSymbols = instruments.map((inst) => inst.inst_id).filter(Boolean);
  const allSearchResultsSelected = searchResultSymbols.length > 0
    && searchResultSymbols.every((symbol) => (fetchForm.symbols || []).includes(symbol));
  const fetchBusy = fetchJob && !FETCH_TERMINAL_STATUSES.has(fetchJob.status);
  const fetchCanCancel = !!fetchJob?.job_id && ["running", "cancelling"].includes(fetchJob.status);

  function refreshCoverage() {
    window.API.fetchDataCoverage().then(setCoverage).catch(() => setCoverage([]));
  }

  function currentFetchForm(overrides = {}) {
    const exchange = document.getElementById(FETCH_EXCHANGE_SELECT_ID)?.value || fetchForm.exchange || "okx";
    const bar = document.getElementById(FETCH_BAR_SELECT_ID)?.value || fetchForm.bar;
    const start = document.getElementById(FETCH_START_INPUT_ID)?.value || fetchForm.start;
    const end = document.getElementById(FETCH_END_INPUT_ID)?.value || fetchForm.end;
    return { ...fetchForm, exchange, bar, start, end, ...overrides };
  }

  function currentInstrumentQuery() {
    return String(document.getElementById(FETCH_QUERY_INPUT_ID)?.value ?? instrumentQuery ?? "").trim();
  }

  function refreshInstruments(exchange = fetchForm.exchange || "okx", query = instrumentQuery) {
    const cleanQuery = String(query || "").trim();
    const cleanExchange = String(exchange || "okx").toLowerCase();
    const searchSeq = ++marketDataInstrumentSearchSeq;
    if (!cleanQuery) {
      setInstruments([]);
      setInstrumentSearch({ status: "idle", exchange: cleanExchange, query: "", message: "" });
      return;
    }
    setInstrumentSearch({ status: "loading", exchange: cleanExchange, query: cleanQuery, message: "Searching..." });
    window.API.fetchDataInstruments(cleanExchange, cleanQuery)
      .then((rows) => {
        if (searchSeq !== marketDataInstrumentSearchSeq) return;
        setInstruments(rows || []);
        setInstrumentSearch({
          status: "done",
          exchange: cleanExchange,
          query: cleanQuery,
          message: `${(rows || []).length} match${(rows || []).length === 1 ? "" : "es"}`,
        });
      })
      .catch((err) => {
        if (searchSeq !== marketDataInstrumentSearchSeq) return;
        setInstruments([]);
        setInstrumentSearch({
          status: "error",
          exchange: cleanExchange,
          query: cleanQuery,
          message: err?.message || "Search failed",
        });
      });
  }

  function searchInstruments() {
    const form = currentFetchForm();
    const query = currentInstrumentQuery();
    setInstrumentQuery(query);
    setFetchForm((f) => ({ ...f, exchange: form.exchange, bar: form.bar, start: form.start, end: form.end, symbols: [] }));
    refreshInstruments(form.exchange, query);
  }

  useConfigEffect(() => {
    refreshCoverage();
    setInstruments([]);
  }, []);

  useConfigEffect(() => {
    setInstruments([]);
    setInstrumentSearch({ status: "idle", exchange: fetchForm.exchange || "okx", query: "", message: "" });
  }, [fetchForm.exchange]);

  useConfigEffect(() => {
    const savedJobId = localStorage.getItem("activeDataFetchJobId");
    if (!savedJobId || !window.API.fetchDataFetchStatus) {
      window.API.fetchDataFetchJobs?.()
        .then((jobs) => {
          const running = (jobs || []).find((j) => ["running", "cancelling"].includes(j.status));
          if (running?.job_id) {
            localStorage.setItem("activeDataFetchJobId", running.job_id);
            setFetchJob(running);
          }
        })
        .catch(() => {});
      return;
    }
    let stopped = false;
    let intervalId = null;
    const poll = () => {
      window.API.fetchDataFetchStatus(savedJobId).then((state) => {
        if (stopped) return;
        setFetchJob(state);
        if (FETCH_TERMINAL_STATUSES.has(state.status)) {
          localStorage.removeItem("activeDataFetchJobId");
          refreshCoverage();
          if (intervalId) clearInterval(intervalId);
        }
      }).catch(() => {
        localStorage.removeItem("activeDataFetchJobId");
        if (intervalId) clearInterval(intervalId);
      });
    };
    poll();
    intervalId = setInterval(poll, 2000);
    return () => {
      stopped = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  function triggerFetch() {
    startFetch(currentFetchForm({ existing_only: false }));
  }

  function triggerExistingOnlyFetch() {
    startFetch(currentFetchForm({ symbols: [], existing_only: true }));
  }

  function startFetch(body) {
    const exchange = String(body.exchange || "okx").toLowerCase();
    setFetchStartPending(true);
    setFetchJob({
      status: "running",
      progress: 1,
      exchange,
      existing_only: !!body.existing_only,
      symbols: body.symbols || [],
      symbol_count: body.existing_only ? existingDbFetchSymbols.length : (body.symbols || []).length,
      message: `Queueing ${exchange.toUpperCase()} ${body.existing_only ? "DB pair update" : "fetch"}...`,
    });
    window.API.triggerDataFetch(body).then((job) => {
      setFetchStartPending(false);
      setFetchJob(job);
      localStorage.setItem("activeDataFetchJobId", job.job_id);
      const iv = setInterval(() => {
        window.API.fetchDataFetchStatus(job.job_id).then((s) => {
          setFetchJob(s);
          if (FETCH_TERMINAL_STATUSES.has(s.status)) {
            clearInterval(iv);
            localStorage.removeItem("activeDataFetchJobId");
            refreshCoverage();
          }
        }).catch(() => {
          clearInterval(iv);
          localStorage.removeItem("activeDataFetchJobId");
        });
      }, 2000);
    }).catch((err) => {
      setFetchStartPending(false);
      setFetchJob({
        status: "error",
        progress: 0,
        exchange,
        message: err?.message || "Fetch request failed",
      });
    });
  }

  function cancelFetchJob() {
    if (!fetchJob?.job_id || fetchCancelPending || !window.API.cancelDataFetch) return;
    setFetchCancelPending(true);
    window.API.cancelDataFetch(fetchJob.job_id).then((job) => {
      setFetchJob(job);
      if (FETCH_TERMINAL_STATUSES.has(job.status)) {
        localStorage.removeItem("activeDataFetchJobId");
        refreshCoverage();
      }
    }).catch((err) => {
      setFetchJob((job) => job ? {
        ...job,
        status: job.status || "running",
        message: `Cancel failed: ${err?.message || "request failed"}`,
      } : {
        status: "error",
        progress: 0,
        message: `Cancel failed: ${err?.message || "request failed"}`,
      });
    }).finally(() => setFetchCancelPending(false));
  }

  function toggleFetchSymbol(symbol) {
    setFetchForm((f) => {
      const symbols = f.symbols || [];
      const next = symbols.includes(symbol)
        ? symbols.filter((s) => s !== symbol)
        : [...symbols, symbol];
      return { ...f, symbols: next };
    });
  }

  function toggleAllFetchSymbols() {
    setFetchForm((f) => ({ ...f, symbols: allSearchResultsSelected ? [] : searchResultSymbols }));
  }

  function toggleExportSymbol(symbol) {
    setExportForm((f) => {
      const symbols = f.symbols || [];
      const next = symbols.includes(symbol)
        ? symbols.filter((s) => s !== symbol)
        : [...symbols, symbol];
      return { ...f, symbols: next };
    });
  }
  function toggleExportDataset(dataset) {
    setExportForm((f) => {
      const datasets = f.datasets || [];
      const next = datasets.includes(dataset)
        ? datasets.filter((s) => s !== dataset)
        : [...datasets, dataset];
      return { ...f, datasets: next };
    });
  }

  function triggerExport() {
    const body = {
      kind: exportKind,
      bar: exportForm.bar,
      start: exportForm.start,
      end: exportForm.end,
      format: exportForm.format,
    };
    if (exportKind === "external") {
      const datasets = selectedExportDatasets.join(",");
      if (!datasets) return;
      setExportJob({ status: "running", message: "Refreshing external dataset..." });
      window.API.refreshExternalData({ dataset_ids: selectedExportDatasets, start: exportForm.start, end: exportForm.end })
        .then((job) => {
          setExportJob({ status: "done", message: `${job.datasets?.[0]?.rows_fetched || 0} rows refreshed` });
          window.location.assign(window.API.dataExportUrl({ ...body, datasets }));
          refreshCoverage();
        })
        .catch((err) => setExportJob({ status: "error", message: err.message }));
      return;
    }
    const symbols = selectedExportSymbols.join(",");
    if (!symbols) return;
    window.location.assign(window.API.dataExportUrl({ ...body, symbols }));
  }

  return html`
    <div class="card">
      <div class="card-h">
        <div>
          <div class="card-title">Market Data Coverage</div>
          <div class="card-sub">OHLCV, funding rates, and external feature observations stored in TimescaleDB</div>
        </div>
        <div class="row" style=${{ gap: 8 }}>
          <button class="btn sm" onClick=${() => setShowExportPanel((v) => !v)}>Export CSV</button>
          <button class="btn sm" onClick=${() => setShowFetchPanel((v) => !v)}>+ Add Pair Data</button>
        </div>
      </div>

      ${showExportPanel && html`
        <div class="card" style=${{ background: "var(--surface-2)", marginBottom: 16 }}>
          <div class="card-title" style=${{ marginBottom: 12 }}>Export Market Data</div>
          <div class="grid" style=${{ gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr", gap: 12 }}>
            <div class="field">
              <div class="field-label">${exportKind === "external" ? "External datasets" : "Trading pairs"}</div>
              <button class="btn sm" style=${{ marginBottom: 4 }}
                onClick=${() => {
                  if (exportKind === "external") {
                    const allSelected = externalOptions.length > 0 && selectedExportDatasets.length === externalOptions.length;
                    setExportForm((f) => ({ ...f, datasets: allSelected ? [] : [...externalOptions] }));
                  } else {
                    const allSelected = exportSymbols.length > 0 && selectedExportSymbols.length === exportSymbols.length;
                    setExportForm((f) => ({ ...f, symbols: allSelected ? [] : [...exportSymbols] }));
                  }
                }}>
                ${(exportKind === "external"
                  ? externalOptions.length > 0 && selectedExportDatasets.length === externalOptions.length
                  : exportSymbols.length > 0 && selectedExportSymbols.length === exportSymbols.length) ? "Deselect All" : "Select All"}
              </button>
              <div class="tbl-wrap" style=${{ maxHeight: 160 }}>
                <table class="tbl" style=${{ fontSize: 12 }}>
                  <tbody>
                    ${exportKind === "external" ? externalOptions.map((dataset) => html`
                      <tr key=${dataset} style=${{ cursor: "pointer" }} onClick=${() => toggleExportDataset(dataset)}>
                        <td style=${{ width: 28 }}>
                          <input
                            type="checkbox"
                            checked=${(exportForm.datasets || []).includes(dataset)}
                            onChange=${() => {}}
                          />
                        </td>
                        <td class="mono">${dataset}</td>
                      </tr>
                    `) : exportSymbols.length ? exportSymbols.map((symbol) => html`
                      <tr key=${symbol} style=${{ cursor: "pointer" }} onClick=${() => toggleExportSymbol(symbol)}>
                        <td style=${{ width: 28 }}>
                          <input
                            type="checkbox"
                            checked=${(exportForm.symbols || []).includes(symbol)}
                            onChange=${() => {}}
                          />
                        </td>
                        <td class="mono">${symbol}</td>
                      </tr>
                    `) : html`<tr><td colSpan=${2} class="field-hint" style=${{ padding: 12 }}>No DB trading pairs available for ${exportForm.bar}.</td></tr>`}
                  </tbody>
                </table>
              </div>
              <div class="field-hint">
                ${selectedExportCount} selected${exportKind === "ohlcv" && exportForm.bar === "1H" ? " - 1H exports are aggregated from 1m candles" : ""}
              </div>
              ${estRows > 0 && html`<div class="field-hint">Est. size: ~${fmtBytes(estBytes)}</div>`}
            </div>
            <div class="field">
              <div class="field-label">Kind</div>
              <select class="select mono" value=${exportKind}
                onChange=${(e) => setExportForm((f) => ({ ...f, kind: e.target.value, symbols: [], datasets: e.target.value === "external" ? ["cme_btc_yfinance"] : [] }))}>
                <option value="ohlcv">OHLCV</option>
                <option value="funding">Funding</option>
                <option value="external">External</option>
              </select>
            </div>
            <div class="field">
              <div class="field-label">Bar</div>
              <select class="select mono" value=${exportForm.bar}
                disabled=${exportKind !== "ohlcv"}
                onChange=${(e) => setExportForm((f) => ({ ...f, bar: e.target.value, symbols: [] }))}>
                ${["1H", "1m", "5m", "15m"].map((b) => html`<option key=${b}>${b}</option>`)}
              </select>
            </div>
            <div class="field">
              <div class="field-label">Start</div>
              <input class="input mono" type="date" value=${exportForm.start}
                onChange=${(e) => setExportForm((f) => ({ ...f, start: e.target.value }))} />
            </div>
            <div class="field">
              <div class="field-label">End</div>
              <input class="input mono" type="date" value=${exportForm.end}
                onChange=${(e) => setExportForm((f) => ({ ...f, end: e.target.value }))} />
            </div>
            <div class="field">
              <div class="field-label">Format</div>
              <select class="select mono" value=${exportForm.format}
                onChange=${(e) => setExportForm((f) => ({ ...f, format: e.target.value }))}>
                <option value="xlsx">xlsx (multi-sheet)</option>
                <option value="csv">csv (single file)</option>
              </select>
            </div>
          </div>
          ${exportJob && html`
            <div class="row" style=${{ gap: 8, marginTop: 10, alignItems: "center" }}>
              <span class=${`chip ${exportJob.status === "done" ? "profit" : exportJob.status === "error" ? "loss" : "warn"}`}>${exportJob.status}</span>
              <span class="field-hint">${exportJob.message || ""}</span>
            </div>
          `}
          <button class="btn primary sm" style=${{ marginTop: 12 }}
            disabled=${selectedExportCount < 1 || exportForm.start >= exportForm.end || exportJob?.status === "running"}
            onClick=${triggerExport}>
            Download Data
          </button>
        </div>
      `}

      ${showFetchPanel && html`
        <div class="card" style=${{ background: "var(--surface-2)", marginBottom: 16 }}>
          <div class="card-title" style=${{ marginBottom: 12 }}>Add Trading Pair Data to DB</div>
          <div class="field" style=${{ maxWidth: 760 }}>
            <div class="field-label">USDT swap trading pairs</div>
            <div class="row" style=${{ gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
              <input
                id=${FETCH_QUERY_INPUT_ID}
                class="input mono"
                style=${{ minWidth: 220, flex: "1 1 260px" }}
                placeholder="Search BTC, ETH, PEPE..."
                value=${instrumentQuery}
                onInput=${(e) => setInstrumentQuery(e.currentTarget.value)}
                onKeyDown=${(e) => {
                  if (e.key === "Enter") searchInstruments();
                }}
              />
              <button
                class="btn sm"
                onClick=${searchInstruments}
              >
                ${instrumentSearch.status === "loading" ? "Searching" : "Search"}
              </button>
              <button class="btn ghost sm" disabled=${!searchResultSymbols.length} onClick=${toggleAllFetchSymbols}>
                ${allSearchResultsSelected ? "Deselect All" : "Select All"}
              </button>
            </div>
            <div class="tbl-wrap" style=${{ maxHeight: 180 }}>
              <table class="tbl" style=${{ fontSize: 12 }}>
                <tbody>
                  ${instruments.length ? instruments.map((inst) => html`
                    <tr key=${inst.inst_id}>
                      <td style=${{ width: 28 }}>
                        <input
                          type="checkbox"
                          checked=${(fetchForm.symbols || []).includes(inst.inst_id)}
                          onChange=${() => toggleFetchSymbol(inst.inst_id)}
                        />
                      </td>
                      <td class="mono">${inst.inst_id}</td>
                      <td class="mono" style=${{ color: "var(--text-subtle)" }}>${inst.native_symbol && inst.native_symbol !== inst.inst_id ? inst.native_symbol : inst.exchange || ""}</td>
                      <td class="num mono" style=${{ color: "var(--text-subtle)" }}>${inst.list_date || "-"}</td>
                    </tr>
                  `) : html`
                    <tr>
                      <td colSpan=${4} class="field-hint" style=${{ padding: 12 }}>
                        ${instrumentSearch.status === "loading"
                          ? `Searching ${(fetchForm.exchange || "okx").toUpperCase()}...`
                          : instrumentSearch.status === "error"
                            ? `Search failed: ${instrumentSearch.message}`
                            : instrumentSearch.status === "done" && instrumentSearch.query
                              ? `No ${(instrumentSearch.exchange || fetchForm.exchange || "okx").toUpperCase()} matches for ${instrumentSearch.query || fetchSearchQuery}.`
                              : "Search exchange pairs, or update existing DB pairs only."}
                      </td>
                    </tr>
                  `}
                </tbody>
              </table>
            </div>
            <div class="field-hint">
              ${(fetchForm.symbols || []).length} selected from search - ${existingDbFetchSymbols.length} DB trading pairs available for ${fetchForm.bar}
            </div>
          </div>
          <div class="grid" style=${{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginTop: 12 }}>
            <div class="field">
              <div class="field-label">Exchange</div>
              <select id=${FETCH_EXCHANGE_SELECT_ID} class="select mono" value=${fetchForm.exchange || "okx"}
                onChange=${(e) => {
                  setInstruments([]);
                  setFetchForm((f) => ({ ...f, exchange: e.target.value, symbols: [] }));
                }}>
                <option value="okx">OKX</option>
                <option value="binance">Binance</option>
              </select>
            </div>
            <div class="field">
              <div class="field-label">Bar</div>
              <select id=${FETCH_BAR_SELECT_ID} class="select mono" value=${fetchForm.bar}
                onChange=${(e) => setFetchForm((f) => ({ ...f, bar: e.target.value }))}>
                ${["1m", "5m", "15m", "1H", "4H", "1D"].map((b) => html`<option key=${b}>${b}</option>`)}
              </select>
            </div>
            <div class="field">
              <div class="field-label">Start</div>
              <input id=${FETCH_START_INPUT_ID} class="input mono" type="date" value=${fetchForm.start}
                onChange=${(e) => setFetchForm((f) => ({ ...f, start: e.target.value }))} />
              ${latestSelectedListing && html`<div class="field-hint">trading pairs listed after start auto-fetch from their listing date; latest selected listing: ${latestSelectedListing}</div>`}
            </div>
            <div class="field">
              <div class="field-label">End</div>
              <input id=${FETCH_END_INPUT_ID} class="input mono" type="date" value=${fetchForm.end} max=${yesterday}
                onChange=${(e) => setFetchForm((f) => ({ ...f, end: e.target.value > yesterday ? yesterday : e.target.value }))} />
            </div>
          </div>
          ${fetchJob && html`
            <div class="row" style=${{ gap: 12, marginTop: 12, alignItems: "center" }}>
              <span class=${`chip ${fetchJob.status === "done" ? "profit" : fetchJob.status === "error" ? "loss" : "warn"}`}>
                ${fetchJob.status}
              </span>
              <${ProgressStage} job=${fetchJob} />
            </div>
          `}
          <div class="row" style=${{ gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            <button class="btn primary sm"
              disabled=${fetchStartPending || fetchBusy || !(fetchForm.symbols || []).length || fetchForm.start >= fetchForm.end}
              onClick=${triggerFetch}>
              Confirm and Fetch to DB
            </button>
            <button class="btn sm"
              disabled=${fetchStartPending || fetchBusy || !existingDbFetchSymbols.length || fetchForm.start >= fetchForm.end}
              onClick=${triggerExistingOnlyFetch}>
              Update DB Pairs Only (${existingDbFetchSymbols.length})
            </button>
            ${fetchCanCancel && html`
              <button class="btn ghost sm"
                disabled=${fetchCancelPending || fetchJob.status === "cancelling"}
                onClick=${cancelFetchJob}>
                ${fetchCancelPending || fetchJob.status === "cancelling" ? "Cancelling..." : "Cancel"}
              </button>
            `}
          </div>
          ${fetchJob?.results?.length > 0 && html`
            <div class="field-hint" style=${{ marginTop: 8 }}>
              ${fetchJob.results.map((r) => `${(r.exchange || fetchForm.exchange || "").toUpperCase()} ${r.symbol}${r.native_symbol && r.native_symbol !== r.symbol ? ` (${r.native_symbol})` : ""}: ${r.rows?.toLocaleString?.() ?? r.rows} rows from ${r.effective_start || r.list_date || "-"}`).join(" - ")}
            </div>
          `}
        </div>
      `}

      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Dataset / Trading Pair</th><th>Type</th><th>Bar / Frequency</th><th>Provider</th><th class="num">First date</th>
              <th class="num">Last date</th><th class="num">Rows</th>
              <th class="num">Gaps</th>
            </tr>
          </thead>
          <tbody>
            ${(coverage || []).map((row, i) => html`
              <tr key=${i}>
                <td class="mono">${row.inst_id}</td>
                <td>${row.data_kind || (row.bar === "funding" ? "funding" : "ohlcv")}</td>
                <td class="mono">${row.bar}</td>
                <td class="mono">${row.provider || "-"}</td>
                <td class="num mono">${row.first_ts ? new Date(row.first_ts).toISOString().slice(0, 10) : "-"}</td>
                <td class="num mono">${row.last_ts ? new Date(row.last_ts).toISOString().slice(0, 10) : "-"}</td>
                <td class="num">${(row.row_count || 0).toLocaleString()}</td>
                <td class="num" style=${{ color: row.gap_count > 0 ? "var(--warn)" : "var(--profit)" }}>
                  ${row.gap_count ?? "-"}
                </td>
              </tr>
            `)}
            ${(!coverage || !coverage.length) && html`
              <tr><td colSpan=${8} class="field-hint" style=${{ textAlign: "center", padding: 24 }}>No data in DB. Use "Fetch from Exchange" or external ingest scripts to load historical data.</td></tr>
            `}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

window.RunConfigView = RunBacktestView;
window.KPI = KPI;

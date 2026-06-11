import { h } from 'preact';
import { useState, useEffect, useCallback } from 'preact/hooks';
import { html } from 'htm/preact';

// Backtest Runs browser + Run Detail view — reads from /api/backtest/* endpoints.
const { LineChart, TradePriceChart, IndicatorChart, adaptiveDateLabel, MAX_Y_ZOOM = 8 } = window.Charts;

const TECHNICAL_STRATEGIES_SET = new Set(["ma_crossover", "ema_crossover", "macd_crossover"]);

const PHASE2_IDLE_PARTS = {
  equity: false,
  ledger: false,
  validation: false,
  market: false,
  risk: false,
  indicators: false,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function n(v, d = 2) { return v == null || isNaN(+v) ? "—" : (+v).toFixed(d); }
function pct(v) { return v == null || isNaN(+v) ? "—" : ((+v) * 100).toFixed(2) + "%"; }
function usd(v, d = 2) { return v == null || isNaN(+v) ? "—" : "$" + Math.abs(+v).toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d }); }
function fmtDt(s) { if (!s) return "—"; try { return new Date(s).toISOString().slice(0, 19).replace("T", " "); } catch { return s; } }
function parseObj(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  if (typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}
function runParametersText(run) {
  const params = run?.parameters || {};
  const strategyParams = params.strategies || {};
  const overrideParams = parseObj(params.overrides?.strategy_params);
  const names = (run?.strategies || [run?.strategy]).filter(Boolean);
  const parts = [];
  for (const name of names) {
    const p = { ...(strategyParams[name] || {}), ...(names.length === 1 ? overrideParams : {}) };
    if (name === "ma_crossover" && (p.fast_window || p.slow_window)) parts.push(`MA ${p.fast_window ?? "?"}/${p.slow_window ?? "?"}`);
    else if (name === "ema_crossover" && (p.fast_span || p.slow_span)) parts.push(`EMA ${p.fast_span ?? "?"}/${p.slow_span ?? "?"}`);
    else if (name === "macd_crossover" && (p.fast_span || p.slow_span || p.signal_span)) parts.push(`MACD ${p.fast_span ?? "?"}/${p.slow_span ?? "?"}/${p.signal_span ?? "?"}`);
  }
  const risk = { ...(params.risk || {}), ...parseObj(params.overrides?.risk_overrides) };
  if (risk.max_pos_pct_equity != null) parts.push(`max pos ${(+risk.max_pos_pct_equity * 100).toFixed(0)}%`);
  if (risk.max_order_notional_usd != null) parts.push(`order $${(+risk.max_order_notional_usd).toLocaleString("en", { maximumFractionDigits: 0 })}`);
  if (risk.max_leverage != null) parts.push(`lev ${(+risk.max_leverage).toFixed(1)}x`);
  return parts.length ? parts.join(" | ") : "—";
}
function signedUsd(v, d = 2) {
  if (v == null || isNaN(+v)) return "—";
  const sign = +v < 0 ? "-" : "";
  return sign + "$" + Math.abs(+v).toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function chartTimestamp(row) {
  return row?.datetime || row?.ts || "";
}
function parseChartDate(value) {
  if (value == null || value === "") return null;
  const raw = typeof value === "string" && /^\d+$/.test(value) ? +value : value;
  const d = new Date(raw);
  return isNaN(d.getTime()) ? null : d;
}
function chartDateTick(value) {
  const d = parseChartDate(value);
  return d ? d.toISOString().slice(0, 10) : String(value || "—");
}
function safeNum(v) {
  return v == null || v === "" ? NaN : +v;
}
function chartRangeMs(range) {
  if (!range || !Array.isArray(range)) return NaN;
  const [startMs, endMs] = range;
  return Number.isFinite(startMs) && Number.isFinite(endMs) ? Math.abs(endMs - startMs) : NaN;
}
function chartDateTickForRange(range) {
  const span = chartRangeMs(range);
  return (value, _idx, visibleSpan) => adaptiveDateLabel(value, Number.isFinite(visibleSpan) ? visibleSpan : span);
}
function chartDateTooltip(value) {
  const d = parseChartDate(value);
  return d ? d.toISOString().slice(0, 19).replace("T", " ") + " UTC" : String(value || "—");
}

function parseMetadata(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  if (typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function firstFinite(...values) {
  for (const value of values) {
    const n = +value;
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function tradeNotional(row, price, qty) {
  const meta = parseMetadata(row?.metadata);
  const explicit = firstFinite(row?.notional_usd, row?.notional, meta.notional_usd);
  if (explicit != null) return Math.abs(explicit);
  const ctVal = firstFinite(row?.ct_val, meta.ct_val, 1);
  const fallback = Math.abs((+price || 0) * (+qty || 0) * (ctVal ?? 1));
  return Number.isFinite(fallback) ? fallback : 0;
}

function markerMatchKey(row) {
  const price = firstFinite(row?.price, row?.fill_px, row?.px, 0);
  const qty = firstFinite(row?.qty, row?.fill_sz, row?.sz, 0);
  return [
    row?.inst_id || row?.symbol || "",
    row?.ts || row?.datetime || "",
    String(row?.side || "").toLowerCase(),
    (price ?? 0).toFixed(8),
    (qty ?? 0).toFixed(8),
  ].join("|");
}

const SYMBOL_COLORS = [
  "#2563eb",
  "#dc2626",
  "#059669",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#4f46e5",
];

function symbolColor(symbol, index = 0) {
  return SYMBOL_COLORS[Math.abs(index) % SYMBOL_COLORS.length];
}

function validationModeFrom(validation, metrics, walkForward, cpcv) {
  const windows = walkForward || [];
  const combos = cpcv?.combos || [];
  if (validation?.validation_mode) return validation.validation_mode;
  if (validation?.validation_requested) return validation.validation_requested;
  if (metrics?.validation_requested) return metrics.validation_requested;
  return (windows.length || combos.length) ? "embedded" : "none";
}

function validationModeForRun(result) {
  if (!result) return "none";
  return validationModeFrom(
    result.validation || {},
    result.metrics || {},
    result.walk_forward || result.walkForward || [],
    result.cpcv || null,
  );
}

// ---------------------------------------------------------------------------
// Metric descriptions for tooltip (title) on hover
// ---------------------------------------------------------------------------
const METRIC_DESCRIPTIONS = {
  sharpe:                   { desc: "Annualized Sharpe ratio: (mean return - risk-free) / return volatility", unit: "dimensionless" },
  sortino:                  { desc: "Sharpe variant that only penalizes downside volatility", unit: "dimensionless" },
  calmar:                   { desc: "CAGR / |Max Drawdown| — return per unit of peak-to-trough loss", unit: "dimensionless" },
  omega:                    { desc: "Ratio of gains to losses above a threshold return (>1 is profitable)", unit: "dimensionless" },
  dsr:                      { desc: "Deflated Sharpe Ratio: Sharpe adjusted for multiple-testing bias (CPCV gate ≥ 0.95)", unit: "dimensionless" },
  psr:                      { desc: "Probabilistic Sharpe Ratio: probability that true Sharpe > 0", unit: "probability [0,1]" },
  total_return:             { desc: "Total percentage return over the full backtest period", unit: "%" },
  cagr:                     { desc: "Compound Annual Growth Rate", unit: "%" },
  max_drawdown:             { desc: "Largest peak-to-trough equity decline during the period", unit: "%" },
  win_rate:                 { desc: "Fraction of closed trades that were profitable", unit: "% [0,1]" },
  profit_factor:            { desc: "Gross profit / gross loss across all trades (>1 is profitable)", unit: "dimensionless" },
  fill_rate:                { desc: "Fraction of submitted orders that were filled (1.0 = all filled)", unit: "ratio [0,1]" },
  bankrupt:                 { desc: "True if equity fell below zero at any point during the backtest", unit: "boolean" },
  kurtosis:                 { desc: "Fat-tail measure of return distribution (>3 = heavier tails than normal)", unit: "dimensionless" },
  skewness:                 { desc: "Asymmetry of return distribution (positive = right-skewed, occasional large gains)", unit: "dimensionless" },
  n_periods:                { desc: "Total number of time bars processed in the simulation", unit: "bars" },
  fill_count:               { desc: "Total fill events recorded (includes partial fills)", unit: "count" },
  real_fill_count:          { desc: "Number of fills with non-zero quantity and filled/partially_filled state", unit: "count" },
  partial_fill_count:       { desc: "Fills with state=partially_filled (order not yet fully executed)", unit: "count" },
  orders_filled_count:      { desc: "Number of unique orders that received at least one fill", unit: "count" },
  submitted_order_count:    { desc: "Total number of orders submitted to the execution engine", unit: "count" },
  order_count:              { desc: "Total number of orders submitted to the execution engine", unit: "count" },
  min_equity:               { desc: "Minimum account equity reached during the simulation (negative = insolvent)", unit: "USD" },
  last_equity:              { desc: "Final account equity at the end of the simulation", unit: "USD" },
  total_fees:               { desc: "Total trading fees paid across all fills", unit: "USD" },
  fill_notional_usd:        { desc: "Total gross notional value of all fills", unit: "USD" },
  funding_cashflow:         { desc: "Net cashflow from funding rate settlements (positive = earned, negative = paid)", unit: "USD" },
  funding_settlement_count: { desc: "Number of funding settlement events processed", unit: "count" },
  tail_ratio:               { desc: "95th percentile gain / |5th percentile loss| - measures tail balance", unit: "dimensionless" },
  pending_fill_event_count: { desc: "Number of fill events still in pending state at backtest end", unit: "count" },
  terminal_open_position_count: { desc: "Open positions still present before terminal liquidation or end-of-run closeout", unit: "count" },
  terminal_liquidation_fill_count: { desc: "Synthetic fills generated to close remaining positions at the run endpoint", unit: "count" },
  terminal_liquidation_notional_usd: { desc: "Notional value closed by terminal liquidation fills", unit: "USD" },
  validation_only:          { desc: "True when the strategy/run is for system validation only and is not deployable", unit: "boolean" },
  number_of_trades:         { desc: "Strategy-specific count of completed round trips or trade decisions", unit: "count" },
  expected_trade_days:      { desc: "Expected number of trading days in a daily validation run", unit: "days" },
  loaded_symbols:           { desc: "Symbols that had enough data and were included in the run", unit: "list" },
  skipped_symbols:          { desc: "Requested symbols skipped because data was unavailable or invalid", unit: "list" },
};

function metricTitle(key) {
  const entry = METRIC_DESCRIPTIONS[key];
  if (!entry) return key;
  return `${entry.desc}\nUnit: ${entry.unit}`;
}

// ---------------------------------------------------------------------------
// Delete confirmation modal
// ---------------------------------------------------------------------------
function DeleteModal({ runId, onConfirm, onCancel }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  function handleDelete() {
    setDeleting(true);
    setError(null);
    window.API.deleteRun(runId)
      .then(() => onConfirm(runId))
      .catch((e) => { setError(e.message); setDeleting(false); });
  }

  return html`
    <div style=${{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.45)", display: "flex",
      alignItems: "center", justifyContent: "center",
    }} onClick=${onCancel}>
      <div style=${{
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 12, padding: 28, minWidth: 360, maxWidth: 480,
        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
      }} onClick=${(e) => e.stopPropagation()}>
        <div style=${{ fontWeight: 600, fontSize: 16, marginBottom: 8, color: "var(--loss)" }}>Delete backtest run?</div>
        <div class="field-hint" style=${{ marginBottom: 16 }}>
          This will permanently remove all artifacts for:
        </div>
        <div class="mono" style=${{
          fontSize: 12, background: "var(--surface-2)", borderRadius: 6,
          padding: "8px 12px", marginBottom: 20, wordBreak: "break-all",
          color: "var(--text-muted)",
        }}>${runId}</div>
        ${error && html`<div style=${{ color: "var(--loss)", fontSize: 13, marginBottom: 12 }}>Error: ${error}</div>`}
        <div class="row" style=${{ gap: 8, justifyContent: "flex-end" }}>
          <button class="btn ghost sm" onClick=${onCancel} disabled=${deleting}>Cancel</button>
          <button
            class="btn sm"
            style=${{ background: "var(--loss)", color: "#fff", borderColor: "transparent" }}
            onClick=${handleDelete}
            disabled=${deleting}
          >${deleting ? "Deleting…" : "Delete"}</button>
        </div>
      </div>
    </div>
  `;
}

function StatusBadge({ ok, children }) {
  return html`
    <span class="chip" style=${{
      background: ok ? "var(--profit-soft)" : "var(--loss-soft)",
      color: ok ? "var(--profit)" : "var(--loss)",
      borderColor: "transparent",
    }}>${children}</span>
  `;
}

function MetricCard({ label, value, sub, tone }) {
  const color = tone === "up" ? "var(--profit)" : tone === "down" ? "var(--loss)" : "var(--text)";
  return html`
    <div class="card" style=${{ padding: "14px 16px" }}>
      <div class="kpi-label" style=${{ marginBottom: 4 }}>${label}</div>
      <div class="mono" style=${{ fontSize: 20, fontWeight: 600, color }}>${value}</div>
      ${sub && html`<div class="field-hint" style=${{ marginTop: 4 }}>${sub}</div>`}
    </div>
  `;
}

function MetricValue({ value }) {
  if (Array.isArray(value)) {
    return html`
      <div class="mono" style=${{ display: "grid", gap: 2, lineHeight: 1.35, overflowWrap: "anywhere" }}>
        ${value.map((item, i) => html`<div key=${i}>${String(item)}</div>`)}
      </div>
    `;
  }
  if (value && typeof value === "object") {
    return html`
      <pre class="mono" style=${{
        margin: 0,
        whiteSpace: "pre-wrap",
        overflowWrap: "anywhere",
        fontSize: 12,
        lineHeight: 1.35,
      }}>${JSON.stringify(value, null, 2)}</pre>
    `;
  }
  if (typeof value === "boolean") {
    return html`<span style=${{ color: value ? "var(--loss)" : "var(--profit)" }}>${String(value)}</span>`;
  }
  const text = typeof value === "number"
    ? (Math.abs(value) < 1 && value !== 0 ? value.toFixed(4) : value.toFixed(2))
    : String(value);
  return html`<span class="mono" style=${{ overflowWrap: "anywhere" }}>${text}</span>`;
}

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function hasDisplayRows(value) {
  return isPlainObject(value) && Object.keys(value).length > 0;
}

function parameterLabel(key) {
  return String(key).replace(/_/g, " ");
}

function parameterValue(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    return Math.abs(value) >= 1000 ? value.toLocaleString("en", { maximumFractionDigits: 2 }) : String(value);
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function parameterGroupsForRun(run) {
  const params = run?.parameters || {};
  const groups = [];
  const strategyParams = isPlainObject(params.strategies) ? params.strategies : {};
  const names = (run?.strategies || [run?.strategy]).filter(Boolean);
  for (const name of names) {
    const values = strategyParams[name];
    if (hasDisplayRows(values)) {
      groups.push({ title: `${name} strategy`, rows: values });
    }
  }
  if (hasDisplayRows(params.risk)) {
    groups.push({ title: "Risk", rows: params.risk });
  }
  if (hasDisplayRows(params.backtest)) {
    groups.push({ title: "Backtest Execution", rows: params.backtest });
  }
  const overrides = params.overrides || {};
  if (hasDisplayRows(overrides.strategy_params)) {
    groups.push({ title: "Strategy Overrides", rows: overrides.strategy_params });
  }
  if (hasDisplayRows(overrides.risk_overrides)) {
    groups.push({ title: "Risk Overrides", rows: overrides.risk_overrides });
  }
  return groups;
}

function ParametersPanel({ run }) {
  const groups = parameterGroupsForRun(run);
  if (!groups.length) return null;
  return html`
    <div class="card">
      <div class="card-h">
        <div>
          <div class="card-title">Parameters</div>
          <div class="card-sub">strategy, risk, and replay execution inputs</div>
        </div>
      </div>
      <div class="param-group-grid">
        ${groups.map((group) => html`
          <div class="param-group" key=${group.title}>
            <div class="param-group-title">${group.title}</div>
            <div class="param-kv-grid">
              ${Object.entries(group.rows).map(([key, value]) => html`
                <div class="param-kv" key=${key}>
                  <div class="param-key">${parameterLabel(key)}</div>
                  <div class="param-value mono" title=${parameterValue(value)}>${parameterValue(value)}</div>
                </div>
              `)}
            </div>
          </div>
        `)}
      </div>
    </div>
  `;
}

function ExecutionQualitySummary({ metrics, parameters }) {
  const partial = +(metrics.partial_fill_count ?? 0);
  const pending = +(metrics.pending_fill_event_count ?? 0);
  const realFills = +(metrics.real_fill_count ?? metrics.fill_count ?? 0);
  const fillRate = metrics.fill_rate;
  const queueFraction = parameters?.backtest?.queue_fill_fraction;
  if (!partial && !pending && !(fillRate != null && +fillRate > 1)) return null;
  return html`
    <div class="card">
      <div class="card-h">
        <div>
          <div class="card-title">Execution Quality</div>
          <div class="card-sub">partial fills are replay lifecycle states, not risk rejections</div>
        </div>
      </div>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${MetricCard} label="Partial Fills" value=${partial.toLocaleString()} sub=${realFills ? `${pct(partial / realFills)} of real fills` : "no real fills"} tone=${partial ? "down" : undefined} />
        <${MetricCard} label="Pending Events" value=${pending.toLocaleString()} sub="unfilled at run end" tone=${pending ? "down" : undefined} />
        <${MetricCard} label="Fill Rate" value=${pct(fillRate)} sub="unique filled orders / submitted orders" tone=${fillRate != null && +fillRate <= 1 ? "up" : "down"} />
        <${MetricCard} label="Queue Fraction" value=${queueFraction == null ? "—" : pct(queueFraction)} sub="replay queue allocation" />
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Bankruptcy / anomaly banner
// ---------------------------------------------------------------------------
function AnomalyBanner({ metrics }) {
  const warnings = [];
  if (metrics.bankrupt) warnings.push("⚠ equity went below zero during the period — would be liquidated in live trading");
  if (metrics.fill_rate != null && +metrics.fill_rate > 1) warnings.push(`fill_rate ${(+metrics.fill_rate).toFixed(2)} > 1 — check execution model`);
  if (Math.abs(+metrics.max_drawdown) > 1) warnings.push(`max_drawdown ${pct(metrics.max_drawdown)} exceeds 100% — position sizing too aggressive`);
  if (metrics.sharpe != null && Math.abs(+metrics.sharpe) < 0.1) warnings.push("Sharpe ≈ 0 — returns indistinguishable from noise");
  if (!warnings.length) return null;
  return html`
    <div style=${{ background: "var(--loss-soft)", border: "1px solid var(--loss)", borderRadius: 8, padding: "12px 16px" }}>
      <div style=${{ fontWeight: 600, color: "var(--loss)", marginBottom: 6 }}>Strategy Risk Warnings</div>
      ${warnings.map((w, i) => html`<div key=${i} style=${{ color: "var(--loss)", fontSize: 13, marginTop: 4 }}>• ${w}</div>`)}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Run Detail View — phase-1 loads result immediately; phase-2 loads heavy data
// ---------------------------------------------------------------------------
function ChartZoomControls({
  range,
  onReset,
  xResetLabel = "Reset X",
  yZoom = 1,
  onYZoomIn = null,
  onYZoomOut = null,
  onYReset = null,
  yResetLabel = "Reset Y",
}) {
  const hasRange = Array.isArray(range);
  const hasYControls = typeof onYZoomIn === "function" || typeof onYZoomOut === "function";
  const isYZoomed = Number.isFinite(+yZoom) && +yZoom > 1.0001;
  if (!hasRange && !hasYControls) return null;
  const [startMs, endMs] = hasRange ? range : [null, null];
  const fmtZoom = (ms) => {
    const d = new Date(ms);
    return isNaN(d.getTime()) ? "--" : d.toISOString().slice(0, 16).replace("T", " ");
  };
  return html`
    <div class="chart-zoom-reset" role="status">
      <div class="chart-zoom-caption">
        ${hasRange ? `Zoom ${fmtZoom(startMs)} - ${fmtZoom(endMs)} UTC` : `Y ${(+yZoom || 1).toFixed(1)}x`}
      </div>
      ${hasYControls && html`
        <button class="btn ghost sm" type="button" title="Zoom Y axis in" aria-label="Zoom Y axis in" onClick=${onYZoomIn}>Y+</button>
        <button class="btn ghost sm" type="button" title="Zoom Y axis out" aria-label="Zoom Y axis out" disabled=${!isYZoomed} onClick=${onYZoomOut}>Y-</button>
      `}
      ${hasRange && typeof onReset === "function" && html`
        <button class="btn ghost sm" type="button" onClick=${onReset}>${xResetLabel}</button>
      `}
      ${isYZoomed && typeof onYReset === "function" && html`
        <button class="btn ghost sm" type="button" onClick=${onYReset}>${yResetLabel}</button>
      `}
    </div>
  `;
}

function RunDetailView({ runId, onBack, onDelete }) {
  const [result, setResult] = useState(null);
  const [phase1Loading, setPhase1Loading] = useState(true);
  const [phase1Error, setPhase1Error] = useState(null);

  const [equity, setEquity] = useState([]);
  const [fills, setFills] = useState([]);
  const [trades, setTrades] = useState([]);
  const [walkForward, setWalkForward] = useState([]);
  const [cpcv, setCpcv] = useState(null);
  const [riskEvents, setRiskEvents] = useState([]);
  const [priceSeries, setPriceSeries] = useState([]);
  const [executionMarkers, setExecutionMarkers] = useState([]);
  const [, setPhase2Loading] = useState(true);
  const [phase2Parts, setPhase2Parts] = useState(PHASE2_IDLE_PARTS);
  const [phase2Error, setPhase2Error] = useState(null);

  const [activeTab, setActiveTab] = useState("fills");
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedChartSymbols, setSelectedChartSymbols] = useState([]);
  const [chartRanges, setChartRanges] = useState(new Map());
  const [chartYZooms, setChartYZooms] = useState(new Map());
  const [visibleSeries, setVisibleSeries] = useState(new Map());
  const [indicators, setIndicators] = useState([]);

  // Phase 1: load result.json (fast — small payload)
  useEffect(() => {
    setPhase1Loading(true);
    setPhase1Error(null);
    setResult(null);
    window.API.fetchBacktest(runId)
      .then((r) => setResult(r))
      .catch((e) => setPhase1Error(e.message))
      .finally(() => setPhase1Loading(false));
  }, [runId]);

  // Phase 2: load heavy data after phase 1 completes
  useEffect(() => {
    if (!result) return;
    let cancelled = false;
    const activeStrategiesForLoad = result.strategies || (result.strategy ? [result.strategy] : []);
    const shouldLoadValidation = validationModeForRun(result) !== "none";
    const shouldLoadIndicators = activeStrategiesForLoad.some((s) => TECHNICAL_STRATEGIES_SET.has(s));
    const setPartDone = (key) => {
      if (!cancelled) setPhase2Parts((prev) => ({ ...prev, [key]: false }));
    };

    setPhase2Loading(true);
    setPhase2Parts({
      equity: true,
      ledger: true,
      validation: shouldLoadValidation,
      market: true,
      risk: true,
      indicators: shouldLoadIndicators,
    });
    setPhase2Error(null);
    setEquity([]);
    setFills([]);
    setTrades([]);
    setWalkForward([]);
    setCpcv(null);
    setRiskEvents([]);
    setPriceSeries([]);
    setExecutionMarkers([]);
    setSelectedChartSymbols([]);
    setIndicators([]);
    setChartRanges(new Map());
    setChartYZooms(new Map());
    setVisibleSeries(new Map());
    const tasks = [];

    tasks.push(
      window.API.fetchBacktestEquity(runId)
        .then((eq) => { if (!cancelled) setEquity(eq || []); })
        .catch((e) => { if (!cancelled) { setEquity([]); setPhase2Error(e.message); } })
        .finally(() => setPartDone("equity"))
    );

    tasks.push(
      Promise.all([
        window.API.fetchBacktestFills(runId).catch(() => []),
        window.API.fetchBacktestTrades(runId).catch(() => []),
      ]).then(([fl, tr]) => {
        if (cancelled) return;
        setFills(fl || []);
        setTrades(tr || []);
      }).finally(() => setPartDone("ledger"))
    );

    if (shouldLoadValidation) {
      tasks.push(
        Promise.all([
          window.API.fetchWalkForward(runId).catch(() => []),
          window.API.fetchCPCV(runId).catch(() => null),
        ]).then(([wf, cv]) => {
          if (cancelled) return;
          setWalkForward(wf || []);
          setCpcv(cv || null);
        }).finally(() => setPartDone("validation"))
      );
    }

    tasks.push(
      window.API.fetchBacktestRiskEvents(runId)
        .then((re) => { if (!cancelled) setRiskEvents(re || []); })
        .catch(() => { if (!cancelled) setRiskEvents([]); })
        .finally(() => setPartDone("risk"))
    );

    tasks.push(
      Promise.all([
        window.API.fetchBacktestPriceSeries(runId).catch(() => []),
        window.API.fetchBacktestExecutionMarkers(runId).catch(() => []),
      ]).then(([ps, em]) => {
        if (cancelled) return;
        setPriceSeries(ps || []);
        setExecutionMarkers(em || []);
      }).finally(() => setPartDone("market"))
    );

    if (shouldLoadIndicators) {
      tasks.push(
        (window.API.fetchBacktestIndicators?.(runId) ?? Promise.resolve([]))
          .then((ind) => { if (!cancelled) setIndicators(ind || []); })
          .catch(() => { if (!cancelled) setIndicators([]); })
          .finally(() => setPartDone("indicators"))
      );
    }

    Promise.allSettled(tasks).finally(() => {
      if (!cancelled) setPhase2Loading(false);
    });
    return () => { cancelled = true; };
  }, [runId, result]);

  if (phase1Loading) return html`<div class="field-hint" style=${{ padding: 32 }}>Loading run ${runId}…</div>`;
  if (phase1Error) return html`<div style=${{ color: "var(--loss)", padding: 32 }}>Error: ${phase1Error}</div>`;
  if (!result) return null;

  const m = result.metrics || {};
  const equityLoading = phase2Parts.equity;
  const ledgerLoading = phase2Parts.ledger;
  const validationLoading = phase2Parts.validation;
  const marketLoading = phase2Parts.market;
  const riskLoading = phase2Parts.risk;
  const bottomPanelLoading = activeTab === "risk" ? riskLoading : ledgerLoading;
  const activeStrategies = result.strategies || (result.strategy ? [result.strategy] : []);
  const isDailyWinnerRun = activeStrategies.includes("daily_winner");
  const fundingNotModeled = isDailyWinnerRun || m.funding_mode === "not_modeled";
  const totalCostLabel = isDailyWinnerRun ? "Total Costs" : "Total Fees";
  const totalCostSub = isDailyWinnerRun
    ? `Notional ${usd(m.fill_notional_usd)} (fee+slip)`
    : `Notional ${usd(m.fill_notional_usd)}`;
  const strats = (result.strategies || []).join(", ") || result.strategy || "—";
  const symbols = (result.symbols || []).join(", ") || result.symbol || "—";
  const bar = result.bar || "—";
  const start = result.start ? result.start.slice(0, 10) : "—";
  const end = result.end ? result.end.slice(0, 10) : "—";

  const equityChartRows = equity.filter(r => r.equity != null);
  const drawdownChartRows = equity.filter(r => r.drawdown != null);
  const eqValues = equityChartRows.map(r => +r.equity);
  const eqDates = equityChartRows.map(chartTimestamp);
  const ddValues = drawdownChartRows.map(r => +r.drawdown);
  const ddDates = drawdownChartRows.map(chartTimestamp);
  const chartSymbols = [...new Set([
    ...(result.symbols || []),
    ...priceSeries.map((r) => r.inst_id).filter(Boolean),
    ...executionMarkers.map((r) => r.inst_id).filter(Boolean),
  ])].sort();
  const chartSymbolColors = Object.fromEntries(chartSymbols.map((symbol, i) => [symbol, symbolColor(symbol, i)]));
  const effectiveSelectedChartSymbols = selectedChartSymbols.length
    ? selectedChartSymbols
    : chartSymbols.slice(0, 1);
  const fillNotionalByMarker = new Map();
  for (const fill of fills) {
    const price = +(fill.fill_px ?? fill.price ?? fill.px ?? 0);
    const qty = +(fill.fill_sz ?? fill.qty ?? fill.sz ?? 0);
    fillNotionalByMarker.set(markerMatchKey(fill), tradeNotional(fill, price, qty));
  }
  const enrichedExecutionMarkers = executionMarkers.map((marker) => ({
    ...marker,
    notional_usd: firstFinite(marker.notional_usd, fillNotionalByMarker.get(markerMatchKey(marker))),
  }));
  const selectedSymbolSet = new Set(effectiveSelectedChartSymbols);
  const filteredPriceSeries = priceSeries.filter((r) => selectedSymbolSet.has(r.inst_id));
  const filteredMarkers = enrichedExecutionMarkers.filter((r) => selectedSymbolSet.has(r.inst_id));
  const filteredTrades = trades.filter((r) => selectedSymbolSet.has(r.inst_id || r.symbol));
  const filteredFills = fills.filter((r) => selectedSymbolSet.has(r.inst_id || r.symbol));
  const filteredRiskEvents = riskEvents.filter((r) => selectedSymbolSet.has(r.inst_id || r.symbol));

  const realFills = filteredFills.filter(f => f.fill_sz && +f.fill_sz > 0 && (f.state === "filled" || f.state === "partially_filled"));

  function getChartRange(id) {
    const setRange = (nextRange) => {
      setChartRanges((prev) => {
        const next = new Map(prev);
        if (nextRange) next.set(id, nextRange);
        else next.delete(id);
        return next;
      });
    };
    return [chartRanges.get(id) || null, setRange];
  }

  function getChartYControls(id) {
    const yZoom = chartYZooms.get(id) || 1;
    const setYZoom = (nextValue) => {
      setChartYZooms((prev) => {
        const next = new Map(prev);
        const clean = Math.max(1, Math.min(MAX_Y_ZOOM, Number.isFinite(+nextValue) ? +nextValue : 1));
        if (clean <= 1.0001) next.delete(id);
        else next.set(id, clean);
        return next;
      });
    };
    return {
      yZoom,
      onYZoomIn: () => setYZoom(yZoom * 1.4),
      onYZoomOut: () => setYZoom(yZoom / 1.4),
      onYReset: () => setYZoom(1),
    };
  }

  function indicatorVisibleState(id, hasMacd) {
    const current = visibleSeries.get(id);
    return {
      price: current?.price !== false,
      fast: current?.fast !== false,
      slow: current?.slow !== false,
      macd: hasMacd ? current?.macd !== false : false,
    };
  }

  function toggleIndicatorSeries(id, key, hasMacd) {
    setVisibleSeries((prev) => {
      const current = indicatorVisibleState(id, hasMacd);
      const visibleKeys = ["price", "fast", "slow", ...(hasMacd ? ["macd"] : [])].filter((k) => current[k]);
      if (current[key] && visibleKeys.length <= 1) return prev;
      const next = new Map(prev);
      next.set(id, { ...current, [key]: !current[key] });
      return next;
    });
  }

  const [marketRange, setMarketRange] = getChartRange("market");
  const [equityRange, setEquityRange] = getChartRange("equity");
  const [drawdownRange, setDrawdownRange] = getChartRange("drawdown");

  // Technical-indicator strategies render per-symbol IndicatorChart cards.
  const isTechnicalRun = activeStrategies.some((s) => TECHNICAL_STRATEGIES_SET.has(s));
  const indicatorBySymbol = (() => {
    if (!isTechnicalRun || !indicators.length) return new Map();
    const groups = new Map();
    for (const row of indicators) {
      const sym = row.inst_id || row.symbol || "";
      if (!groups.has(sym)) groups.set(sym, []);
      groups.get(sym).push(row);
    }
    for (const rows of groups.values()) {
      rows.sort((a, b) => new Date(chartTimestamp(a)).getTime() - new Date(chartTimestamp(b)).getTime());
    }
    return groups;
  })();
  const indicatorSymbols = [...indicatorBySymbol.keys()].filter((s) => selectedSymbolSet.has(s));
  const markersBySymbol = new Map();
  for (const m of enrichedExecutionMarkers) {
    const sym = m.inst_id || m.symbol || "";
    if (!sym) continue;
    if (!markersBySymbol.has(sym)) markersBySymbol.set(sym, []);
    markersBySymbol.get(sym).push(m);
  }

  const tradesMap = new Map();
  for (const t of filteredTrades) {
    if (t.cl_ord_id && t.net_realized_pnl != null) {
      tradesMap.set(t.cl_ord_id, (tradesMap.get(t.cl_ord_id) ?? 0) + +t.net_realized_pnl);
    }
  }
  const priceChartSymbols = effectiveSelectedChartSymbols.filter((sym) =>
    filteredPriceSeries.some((row) => row.inst_id === sym)
  );
  const equityY = getChartYControls("equity");
  const drawdownY = getChartYControls("drawdown");

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      ${showDeleteModal && html`
        <${DeleteModal}
          runId=${runId}
          onConfirm=${() => { setShowDeleteModal(false); onDelete?.(runId); onBack(); }}
          onCancel=${() => setShowDeleteModal(false)}
        />
      `}

      <div class="row" style=${{ alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <button class="btn ghost sm" onClick=${onBack}>← Runs</button>
        <div class="mono" style=${{ fontSize: 13, color: "var(--text-subtle)", flex: 1 }}>${runId}</div>
        <span class="chip">${strats}</span>
        <span class="chip">${symbols}</span>
        <span class="chip">${bar}</span>
        <span class="chip">${start} → ${end}</span>
        <${StatusBadge} ok=${!m.bankrupt}>${m.bankrupt ? "BANKRUPT" : "OK"}<//>
        <button
          class="btn ghost sm"
          style=${{ color: "var(--loss)", borderColor: "var(--loss)" }}
          onClick=${() => setShowDeleteModal(true)}
          title="Delete this backtest run"
        >
          <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style=${{ marginRight: 5 }}>
            <path d="M2.5 4h11M6 4V2.5h4V4M5 6v6M8 6v6M11 6v6M4 4l.5 10h7L12 4" />
          </svg>
          Delete
        </button>
      </div>

      <${AnomalyBanner} metrics=${m} />

      <${ParametersPanel} run=${result} />

      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${MetricCard} label="Total Return" value=${pct(m.total_return)} tone=${+m.total_return >= 0 ? "up" : "down"} sub=${`Min equity: ${usd(m.min_equity)}`} />
        <${MetricCard} label="Sharpe (ann.)" value=${n(m.sharpe)} sub=${`Sortino ${n(m.sortino)}`} tone=${+m.sharpe >= 1 ? "up" : +m.sharpe >= 0.5 ? undefined : "down"} />
        <${MetricCard} label="Max Drawdown" value=${pct(m.max_drawdown)} tone="down" sub=${`Calmar ${n(m.calmar)}`} />
        <${MetricCard} label="Win Rate" value=${pct(m.win_rate)} sub=${`Profit Factor ${n(m.profit_factor)}`} />
      </div>

      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${MetricCard} label="PSR" value=${n(m.psr)} sub="prob Sharpe > 0" />
        <${MetricCard} label="Orders / Fills" value=${`${m.submitted_order_count ?? m.order_count ?? "—"} / ${m.orders_filled_count ?? m.real_fill_count ?? m.fill_count ?? "—"}`} sub=${`Fill rate ${pct(m.fill_rate)}`} />
        <${MetricCard} label=${totalCostLabel} value=${usd(m.total_fees)} sub=${totalCostSub} />
        <${MetricCard}
          label="Funding P&L"
          value=${fundingNotModeled ? "N/A" : (+m.funding_cashflow >= 0 ? "+" : "") + usd(m.funding_cashflow)}
          tone=${fundingNotModeled ? undefined : +m.funding_cashflow >= 0 ? "up" : "down"}
          sub=${fundingNotModeled ? "not modeled for daily_winner" : `${m.funding_settlement_count ?? 0} settlements`}
        />
      </div>

      <${ValidationSummary} walkForward=${walkForward} cpcv=${cpcv} metrics=${m} validation=${result.validation} loading=${validationLoading} />

      <${ExecutionQualitySummary} metrics=${m} parameters=${result.parameters || {}} />

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Trades / Orders</div>
            <div class="card-sub">round trips and execution rows for the selected run</div>
          </div>
          ${ledgerLoading && html`<div class="field-hint" style=${{ marginLeft: 12 }}>Loading...</div>`}
        </div>
        ${ledgerLoading
          ? html`<div class="field-hint" style=${{ padding: 24, textAlign: "center" }}>Loading trades and orders...</div>`
          : html`<${TradesOrdersTable} trades=${trades} fills=${fills} />`
        }
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Price + Trade Markers</div>
            <div class="card-sub">
              ${marketLoading ? "Loading…" : `${filteredPriceSeries.length.toLocaleString()} price samples · ${filteredMarkers.length.toLocaleString()} markers`}
            </div>
          </div>
        </div>
        ${marketLoading
          ? html`<div class="field-hint" style=${{ padding: "28px 0", textAlign: "center" }}>Loading price series…</div>`
          : html`
            <div class="chart-stack">
              ${priceChartSymbols.length
                ? priceChartSymbols.map((sym) => {
                    const chartId = `price:${sym}`;
                    const y = getChartYControls(chartId);
                    const rows = filteredPriceSeries.filter((row) => row.inst_id === sym);
                    const markerRows = filteredMarkers.filter((row) => row.inst_id === sym);
                    return html`
                      <div key=${sym} class="chart-panel">
                        <div class="chart-panel-h">
                          <div>
                            <div class="card-title">${sym}</div>
                            <div class="card-sub">${rows.length.toLocaleString()} price samples - ${markerRows.length.toLocaleString()} markers</div>
                          </div>
                        </div>
                        <${ChartZoomControls}
                          range=${marketRange}
                          onReset=${() => setMarketRange(null)}
                          xResetLabel="Reset X (market)"
                          yZoom=${y.yZoom}
                          onYZoomIn=${y.onYZoomIn}
                          onYZoomOut=${y.onYZoomOut}
                          onYReset=${y.onYReset}
                        />
                        <div class="chart-wrap">
                          <${TradePriceChart}
                            prices=${rows}
                            markers=${markerRows}
                            height=${280}
                            symbolColors=${chartSymbolColors}
                            xTickFormatter=${adaptiveDateLabel}
                            tooltipLabelFormatter=${chartDateTooltip}
                            range=${marketRange}
                            onRangeChange=${setMarketRange}
                            yZoom=${y.yZoom}
                          />
                        </div>
                      </div>
                    `;
                  })
                : html`<div class="field-hint" style=${{ padding: "28px 0", textAlign: "center" }}>No selected price series available for this run.</div>`
              }
              <${SymbolPillBar}
                symbols=${chartSymbols}
                selected=${effectiveSelectedChartSymbols}
                colors=${chartSymbolColors}
                onChange=${setSelectedChartSymbols}
              />
            </div>
          `
        }
      </div>

      ${isTechnicalRun && indicatorSymbols.length > 0 && indicatorSymbols.map((sym) => {
        const rows = indicatorBySymbol.get(sym) || [];
        if (rows.length < 2) return null;
        const chartId = `indicator:${sym}`;
        const y = getChartYControls(chartId);
        const strategyForLabel = activeStrategies.find((s) => TECHNICAL_STRATEGIES_SET.has(s)) || "";
        const timestamps = rows.map(chartTimestamp);
        const closes = rows.map((r) => safeNum(r.close)).map((v) => Number.isFinite(v) ? v : NaN);
        const fast = rows.map((r) => safeNum(r.fast_value)).map((v) => Number.isFinite(v) ? v : NaN);
        const slow = rows.map((r) => safeNum(r.slow_value)).map((v) => Number.isFinite(v) ? v : NaN);
        const macd = rows.map((r) => safeNum(r.macd));
        const macdSignalVals = rows.map((r) => safeNum(r.macd_signal));
        const macdHist = rows.map((r) => safeNum(r.macd_histogram));
        const hasMacd = strategyForLabel === "macd_crossover";
        const macdY = getChartYControls(`${chartId}:macd`);
        const indicatorVisible = indicatorVisibleState(chartId, hasMacd);
        const warmupSource = rows.some((r) => String(r.warmup_source || "").toLowerCase() === "db") ? "db" : "cold";
        const warmupLabel = warmupSource === "db"
          ? "DB warmup (opt-in visual aid)"
          : "Cold-start (strategy-aligned)";
        // Map markers from datetime back to row index for this symbol.
        const dtToIdx = new Map(timestamps.map((t, i) => [String(t), i]));
        const symMarkers = (markersBySymbol.get(sym) || []).map((m) => {
          const key = String(m.datetime || m.ts || "");
          let idx = dtToIdx.get(key);
          if (idx == null) {
            const target = new Date(key).getTime();
            if (Number.isFinite(target)) {
              let best = 0, bestDiff = Infinity;
              for (let i = 0; i < timestamps.length; i++) {
                const t = new Date(timestamps[i]).getTime();
                const diff = Math.abs(t - target);
                if (diff < bestDiff) { best = i; bestDiff = diff; }
              }
              idx = best;
            }
          }
          return { ...m, idx };
        }).filter((m) => Number.isFinite(m.idx));
        const labels = strategyForLabel === "ma_crossover"
          ? { fast: "Fast MA", slow: "Slow MA" }
          : strategyForLabel === "ema_crossover"
            ? { fast: "Fast EMA", slow: "Slow EMA" }
            : { fast: "MACD fast", slow: "MACD slow" };
        return html`
          <div key=${sym} class="card">
            <div class="card-h">
              <div>
                <div class="card-title">${sym} — ${strategyForLabel || "indicator"}</div>
                <div class="card-sub">price + ${labels.fast.toLowerCase()} / ${labels.slow.toLowerCase()}${hasMacd ? " - MACD sub-panel" : ""}</div>
              </div>
            </div>
            <${ChartZoomControls}
              range=${marketRange}
              onReset=${() => setMarketRange(null)}
              xResetLabel="Reset X (market)"
              yZoom=${y.yZoom}
              onYZoomIn=${y.onYZoomIn}
              onYZoomOut=${y.onYZoomOut}
              onYReset=${y.onYReset}
            />
            <div class=${`indicator-warmup-banner ${warmupSource === "db" ? "warn" : "accent"}`}>
              ${warmupLabel}
            </div>
            <${IndicatorSeriesPillBar}
              visible=${indicatorVisible}
              labels=${labels}
              hasMacd=${hasMacd}
              onToggle=${(key) => toggleIndicatorSeries(chartId, key, hasMacd)}
            />
            ${hasMacd && html`
              <div class="chart-axis-controls">
                <span>MACD Y ${macdY.yZoom.toFixed(1)}x</span>
                <button class="btn ghost sm" type="button" title="Zoom MACD Y axis in" aria-label="Zoom MACD Y axis in" onClick=${macdY.onYZoomIn}>MACD Y+</button>
                <button class="btn ghost sm" type="button" title="Zoom MACD Y axis out" aria-label="Zoom MACD Y axis out" disabled=${macdY.yZoom <= 1.0001} onClick=${macdY.onYZoomOut}>MACD Y-</button>
                ${macdY.yZoom > 1.0001 && html`
                  <button class="btn ghost sm" type="button" onClick=${macdY.onYReset}>Reset MACD Y</button>
                `}
              </div>
            `}
            <div class="chart-wrap fluid">
              <${IndicatorChart}
                symbol=${sym}
                timestamps=${timestamps}
                prices=${closes}
                fast=${fast}
                slow=${slow}
                fastLabel=${labels.fast}
                slowLabel=${labels.slow}
                macd=${hasMacd ? macd : null}
                macdSignal=${hasMacd ? macdSignalVals : null}
                macdHistogram=${hasMacd ? macdHist : null}
                markers=${symMarkers}
                visibleSeries=${indicatorVisible}
                range=${marketRange}
                onRangeChange=${setMarketRange}
                yZoom=${y.yZoom}
                macdYZoom=${hasMacd ? macdY.yZoom : 1}
                xTickFormatter=${adaptiveDateLabel}
                tooltipLabelFormatter=${chartDateTooltip}
              />
            </div>
          </div>
        `;
      })}

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Equity curve</div>
            <div class="card-sub">
              ${equityLoading ? "Loading…" : eqValues.length > 0 ? `${eqValues.length.toLocaleString()} samples · initial $5,000` : "No equity data"}
            </div>
          </div>
          ${m.bankrupt && html`<${StatusBadge} ok=${false}>Bankrupt<//>`}
        </div>
        ${equityLoading
          ? html`<div class="field-hint" style=${{ padding: "32px 0", textAlign: "center" }}>Loading equity curve…</div>`
          : phase2Error
            ? html`<div style=${{ color: "var(--loss)", padding: 16 }}>Failed to load equity data: ${phase2Error}</div>`
            : eqValues.length > 1
            ? html`
                <${ChartZoomControls}
                  range=${equityRange}
                  onReset=${() => setEquityRange(null)}
                  yZoom=${equityY.yZoom}
                  onYZoomIn=${equityY.onYZoomIn}
                  onYZoomOut=${equityY.onYZoomOut}
                  onYReset=${equityY.onYReset}
                />
                <div class="chart-wrap"><${LineChart}
                  series=${[{ values: eqValues, color: m.bankrupt ? "var(--loss)" : "var(--accent)", label: "Equity" }]}
                  height=${220}
                  mode="area"
                  xLabels=${eqDates}
                  xTickFormatter=${chartDateTickForRange(equityRange)}
                  tooltipLabelFormatter=${chartDateTooltip}
                  tooltipValueFormatter=${(v) => signedUsd(v)}
                  range=${equityRange}
                  onRangeChange=${setEquityRange}
                  yZoom=${equityY.yZoom}
                /></div>`
              : html`<div class="field-hint" style=${{ padding: "32px 0", textAlign: "center" }}>No equity data available for this run.</div>`
        }
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Drawdown</div>
            <div class="card-sub">underwater curve</div>
          </div>
          <span class="chip loss">Max ${pct(m.max_drawdown)}</span>
        </div>
        ${equityLoading
          ? html`<div class="field-hint" style=${{ padding: "24px 0", textAlign: "center" }}>Loading drawdown…</div>`
          : ddValues.length > 1
            ? html`
              <${ChartZoomControls}
                range=${drawdownRange}
                onReset=${() => setDrawdownRange(null)}
                yZoom=${drawdownY.yZoom}
                onYZoomIn=${drawdownY.onYZoomIn}
                onYZoomOut=${drawdownY.onYZoomOut}
                onYReset=${drawdownY.onYReset}
              />
              <div class="chart-wrap"><${LineChart}
                series=${[{ values: ddValues, color: "var(--loss)", label: "Drawdown" }]}
                height=${140}
                mode="area"
                xLabels=${ddDates}
                xTickFormatter=${chartDateTickForRange(drawdownRange)}
                tooltipLabelFormatter=${chartDateTooltip}
                tooltipValueFormatter=${(v) => pct(v)}
                range=${drawdownRange}
                onRangeChange=${setDrawdownRange}
                yZoom=${drawdownY.yZoom}
                yZoomAnchor="min"
              /></div>`
            : html`<div class="field-hint" style=${{ padding: "24px 0", textAlign: "center" }}>No drawdown data available.</div>`
        }
      </div>

      <div class="card">
        <div class="card-h">
          <div class="card-title">All metrics</div>
          <div class="card-sub">analytics/performance.py · hover a metric for description</div>
        </div>
        <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          ${Object.entries(m).map(([k, v]) => {
            if (v == null) return null;
            return html`
              <div key=${k} title=${metricTitle(k)} style=${{ borderBottom: "1px solid var(--border)", paddingBottom: 8, cursor: "help" }}>
                <div class="kpi-label" style=${{ fontSize: 11 }}>${k}</div>
                <div style=${{ marginTop: 2, fontSize: 14, minWidth: 0 }}>
                  <${MetricValue} value=${v} />
                </div>
              </div>
            `;
          })}
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <div class="row" style=${{ gap: 4 }}>
            ${[["fills", `Fills (${realFills.length})`], ["all_fills", `All fills (${filteredFills.length})`], ["risk", `Risk events (${filteredRiskEvents.length})`]].map(([id, label]) => html`
              <button
                key=${id}
                class=${`btn sm ${activeTab === id ? "" : "ghost"}`}
                onClick=${() => setActiveTab(id)}
              >${label}</button>
            `)}
          </div>
          ${bottomPanelLoading && html`<div class="field-hint" style=${{ marginLeft: 12 }}>Loading…</div>`}
        </div>

        ${(activeTab === "fills" || activeTab === "all_fills") && (
          ledgerLoading
            ? html`<div class="field-hint" style=${{ padding: 24, textAlign: "center" }}>Loading fills data…</div>`
            : html`<${FillsTable} rows=${activeTab === "fills" ? realFills : filteredFills} tradesMap=${tradesMap} />`
        )}
        ${activeTab === "risk" && (
          riskLoading
            ? html`<div class="field-hint" style=${{ padding: 24, textAlign: "center" }}>Loading risk events…</div>`
            : html`<${RiskEventsTable} rows=${filteredRiskEvents} />`
        )}
      </div>
    </div>
  `;
}

function SymbolPillBar({ symbols, selected, colors, onChange }) {
  const selectedSet = new Set(selected || []);
  function toggle(symbol) {
    if (selectedSet.has(symbol) && selectedSet.size <= 1) return;
    const next = selectedSet.has(symbol)
      ? (selected || []).filter((item) => item !== symbol)
      : [...(selected || []), symbol];
    onChange(next.filter((item, index, arr) => arr.indexOf(item) === index).sort());
  }
  return html`
    <div class="symbol-pill-bar" aria-label="Visible symbols">
      ${(symbols || []).map((symbol, i) => {
        const checked = selectedSet.has(symbol);
        const color = colors?.[symbol] || symbolColor(symbol, i);
        const disabled = checked && selectedSet.size <= 1;
        return html`
          <button
            key=${symbol}
            type="button"
            class="symbol-pill"
            aria-pressed=${checked ? "true" : "false"}
            disabled=${disabled}
            onClick=${() => toggle(symbol)}
          >
            <span class="symbol-pill-swatch" style=${{ background: color }}></span>
            <span class="mono">${symbol}</span>
          </button>
        `;
      })}
    </div>
  `;
}

function IndicatorSeriesPillBar({ visible, labels, hasMacd, onToggle }) {
  const items = [
    ["price", "Price"],
    ["fast", labels.fast],
    ["slow", labels.slow],
    ...(hasMacd ? [["macd", "MACD"]] : []),
  ];
  const visibleCount = items.filter(([key]) => visible[key]).length;
  return html`
    <div class="indicator-pill-bar" aria-label="Visible indicator series">
      ${items.map(([key, label]) => {
        const active = visible[key];
        const disabled = active && visibleCount <= 1;
        return html`
          <button
            key=${key}
            type="button"
            class="symbol-pill"
            aria-pressed=${active ? "true" : "false"}
            disabled=${disabled}
            onClick=${() => onToggle(key)}
          >${label}</button>
        `;
      })}
    </div>
  `;
}

function ValidationSummary({ walkForward, cpcv, metrics, validation, loading }) {
  const windows = walkForward || [];
  const combos = cpcv?.combos || [];
  const validationMode = validationModeFrom(validation || {}, metrics || {}, windows, cpcv);
  if (!loading && validationMode === "none" && !windows.length && !combos.length) return null;
  const oos = windows.map((w) => +w.oos_sharpe || 0);
  const meanOos = oos.length ? oos.reduce((a, b) => a + b, 0) / oos.length : null;
  return html`
    <div class="card">
      <div class="card-h">
        <div>
          <div class="card-title">Walk-Forward / CPCV / DSR</div>
          <div class="card-sub">validation summary embedded with the selected run</div>
        </div>
        ${metrics.validation_only && html`<span class="chip warn">Validation-only</span>`}
      </div>
      ${loading ? html`
        <div class="field-hint" style=${{ padding: 20, textAlign: "center" }}>Loading validation data...</div>
      ` : html`
        <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 14 }}>
          <${MetricCard} label="WF windows" value=${windows.length} sub=${meanOos == null ? "not run" : `Mean OOS ${n(meanOos)}`} />
          <${MetricCard} label="CPCV combos" value=${combos.length} sub=${cpcv ? `Std ${n(cpcv.std_oos_sharpe)}` : "not run"} />
          <${MetricCard} label="DSR" value=${n(metrics.dsr ?? cpcv?.dsr)} sub="deflated Sharpe" tone=${(metrics.dsr ?? cpcv?.dsr ?? 0) >= 0.95 ? "up" : undefined} />
          <${MetricCard} label="PSR" value=${n(metrics.psr ?? cpcv?.psr)} sub="prob Sharpe > 0" />
        </div>
        <div class="tbl-wrap" style=${{ maxHeight: 260 }}>
          <table class="tbl">
            <thead>
              <tr>
                <th>#</th><th>OOS start</th><th>OOS end</th>
                <th class="num">IS Sharpe</th><th class="num">OOS Sharpe</th>
                <th class="num">OOS Return</th><th class="num">OOS MDD</th>
              </tr>
            </thead>
            <tbody>
              ${windows.map((w, i) => html`
                <tr key=${i}>
                  <td class="mono">${w.i ?? i}</td>
                  <td class="mono">${fmtDt(w.oos_start).slice(0, 10)}</td>
                  <td class="mono">${fmtDt(w.oos_end).slice(0, 10)}</td>
                  <td class="num">${n(w.is_sharpe)}</td>
                  <td class="num" style=${{ color: +w.oos_sharpe >= 0 ? "var(--profit)" : "var(--loss)" }}>${n(w.oos_sharpe)}</td>
                  <td class="num" style=${{ color: +w.oos_return >= 0 ? "var(--profit)" : "var(--loss)" }}>${pct(w.oos_return)}</td>
                  <td class="num" style=${{ color: "var(--loss)" }}>${pct(w.oos_mdd)}</td>
                </tr>
              `)}
              ${!windows.length && html`
                <tr><td colSpan=${7} class="field-hint" style=${{ textAlign: "center", padding: 14 }}>Walk-Forward was not run for this backtest.</td></tr>
              `}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

function normalizeLedgerTrade(t, i) {
  const ts = t.datetime || t.entry_ts || t.ts || t.exit_ts || "";
  const side = String(t.side || "buy").toUpperCase();
  const price = +(t.price ?? t.entry_price ?? t.fill_px ?? t.px ?? 0);
  const qty = +(t.qty ?? t.fill_sz ?? t.sz ?? 0);
  const fee = +(t.fee ?? 0);
  const isExecutionRow = !!t.execution_phase || t.type === "validation_synthetic_fill";
  const pnlKeys = isExecutionRow
    ? ["pnl_usd", "net_realized_pnl", "realized_pnl", "pnl"]
    : ["pnl_usd", "net_realized_pnl", "realized_pnl", "pnl", "net_return"];
  const pnlKey = pnlKeys.find((key) => Object.prototype.hasOwnProperty.call(t, key) && t[key] != null && t[key] !== "");
  const pnl = pnlKey ? +t[pnlKey] : 0;
  return {
    id: t.id ?? t.cl_ord_id ?? i,
    ts,
    symbol: t.symbol || t.inst_id || "-",
    side,
    type: t.type || t.ord_type || "validation_round_trip",
    price,
    qty,
    notional: tradeNotional(t, price, qty),
    fee,
    pnl,
    hasPnl: !!pnlKey && Number.isFinite(pnl),
    status: String(t.status || t.state || "FILLED").toUpperCase(),
    strategy: t.strategy || "-",
    exit_ts: t.exit_ts,
    note: t.note,
  };
}

function formatLedgerPnl(t) {
  if (!t.hasPnl) return "-";
  if (t.notional === 0 && Math.abs(t.pnl) < 1) return pct(t.pnl);
  return (t.pnl >= 0 ? "+" : "") + signedUsd(t.pnl);
}

function TradesOrdersTable({ trades, fills }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sideFilter, setSideFilter] = useState("ALL");
  const tradeRows = (trades || []).map(normalizeLedgerTrade);
  const fillRows = (fills || []).map(normalizeLedgerTrade);
  const baseRows = tradeRows.length ? tradeRows : fillRows;
  const tradingPairs = [...new Set(
    [...tradeRows, ...fillRows].map((row) => row.symbol).filter((symbol) => symbol && symbol !== "-")
  )].sort();
  const [pairFilter, setPairFilter] = useState("ALL");
  useEffect(() => setPage(1), [sideFilter, pairFilter]);
  useEffect(() => {
    if (pairFilter !== "ALL" && !tradingPairs.includes(pairFilter)) setPairFilter("ALL");
  }, [tradingPairs.join("|"), pairFilter]);
  const rows = baseRows.filter((row) => {
    if (sideFilter !== "ALL" && row.side !== sideFilter) return false;
    if (pairFilter !== "ALL" && row.symbol !== pairFilter) return false;
    return true;
  });
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageRows = rows.slice((safePage - 1) * pageSize, safePage * pageSize);
  const showExit = rows.some((row) => row.exit_ts);
  const emptyColSpan = showExit ? 13 : 12;
  if (!baseRows.length) return html`<div class="field-hint" style=${{ padding: 16 }}>No trades or orders for this run.</div>`;
  return html`
    <div>
      <div class="row wrap" style=${{ gap: 12, alignItems: "center", marginBottom: 12 }}>
        <div class="field-hint" style=${{ flex: 1 }}>
          ${rows.length
            ? `Showing ${((safePage - 1) * pageSize + 1).toLocaleString()}-${Math.min(safePage * pageSize, rows.length).toLocaleString()} of ${rows.length.toLocaleString()}`
            : `No rows match the current filters in ${baseRows.length.toLocaleString()} trades / orders`}
        </div>
        <select class="select" value=${pairFilter} onChange=${(e) => setPairFilter(e.target.value)} style=${{ width: 190 }}>
          <option value="ALL">All trading pairs</option>
          ${tradingPairs.map((symbol) => html`<option key=${symbol} value=${symbol}>${symbol}</option>`)}
        </select>
        <select class="select" value=${sideFilter} onChange=${(e) => setSideFilter(e.target.value)} style=${{ width: 130 }}>
          <option value="ALL">All sides</option>
          <option value="BUY">Buy only</option>
          <option value="SELL">Sell only</option>
        </select>
        <select class="select" value=${pageSize} onChange=${(e) => { setPageSize(+e.target.value); setPage(1); }} style=${{ width: 140 }}>
          ${[25, 50, 100, 250, 500].map((size) => html`<option key=${size} value=${size}>${size} / page</option>`)}
        </select>
        <button class="btn ghost sm" disabled=${safePage <= 1} onClick=${() => setPage(safePage - 1)}>Prev</button>
        <span class="mono" style=${{ color: "var(--text-muted)", fontSize: 12 }}>Page ${safePage} / ${totalPages}</span>
        <button class="btn ghost sm" disabled=${safePage >= totalPages} onClick=${() => setPage(safePage + 1)}>Next</button>
      </div>
      <div class="tbl-wrap" style=${{ maxHeight: 620 }}>
        <table class="tbl">
          <thead>
            <tr>
              <th>ID</th><th>Timestamp (UTC)</th>${showExit && html`<th>Exit</th>`}<th>Trading Pair</th><th>Side</th><th>Type</th>
              <th class="num">Price</th><th class="num">Qty</th><th class="num">Notional (USDT)</th>
              <th class="num">Fee</th><th class="num">PnL</th><th>Status</th><th>Strategy</th>
            </tr>
          </thead>
          <tbody>
            ${pageRows.map((t, i) => html`
              <tr key=${`${t.id}-${i}`}>
                <td class="mono" style=${{ color: "var(--text-muted)" }}>${t.id}</td>
                <td class="mono">${fmtDt(t.ts)}</td>
                ${showExit && html`<td class="mono">${t.exit_ts ? fmtDt(t.exit_ts).slice(0, 10) : "-"}</td>`}
                <td class="mono">${t.symbol}</td>
                <td><span class="chip" style=${{ color: t.side === "BUY" ? "var(--profit)" : "var(--loss)", background: t.side === "BUY" ? "var(--profit-soft)" : "var(--loss-soft)", borderColor: "transparent" }}>${t.side}</span></td>
                <td class="mono" title=${t.note || ""} style=${{ color: "var(--text-muted)" }}>${t.type}</td>
                <td class="num">${n(t.price, 4)}</td>
                <td class="num">${n(t.qty, 4)}</td>
                <td class="num">${usd(t.notional)}</td>
                <td class="num" style=${{ color: "var(--text-muted)" }}>${usd(t.fee, 4)}</td>
                <td class="num" style=${{ color: !t.hasPnl ? "var(--text-muted)" : t.pnl >= 0 ? "var(--profit)" : "var(--loss)" }}>${t.status === "FILLED" ? formatLedgerPnl(t) : "-"}</td>
                <td><span class=${`chip ${t.status === "FILLED" ? "profit" : t.status === "REJECTED" ? "loss" : "warn"}`} style=${{ fontSize: 10 }}>${t.status}</span></td>
                <td class="mono" style=${{ color: "var(--text-subtle)", fontSize: 11 }}>${t.strategy}</td>
              </tr>
            `)}
            ${!rows.length && html`<tr><td colSpan=${emptyColSpan} class="field-hint" style=${{ textAlign: "center", padding: 16 }}>No trades match the current filters.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function FillsTable({ rows, tradesMap }) {
  if (!rows.length) return html`<div class="field-hint" style=${{ padding: 16 }}>No fills in this run.</div>`;
  const hasPnl = tradesMap && tradesMap.size > 0;
  return html`
    <div>
      ${!hasPnl && html`
        <div class="field-hint" style=${{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
          Net PnL is computed per closed order from trades data.
          Partially-filled orders show — until closed.
        </div>
      `}
      <div class="tbl-wrap" style=${{ maxHeight: 480 }}>
        <table class="tbl">
          <thead>
            <tr>
              <th>Datetime (UTC)</th>
              <th>Trading Pair</th>
              <th>Side</th>
              <th class="num">Fill px</th>
              <th class="num">Qty</th>
              <th class="num">Notional (USDT)</th>
              <th class="num">Fee</th>
              <th class="num" title="Net realized PnL for this order's fills (from trades data)">Net PnL</th>
              <th>State</th>
              <th>Strategy</th>
            </tr>
          </thead>
          <tbody>
            ${rows.slice(0, 500).map((f, i) => {
              const side = (f.side || "").toLowerCase();
              const state = f.state || "";
              const pnlVal = hasPnl ? tradesMap.get(f.cl_ord_id) : null;
              const showPnl = pnlVal != null && state === "filled";
              return html`
                <tr key=${i}>
                  <td class="mono" style=${{ fontSize: 11 }}>${fmtDt(f.datetime)}</td>
                  <td class="mono">${f.inst_id || "—"}</td>
                  <td>
                    <span class="chip" style=${{
                      color: side === "buy" ? "var(--profit)" : "var(--loss)",
                      background: side === "buy" ? "var(--profit-soft)" : "var(--loss-soft)",
                      borderColor: "transparent",
                      fontSize: 10,
                    }}>${side.toUpperCase()}</span>
                  </td>
                  <td class="num">${n(f.fill_px, 4)}</td>
                  <td class="num">${n(f.fill_sz, 4)}</td>
                  <td class="num">${usd(f.notional_usd)}</td>
                  <td class="num" style=${{ color: "var(--text-muted)" }}>${usd(f.fee, 4)}</td>
                  <td class="num" style=${{ color: showPnl ? (pnlVal >= 0 ? "var(--profit)" : "var(--loss)") : "var(--text-muted)" }}>
                    ${showPnl ? (pnlVal >= 0 ? "+" : "") + signedUsd(pnlVal) : "—"}
                  </td>
                  <td>
                    <span class=${`chip ${state === "filled" ? "profit" : state === "partially_filled" ? "warn" : ""}`} style=${{ fontSize: 10 }}>
                      ${state.toUpperCase().replace(/_/g, " ")}
                    </span>
                  </td>
                  <td class="mono" style=${{ fontSize: 11, color: "var(--text-subtle)" }}>${f.strategy || "—"}</td>
                </tr>
              `;
            })}
          </tbody>
        </table>
        ${rows.length > 500 && html`<div class="field-hint" style=${{ padding: "8px 0" }}>showing 500 of ${rows.length.toLocaleString()} fills</div>`}
      </div>
    </div>
  `;
}

function RiskEventsTable({ rows }) {
  if (!rows.length) return html`<div class="field-hint" style=${{ padding: 16 }}>No risk events recorded.</div>`;
  return html`
    <div class="tbl-wrap" style=${{ maxHeight: 400 }}>
      <table class="tbl">
        <thead>
          <tr>
            <th>Datetime (UTC)</th>
            <th>Trading Pair</th>
            <th>Side</th>
            <th class="num">Notional</th>
            <th>Reason</th>
            <th class="num">Equity</th>
            <th>Strategy</th>
          </tr>
        </thead>
        <tbody>
          ${rows.slice(0, 200).map((r, i) => html`
            <tr key=${i}>
              <td class="mono" style=${{ fontSize: 11 }}>${fmtDt(r.datetime)}</td>
              <td class="mono">${r.inst_id || "—"}</td>
              <td class="mono">${r.side || "—"}</td>
              <td class="num">${usd(r.notional_usd)}</td>
              <td>
                <span class="chip loss" style=${{ fontSize: 10 }}>${r.reason || "—"}</span>
              </td>
              <td class="num">${usd(r.current_equity)}</td>
              <td class="mono" style=${{ fontSize: 11, color: "var(--text-subtle)" }}>${r.strategy || "—"}</td>
            </tr>
          `)}
        </tbody>
      </table>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Run List View
// ---------------------------------------------------------------------------
function RunListView({ onSelect, onDelete }) {
  const [runs, setRuns] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    window.API.fetchRuns()
      .then(r => setRuns(r || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function handleDeleteConfirm(runId) {
    setDeletingId(null);
    setRuns((rs) => (rs || []).filter((r) => r.run_id !== runId));
    onDelete?.(runId);
  }

  if (loading) return html`<div class="field-hint" style=${{ padding: 32 }}>Loading backtest runs…</div>`;
  if (error) return html`
    <div class="card">
      <div style=${{ color: "var(--loss)", marginBottom: 8 }}>Could not load runs: ${error}</div>
      <div class="field-hint">Make sure the FastAPI server is running and <code>results/</code> contains at least one run.</div>
    </div>
  `;
  if (!runs.length) return html`
    <div class="card">
      <div class="card-title" style=${{ marginBottom: 8 }}>No backtest runs found</div>
      <div class="field-hint">Run a backtest with <code>--save-artifacts</code> to populate this view.</div>
      <pre style=${{ marginTop: 12, fontSize: 12, color: "var(--text-muted)", background: "var(--surface-2)", padding: 12, borderRadius: 6 }}>${`python scripts/run_replay_backtest.py \\
  --strategy pairs_trading \\
  --start 2024-01-01 --end 2024-01-08 \\
  --bar 1m --save-artifacts`}</pre>
    </div>
  `;

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      ${deletingId && html`
        <${DeleteModal}
          runId=${deletingId}
          onConfirm=${handleDeleteConfirm}
          onCancel=${() => setDeletingId(null)}
        />
      `}
      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${MetricCard} label="Total runs" value=${runs.length} sub="saved in results/" />
        <${MetricCard}
          label="Best Sharpe"
          value=${n(Math.max(...runs.map(r => r.sharpe ?? -Infinity)))}
          tone="up"
        />
        <${MetricCard}
          label="Best Return"
          value=${pct(Math.max(...runs.map(r => r.total_return ?? -Infinity)))}
          tone="up"
        />
        <${MetricCard}
          label="Latest run"
          value=${runs[0]?.created_at ? new Date(runs[0].created_at).toLocaleDateString() : "—"}
        />
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Backtest Runs</div>
            <div class="card-sub">click a row to view full results</div>
          </div>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Strategy</th>
                <th>Trading Pairs</th>
                <th>Parameters</th>
                <th>Bar</th>
                <th>Period</th>
                <th class="num">Return</th>
                <th class="num">Sharpe</th>
                <th class="num">Max DD</th>
                <th class="num">Orders</th>
                <th class="num">Fills</th>
                <th>Created</th>
                <th class="num">Delete</th>
              </tr>
            </thead>
            <tbody>
              ${runs.map((r) => {
                const bankrupt = r.total_return != null && Math.abs(+r.max_drawdown) > 1;
                const symbols = (r.symbols || [r.symbol]).filter(Boolean);
                return html`
                  <tr
                    key=${r.run_id}
                    style=${{ cursor: "pointer" }}
                    onClick=${() => onSelect(r.run_id)}
                  >
                    <td class="mono" style=${{ fontSize: 11, color: "var(--text-subtle)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      ${r.run_id}
                    </td>
                    <td class="mono" style=${{ fontSize: 12 }}>
                      ${(r.strategies || [r.strategy]).filter(Boolean).join(", ")}
                    </td>
                    <td class="mono" style=${{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.7, whiteSpace: "normal" }}>
                      ${symbols.length
                        ? symbols.map((symbol, index) => html`<div key=${`${symbol}-${index}`}>${symbol}${index < symbols.length - 1 ? "," : ""}</div>`)
                        : "—"}
                    </td>
                    <td class="mono" title=${runParametersText(r)} style=${{ fontSize: 11, color: "var(--text-muted)", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      ${runParametersText(r)}
                    </td>
                    <td class="mono">${r.bar || "—"}</td>
                    <td class="mono" style=${{ fontSize: 11 }}>
                      ${r.start ? r.start.slice(0, 10) : "—"} → ${r.end ? r.end.slice(0, 10) : "—"}
                    </td>
                    <td class="num" style=${{ color: r.total_return >= 0 ? "var(--profit)" : "var(--loss)" }}>
                      ${pct(r.total_return)}
                    </td>
                    <td class="num">${n(r.sharpe)}</td>
                    <td class="num" style=${{ color: "var(--loss)" }}>${pct(r.max_drawdown)}</td>
                    <td class="num">${r.order_count ?? "—"}</td>
                    <td class="num">${r.real_fill_count ?? "—"}</td>
                    <td class="mono" style=${{ fontSize: 11 }}>
                      ${r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                      ${bankrupt && html`<span class="chip loss" style=${{ marginLeft: 6, fontSize: 9 }}>⚠ bankrupt</span>`}
                    </td>
                    <td class="num">
                      <button
                        class="btn ghost sm"
                        title="Delete run"
                        aria-label="Delete run"
                        style=${{ color: "var(--loss)" }}
                        onClick=${(e) => { e.stopPropagation(); setDeletingId(r.run_id); }}
                      >
                        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M2.5 4h11M6 4V2.5h4V4M5 6v6M8 6v6M11 6v6M4 4l.5 10h7L12 4" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                `;
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Top-level BacktestView
// ---------------------------------------------------------------------------
function BacktestView({ selectedRunId, setSelectedRunId, onRunsChanged }) {
  function handleDelete(runId) {
    if (selectedRunId === runId) setSelectedRunId(null);
    onRunsChanged?.();
  }

  return selectedRunId
    ? html`<${RunDetailView} runId=${selectedRunId} onBack=${() => setSelectedRunId(null)} onDelete=${handleDelete} />`
    : html`<${RunListView} onSelect=${setSelectedRunId} onDelete=${handleDelete} />`;
}

window.BacktestView = BacktestView;
window.METRIC_DESCRIPTIONS = METRIC_DESCRIPTIONS;
window.DeleteModal = DeleteModal;

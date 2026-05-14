import { h } from 'preact';
import { useState, useEffect, useCallback } from 'preact/hooks';
import { html } from 'htm/preact';

// Backtest Runs browser + Run Detail view — reads from /api/backtest/* endpoints.
const { LineChart, TradePriceChart } = window.Charts;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function n(v, d = 2) { return v == null || isNaN(+v) ? "—" : (+v).toFixed(d); }
function pct(v) { return v == null || isNaN(+v) ? "—" : ((+v) * 100).toFixed(2) + "%"; }
function usd(v, d = 2) { return v == null || isNaN(+v) ? "—" : "$" + Math.abs(+v).toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d }); }
function fmtDt(s) { if (!s) return "—"; try { return new Date(s).toISOString().slice(0, 19).replace("T", " "); } catch { return s; } }
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
function chartDateTooltip(value) {
  const d = parseChartDate(value);
  return d ? d.toISOString().slice(0, 19).replace("T", " ") + " UTC" : String(value || "—");
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
  tail_ratio:               { desc: "95th percentile gain / |5th percentile loss| — measures tail balance", unit: "dimensionless" },
  pending_fill_event_count: { desc: "Number of fill events still in pending state at backtest end", unit: "count" },
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
  const [phase2Loading, setPhase2Loading] = useState(true);
  const [phase2Error, setPhase2Error] = useState(null);

  const [activeTab, setActiveTab] = useState("fills");
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [chartSymbol, setChartSymbol] = useState("__all__");

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
    setPhase2Loading(true);
    setPhase2Error(null);
    setEquity([]);
    setFills([]);
    setTrades([]);
    setWalkForward([]);
    setCpcv(null);
    setRiskEvents([]);
    setPriceSeries([]);
    setExecutionMarkers([]);
    Promise.all([
      window.API.fetchBacktestEquity(runId).catch(() => []),
      window.API.fetchBacktestFills(runId).catch(() => []),
      window.API.fetchBacktestTrades(runId).catch(() => []),
      window.API.fetchWalkForward(runId).catch(() => []),
      window.API.fetchCPCV(runId).catch(() => null),
      window.API.fetchBacktestRiskEvents(runId).catch(() => []),
      window.API.fetchBacktestPriceSeries(runId).catch(() => []),
      window.API.fetchBacktestExecutionMarkers(runId).catch(() => []),
    ]).then(([eq, fl, tr, wf, cv, re, ps, em]) => {
      setEquity(eq || []);
      setFills(fl || []);
      setTrades(tr || []);
      setWalkForward(wf || []);
      setCpcv(cv || null);
      setRiskEvents(re || []);
      setPriceSeries(ps || []);
      setExecutionMarkers(em || []);
    }).catch((e) => setPhase2Error(e.message))
      .finally(() => setPhase2Loading(false));
  }, [runId]);

  if (phase1Loading) return html`<div class="field-hint" style=${{ padding: 32 }}>Loading run ${runId}…</div>`;
  if (phase1Error) return html`<div style=${{ color: "var(--loss)", padding: 32 }}>Error: ${phase1Error}</div>`;
  if (!result) return null;

  const m = result.metrics || {};
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
  const filteredPriceSeries = chartSymbol === "__all__"
    ? priceSeries
    : priceSeries.filter((r) => r.inst_id === chartSymbol);
  const filteredMarkers = chartSymbol === "__all__"
    ? executionMarkers
    : executionMarkers.filter((r) => r.inst_id === chartSymbol);

  const realFills = fills.filter(f => f.fill_sz && +f.fill_sz > 0 && (f.state === "filled" || f.state === "partially_filled"));

  const tradesMap = new Map();
  for (const t of trades) {
    if (t.cl_ord_id && t.net_realized_pnl != null) {
      tradesMap.set(t.cl_ord_id, (tradesMap.get(t.cl_ord_id) ?? 0) + +t.net_realized_pnl);
    }
  }

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

      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${MetricCard} label="Total Return" value=${pct(m.total_return)} tone=${+m.total_return >= 0 ? "up" : "down"} sub=${`Min equity: ${usd(m.min_equity)}`} />
        <${MetricCard} label="Sharpe (ann.)" value=${n(m.sharpe)} sub=${`Sortino ${n(m.sortino)}`} tone=${+m.sharpe >= 1 ? "up" : +m.sharpe >= 0.5 ? undefined : "down"} />
        <${MetricCard} label="Max Drawdown" value=${pct(m.max_drawdown)} tone="down" sub=${`Calmar ${n(m.calmar)}`} />
        <${MetricCard} label="Win Rate" value=${pct(m.win_rate)} sub=${`Profit Factor ${n(m.profit_factor)}`} />
      </div>

      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${MetricCard} label="PSR" value=${n(m.psr)} sub="prob Sharpe > 0" />
        <${MetricCard} label="Orders / Fills" value=${`${m.submitted_order_count ?? m.order_count ?? "—"} / ${m.orders_filled_count ?? m.real_fill_count ?? m.fill_count ?? "—"}`} sub=${`Fill rate ${pct(m.fill_rate)}`} />
        <${MetricCard} label="Total Fees" value=${usd(m.total_fees)} sub=${`Notional ${usd(m.fill_notional_usd)}`} />
        <${MetricCard} label="Funding P&L" value=${(+m.funding_cashflow >= 0 ? "+" : "") + usd(m.funding_cashflow)} tone=${+m.funding_cashflow >= 0 ? "up" : "down"} sub=${`${m.funding_settlement_count ?? 0} settlements`} />
      </div>

      <${ValidationSummary} walkForward=${walkForward} cpcv=${cpcv} metrics=${m} loading=${phase2Loading} />

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Trades / Orders</div>
            <div class="card-sub">round trips and execution rows for the selected run</div>
          </div>
          ${phase2Loading && html`<div class="field-hint" style=${{ marginLeft: 12 }}>Loading...</div>`}
        </div>
        ${phase2Loading
          ? html`<div class="field-hint" style=${{ padding: 24, textAlign: "center" }}>Loading trades and orders...</div>`
          : html`<${TradesOrdersTable} trades=${trades} fills=${fills} />`
        }
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Price + Trade Markers</div>
            <div class="card-sub">
              ${phase2Loading ? "Loading…" : `${filteredPriceSeries.length.toLocaleString()} price samples · ${filteredMarkers.length.toLocaleString()} markers`}
            </div>
          </div>
          <select class="select mono" value=${chartSymbol} onChange=${(e) => setChartSymbol(e.target.value)} style=${{ width: 190 }}>
            <option value="__all__">All symbols</option>
            ${chartSymbols.map((s) => html`<option key=${s} value=${s}>${s}</option>`)}
          </select>
        </div>
        ${phase2Loading
          ? html`<div class="field-hint" style=${{ padding: "28px 0", textAlign: "center" }}>Loading price series…</div>`
          : filteredPriceSeries.length > 1
            ? html`<div class="chart-wrap"><${TradePriceChart}
                prices=${filteredPriceSeries}
                markers=${filteredMarkers}
                height=${260}
                tooltipLabelFormatter=${chartDateTooltip}
              /></div>`
            : html`<div class="field-hint" style=${{ padding: "28px 0", textAlign: "center" }}>No price series available for this run.</div>`
        }
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Equity curve</div>
            <div class="card-sub">
              ${phase2Loading ? "Loading…" : eqValues.length > 0 ? `${eqValues.length.toLocaleString()} samples · initial $5,000` : "No equity data"}
            </div>
          </div>
          ${m.bankrupt && html`<${StatusBadge} ok=${false}>Bankrupt<//>`}
        </div>
        ${phase2Loading
          ? html`<div class="field-hint" style=${{ padding: "32px 0", textAlign: "center" }}>Loading equity curve…</div>`
          : phase2Error
            ? html`<div style=${{ color: "var(--loss)", padding: 16 }}>Failed to load equity data: ${phase2Error}</div>`
            : eqValues.length > 1
              ? html`<div class="chart-wrap"><${LineChart}
                  series=${[{ values: eqValues, color: m.bankrupt ? "var(--loss)" : "var(--accent)", label: "Equity" }]}
                  height=${220}
                  mode="area"
                  xLabels=${eqDates}
                  xTickFormatter=${chartDateTick}
                  tooltipLabelFormatter=${chartDateTooltip}
                  tooltipValueFormatter=${(v) => signedUsd(v)}
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
        ${phase2Loading
          ? html`<div class="field-hint" style=${{ padding: "24px 0", textAlign: "center" }}>Loading drawdown…</div>`
          : ddValues.length > 1
            ? html`<div class="chart-wrap"><${LineChart}
                series=${[{ values: ddValues, color: "var(--loss)", label: "Drawdown" }]}
                height=${140}
                mode="area"
                xLabels=${ddDates}
                xTickFormatter=${chartDateTick}
                tooltipLabelFormatter=${chartDateTooltip}
                tooltipValueFormatter=${(v) => pct(v)}
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
            ${[["fills", `Fills (${realFills.length})`], ["all_fills", `All fills (${fills.length})`], ["risk", `Risk events (${riskEvents.length})`]].map(([id, label]) => html`
              <button
                key=${id}
                class=${`btn sm ${activeTab === id ? "" : "ghost"}`}
                onClick=${() => setActiveTab(id)}
              >${label}</button>
            `)}
          </div>
          ${phase2Loading && html`<div class="field-hint" style=${{ marginLeft: 12 }}>Loading…</div>`}
        </div>

        ${(activeTab === "fills" || activeTab === "all_fills") && (
          phase2Loading
            ? html`<div class="field-hint" style=${{ padding: 24, textAlign: "center" }}>Loading fills data…</div>`
            : html`<${FillsTable} rows=${activeTab === "fills" ? realFills : fills} tradesMap=${tradesMap} />`
        )}
        ${activeTab === "risk" && (
          phase2Loading
            ? html`<div class="field-hint" style=${{ padding: 24, textAlign: "center" }}>Loading risk events…</div>`
            : html`<${RiskEventsTable} rows=${riskEvents} />`
        )}
      </div>
    </div>
  `;
}

function ValidationSummary({ walkForward, cpcv, metrics, loading }) {
  const windows = walkForward || [];
  const combos = cpcv?.combos || [];
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
  const price = +(t.price ?? t.entry_price ?? t.fill_px ?? 0);
  const qty = +(t.qty ?? t.fill_sz ?? 0);
  const fee = +(t.fee ?? 0);
  const pnlRaw = t.pnl_usd ?? t.net_realized_pnl ?? t.realized_pnl ?? t.pnl ?? t.net_return ?? 0;
  const pnl = +(pnlRaw ?? 0);
  return {
    id: t.id ?? t.cl_ord_id ?? i,
    ts,
    symbol: t.symbol || t.inst_id || "-",
    side,
    type: t.type || t.ord_type || "validation_round_trip",
    price,
    qty,
    notional: +(t.notional ?? t.notional_usd ?? 0),
    fee,
    pnl,
    status: String(t.status || t.state || "FILLED").toUpperCase(),
    strategy: t.strategy || "-",
    exit_ts: t.exit_ts,
    note: t.note,
  };
}

function formatLedgerPnl(t) {
  if (t.notional === 0 && Math.abs(t.pnl) < 1) return pct(t.pnl);
  return (t.pnl >= 0 ? "+" : "") + usd(t.pnl);
}

function TradesOrdersTable({ trades, fills }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const tradeRows = (trades || []).map(normalizeLedgerTrade);
  const fillRows = (fills || []).map(normalizeLedgerTrade);
  const rows = tradeRows.length ? tradeRows : fillRows;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageRows = rows.slice((safePage - 1) * pageSize, safePage * pageSize);
  if (!rows.length) return html`<div class="field-hint" style=${{ padding: 16 }}>No trades or orders in this run.</div>`;
  return html`
    <div>
      <div class="row wrap" style=${{ gap: 12, alignItems: "center", marginBottom: 12 }}>
        <div class="field-hint" style=${{ flex: 1 }}>
          Showing ${((safePage - 1) * pageSize + 1).toLocaleString()}-${Math.min(safePage * pageSize, rows.length).toLocaleString()} of ${rows.length.toLocaleString()}
        </div>
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
              <th>ID</th><th>Timestamp (UTC)</th><th>Exit</th><th>Symbol</th><th>Side</th><th>Type</th>
              <th class="num">Price</th><th class="num">Qty</th><th class="num">Notional</th>
              <th class="num">Fee</th><th class="num">PnL</th><th>Status</th><th>Strategy</th>
            </tr>
          </thead>
          <tbody>
            ${pageRows.map((t, i) => html`
              <tr key=${`${t.id}-${i}`}>
                <td class="mono" style=${{ color: "var(--text-muted)" }}>${t.id}</td>
                <td class="mono">${fmtDt(t.ts)}</td>
                <td class="mono">${t.exit_ts ? fmtDt(t.exit_ts).slice(0, 10) : "-"}</td>
                <td class="mono">${t.symbol}</td>
                <td><span class="chip" style=${{ color: t.side === "BUY" ? "var(--profit)" : "var(--loss)", background: t.side === "BUY" ? "var(--profit-soft)" : "var(--loss-soft)", borderColor: "transparent" }}>${t.side}</span></td>
                <td class="mono" title=${t.note || ""} style=${{ color: "var(--text-muted)" }}>${t.type}</td>
                <td class="num">${n(t.price, 4)}</td>
                <td class="num">${n(t.qty, 4)}</td>
                <td class="num">${usd(t.notional)}</td>
                <td class="num" style=${{ color: "var(--text-muted)" }}>${usd(t.fee, 4)}</td>
                <td class="num" style=${{ color: t.pnl >= 0 ? "var(--profit)" : "var(--loss)" }}>${t.status === "FILLED" ? formatLedgerPnl(t) : "-"}</td>
                <td><span class=${`chip ${t.status === "FILLED" ? "profit" : t.status === "REJECTED" ? "loss" : "warn"}`} style=${{ fontSize: 10 }}>${t.status}</span></td>
                <td class="mono" style=${{ color: "var(--text-subtle)", fontSize: 11 }}>${t.strategy}</td>
              </tr>
            `)}
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
              <th>Symbol</th>
              <th>Side</th>
              <th class="num">Fill px</th>
              <th class="num">Qty</th>
              <th class="num">Notional</th>
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
                    ${showPnl ? (pnlVal >= 0 ? "+" : "") + usd(pnlVal) : "—"}
                  </td>
                  <td>
                    <span class=${`chip ${state === "filled" ? "profit" : state === "partially_filled" ? "warn" : ""}`} style=${{ fontSize: 10 }}>
                      ${state.toUpperCase().replace("_", " ")}
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
            <th>Symbol</th>
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
                <th>Symbols</th>
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
                    <td class="mono" style=${{ fontSize: 11, color: "var(--text-muted)" }}>
                      ${(r.symbols || [r.symbol]).filter(Boolean).join(", ")}
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

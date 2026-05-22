import { h, Fragment } from 'preact';
import { useState, useEffect, useMemo } from 'preact/hooks';
import { html } from 'htm/preact';
const useStateResults = useState;
const useEffectResults = useEffect;
const useMemoResults = useMemo;

const KPI = window.KPI;
const fmt = window.fmt;
const { LineChart, HistogramChart } = window.Charts;

function metricLabel(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function displayMetric(key, value) {
  if (value == null) return "-";
  if (typeof value === "boolean") return String(value);
  if (typeof value !== "number") return String(value);
  if (key.includes("return") || key.includes("drawdown") || key.includes("rate") || key.includes("pct")) {
    return fmt.pct(value);
  }
  return Math.abs(value) >= 1000 ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : fmt.num(value, 2);
}

function valueAt(row, keys, fallback = 0) {
  for (const key of keys) {
    if (row?.[key] != null && row[key] !== "") return +row[key];
  }
  return fallback;
}

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

// ---------------------------------------------------------------------------
// Compact run picker shown when no run is selected
// ---------------------------------------------------------------------------
function RunPicker({ onSelect }) {
  const [runs, setRuns] = useStateResults(null);
  const [loading, setLoading] = useStateResults(true);
  const [deletingId, setDeletingId] = useStateResults(null);

  useEffectResults(() => {
    window.API.fetchRuns()
      .then((r) => setRuns(r || []))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return html`<div class="field-hint" style=${{ padding: 32, textAlign: "center" }}>Loading runs…</div>`;
  if (!runs || !runs.length) return html`
    <div style=${{ padding: 48, textAlign: "center", color: "var(--text-subtle)" }}>
      <div style=${{ fontSize: 18, marginBottom: 12 }}>No backtest runs found</div>
      <div class="field-hint">Run a backtest with <code>--save-artifacts</code> to populate this view, then return here.</div>
    </div>
  `;

  function n(v, d = 2) { return v == null || isNaN(+v) ? "—" : (+v).toFixed(d); }
  function pct(v) { return v == null || isNaN(+v) ? "—" : ((+v) * 100).toFixed(2) + "%"; }

  function handleDeleteConfirm(runId) {
    setDeletingId(null);
    setRuns((rs) => (rs || []).filter((r) => r.run_id !== runId));
  }

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      ${deletingId && html`
        <${window.DeleteModal}
          runId=${deletingId}
          onConfirm=${handleDeleteConfirm}
          onCancel=${() => setDeletingId(null)}
        />
      `}
      <div style=${{ color: "var(--text-subtle)", fontSize: 13 }}>
        Select a backtest run to view its equity curve, drawdown, and KPIs.
      </div>
      <div class="card">
        <div class="card-h">
          <div class="card-title">All runs</div>
          <div class="card-sub">click a row to load it here</div>
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
                <th>Created</th>
                <th class="num">Delete</th>
              </tr>
            </thead>
            <tbody>
              ${runs.map((r) => html`
                <tr key=${r.run_id} style=${{ cursor: "pointer" }} onClick=${() => onSelect(r.run_id)}>
                  <td class="mono" style=${{ fontSize: 11, color: "var(--text-subtle)", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>${r.run_id}</td>
                  <td class="mono" style=${{ fontSize: 12 }}>${(r.strategies || [r.strategy]).filter(Boolean).join(", ")}</td>
                  <td class="mono" style=${{ fontSize: 11, color: "var(--text-muted)" }}>${(r.symbols || [r.symbol]).filter(Boolean).join(", ")}</td>
                  <td class="mono" title=${runParametersText(r)} style=${{ fontSize: 11, color: "var(--text-muted)", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>${runParametersText(r)}</td>
                  <td class="mono">${r.bar || "—"}</td>
                  <td class="mono" style=${{ fontSize: 11 }}>${r.start ? r.start.slice(0, 10) : "—"} → ${r.end ? r.end.slice(0, 10) : "—"}</td>
                  <td class="num" style=${{ color: r.total_return >= 0 ? "var(--profit)" : "var(--loss)" }}>${pct(r.total_return)}</td>
                  <td class="num">${n(r.sharpe)}</td>
                  <td class="num" style=${{ color: "var(--loss)" }}>${pct(r.max_drawdown)}</td>
                  <td class="mono" style=${{ fontSize: 11 }}>${r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                  <td class="num">
                    <button
                      class="btn ghost sm"
                      title="Delete run"
                      style=${{ color: "var(--loss)" }}
                      onClick=${(e) => { e.stopPropagation(); setDeletingId(r.run_id); }}
                    >
                      <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2.5 4h11M6 4V2.5h4V4M5 6v6M8 6v6M11 6v6M4 4l.5 10h7L12 4" />
                      </svg>
                    </button>
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function OverviewView({ tweaks, selectedRunId, setSelectedRunId }) {
  const [metrics, setMetrics] = useStateResults(null);
  const [equity, setEquity] = useStateResults([]);
  const [returns, setReturns] = useStateResults([]);
  const [drawdown, setDrawdown] = useStateResults([]);
  const [loading, setLoading] = useStateResults(false);
  const equityMode = tweaks.equityMode || "area";

  useEffectResults(() => {
    if (!selectedRunId) return;
    setLoading(true);
    Promise.all([
      window.API.fetchBacktestMetrics(selectedRunId),
      window.API.fetchBacktestEquity(selectedRunId).catch(() => []),
      window.API.fetchBacktestReturns(selectedRunId).catch(() => []),
      window.API.fetchBacktestDrawdown(selectedRunId).catch(() => []),
    ]).then(([m, eq, ret, dd]) => {
      setMetrics(m || {});
      setEquity(eq || []);
      setReturns(ret || []);
      setDrawdown(dd || []);
    }).finally(() => setLoading(false));
  }, [selectedRunId]);

  const equityValues = useMemoResults(() => {
    if (!equity.length) return [];
    const first = valueAt(equity[0], ["equity_usd", "equity"], 1) || 1;
    return equity.map((r) => {
      if (r.cum_return != null) return +r.cum_return;
      return valueAt(r, ["equity_usd", "equity"], first) / first - 1;
    });
  }, [equity]);

  const ddValues = useMemoResults(() => {
    if (drawdown.length) return drawdown.map((r) => valueAt(r, ["drawdown_pct", "drawdown"], 0));
    return equity.map((r) => valueAt(r, ["drawdown"], 0));
  }, [drawdown, equity]);

  const monthlyRet = useMemoResults(() => {
    const map = new Map();
    returns.forEach((r) => {
      const ts = r.ts || r.datetime;
      if (!ts) return;
      const d = new Date(ts);
      if (isNaN(d.getTime())) return;
      const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
      const ret = valueAt(r, ["simple_return", "return"], 0);
      map.set(key, (1 + (map.get(key) ?? 0)) * (1 + ret) - 1);
    });
    return [...map.entries()].map(([month, ret]) => ({ month, ret }));
  }, [returns]);

  if (!selectedRunId) return html`<${RunPicker} onSelect=${setSelectedRunId} />`;
  if (!metrics && !loading) return html`<${RunPicker} onSelect=${setSelectedRunId} />`;
  if (loading) return html`<div class="field-hint" style=${{ padding: 32 }}>Loading selected run...</div>`;

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${KPI} label="Total Return" value=${fmt.pct(metrics.total_return)} sub=${`CAGR ${fmt.pct(metrics.cagr)}`} tone=${metrics.total_return >= 0 ? "up" : "down"} spark=${equityValues.length ? equityValues : null} sparkMode=${equityMode} />
        <${KPI} label="Sharpe (ann.)" value=${fmt.num(metrics.sharpe, 2)} sub=${`Sortino ${fmt.num(metrics.sortino, 2)}`} tone=${metrics.sharpe >= 0 ? "up" : "down"} />
        <${KPI} label="Max Drawdown" value=${fmt.pct(metrics.max_drawdown)} sub=${`Calmar ${fmt.num(metrics.calmar, 2)}`} tone="down" spark=${ddValues.length ? ddValues : null} sparkMode="area" />
        <${KPI} label="Win rate" value=${fmt.pct(metrics.win_rate)} sub=${`PF ${fmt.num(metrics.profit_factor, 2)}`} />
      </div>

      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${KPI} label="DSR" value=${fmt.num(metrics.dsr, 2)} sub="0.95 promotion gate" tone=${metrics.dsr >= 0.95 ? "up" : "down"} hint="CPCV" />
        <${KPI} label="PSR" value=${fmt.num(metrics.psr, 2)} sub="prob Sharpe > 0" />
        <${KPI} label="Orders" value=${(metrics.order_count ?? metrics.submitted_order_count ?? 0).toLocaleString()} sub=${`${metrics.real_fill_count ?? metrics.orders_filled_count ?? 0} real fills`} />
        <${KPI} label="Fill rate" value=${fmt.pct(metrics.fill_rate)} sub=${metrics.bankrupt ? "bankrupt run" : "execution model"} tone=${metrics.bankrupt ? "down" : undefined} />
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Equity curve</div>
            <div class="card-sub mono">${selectedRunId}</div>
          </div>
          <div class="row" style=${{ gap: 8 }}>
            <span class="chip">N = ${equity.length.toLocaleString()}</span>
          </div>
        </div>
        <div class="chart-wrap"><${LineChart} series=${[{ values: equityValues.length ? equityValues : [0], color: "var(--accent)" }]} height=${260} mode=${equityMode} /></div>
      </div>

      <div class="row" style=${{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
        <div class="card" style=${{ flex: 2 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Drawdown</div>
              <div class="card-sub">underwater curve</div>
            </div>
            <span class="chip loss">Max ${fmt.pct(metrics.max_drawdown)}</span>
          </div>
          <div class="chart-wrap"><${LineChart} series=${[{ values: ddValues.length ? ddValues : [0], color: "var(--loss)" }]} height=${180} mode="area" /></div>
        </div>
        <div class="card" style=${{ flex: 1 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Monthly returns</div>
              <div class="card-sub">compounded from returns.csv</div>
            </div>
          </div>
          <table class="tbl" style=${{ fontSize: 12 }}>
            <thead><tr><th>Month</th><th class="num">Return</th><th class="num"></th></tr></thead>
            <tbody>
              ${monthlyRet.map((m) => html`
                <tr key=${m.month}>
                  <td class="mono">${m.month}</td>
                  <td class="num" style=${{ color: m.ret >= 0 ? "var(--profit)" : "var(--loss)" }}>${fmt.pct(m.ret)}</td>
                  <td class="num" style=${{ width: 80 }}>
                    <div class="bar" style=${{ background: "var(--surface-2)" }}>
                      <i style=${{ width: `${Math.min(100, Math.abs(m.ret) * 1500)}%`, background: m.ret >= 0 ? "var(--profit)" : "var(--loss)" }}></i>
                    </div>
                  </td>
                </tr>
              `)}
              ${!monthlyRet.length && html`<tr><td colSpan=${3} class="field-hint" style=${{ textAlign: "center", padding: 16 }}>No returns.csv data.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <div class="card-title">Extended metrics</div>
          <div class="card-sub">full metrics.json object · hover for description</div>
        </div>
        <div class="grid" style=${{ gridTemplateColumns: "repeat(6, 1fr)", gap: 16 }}>
          ${Object.entries(metrics).map(([k, v]) => {
            const entry = typeof window.METRIC_DESCRIPTIONS !== "undefined" ? window.METRIC_DESCRIPTIONS?.[k] : null;
            const titleText = entry ? `${entry.desc}\nUnit: ${entry.unit}` : k;
            return html`
              <div key=${k} title=${titleText} style=${{ cursor: "help" }}>
                <div class="kpi-label">${metricLabel(k)}</div>
                <div class="mono" style=${{ fontSize: 18, marginTop: 2 }}>${displayMetric(k, v)}</div>
              </div>
            `;
          })}
        </div>
      </div>
    </div>
  `;
}

function WalkForwardView({ selectedRunId }) {
  const [windows, setWindows] = useStateResults([]);
  const [loaded, setLoaded] = useStateResults(false);

  useEffectResults(() => {
    if (!selectedRunId) return;
    setLoaded(false);
    window.API.fetchWalkForward(selectedRunId)
      .then((rows) => setWindows(rows || []))
      .catch(() => setWindows([]))
      .finally(() => setLoaded(true));
  }, [selectedRunId]);

  if (!selectedRunId) return html`<div style=${{ padding: 32, color: "var(--text-subtle)" }}>Select a backtest run first.</div>`;
  if (!loaded) return html`<div class="field-hint" style=${{ padding: 32 }}>Loading walk-forward data...</div>`;
  if (!windows.length) return html`<div style=${{ padding: 32, color: "var(--text-subtle)" }}>Walk-Forward validation was not run for this backtest.</div>`;

  const oos = windows.map((w) => +w.oos_sharpe || 0);
  const isS = windows.map((w) => +w.is_sharpe || 0);
  const meanOos = oos.reduce((a, b) => a + b, 0) / Math.max(oos.length, 1);
  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${KPI} label="Windows" value=${windows.length} sub="non-overlapping IS/OOS" />
        <${KPI} label="Mean OOS Sharpe" value=${fmt.num(meanOos, 2)} tone=${meanOos >= 0 ? "up" : "down"} />
        <${KPI} label="OOS positive %" value=${fmt.pct(oos.filter((v) => v > 0).length / Math.max(oos.length, 1))} />
        <${KPI} label="Selected run" value=${selectedRunId.slice(-8)} sub="result.json walk_forward" />
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">IS vs OOS Sharpe</div>
            <div class="card-sub">per validation window</div>
          </div>
        </div>
        <div class="chart-wrap"><${LineChart} series=${[
          { values: isS, color: "var(--text-subtle)" },
          { values: oos, color: "var(--accent)" },
        ]} height=${200} /></div>
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Window timeline</div>
            <div class="card-sub">one row per validation window</div>
          </div>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>#</th><th>IS start</th><th>IS end</th><th>OOS start</th><th>OOS end</th>
                <th class="num">IS Sharpe</th><th class="num">OOS Sharpe</th>
                <th class="num">OOS Return</th><th class="num">OOS MDD</th><th class="num">Decay</th>
              </tr>
            </thead>
            <tbody>
              ${windows.map((w, i) => {
                const idx = w.i ?? i;
                const decay = (+w.oos_sharpe || 0) / (+w.is_sharpe || 1e-9);
                return html`
                  <tr key=${idx}>
                    <td class="mono">${String(idx).padStart(2, "0")}</td>
                    <td class="mono" style=${{ color: "var(--text-muted)" }}>${fmt.date(w.is_start)}</td>
                    <td class="mono" style=${{ color: "var(--text-muted)" }}>${fmt.date(w.is_end)}</td>
                    <td class="mono">${fmt.date(w.oos_start)}</td>
                    <td class="mono">${fmt.date(w.oos_end)}</td>
                    <td class="num">${fmt.num(w.is_sharpe, 2)}</td>
                    <td class="num" style=${{ color: w.oos_sharpe >= 0 ? "var(--profit)" : "var(--loss)" }}>${fmt.num(w.oos_sharpe, 2)}</td>
                    <td class="num" style=${{ color: w.oos_return >= 0 ? "var(--profit)" : "var(--loss)" }}>${fmt.pct(w.oos_return)}</td>
                    <td class="num" style=${{ color: "var(--loss)" }}>${fmt.pct(w.oos_mdd)}</td>
                    <td class="num" style=${{ color: "var(--text-muted)" }}>${fmt.num(decay, 2)}x</td>
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

function CPCVView({ selectedRunId }) {
  const [cpcv, setCpcv] = useStateResults(null);
  const [loaded, setLoaded] = useStateResults(false);

  useEffectResults(() => {
    if (!selectedRunId) return;
    setLoaded(false);
    window.API.fetchCPCV(selectedRunId)
      .then((data) => setCpcv(data || null))
      .catch(() => setCpcv(null))
      .finally(() => setLoaded(true));
  }, [selectedRunId]);

  if (!selectedRunId) return html`<div style=${{ padding: 32, color: "var(--text-subtle)" }}>Select a backtest run first.</div>`;
  if (!loaded) return html`<div class="field-hint" style=${{ padding: 32 }}>Loading CPCV data...</div>`;
  if (!cpcv) return html`<div style=${{ padding: 32, color: "var(--text-subtle)" }}>CPCV validation was not run for this backtest.</div>`;

  const combos = cpcv.combos || [];
  if (!combos.length) return html`<div style=${{ padding: 32, color: "var(--text-subtle)" }}>CPCV validation was not run for this backtest.</div>`;

  const groupCount = Math.max(6, ...combos.flatMap((co) => co.test_groups || []).map((v) => +v + 1));
  const grid = Array.from({ length: groupCount }, () => Array(groupCount).fill(null));
  combos.forEach((co, idx) => {
    const groups = co.test_groups || [];
    if (groups.length >= 2) {
      const [a, b] = groups;
      grid[a][b] = co.sharpe;
      grid[b][a] = co.sharpe;
    } else {
      const a = Math.floor(idx / groupCount);
      const b = idx % groupCount;
      grid[a][b] = co.sharpe;
    }
  });
  const allS = combos.map((co) => +co.sharpe || 0);
  const minS = Math.min(...allS), maxS = Math.max(...allS);
  function heat(v) {
    if (v == null) return "var(--surface-2)";
    const t = (v - minS) / (maxS - minS || 1);
    if (v >= 0) return `oklch(${0.95 - t * 0.40} ${0.05 + t * 0.13} 155)`;
    return `oklch(${0.95 - (1 - t) * 0.40} ${0.05 + (1 - t) * 0.13} 25)`;
  }

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${KPI} label="DSR (Deflated Sharpe)" value=${fmt.num(cpcv.dsr, 2)} sub=${cpcv.dsr >= 0.95 ? "promote-eligible" : "below 0.95 gate"} tone=${cpcv.dsr >= 0.95 ? "up" : "down"} />
        <${KPI} label="PSR" value=${fmt.num(cpcv.psr, 2)} sub="prob true SR > 0" tone="up" />
        <${KPI} label="Mean OOS Sharpe" value=${fmt.num(cpcv.mean_oos_sharpe, 2)} sub=${`std ${fmt.num(cpcv.std_oos_sharpe, 2)}`} />
        <${KPI} label="Combinations" value=${`${combos.length} / ${(cpcv.paths || []).length} paths`} sub="result.json cpcv" />
      </div>

      <div class="row" style=${{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
        <div class="card" style=${{ flex: 1 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Combination heatmap</div>
              <div class="card-sub">test groups to OOS Sharpe</div>
            </div>
          </div>
          <div style=${{ display: "grid", gridTemplateColumns: `auto repeat(${groupCount}, 1fr)`, gap: 4, fontSize: 11 }}>
            <div></div>
            ${Array.from({ length: groupCount }, (_, j) => html`<div key=${j} class="mono" style=${{ textAlign: "center", color: "var(--text-subtle)" }}>g${j}</div>`)}
            ${grid.map((row, i) => html`
              <${Fragment} key=${i}>
                <div class="mono" style=${{ color: "var(--text-subtle)" }}>g${i}</div>
                ${row.map((v, j) => html`
                  <div key=${j} class="heat-cell" style=${{ height: 44, background: heat(v), color: v != null && Math.abs(v) > (maxS - minS) * 0.5 ? "white" : "var(--text)" }}>
                    ${v != null ? (+v).toFixed(2) : ""}
                  </div>
                `)}
              <//>
            `)}
          </div>
        </div>

        <div class="card" style=${{ flex: 1 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Sharpe distribution</div>
              <div class="card-sub">over CPCV combinations</div>
            </div>
          </div>
          <div class="chart-wrap"><${HistogramChart} values=${allS} bins=${12} height=${200} color="var(--accent)" /></div>
          <div class="field-hint" style=${{ marginTop: 8 }}>mean = ${fmt.num(cpcv.mean_oos_sharpe, 2)} · std = ${fmt.num(cpcv.std_oos_sharpe, 2)}</div>
        </div>
      </div>
    </div>
  `;
}

window.OverviewView = OverviewView;
window.WalkForwardView = WalkForwardView;
window.CPCVView = CPCVView;

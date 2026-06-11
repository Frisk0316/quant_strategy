import { h } from 'preact';
import { useState, useEffect, useMemo } from 'preact/hooks';
import { html } from 'htm/preact';
const useTradesState = useState;
const useTradesEffect = useEffect;
const useTradesMemo = useMemo;

const KPI = window.KPI;
const fmt = window.fmt;
const MOCK = window.MOCK;
const { LineChart } = window.Charts;

function signedUsd(v, d = 2) {
  if (v == null || !isFinite(v)) return "-";
  const value = +v;
  const sign = value < 0 ? "-" : "";
  return `${sign}$${fmt.num(Math.abs(value), d)}`;
}

function pnlUsd(v, d = 2) {
  if (v == null || !isFinite(v)) return "-";
  return `${+v > 0 ? "+" : ""}${signedUsd(v, d)}`;
}

function normalizeTrade(t, i) {
  const ts = t.datetime || t.ts || Date.now();
  const side = String(t.side || "").toUpperCase();
  const price = +(t.price ?? t.fill_px ?? 0);
  const qty = +(t.qty ?? t.fill_sz ?? 0);
  const fee = +(t.fee ?? 0);
  const pnl = +(t.pnl ?? t.net_realized_pnl ?? t.realized_pnl ?? 0);
  const state = String(t.status || t.state || "FILLED").toUpperCase();
  return {
    id: t.id ?? t.cl_ord_id ?? i,
    ts,
    symbol: t.symbol || t.inst_id || "-",
    side,
    type: t.type || t.ord_type || "post_only",
    price,
    qty,
    notional: +(t.notional ?? t.notional_usd ?? price * qty),
    fee,
    pnl,
    status: state,
    strategy: t.strategy || "-",
  };
}

function TradesView({ selectedRunId }) {
  const [side, setSide] = useTradesState("ALL");
  const [status, setStatus] = useTradesState("ALL");
  const [strat, setStrat] = useTradesState("ALL");
  const [pair, setPair] = useTradesState("ALL");
  const [search, setSearch] = useTradesState("");
  const [rows, setRows] = useTradesState(null);

  useTradesEffect(() => {
    if (!selectedRunId) {
      setRows(null);
      return;
    }
    window.API.fetchBacktestTrades(selectedRunId)
      .then((data) => setRows((data || []).map(normalizeTrade)))
      .catch(() => setRows([]));
  }, [selectedRunId]);

  const data = rows ?? MOCK.trades.map(normalizeTrade);
  const strategies = [...new Set([...MOCK.STRATEGIES.map((s) => s.id), ...data.map((t) => t.strategy)].filter(Boolean))];
  const tradingPairs = [...new Set(data.map((t) => t.symbol).filter((s) => s && s !== "-"))].sort();

  const filtered = useTradesMemo(() => {
    return data.filter((t) => {
      if (pair !== "ALL" && t.symbol !== pair) return false;
      if (side !== "ALL" && t.side !== side) return false;
      if (status !== "ALL" && t.status !== status) return false;
      if (strat !== "ALL" && t.strategy !== strat) return false;
      if (search && !t.symbol.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [data, pair, side, status, strat, search]);

  const totalPnl = filtered.reduce((a, t) => a + (t.status === "FILLED" ? t.pnl : 0), 0);
  const totalFee = filtered.reduce((a, t) => a + t.fee, 0);

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${KPI} label="Filtered trades" value=${filtered.length.toLocaleString()} sub=${`of ${data.length}`} />
        <${KPI} label="Net PnL" value=${pnlUsd(totalPnl)} tone=${totalPnl >= 0 ? "up" : "down"} />
        <${KPI} label="Fees paid" value=${fmt.usd(totalFee)} sub="post_only maker execution" />
        <${KPI} label="Fill rate" value=${fmt.pct(filtered.filter((t) => t.status === "FILLED").length / Math.max(filtered.length, 1))} sub=${selectedRunId ? selectedRunId.slice(-8) : "MOCK fallback"} />
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Trades / Orders</div>
            <div class="card-sub">${selectedRunId ? "selected run trades.csv" : "MOCK fallback data"}</div>
          </div>
          <div class="row" style=${{ gap: 8 }}>
            <button class="btn ghost sm">Export CSV</button>
            <button class="btn ghost sm">Replay</button>
          </div>
        </div>

        <div class="row wrap" style=${{ gap: 12, marginBottom: 12 }}>
          <input class="input" placeholder="Search trading pair..." value=${search} onChange=${(e) => setSearch(e.target.value)} style=${{ width: 200 }} />
          <select class="select" value=${pair} onChange=${(e) => setPair(e.target.value)} style=${{ width: 190 }}>
            <option value="ALL">All trading pairs</option>
            ${tradingPairs.map((s) => html`<option key=${s} value=${s}>${s}</option>`)}
          </select>
          <select class="select" value=${side} onChange=${(e) => setSide(e.target.value)} style=${{ width: 120 }}>
            <option value="ALL">Side ALL</option>
            <option>BUY</option>
            <option>SELL</option>
          </select>
          <select class="select" value=${status} onChange=${(e) => setStatus(e.target.value)} style=${{ width: 140 }}>
            <option value="ALL">Status ALL</option>
            <option>FILLED</option>
            <option>CANCELLED</option>
            <option>REJECTED</option>
          </select>
          <select class="select" value=${strat} onChange=${(e) => setStrat(e.target.value)} style=${{ width: 200 }}>
            <option value="ALL">Strategy ALL</option>
            ${strategies.map((s) => html`<option key=${s} value=${s}>${s}</option>`)}
          </select>
        </div>

        <div class="tbl-wrap" style=${{ maxHeight: 520 }}>
          <table class="tbl">
            <thead>
              <tr>
                <th>ID</th><th>Timestamp (UTC)</th><th>Trading Pair</th><th>Side</th><th>Type</th>
                <th class="num">Price</th><th class="num">Qty</th><th class="num">Notional</th>
                <th class="num">Fee</th><th class="num">PnL</th><th>Status</th><th>Strategy</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.slice(0, 80).map((t, i) => html`
                <tr key=${`${t.id}-${i}`}>
                  <td class="mono" style=${{ color: "var(--text-muted)" }}>${t.id}</td>
                  <td class="mono">${fmt.ts(t.ts)}</td>
                  <td class="mono">${t.symbol}</td>
                  <td>
                    <span class="chip" style=${{ color: t.side === "BUY" ? "var(--profit)" : "var(--loss)", background: t.side === "BUY" ? "var(--profit-soft)" : "var(--loss-soft)", borderColor: "transparent" }}>${t.side}</span>
                  </td>
                  <td class="mono" style=${{ color: "var(--text-muted)" }}>${t.type}</td>
                  <td class="num">${fmt.num(t.price, 2)}</td>
                  <td class="num">${fmt.num(t.qty, 4)}</td>
                  <td class="num">${fmt.usd(t.notional)}</td>
                  <td class="num" style=${{ color: "var(--text-muted)" }}>${fmt.usd(t.fee, 3)}</td>
                  <td class="num" style=${{ color: t.pnl >= 0 ? "var(--profit)" : "var(--loss)" }}>${t.status === "FILLED" ? pnlUsd(t.pnl) : "-"}</td>
                  <td><span class=${`chip ${t.status === "FILLED" ? "profit" : t.status === "REJECTED" ? "loss" : "warn"}`} style=${{ fontSize: 10 }}>${t.status}</span></td>
                  <td class="mono" style=${{ color: "var(--text-subtle)", fontSize: 11 }}>${t.strategy}</td>
                </tr>
              `)}
              ${!filtered.length && html`<tr><td colSpan=${12} class="field-hint" style=${{ textAlign: "center", padding: 16 }}>No trades match the current filters.</td></tr>`}
            </tbody>
          </table>
        </div>
        <div class="field-hint" style=${{ marginTop: 8 }}>showing first 80 of ${filtered.length}</div>
      </div>
    </div>
  `;
}

const COLORS = ["var(--accent)", "var(--profit)", "var(--loss)", "var(--warn)", "var(--text-muted)", "oklch(0.55 0.18 310)"];

function normalizeTsKey(ts) {
  if (ts == null) return null;
  if (typeof ts === "number" || /^\d+$/.test(String(ts))) return new Date(+ts).toISOString();
  const d = new Date(ts);
  return isNaN(d.getTime()) ? String(ts) : d.toISOString();
}

function normalizeEquityRows(rows) {
  if (!rows?.length) return [];
  const first = +(rows[0].equity_usd ?? rows[0].equity ?? 1) || 1;
  return rows.map((r) => {
    const equity = +(r.equity_usd ?? r.equity ?? 0);
    return {
      ...r,
      _ts: normalizeTsKey(r.ts || r.datetime),
      _equity: equity,
      _pnl: equity - first,
      _cumReturn: r.cum_return != null ? +r.cum_return : equity / first - 1,
    };
  }).filter((r) => r._ts);
}

function CompareView({ selectedRunId }) {
  const [allRuns, setAllRuns] = useTradesState([]);
  const [selectedIds, setSelectedIds] = useTradesState([]);
  const [runData, setRunData] = useTradesState({});
  const [hoverIdx, setHoverIdx] = useTradesState(null);

  useTradesEffect(() => {
    window.API.fetchRuns().then((runs) => {
      setAllRuns(runs || []);
      if (selectedRunId) setSelectedIds([selectedRunId]);
    }).catch(() => setAllRuns([]));
  }, []);

  useTradesEffect(() => {
    if (selectedRunId) setSelectedIds((ids) => ids.includes(selectedRunId) ? ids : [selectedRunId, ...ids].slice(0, 4));
  }, [selectedRunId]);

  useTradesEffect(() => {
    selectedIds.forEach((id) => {
      if (runData[id]) return;
      Promise.all([
        window.API.fetchBacktestMetrics(id),
        window.API.fetchBacktestEquity(id).catch(() => []),
      ]).then(([metrics, equity]) => {
        setRunData((prev) => ({ ...prev, [id]: { metrics: metrics || {}, equity: normalizeEquityRows(equity || []) } }));
      });
    });
  }, [selectedIds, runData]);

  const allTs = useTradesMemo(() => [...new Set(
    selectedIds.flatMap((id) => (runData[id]?.equity || []).map((r) => r._ts))
  )].sort(), [selectedIds, runData]);

  const aligned = useTradesMemo(() => {
    const out = {};
    selectedIds.forEach((id) => {
      const rows = runData[id]?.equity || [];
      const byTs = new Map(rows.map((r) => [r._ts, r]));
      let last = null;
      out[id] = allTs.map((ts) => {
        const exact = byTs.get(ts);
        if (exact) last = exact;
        return last ? { ts, pnl: last._pnl, cumReturn: last._cumReturn, equity: last._equity } : { ts, pnl: null, cumReturn: null, equity: null };
      });
    });
    return out;
  }, [selectedIds, runData, allTs]);

  const chartSeries = selectedIds.map((id, i) => ({
    values: (aligned[id] || []).map((p) => p.pnl ?? 0),
    color: COLORS[i % COLORS.length],
    label: id.slice(-8),
  }));

  function toggleRun(id) {
    setSelectedIds((ids) => ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  }

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Run selector</div>
            <div class="card-sub">choose saved runs to align on a shared timeline</div>
          </div>
        </div>
        <div class="row wrap" style=${{ gap: 8 }}>
          ${allRuns.map((r) => html`
            <button key=${r.run_id} class=${`btn sm ${selectedIds.includes(r.run_id) ? "" : "ghost"}`} onClick=${() => toggleRun(r.run_id)}>
              <span class="mono">${r.run_id.slice(-8)}</span>
              <span style=${{ marginLeft: 6 }}>${fmt.pct(r.total_return)}</span>
            </button>
          `)}
          ${!allRuns.length && html`<div class="field-hint">No saved runs found.</div>`}
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Equity curves</div>
            <div class="card-sub">PnL on a union timeline with forward-filled gaps</div>
          </div>
          <span class="chip">${allTs.length.toLocaleString()} timestamps</span>
        </div>
        <div
          class="chart-wrap"
          style=${{ position: "relative" }}
          onMouseLeave=${() => setHoverIdx(null)}
          onMouseMove=${(e) => {
            if (!allTs.length) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
            setHoverIdx(Math.round((x / rect.width) * (allTs.length - 1)));
          }}
        >
          <${LineChart}
            series=${chartSeries.length ? chartSeries : [{ values: [0], color: "var(--accent)" }]}
            height=${280}
            xLabels=${allTs}
            tooltipLabelFormatter=${(value) => fmt.date(value)}
            tooltipValueFormatter=${(value) => pnlUsd(value)}
          />
          ${hoverIdx != null && allTs[hoverIdx] && html`
            <div style=${{ position: "absolute", top: 8, left: 16, background: "var(--surface-2)",
                            border: "1px solid var(--border-strong)", borderRadius: 6,
                            padding: "8px 12px", fontSize: 12, zIndex: 10 }}>
              <div class="mono" style=${{ marginBottom: 6 }}>${allTs[hoverIdx]?.slice(0, 10)}</div>
              ${selectedIds.map((id, i) => {
                const points = aligned[id] || [];
                const p = points[hoverIdx];
                const pnl = p?.pnl;
                return html`
                  <div key=${id}>
                    <span style=${{ color: COLORS[i % COLORS.length] }}>●</span> ${id.slice(-8)}: ${p?.cumReturn != null ? fmt.pct(p.cumReturn) : "-"} · PnL ${pnl != null ? pnlUsd(pnl) : "-"}
                  </div>
                `;
              })}
            </div>
          `}
        </div>
        <div class="row wrap" style=${{ gap: 16, marginTop: 14 }}>
          ${selectedIds.map((id, i) => html`
            <div key=${id} class="row" style=${{ gap: 8, alignItems: "center" }}>
              <div style=${{ width: 18, height: 3, background: COLORS[i % COLORS.length], borderRadius: 2 }}></div>
              <div class="mono" style=${{ fontSize: 12 }}>${id}</div>
            </div>
          `)}
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Side-by-side metrics</div>
            <div class="card-sub">one column per selected run</div>
          </div>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Metric</th>
                ${selectedIds.map((id) => html`<th key=${id} class="num">${id.slice(-8)}</th>`)}
              </tr>
            </thead>
            <tbody>
              ${[
                ["Total Return", "total_return", "pct"],
                ["CAGR", "cagr", "pct"],
                ["Sharpe", "sharpe", "num"],
                ["Sortino", "sortino", "num"],
                ["Calmar", "calmar", "num"],
                ["Max Drawdown", "max_drawdown", "pct"],
                ["Profit Factor", "profit_factor", "num"],
                ["Win rate", "win_rate", "pct"],
              ].map(([label, key, kind]) => html`
                <tr key=${key}>
                  <td>${label}</td>
                  ${selectedIds.map((id) => {
                    const v = runData[id]?.metrics?.[key];
                    return html`<td key=${id} class="num">${kind === "pct" ? fmt.pct(v) : fmt.num(v, 2)}</td>`;
                  })}
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function RiskView({ selectedRunId }) {
  const [riskConfig, setRiskConfig] = useTradesState(null);
  const [metrics, setMetrics] = useTradesState(null);

  useTradesEffect(() => {
    window.API.fetchRiskConfig().then(setRiskConfig).catch(() => setRiskConfig(null));
  }, []);

  useTradesEffect(() => {
    if (!selectedRunId) {
      setMetrics(null);
      return;
    }
    window.API.fetchBacktestMetrics(selectedRunId).then(setMetrics).catch(() => setMetrics(null));
  }, [selectedRunId]);

  const cfg = riskConfig?.risk || riskConfig || {};
  const limits = [
    { name: "Daily loss halt", val: 0, max: cfg.max_daily_loss_pct ?? 0.05, fmt: "pct", warn: 60, danger: 90 },
    { name: "Soft drawdown", val: Math.abs(metrics?.max_drawdown ?? MOCK.risk.soft_dd_used), max: cfg.soft_drawdown_pct ?? 0.10, fmt: "pct", warn: 60, danger: 90 },
    { name: "Hard drawdown", val: Math.abs(metrics?.max_drawdown ?? MOCK.risk.soft_dd_used), max: cfg.hard_drawdown_pct ?? 0.15, fmt: "pct", warn: 60, danger: 90 },
    { name: "Leverage", val: MOCK.risk.leverage, max: cfg.max_leverage ?? MOCK.risk.max_leverage, fmt: "num", warn: 60, danger: 85 },
    { name: "Position % equity", val: MOCK.risk.pos_pct_equity, max: cfg.max_pos_pct_equity ?? MOCK.risk.max_pos_pct_equity, fmt: "pct", warn: 70, danger: 90 },
    { name: "Order notional", val: MOCK.risk.last_order_notional, max: cfg.max_order_notional_usd ?? MOCK.risk.max_order_notional, fmt: "usd", warn: 70, danger: 90 },
  ];

  function fm(kind, v) {
    return kind === "pct" ? fmt.pct(v) : kind === "usd" ? fmt.usd(v, 0) : fmt.num(v, 2) + "x";
  }

  function Gauge({ label, value, max, format, danger, warn }) {
    const pct = Math.min(100, (Math.abs(value) / Math.max(max, 1e-9)) * 100);
    const color = pct >= danger ? "var(--loss)" : pct >= warn ? "var(--warn)" : "var(--profit)";
    return html`
      <div class="card">
        <div class="kpi-label">${label}</div>
        <div class="row" style=${{ alignItems: "baseline", gap: 8, marginTop: 4 }}>
          <div class="mono" style=${{ fontSize: 22 }}>${format(value)}</div>
          <div class="mono" style=${{ color: "var(--text-subtle)", fontSize: 12 }}>/ ${format(max)}</div>
        </div>
        <div class="bar" style=${{ height: 6, marginTop: 10 }}>
          <i style=${{ width: `${pct}%`, background: color }}></i>
        </div>
        <div class="field-hint" style=${{ marginTop: 6 }}>${pct.toFixed(1)}% of limit</div>
      </div>
    `;
  }

  const dsr = metrics?.dsr ?? metrics?.deflated_sharpe;
  const gateRows = [
    ["Historical backtest", !!selectedRunId],
    ["Bankrupt flag clear", metrics ? !metrics.bankrupt : false],
    ["Sharpe > 0", metrics ? (metrics.sharpe ?? 0) > 0 : false],
    ["DSR >= 0.95", dsr != null ? dsr >= 0.95 : false],
    ["Demo run", false],
    ["Live deployment", false],
  ];

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <${KPI} label="Final equity" value=${metrics?.last_equity != null ? fmt.usd(metrics.last_equity, 0) : metrics?.final_equity != null ? fmt.usd(metrics.final_equity, 0) : "-"} sub=${selectedRunId ? selectedRunId.slice(-8) : "No run selected"} tone="up" />
        <${KPI} label="Daily PnL" value="N/A" sub="demo mode" />
        <${KPI} label="Sharpe" value=${fmt.num(metrics?.sharpe, 2)} sub="selected run metrics" />
        <${KPI} label="Mode" value="DEMO" sub="offline API view" />
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Risk limits</div>
            <div class="card-sub">config/risk.yaml</div>
          </div>
          <span class="chip profit">Config loaded</span>
        </div>
        <div class="grid" style=${{ gridTemplateColumns: "repeat(3, 1fr)" }}>
          ${limits.map((l) => html`<${Gauge} key=${l.name} label=${l.name} value=${l.val} max=${l.max} format=${(v) => fm(l.fmt, v)} warn=${l.warn} danger=${l.danger} />`)}
        </div>
      </div>

      <div class="row" style=${{ gap: "var(--gap-lg)" }}>
        <div class="card" style=${{ flex: 1 }}>
          <div class="card-title" style=${{ marginBottom: 12 }}>Circuit breakers</div>
          <table class="tbl">
            <thead><tr><th>Breaker</th><th class="num">Current</th><th class="num">Threshold</th><th>Status</th></tr></thead>
            <tbody>
              <tr><td>WS reconnects</td><td class="num">0</td><td class="num">${cfg.ws_reconnect_circuit_threshold ?? 3}</td><td><span class="chip profit">OK</span></td></tr>
              <tr><td>REST error rate</td><td class="num">N/A</td><td class="num">${fmt.pct(cfg.rest_error_rate_circuit_threshold ?? 0.05)}</td><td><span class="chip">demo</span></td></tr>
              <tr><td>Stale quote deviation</td><td class="num">N/A</td><td class="num">${fmt.pct(cfg.stale_quote_pct ?? 0.02)}</td><td><span class="chip">demo</span></td></tr>
              <tr><td>Hard stop cooldown</td><td class="num">inactive</td><td class="num">${cfg.hard_stop_cooldown_hours ?? 48}h</td><td><span class="chip">inactive</span></td></tr>
            </tbody>
          </table>
        </div>

        <div class="card" style=${{ flex: 1 }}>
          <div class="card-title" style=${{ marginBottom: 12 }}>Promotion gate</div>
          <div class="col" style=${{ gap: 10 }}>
            ${gateRows.map(([name, ok], i) => html`
              <div key=${i} class="row" style=${{ alignItems: "center", gap: 10 }}>
                <div style=${{
                  width: 18, height: 18, borderRadius: 999,
                  background: ok ? "var(--profit)" : "var(--surface-2)",
                  border: "1px solid",
                  borderColor: ok ? "var(--profit)" : "var(--border-strong)",
                  display: "grid", placeItems: "center",
                  color: "white", fontSize: 11,
                }}>${ok ? "✓" : ""}</div>
                <div style=${{ flex: 1, color: ok ? "var(--text)" : "var(--text-muted)" }}>${name}</div>
                <span class=${`chip ${ok ? "profit" : ""}`}>${ok ? "passed" : "pending"}</span>
              </div>
            `)}
          </div>
          <div class="sep"></div>
          <button class="btn primary" disabled style=${{ width: "100%", opacity: 0.5 }}>Promote to LIVE</button>
        </div>
      </div>
    </div>
  `;
}

window.TradesView = TradesView;
window.CompareView = CompareView;
window.RiskView = RiskView;

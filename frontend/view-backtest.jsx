/* global React, Charts, KPI, fmt */
// Backtest Runs browser + Run Detail view — reads from /api/backtest/* endpoints.
const { useState, useEffect, useCallback } = React;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function n(v, d = 2) { return v == null || isNaN(+v) ? "—" : (+v).toFixed(d); }
function pct(v) { return v == null || isNaN(+v) ? "—" : ((+v) * 100).toFixed(2) + "%"; }
function usd(v, d = 2) { return v == null || isNaN(+v) ? "—" : "$" + Math.abs(+v).toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d }); }
function fmtDt(s) { if (!s) return "—"; try { return new Date(s).toISOString().slice(0, 19).replace("T", " "); } catch { return s; } }

function StatusBadge({ ok, children }) {
  return (
    <span className="chip" style={{
      background: ok ? "var(--profit-soft)" : "var(--loss-soft)",
      color: ok ? "var(--profit)" : "var(--loss)",
      borderColor: "transparent",
    }}>{children}</span>
  );
}

function MetricCard({ label, value, sub, tone }) {
  const color = tone === "up" ? "var(--profit)" : tone === "down" ? "var(--loss)" : "var(--text)";
  return (
    <div className="card" style={{ padding: "14px 16px" }}>
      <div className="kpi-label" style={{ marginBottom: 4 }}>{label}</div>
      <div className="mono" style={{ fontSize: 20, fontWeight: 600, color }}>{value}</div>
      {sub && <div className="field-hint" style={{ marginTop: 4 }}>{sub}</div>}
    </div>
  );
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
  return (
    <div style={{ background: "var(--loss-soft)", border: "1px solid var(--loss)", borderRadius: 8, padding: "12px 16px" }}>
      <div style={{ fontWeight: 600, color: "var(--loss)", marginBottom: 6 }}>Strategy Risk Warnings</div>
      {warnings.map((w, i) => <div key={i} style={{ color: "var(--loss)", fontSize: 13, marginTop: 4 }}>• {w}</div>)}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Run Detail View
// ---------------------------------------------------------------------------
function RunDetailView({ runId, onBack }) {
  const [result, setResult] = useState(null);
  const [equity, setEquity] = useState([]);
  const [fills, setFills] = useState([]);
  const [riskEvents, setRiskEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("fills");

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      window.API.fetchBacktest(runId),
      window.API.fetchBacktestEquity(runId).catch(() => []),
      window.API.fetchBacktestFills(runId).catch(() => []),
      window.API.fetchBacktestRiskEvents(runId).catch(() => []),
    ]).then(([r, eq, fl, re]) => {
      setResult(r);
      setEquity(eq || []);
      setFills(fl || []);
      setRiskEvents(re || []);
    }).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [runId]);

  if (loading) return <div className="field-hint" style={{ padding: 32 }}>Loading run {runId}…</div>;
  if (error) return <div style={{ color: "var(--loss)", padding: 32 }}>Error: {error}</div>;
  if (!result) return null;

  const m = result.metrics || {};
  const strats = (result.strategies || []).join(", ") || result.strategy || "—";
  const symbols = (result.symbols || []).join(", ") || result.symbol || "—";
  const bar = result.bar || "—";
  const start = result.start ? result.start.slice(0, 10) : "—";
  const end = result.end ? result.end.slice(0, 10) : "—";

  // Equity chart values
  const eqValues = equity.filter(r => r.equity != null).map(r => +r.equity);
  const ddValues = equity.filter(r => r.drawdown != null).map(r => +r.drawdown);

  // Real fills only
  const realFills = fills.filter(f => f.fill_sz && +f.fill_sz > 0 && (f.state === "filled" || f.state === "partially_filled"));

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      {/* Header row */}
      <div className="row" style={{ alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <button className="btn ghost sm" onClick={onBack}>← Runs</button>
        <div className="mono" style={{ fontSize: 13, color: "var(--text-subtle)", flex: 1 }}>{runId}</div>
        <span className="chip">{strats}</span>
        <span className="chip">{symbols}</span>
        <span className="chip">{bar}</span>
        <span className="chip">{start} → {end}</span>
        <StatusBadge ok={!m.bankrupt}>{m.bankrupt ? "BANKRUPT" : "OK"}</StatusBadge>
      </div>

      <AnomalyBanner metrics={m} />

      {/* Primary KPIs */}
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <MetricCard label="Total Return" value={pct(m.total_return)} tone={+m.total_return >= 0 ? "up" : "down"} sub={`Min equity: ${usd(m.min_equity)}`} />
        <MetricCard label="Sharpe (ann.)" value={n(m.sharpe)} sub={`Sortino ${n(m.sortino)}`} tone={+m.sharpe >= 1 ? "up" : +m.sharpe >= 0.5 ? undefined : "down"} />
        <MetricCard label="Max Drawdown" value={pct(m.max_drawdown)} tone="down" sub={`Calmar ${n(m.calmar)}`} />
        <MetricCard label="Win Rate" value={pct(m.win_rate)} sub={`Profit Factor ${n(m.profit_factor)}`} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <MetricCard label="PSR" value={n(m.psr)} sub="prob Sharpe > 0" />
        <MetricCard label="Orders / Fills" value={`${m.submitted_order_count ?? m.order_count ?? "—"} / ${m.orders_filled_count ?? m.real_fill_count ?? "—"}`} sub={`Fill rate ${pct(m.fill_rate)}`} />
        <MetricCard label="Total Fees" value={usd(m.total_fees)} sub={`Notional ${usd(m.fill_notional_usd)}`} />
        <MetricCard label="Funding P&L" value={(+m.funding_cashflow >= 0 ? "+" : "") + usd(m.funding_cashflow)} tone={+m.funding_cashflow >= 0 ? "up" : "down"} sub={`${m.funding_settlement_count ?? 0} settlements`} />
      </div>

      {/* Equity curve */}
      {eqValues.length > 1 && (
        <div className="card">
          <div className="card-h">
            <div>
              <div className="card-title">Equity curve</div>
              <div className="card-sub">{eqValues.length.toLocaleString()} samples · initial $5,000</div>
            </div>
            {m.bankrupt && <StatusBadge ok={false}>Bankrupt</StatusBadge>}
          </div>
          <Charts.LineChart
            series={[{ values: eqValues, color: m.bankrupt ? "var(--loss)" : "var(--accent)" }]}
            height={220}
            mode="area"
          />
        </div>
      )}

      {/* Drawdown */}
      {ddValues.length > 1 && (
        <div className="card">
          <div className="card-h">
            <div>
              <div className="card-title">Drawdown</div>
              <div className="card-sub">underwater curve</div>
            </div>
            <span className="chip loss">Max {pct(m.max_drawdown)}</span>
          </div>
          <Charts.LineChart
            series={[{ values: ddValues, color: "var(--loss)" }]}
            height={140}
            mode="area"
          />
        </div>
      )}

      {/* Extended metrics */}
      <div className="card">
        <div className="card-h">
          <div className="card-title">All metrics</div>
          <div className="card-sub">analytics/performance.py</div>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          {Object.entries(m).map(([k, v]) => {
            if (v == null) return null;
            const isFlag = typeof v === "boolean";
            const display = isFlag
              ? <span style={{ color: v ? "var(--loss)" : "var(--profit)" }}>{String(v)}</span>
              : <span className="mono">{typeof v === "number" ? (Math.abs(v) < 1 && v !== 0 ? v.toFixed(4) : v.toFixed(2)) : v}</span>;
            return (
              <div key={k} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>
                <div className="kpi-label" style={{ fontSize: 11 }}>{k}</div>
                <div style={{ marginTop: 2, fontSize: 14 }}>{display}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tabs: Fills / Risk Events */}
      <div className="card">
        <div className="card-h">
          <div className="row" style={{ gap: 4 }}>
            {[["fills", `Fills (${realFills.length})`], ["all_fills", `All fills (${fills.length})`], ["risk", `Risk events (${riskEvents.length})`]].map(([id, label]) => (
              <button
                key={id}
                className={`btn sm ${activeTab === id ? "" : "ghost"}`}
                onClick={() => setActiveTab(id)}
              >{label}</button>
            ))}
          </div>
        </div>

        {(activeTab === "fills" || activeTab === "all_fills") && (
          <FillsTable rows={activeTab === "fills" ? realFills : fills} />
        )}
        {activeTab === "risk" && (
          <RiskEventsTable rows={riskEvents} />
        )}
      </div>
    </div>
  );
}

function FillsTable({ rows }) {
  if (!rows.length) return <div className="field-hint" style={{ padding: 16 }}>No fills in this run.</div>;
  return (
    <div className="tbl-wrap" style={{ maxHeight: 480 }}>
      <table className="tbl">
        <thead>
          <tr>
            <th>Datetime (UTC)</th>
            <th>Symbol</th>
            <th>Side</th>
            <th className="num">Fill px</th>
            <th className="num">Qty</th>
            <th className="num">Notional</th>
            <th className="num">Fee</th>
            <th className="num">Net PnL</th>
            <th>State</th>
            <th>Strategy</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((f, i) => {
            const side = (f.side || "").toLowerCase();
            const state = f.state || "";
            return (
              <tr key={i}>
                <td className="mono" style={{ fontSize: 11 }}>{fmtDt(f.datetime)}</td>
                <td className="mono">{f.inst_id || "—"}</td>
                <td>
                  <span className="chip" style={{
                    color: side === "buy" ? "var(--profit)" : "var(--loss)",
                    background: side === "buy" ? "var(--profit-soft)" : "var(--loss-soft)",
                    borderColor: "transparent",
                    fontSize: 10,
                  }}>{side.toUpperCase()}</span>
                </td>
                <td className="num">{n(f.fill_px, 4)}</td>
                <td className="num">{n(f.fill_sz, 4)}</td>
                <td className="num">{usd(f.notional_usd)}</td>
                <td className="num" style={{ color: "var(--text-muted)" }}>{usd(f.fee, 4)}</td>
                <td className="num" style={{ color: "var(--text-muted)" }}>—</td>
                <td>
                  <span className={`chip ${state === "filled" ? "profit" : state === "partially_filled" ? "warn" : ""}`} style={{ fontSize: 10 }}>
                    {state}
                  </span>
                </td>
                <td className="mono" style={{ fontSize: 11, color: "var(--text-subtle)" }}>{f.strategy || "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length > 200 && <div className="field-hint" style={{ padding: "8px 0" }}>showing 200 of {rows.length}</div>}
    </div>
  );
}

function RiskEventsTable({ rows }) {
  if (!rows.length) return <div className="field-hint" style={{ padding: 16 }}>No risk events recorded.</div>;
  return (
    <div className="tbl-wrap" style={{ maxHeight: 400 }}>
      <table className="tbl">
        <thead>
          <tr>
            <th>Datetime (UTC)</th>
            <th>Symbol</th>
            <th>Side</th>
            <th className="num">Notional</th>
            <th>Reason</th>
            <th className="num">Equity</th>
            <th>Strategy</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((r, i) => (
            <tr key={i}>
              <td className="mono" style={{ fontSize: 11 }}>{fmtDt(r.datetime)}</td>
              <td className="mono">{r.inst_id || "—"}</td>
              <td className="mono">{r.side || "—"}</td>
              <td className="num">{usd(r.notional_usd)}</td>
              <td>
                <span className="chip loss" style={{ fontSize: 10 }}>{r.reason || "—"}</span>
              </td>
              <td className="num">{usd(r.current_equity)}</td>
              <td className="mono" style={{ fontSize: 11, color: "var(--text-subtle)" }}>{r.strategy || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Run List View
// ---------------------------------------------------------------------------
function RunListView({ onSelect, onDelete }) {
  const [runs, setRuns] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    window.API.fetchRuns()
      .then(r => setRuns(r || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function deleteRun(e, runId) {
    e.stopPropagation();
    if (!confirm(`Delete run ${runId}?`)) return;
    window.API.deleteRun(runId)
      .then(() => {
        setRuns((rs) => (rs || []).filter((r) => r.run_id !== runId));
        onDelete?.(runId);
      })
      .catch((err) => alert(`Could not delete run: ${err.message}`));
  }

  if (loading) return <div className="field-hint" style={{ padding: 32 }}>Loading backtest runs…</div>;
  if (error) return (
    <div className="card">
      <div style={{ color: "var(--loss)", marginBottom: 8 }}>Could not load runs: {error}</div>
      <div className="field-hint">Make sure the FastAPI server is running and <code>results/</code> contains at least one run.</div>
    </div>
  );
  if (!runs.length) return (
    <div className="card">
      <div className="card-title" style={{ marginBottom: 8 }}>No backtest runs found</div>
      <div className="field-hint">Run a backtest with <code>--save-artifacts</code> to populate this view.</div>
      <pre style={{ marginTop: 12, fontSize: 12, color: "var(--text-muted)", background: "var(--surface-2)", padding: 12, borderRadius: 6 }}>{`python scripts/run_replay_backtest.py \\
  --strategy pairs_trading \\
  --start 2024-01-01 --end 2024-01-08 \\
  --bar 1m --save-artifacts`}</pre>
    </div>
  );

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <MetricCard label="Total runs" value={runs.length} sub="saved in results/" />
        <MetricCard
          label="Best Sharpe"
          value={n(Math.max(...runs.map(r => r.sharpe ?? -Infinity)))}
          tone="up"
        />
        <MetricCard
          label="Best Return"
          value={pct(Math.max(...runs.map(r => r.total_return ?? -Infinity)))}
          tone="up"
        />
        <MetricCard
          label="Latest run"
          value={runs[0]?.created_at ? new Date(runs[0].created_at).toLocaleDateString() : "—"}
        />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Backtest Runs</div>
            <div className="card-sub">click a row to view full results</div>
          </div>
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Strategy</th>
                <th>Symbols</th>
                <th>Bar</th>
                <th>Period</th>
                <th className="num">Return</th>
                <th className="num">Sharpe</th>
                <th className="num">Max DD</th>
                <th className="num">Orders</th>
                <th className="num">Fills</th>
                <th>Created</th>
                <th className="num">Delete</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const bankrupt = r.total_return != null && Math.abs(+r.max_drawdown) > 1;
                return (
                  <tr
                    key={r.run_id}
                    style={{ cursor: "pointer" }}
                    onClick={() => onSelect(r.run_id)}
                  >
                    <td className="mono" style={{ fontSize: 11, color: "var(--text-subtle)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.run_id}
                    </td>
                    <td className="mono" style={{ fontSize: 12 }}>
                      {(r.strategies || [r.strategy]).filter(Boolean).join(", ")}
                    </td>
                    <td className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {(r.symbols || [r.symbol]).filter(Boolean).join(", ")}
                    </td>
                    <td className="mono">{r.bar || "—"}</td>
                    <td className="mono" style={{ fontSize: 11 }}>
                      {r.start ? r.start.slice(0, 10) : "—"} → {r.end ? r.end.slice(0, 10) : "—"}
                    </td>
                    <td className="num" style={{ color: r.total_return >= 0 ? "var(--profit)" : "var(--loss)" }}>
                      {pct(r.total_return)}
                    </td>
                    <td className="num">{n(r.sharpe)}</td>
                    <td className="num" style={{ color: "var(--loss)" }}>{pct(r.max_drawdown)}</td>
                    <td className="num">{r.order_count ?? "—"}</td>
                    <td className="num">{r.real_fill_count ?? "—"}</td>
                    <td className="mono" style={{ fontSize: 11 }}>
                      {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                      {bankrupt && <span className="chip loss" style={{ marginLeft: 6, fontSize: 9 }}>⚠ bankrupt</span>}
                    </td>
                    <td className="num">
                      <button className="btn ghost sm" title="Delete run" onClick={(e) => deleteRun(e, r.run_id)} aria-label="Delete run">
                        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M2.5 4h11M6 4V2.5h4V4M5 6v6M8 6v6M11 6v6M4 4l.5 10h7L12 4" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
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
    ? <RunDetailView runId={selectedRunId} onBack={() => setSelectedRunId(null)} />
    : <RunListView onSelect={setSelectedRunId} onDelete={handleDelete} />;
}

window.BacktestView = BacktestView;

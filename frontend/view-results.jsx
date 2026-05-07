/* global React, Charts, KPI, fmt */
const { useState: useStateResults, useEffect: useEffectResults, useMemo: useMemoResults } = React;

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

function OverviewView({ tweaks, selectedRunId }) {
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

  if (!selectedRunId || !metrics) return (
    <div style={{ padding: 48, textAlign: "center", color: "var(--text-subtle)" }}>
      <div style={{ fontSize: 18, marginBottom: 12 }}>No run selected</div>
      <div className="field-hint">Go to <strong>Backtest Runs</strong> and click a run to inspect it here.</div>
    </div>
  );

  if (loading) return <div className="field-hint" style={{ padding: 32 }}>Loading selected run...</div>;

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="Total Return" value={fmt.pct(metrics.total_return)} sub={`CAGR ${fmt.pct(metrics.cagr)}`} tone={metrics.total_return >= 0 ? "up" : "down"} spark={equityValues.length ? equityValues : null} sparkMode={equityMode} />
        <KPI label="Sharpe (ann.)" value={fmt.num(metrics.sharpe, 2)} sub={`Sortino ${fmt.num(metrics.sortino, 2)}`} tone={metrics.sharpe >= 0 ? "up" : "down"} />
        <KPI label="Max Drawdown" value={fmt.pct(metrics.max_drawdown)} sub={`Calmar ${fmt.num(metrics.calmar, 2)}`} tone="down" spark={ddValues.length ? ddValues : null} sparkMode="area" />
        <KPI label="Win rate" value={fmt.pct(metrics.win_rate)} sub={`PF ${fmt.num(metrics.profit_factor, 2)}`} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="DSR" value={fmt.num(metrics.dsr, 2)} sub="0.95 promotion gate" tone={metrics.dsr >= 0.95 ? "up" : "down"} hint="CPCV" />
        <KPI label="PSR" value={fmt.num(metrics.psr, 2)} sub="prob Sharpe > 0" />
        <KPI label="Orders" value={(metrics.order_count ?? metrics.submitted_order_count ?? 0).toLocaleString()} sub={`${metrics.real_fill_count ?? metrics.orders_filled_count ?? 0} real fills`} />
        <KPI label="Fill rate" value={fmt.pct(metrics.fill_rate)} sub={metrics.bankrupt ? "bankrupt run" : "execution model"} tone={metrics.bankrupt ? "down" : undefined} />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Equity curve</div>
            <div className="card-sub mono">{selectedRunId}</div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <span className="chip">N = {equity.length.toLocaleString()}</span>
          </div>
        </div>
        <Charts.LineChart series={[{ values: equityValues.length ? equityValues : [0], color: "var(--accent)" }]} height={260} mode={equityMode} />
      </div>

      <div className="row" style={{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
        <div className="card" style={{ flex: 2 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Drawdown</div>
              <div className="card-sub">underwater curve</div>
            </div>
            <span className="chip loss">Max {fmt.pct(metrics.max_drawdown)}</span>
          </div>
          <Charts.LineChart series={[{ values: ddValues.length ? ddValues : [0], color: "var(--loss)" }]} height={180} mode="area" />
        </div>
        <div className="card" style={{ flex: 1 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Monthly returns</div>
              <div className="card-sub">compounded from returns.csv</div>
            </div>
          </div>
          <table className="tbl" style={{ fontSize: 12 }}>
            <thead><tr><th>Month</th><th className="num">Return</th><th className="num"></th></tr></thead>
            <tbody>
              {monthlyRet.map((m) => (
                <tr key={m.month}>
                  <td className="mono">{m.month}</td>
                  <td className="num" style={{ color: m.ret >= 0 ? "var(--profit)" : "var(--loss)" }}>{fmt.pct(m.ret)}</td>
                  <td className="num" style={{ width: 80 }}>
                    <div className="bar" style={{ background: "var(--surface-2)" }}>
                      <i style={{ width: `${Math.min(100, Math.abs(m.ret) * 1500)}%`, background: m.ret >= 0 ? "var(--profit)" : "var(--loss)" }} />
                    </div>
                  </td>
                </tr>
              ))}
              {!monthlyRet.length && <tr><td colSpan={3} className="field-hint" style={{ textAlign: "center", padding: 16 }}>No returns.csv data.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-h">
          <div className="card-title">Extended metrics</div>
          <div className="card-sub">full metrics.json object</div>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(6, 1fr)", gap: 16 }}>
          {Object.entries(metrics).map(([k, v]) => (
            <div key={k}>
              <div className="kpi-label">{metricLabel(k)}</div>
              <div className="mono" style={{ fontSize: 18, marginTop: 2 }}>{displayMetric(k, v)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
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

  if (!selectedRunId) return <div style={{ padding: 32, color: "var(--text-subtle)" }}>Select a backtest run first.</div>;
  if (!loaded) return <div className="field-hint" style={{ padding: 32 }}>Loading walk-forward data...</div>;
  if (!windows.length) return <div style={{ padding: 32, color: "var(--text-subtle)" }}>Walk-Forward validation was not run for this backtest.</div>;

  const oos = windows.map((w) => +w.oos_sharpe || 0);
  const isS = windows.map((w) => +w.is_sharpe || 0);
  const meanOos = oos.reduce((a, b) => a + b, 0) / Math.max(oos.length, 1);
  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="Windows" value={windows.length} sub="non-overlapping IS/OOS" />
        <KPI label="Mean OOS Sharpe" value={fmt.num(meanOos, 2)} tone={meanOos >= 0 ? "up" : "down"} />
        <KPI label="OOS positive %" value={fmt.pct(oos.filter((v) => v > 0).length / Math.max(oos.length, 1))} />
        <KPI label="Selected run" value={selectedRunId.slice(-8)} sub="result.json walk_forward" />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">IS vs OOS Sharpe</div>
            <div className="card-sub">per validation window</div>
          </div>
        </div>
        <Charts.LineChart series={[
          { values: isS, color: "var(--text-subtle)" },
          { values: oos, color: "var(--accent)" },
        ]} height={200} />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Window timeline</div>
            <div className="card-sub">one row per validation window</div>
          </div>
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>#</th><th>IS start</th><th>IS end</th><th>OOS start</th><th>OOS end</th>
                <th className="num">IS Sharpe</th><th className="num">OOS Sharpe</th>
                <th className="num">OOS Return</th><th className="num">OOS MDD</th><th className="num">Decay</th>
              </tr>
            </thead>
            <tbody>
              {windows.map((w, i) => {
                const idx = w.i ?? i;
                const decay = (+w.oos_sharpe || 0) / (+w.is_sharpe || 1e-9);
                return (
                  <tr key={idx}>
                    <td className="mono">{String(idx).padStart(2, "0")}</td>
                    <td className="mono" style={{ color: "var(--text-muted)" }}>{fmt.date(w.is_start)}</td>
                    <td className="mono" style={{ color: "var(--text-muted)" }}>{fmt.date(w.is_end)}</td>
                    <td className="mono">{fmt.date(w.oos_start)}</td>
                    <td className="mono">{fmt.date(w.oos_end)}</td>
                    <td className="num">{fmt.num(w.is_sharpe, 2)}</td>
                    <td className="num" style={{ color: w.oos_sharpe >= 0 ? "var(--profit)" : "var(--loss)" }}>{fmt.num(w.oos_sharpe, 2)}</td>
                    <td className="num" style={{ color: w.oos_return >= 0 ? "var(--profit)" : "var(--loss)" }}>{fmt.pct(w.oos_return)}</td>
                    <td className="num" style={{ color: "var(--loss)" }}>{fmt.pct(w.oos_mdd)}</td>
                    <td className="num" style={{ color: "var(--text-muted)" }}>{fmt.num(decay, 2)}x</td>
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

  if (!selectedRunId) return <div style={{ padding: 32, color: "var(--text-subtle)" }}>Select a backtest run first.</div>;
  if (!loaded) return <div className="field-hint" style={{ padding: 32 }}>Loading CPCV data...</div>;
  if (!cpcv) return <div style={{ padding: 32, color: "var(--text-subtle)" }}>CPCV validation was not run for this backtest.</div>;

  const combos = cpcv.combos || [];
  if (!combos.length) return <div style={{ padding: 32, color: "var(--text-subtle)" }}>CPCV validation was not run for this backtest.</div>;

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

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="DSR (Deflated Sharpe)" value={fmt.num(cpcv.dsr, 2)} sub={cpcv.dsr >= 0.95 ? "promote-eligible" : "below 0.95 gate"} tone={cpcv.dsr >= 0.95 ? "up" : "down"} />
        <KPI label="PSR" value={fmt.num(cpcv.psr, 2)} sub="prob true SR > 0" tone="up" />
        <KPI label="Mean OOS Sharpe" value={fmt.num(cpcv.mean_oos_sharpe, 2)} sub={`std ${fmt.num(cpcv.std_oos_sharpe, 2)}`} />
        <KPI label="Combinations" value={`${combos.length} / ${(cpcv.paths || []).length} paths`} sub="result.json cpcv" />
      </div>

      <div className="row" style={{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
        <div className="card" style={{ flex: 1 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Combination heatmap</div>
              <div className="card-sub">test groups to OOS Sharpe</div>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: `auto repeat(${groupCount}, 1fr)`, gap: 4, fontSize: 11 }}>
            <div></div>
            {Array.from({ length: groupCount }, (_, j) => <div key={j} className="mono" style={{ textAlign: "center", color: "var(--text-subtle)" }}>g{j}</div>)}
            {grid.map((row, i) => (
              <React.Fragment key={i}>
                <div className="mono" style={{ color: "var(--text-subtle)" }}>g{i}</div>
                {row.map((v, j) => (
                  <div key={j} className="heat-cell" style={{ height: 44, background: heat(v), color: v != null && Math.abs(v) > (maxS - minS) * 0.5 ? "white" : "var(--text)" }}>
                    {v != null ? (+v).toFixed(2) : ""}
                  </div>
                ))}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Sharpe distribution</div>
              <div className="card-sub">over CPCV combinations</div>
            </div>
          </div>
          <Charts.HistogramChart values={allS} bins={12} height={200} color="var(--accent)" />
          <div className="field-hint" style={{ marginTop: 8 }}>mean = {fmt.num(cpcv.mean_oos_sharpe, 2)} · std = {fmt.num(cpcv.std_oos_sharpe, 2)}</div>
        </div>
      </div>
    </div>
  );
}

window.OverviewView = OverviewView;
window.WalkForwardView = WalkForwardView;
window.CPCVView = CPCVView;

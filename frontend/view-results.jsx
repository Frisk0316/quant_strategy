/* global React, MOCK, Charts, KPI, fmt */
const { useState, useMemo: useMemo2 } = React;

function OverviewView({ tweaks }) {
  const s = MOCK.mainStats;
  const equityMode = tweaks.equityMode || "area";
  const equityValues = MOCK.main.eq.map((v) => v - 1); // PnL %
  const ddValues = MOCK.main.dd;

  const monthlyRet = useMemo2(() => {
    const buckets = [];
    const ret = MOCK.main.ret;
    const ts = MOCK.ts;
    const map = new Map();
    ret.forEach((r, i) => {
      const d = new Date(ts[i]);
      const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
      map.set(key, (1 + (map.get(key) ?? 0)) * (1 + r) - 1);
    });
    for (const [k, v] of map.entries()) buckets.push({ month: k, ret: v });
    return buckets;
  }, []);

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      {/* KPI strip */}
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="Total Return" value={fmt.pct(s.total_return)} sub={`CAGR ${fmt.pct(s.cagr)}`} tone={s.total_return >= 0 ? "up" : "down"} spark={MOCK.main.eq.map((v) => v - 1)} sparkMode={equityMode} />
        <KPI label="Sharpe (ann.)" value={fmt.num(s.sharpe, 2)} sub={`Sortino ${fmt.num(s.sortino, 2)}`} tone="up" />
        <KPI label="Max Drawdown" value={fmt.pct(s.max_drawdown)} sub={`Calmar ${fmt.num(s.calmar, 2)}`} tone="down" spark={ddValues} sparkMode="area" />
        <KPI label="Win rate" value={fmt.pct(s.win_rate)} sub={`PF ${fmt.num(s.profit_factor, 2)}`} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="DSR" value={fmt.num(MOCK.cpcv.dsr, 2)} sub="≥ 0.95 to promote" tone="up" hint="CPCV" />
        <KPI label="PSR" value={fmt.num(MOCK.cpcv.psr, 2)} sub="prob Sharpe > 0" />
        <KPI label="Trades" value={MOCK.trades.length.toLocaleString()} sub="post_only · maker-only" />
        <KPI label="Avg Fee" value="$0.04" sub="VIP0 maker rebate" />
      </div>

      {/* Equity + DD */}
      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Equity curve</div>
            <div className="card-sub">funding_carry · BTC-USDT-SWAP · 1H · 90 days</div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <span className="chip accent">Walk-Forward verified</span>
            <span className="chip">N = {MOCK.main.eq.length.toLocaleString()}</span>
          </div>
        </div>
        <Charts.LineChart series={[{ values: equityValues, color: "var(--accent)" }]} height={260} mode={equityMode} />
      </div>

      <div className="row" style={{ gap: "var(--gap-lg)" }}>
        <div className="card" style={{ flex: 2 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Drawdown</div>
              <div className="card-sub">underwater curve</div>
            </div>
            <span className="chip loss">Max {fmt.pct(s.max_drawdown)}</span>
          </div>
          <Charts.LineChart series={[{ values: ddValues, color: "var(--loss)" }]} height={180} mode="area" />
        </div>
        <div className="card" style={{ flex: 1 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Monthly returns</div>
              <div className="card-sub">UTC</div>
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
            </tbody>
          </table>
        </div>
      </div>

      {/* Extended metrics */}
      <div className="card">
        <div className="card-h">
          <div className="card-title">Extended metrics</div>
          <div className="card-sub">analytics/performance.py</div>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(6, 1fr)", gap: 16 }}>
          {[
            ["Sharpe", fmt.num(s.sharpe, 2)],
            ["Sortino", fmt.num(s.sortino, 2)],
            ["Calmar", fmt.num(s.calmar, 2)],
            ["Profit Factor", fmt.num(s.profit_factor, 2)],
            ["Win rate", fmt.pct(s.win_rate)],
            ["Total Return", fmt.pct(s.total_return)],
            ["CAGR", fmt.pct(s.cagr)],
            ["Max DD", fmt.pct(s.max_drawdown)],
            ["DSR", fmt.num(MOCK.cpcv.dsr, 2)],
            ["PSR", fmt.num(MOCK.cpcv.psr, 2)],
            ["Periods", s.n_periods.toLocaleString()],
            ["Annualization", "8,760"],
          ].map(([k, v]) => (
            <div key={k}>
              <div className="kpi-label">{k}</div>
              <div className="mono" style={{ fontSize: 18, marginTop: 2 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function WalkForwardView() {
  const wf = MOCK.walkForward;
  const oos = wf.map((w) => w.oos_sharpe);
  const isS = wf.map((w) => w.is_sharpe);
  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="Windows" value={wf.length} sub="non-overlapping IS/OOS" />
        <KPI label="Mean OOS Sharpe" value={fmt.num(oos.reduce((a, b) => a + b, 0) / oos.length, 2)} tone="up" />
        <KPI label="OOS positive %" value={fmt.pct(oos.filter((v) => v > 0).length / oos.length)} />
        <KPI label="IS / OOS span" value="14d / 7d" sub="walk_forward.py" />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">IS vs OOS Sharpe</div>
            <div className="card-sub">per window · expecting OOS ≈ 0.7× IS</div>
          </div>
          <div className="row" style={{ gap: 12 }}>
            <span className="chip"><i style={{ width: 8, height: 8, borderRadius: 999, background: "var(--text-subtle)", display: "inline-block", marginRight: 6 }}></i> IS</span>
            <span className="chip accent"><i style={{ width: 8, height: 8, borderRadius: 999, background: "var(--accent)", display: "inline-block", marginRight: 6 }}></i> OOS</span>
          </div>
        </div>
        <Charts.LineChart
          series={[
            { values: isS, color: "var(--text-subtle)" },
            { values: oos, color: "var(--accent)" },
          ]}
          height={200}
        />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Window timeline</div>
            <div className="card-sub">每 row = 1 window</div>
          </div>
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>#</th>
                <th>IS start</th>
                <th>IS end</th>
                <th>OOS start</th>
                <th>OOS end</th>
                <th className="num">IS Sharpe</th>
                <th className="num">OOS Sharpe</th>
                <th className="num">OOS Return</th>
                <th className="num">OOS MDD</th>
                <th className="num">Decay</th>
              </tr>
            </thead>
            <tbody>
              {wf.map((w) => {
                const decay = w.oos_sharpe / (w.is_sharpe || 1e-9);
                return (
                  <tr key={w.i}>
                    <td className="mono">{w.i.toString().padStart(2, "0")}</td>
                    <td className="mono" style={{ color: "var(--text-muted)" }}>{fmt.date(w.is_start)}</td>
                    <td className="mono" style={{ color: "var(--text-muted)" }}>{fmt.date(w.is_end)}</td>
                    <td className="mono">{fmt.date(w.oos_start)}</td>
                    <td className="mono">{fmt.date(w.oos_end)}</td>
                    <td className="num">{fmt.num(w.is_sharpe, 2)}</td>
                    <td className="num" style={{ color: w.oos_sharpe >= 0 ? "var(--profit)" : "var(--loss)" }}>{fmt.num(w.oos_sharpe, 2)}</td>
                    <td className="num" style={{ color: w.oos_return >= 0 ? "var(--profit)" : "var(--loss)" }}>{fmt.pct(w.oos_return)}</td>
                    <td className="num" style={{ color: "var(--loss)" }}>{fmt.pct(w.oos_mdd)}</td>
                    <td className="num" style={{ color: "var(--text-muted)" }}>{fmt.num(decay, 2)}×</td>
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

function CPCVView() {
  const c = MOCK.cpcv;
  // Heatmap: 6x6 cells where (a,b) = sharpe of combo with test_groups (a,b)
  const grid = Array.from({ length: 6 }, () => Array(6).fill(null));
  c.combos.forEach((co) => {
    const [a, b] = co.test_groups;
    grid[a][b] = co.sharpe;
    grid[b][a] = co.sharpe;
  });
  const allS = c.combos.map((co) => co.sharpe);
  const minS = Math.min(...allS), maxS = Math.max(...allS);
  function heat(v) {
    if (v == null) return "var(--surface-2)";
    const t = (v - minS) / (maxS - minS || 1);
    if (v >= 0) {
      const l = 0.95 - t * 0.40;
      return `oklch(${l} ${0.05 + t * 0.13} 155)`;
    } else {
      const l = 0.95 - (1 - t) * 0.40;
      return `oklch(${l} ${0.05 + (1 - t) * 0.13} 25)`;
    }
  }

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="DSR (Deflated Sharpe)" value={fmt.num(c.dsr, 2)} sub={c.dsr >= 0.95 ? "✓ promote-eligible" : "below 0.95 gate"} tone={c.dsr >= 0.95 ? "up" : "down"} />
        <KPI label="PSR" value={fmt.num(c.psr, 2)} sub="prob true SR > 0" tone="up" />
        <KPI label="Mean OOS Sharpe" value={fmt.num(c.mean_oos_sharpe, 2)} sub={`σ ${fmt.num(c.std_oos_sharpe, 2)}`} />
        <KPI label="Combinations" value={`${c.combos.length} · ${c.paths.length} paths`} sub="N=6, k=2, embargo=2%" />
      </div>

      <div className="row" style={{ gap: "var(--gap-lg)" }}>
        <div className="card" style={{ flex: 1 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Combination heatmap</div>
              <div className="card-sub">test groups (i, j) → OOS Sharpe</div>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "auto repeat(6, 1fr)", gap: 4, fontSize: 11 }}>
            <div></div>
            {[0, 1, 2, 3, 4, 5].map((j) => (
              <div key={j} className="mono" style={{ textAlign: "center", color: "var(--text-subtle)" }}>g{j}</div>
            ))}
            {grid.map((row, i) => (
              <React.Fragment key={i}>
                <div className="mono" style={{ color: "var(--text-subtle)" }}>g{i}</div>
                {row.map((v, j) => (
                  <div
                    key={j}
                    className="heat-cell"
                    style={{
                      height: 44,
                      background: heat(v),
                      color: v != null ? (Math.abs(v) > (maxS - minS) * 0.5 ? "white" : "var(--text)") : "var(--text-subtle)",
                    }}
                    title={v != null ? `g${i}+g${j}: Sharpe ${v.toFixed(2)}` : "—"}
                  >
                    {v != null ? v.toFixed(2) : ""}
                  </div>
                ))}
              </React.Fragment>
            ))}
          </div>
          <div className="row" style={{ gap: 12, marginTop: 12, alignItems: "center", fontSize: 11 }}>
            <span className="mono" style={{ color: "var(--text-subtle)" }}>{minS.toFixed(2)}</span>
            <div style={{ flex: 1, height: 6, background: "linear-gradient(to right, var(--loss-soft), var(--surface-2), var(--profit-soft))", borderRadius: 3 }}></div>
            <span className="mono" style={{ color: "var(--text-subtle)" }}>{maxS.toFixed(2)}</span>
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Sharpe distribution</div>
              <div className="card-sub">over 15 combinations</div>
            </div>
          </div>
          <Charts.HistogramChart values={allS} bins={12} height={200} color="var(--accent)" />
          <div className="field-hint" style={{ marginTop: 8 }}>μ = {c.mean_oos_sharpe.toFixed(2)} · σ = {c.std_oos_sharpe.toFixed(2)}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">5 OOS paths</div>
            <div className="card-sub">each path covers all 6 groups exactly once</div>
          </div>
        </div>
        <Charts.LineChart
          series={c.paths.map((p, i) => ({
            values: p.eq.map((v) => v - 1),
            color: `oklch(${0.55 + i * 0.05} 0.16 ${235 + i * 18})`,
          }))}
          height={240}
        />
        <div className="row wrap" style={{ gap: 16, marginTop: 14 }}>
          {c.paths.map((p, i) => (
            <div key={i} className="row" style={{ gap: 8, alignItems: "center" }}>
              <div style={{ width: 18, height: 3, background: `oklch(${0.55 + i * 0.05} 0.16 ${235 + i * 18})`, borderRadius: 2 }}></div>
              <div className="mono" style={{ fontSize: 12 }}>path {i} · SR {p.sharpe.toFixed(2)} · ret {fmt.pct(p.ret)} · mdd {fmt.pct(p.mdd)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

window.OverviewView = OverviewView;
window.WalkForwardView = WalkForwardView;
window.CPCVView = CPCVView;

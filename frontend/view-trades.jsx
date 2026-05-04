/* global React, MOCK, Charts, KPI, fmt */
const { useState: useS3, useMemo: useM3 } = React;

function TradesView() {
  const [side, setSide] = useS3("ALL");
  const [status, setStatus] = useS3("ALL");
  const [strat, setStrat] = useS3("ALL");
  const [search, setSearch] = useS3("");

  const filtered = useM3(() => {
    return MOCK.trades.filter((t) => {
      if (side !== "ALL" && t.side !== side) return false;
      if (status !== "ALL" && t.status !== status) return false;
      if (strat !== "ALL" && t.strategy !== strat) return false;
      if (search && !t.symbol.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [side, status, strat, search]);

  const totalPnl = filtered.reduce((a, t) => a + (t.status === "FILLED" ? t.pnl : 0), 0);
  const totalFee = filtered.reduce((a, t) => a + t.fee, 0);

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="Filtered trades" value={filtered.length.toLocaleString()} sub={`of ${MOCK.trades.length}`} />
        <KPI label="Net PnL" value={fmt.usd(totalPnl)} tone={totalPnl >= 0 ? "up" : "down"} />
        <KPI label="Fees paid" value={fmt.usd(totalFee)} sub="post_only · maker rebate" />
        <KPI label="Fill rate" value={fmt.pct(filtered.filter((t) => t.status === "FILLED").length / Math.max(filtered.length, 1))} sub="51026 dropped" />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Trades / Orders</div>
            <div className="card-sub">post_only · maker-only execution</div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn ghost sm">Export CSV</button>
            <button className="btn ghost sm">Replay</button>
          </div>
        </div>

        <div className="row wrap" style={{ gap: 12, marginBottom: 12 }}>
          <input className="input" placeholder="Search symbol…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 200 }} />
          <select className="select" value={side} onChange={(e) => setSide(e.target.value)} style={{ width: 120 }}>
            <option value="ALL">Side · ALL</option>
            <option>BUY</option>
            <option>SELL</option>
          </select>
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 140 }}>
            <option value="ALL">Status · ALL</option>
            <option>FILLED</option>
            <option>CANCELLED</option>
            <option>REJECTED</option>
          </select>
          <select className="select" value={strat} onChange={(e) => setStrat(e.target.value)} style={{ width: 200 }}>
            <option value="ALL">Strategy · ALL</option>
            {MOCK.STRATEGIES.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>

        <div className="tbl-wrap" style={{ maxHeight: 520 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>ID</th>
                <th>Timestamp (UTC)</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Type</th>
                <th className="num">Price</th>
                <th className="num">Qty</th>
                <th className="num">Notional</th>
                <th className="num">Fee</th>
                <th className="num">PnL</th>
                <th>Status</th>
                <th>Strategy</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 80).map((t) => (
                <tr key={t.id}>
                  <td className="mono" style={{ color: "var(--text-muted)" }}>{t.id}</td>
                  <td className="mono">{fmt.ts(t.ts)}</td>
                  <td className="mono">{t.symbol}</td>
                  <td>
                    <span className="chip" style={{ color: t.side === "BUY" ? "var(--profit)" : "var(--loss)", background: t.side === "BUY" ? "var(--profit-soft)" : "var(--loss-soft)", borderColor: "transparent" }}>{t.side}</span>
                  </td>
                  <td className="mono" style={{ color: "var(--text-muted)" }}>{t.type}</td>
                  <td className="num">{fmt.num(t.price, 2)}</td>
                  <td className="num">{fmt.num(t.qty, 4)}</td>
                  <td className="num">{fmt.usd(t.notional)}</td>
                  <td className="num" style={{ color: "var(--text-muted)" }}>{fmt.usd(t.fee, 3)}</td>
                  <td className="num" style={{ color: t.pnl >= 0 ? "var(--profit)" : "var(--loss)" }}>{t.status === "FILLED" ? fmt.usd(t.pnl) : "—"}</td>
                  <td>
                    <span className={`chip ${t.status === "FILLED" ? "profit" : t.status === "REJECTED" ? "loss" : "warn"}`} style={{ fontSize: 10 }}>{t.status}</span>
                  </td>
                  <td className="mono" style={{ color: "var(--text-subtle)", fontSize: 11 }}>{t.strategy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="field-hint" style={{ marginTop: 8 }}>showing first 80 of {filtered.length}</div>
      </div>
    </div>
  );
}

function CompareView() {
  const runs = MOCK.compareRuns;
  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Equity curves · 3 runs</div>
            <div className="card-sub">AS market maker · gamma sweep</div>
          </div>
          <button className="btn sm">+ Add run</button>
        </div>
        <Charts.LineChart
          series={runs.map((r) => ({ values: r.eq.map((v) => v - 1), color: r.color }))}
          height={280}
        />
        <div className="row wrap" style={{ gap: 16, marginTop: 14 }}>
          {runs.map((r) => (
            <div key={r.id} className="row" style={{ gap: 8, alignItems: "center" }}>
              <div style={{ width: 18, height: 3, background: r.color, borderRadius: 2 }}></div>
              <div className="mono" style={{ fontSize: 12 }}>{r.name}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Side-by-side metrics</div>
            <div className="card-sub">每欄 = 1 run</div>
          </div>
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Metric</th>
                {runs.map((r) => <th key={r.id} className="num">{r.id}</th>)}
                <th>Best</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Total Return", "total_return", "pct"],
                ["CAGR", "cagr", "pct"],
                ["Sharpe", "sharpe", "num"],
                ["Sortino", "sortino", "num"],
                ["Calmar", "calmar", "num"],
                ["Max Drawdown", "max_drawdown", "pct"],
                ["Profit Factor", "profit_factor", "num"],
                ["Win rate", "win_rate", "pct"],
              ].map(([label, key, kind]) => {
                const vals = runs.map((r) => r.stats[key]);
                const best = key === "max_drawdown" ? Math.max(...vals) : Math.max(...vals);
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    {runs.map((r, i) => {
                      const v = r.stats[key];
                      const isBest = v === best;
                      return (
                        <td key={i} className="num" style={{ fontWeight: isBest ? 600 : 400, color: isBest ? "var(--accent)" : undefined }}>
                          {kind === "pct" ? fmt.pct(v) : fmt.num(v, 2)}
                        </td>
                      );
                    })}
                    <td className="mono" style={{ color: "var(--text-subtle)", fontSize: 11 }}>
                      {runs[vals.indexOf(best)].id}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="row" style={{ gap: "var(--gap-lg)" }}>
        {runs.map((r) => (
          <div className="card" key={r.id} style={{ flex: 1 }}>
            <div className="card-h">
              <div>
                <div className="card-title" style={{ color: r.color }}>{r.id}</div>
                <div className="card-sub">{r.name}</div>
              </div>
            </div>
            <Charts.Sparkline values={r.dd} color="var(--loss)" mode="area" height={48} />
            <div className="field-hint" style={{ marginTop: 6 }}>Drawdown · max {fmt.pct(r.stats.max_drawdown)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RiskView() {
  const r = MOCK.risk;

  function Gauge({ label, value, max, format, danger, warn }) {
    const pct = Math.min(100, (Math.abs(value) / max) * 100);
    const color = pct >= danger ? "var(--loss)" : pct >= warn ? "var(--warn)" : "var(--profit)";
    return (
      <div className="card">
        <div className="kpi-label">{label}</div>
        <div className="row" style={{ alignItems: "baseline", gap: 8, marginTop: 4 }}>
          <div className="mono" style={{ fontSize: 22 }}>{format(value)}</div>
          <div className="mono" style={{ color: "var(--text-subtle)", fontSize: 12 }}>/ {format(max)}</div>
        </div>
        <div className="bar" style={{ height: 6, marginTop: 10 }}>
          <i style={{ width: `${pct}%`, background: color }} />
        </div>
        <div className="field-hint" style={{ marginTop: 6 }}>{pct.toFixed(1)}% of limit</div>
      </div>
    );
  }

  const limits = [
    { name: "Daily loss halt", val: 0.018, max: 0.05, fmt: "pct", warn: 60, danger: 90, action: "Halt all trading" },
    { name: "Soft drawdown", val: r.soft_dd_used, max: 0.10, fmt: "pct", warn: 60, danger: 90, action: "Size × 0.5" },
    { name: "Hard drawdown", val: r.soft_dd_used, max: 0.15, fmt: "pct", warn: 60, danger: 90, action: "Close all · 48h cooldown" },
    { name: "Leverage", val: r.leverage, max: r.max_leverage, fmt: "num", warn: 60, danger: 85, action: "Reject new orders" },
    { name: "Position % equity", val: r.pos_pct_equity, max: r.max_pos_pct_equity, fmt: "pct", warn: 70, danger: 90, action: "Reject add-to" },
    { name: "Order notional", val: r.last_order_notional, max: r.max_order_notional, fmt: "usd", warn: 70, danger: 90, action: "Fat-finger reject" },
  ];

  function fm(kind, v) {
    return kind === "pct" ? fmt.pct(v) : kind === "usd" ? fmt.usd(v, 0) : fmt.num(v, 2) + "×";
  }

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="Equity" value={fmt.usd(r.equity_usd, 0)} sub="initial $5,000" tone="up" />
        <KPI label="Daily PnL" value={fmt.usd(r.daily_pnl_usd)} sub={fmt.pct(r.daily_pnl_pct)} tone={r.daily_pnl_usd >= 0 ? "up" : "down"} />
        <KPI label="Open positions" value="2" sub="BTC + ETH delta-neutral" />
        <KPI label="Mode" value="DEMO" sub="OKX paper trading" />
      </div>

      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">Risk limits</div>
            <div className="card-sub">config/risk.yaml · live</div>
          </div>
          <span className="chip profit">All limits OK</span>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
          {limits.map((l) => (
            <Gauge key={l.name} label={l.name} value={l.val} max={l.max} format={(v) => fm(l.fmt, v)} warn={l.warn} danger={l.danger} />
          ))}
        </div>
      </div>

      <div className="row" style={{ gap: "var(--gap-lg)" }}>
        <div className="card" style={{ flex: 1 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Circuit breakers</div>
          <table className="tbl">
            <thead><tr><th>Breaker</th><th className="num">Current</th><th className="num">Threshold</th><th>Status</th></tr></thead>
            <tbody>
              <tr>
                <td>WS reconnects (60s)</td>
                <td className="num">{r.ws_reconnects}</td>
                <td className="num">3</td>
                <td><span className="chip profit">OK</span></td>
              </tr>
              <tr>
                <td>REST error rate (last 100)</td>
                <td className="num">{fmt.pct(r.rest_error_rate)}</td>
                <td className="num">5%</td>
                <td><span className="chip profit">OK</span></td>
              </tr>
              <tr>
                <td>Stale quote deviation</td>
                <td className="num">0.41%</td>
                <td className="num">2%</td>
                <td><span className="chip profit">OK</span></td>
              </tr>
              <tr>
                <td>Hard stop cooldown</td>
                <td className="num">—</td>
                <td className="num">48h</td>
                <td><span className="chip">inactive</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="card" style={{ flex: 1 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Promotion gate</div>
          <div className="col" style={{ gap: 10 }}>
            {[
              ["Historical backtest", true],
              ["CPCV / Walk-Forward validation", true],
              ["Demo run (≥ 7 days)", true],
              ["Shadow run (≥ 3 days)", false],
              ["DSR ≥ 0.95", MOCK.cpcv.dsr >= 0.95],
              ["Live deployment", false],
            ].map(([name, ok], i) => (
              <div key={i} className="row" style={{ alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 18, height: 18, borderRadius: 999,
                  background: ok ? "var(--profit)" : "var(--surface-2)",
                  border: "1px solid",
                  borderColor: ok ? "var(--profit)" : "var(--border-strong)",
                  display: "grid", placeItems: "center",
                  color: "white", fontSize: 11,
                }}>{ok ? "✓" : ""}</div>
                <div style={{ flex: 1, color: ok ? "var(--text)" : "var(--text-muted)" }}>{name}</div>
                <span className={`chip ${ok ? "profit" : ""}`}>{ok ? "passed" : "pending"}</span>
              </div>
            ))}
          </div>
          <div className="sep"></div>
          <button className="btn primary" disabled style={{ width: "100%", opacity: 0.5 }}>Promote to LIVE · 1 step remaining</button>
        </div>
      </div>
    </div>
  );
}

window.TradesView = TradesView;
window.CompareView = CompareView;
window.RiskView = RiskView;

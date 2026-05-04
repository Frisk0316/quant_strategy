/* global React, MOCK, Charts */
const { useState, useMemo } = React;
const { LineChart, Sparkline, BarChart, HistogramChart } = window.Charts;

const fmtPct = (v, d = 2) => (v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`);
const fmtNum = (v, d = 2) => (v == null || !isFinite(v) ? "—" : v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }));
const fmtUSD = (v, d = 2) => (v == null || !isFinite(v) ? "—" : `$${fmtNum(v, d)}`);
const fmtTs = (ms) => new Date(ms).toISOString().replace("T", " ").slice(0, 16);
const fmtDate = (ms) => new Date(ms).toISOString().slice(0, 10);

window.fmt = { pct: fmtPct, num: fmtNum, usd: fmtUSD, ts: fmtTs, date: fmtDate };

// ───────── KPI Card ─────────
function KPI({ label, value, sub, tone, spark, sparkMode = "area", hint }) {
  const toneClass = tone === "up" ? "up" : tone === "down" ? "down" : "";
  return (
    <div className="kpi">
      <div className="kpi-label">
        {label}
        {hint && <span className="chip" style={{ fontSize: 10, padding: "1px 6px" }}>{hint}</span>}
      </div>
      <div className="kpi-value">{value}</div>
      {sub && <div className={`kpi-delta ${toneClass}`}>{sub}</div>}
      {spark && (
        <div className="kpi-spark">
          <Sparkline values={spark} color={tone === "down" ? "var(--loss)" : tone === "up" ? "var(--profit)" : "var(--accent)"} mode={sparkMode} height={32} />
        </div>
      )}
    </div>
  );
}

// ───────── Run Config view ─────────
function RunConfigView({ tweaks, setTweak }) {
  const [strategy, setStrategy] = useState("funding_carry");
  const [symbol, setSymbol] = useState("BTC-USDT-SWAP");
  const [periods, setPeriods] = useState(365 * 24);
  const [start, setStart] = useState("2026-01-26");
  const [end, setEnd] = useState("2026-04-26");
  const [bar, setBar] = useState("1H");
  const [equity, setEquity] = useState(5000);

  const [source, setSource] = useState("local"); // local | url | api | paste
  const [columns, setColumns] = useState([
    { key: "ts", maps: "ts", type: "datetime", required: true },
    { key: "open", maps: "open", type: "float", required: true },
    { key: "high", maps: "high", type: "float", required: true },
    { key: "low", maps: "low", type: "float", required: true },
    { key: "close", maps: "close", type: "float", required: true },
    { key: "vol", maps: "vol", type: "float", required: false },
  ]);

  function updateCol(i, patch) {
    setColumns((cs) => cs.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }
  function addCol() {
    setColumns((cs) => [...cs, { key: `field_${cs.length}`, maps: "(ignore)", type: "float", required: false }]);
  }
  function removeCol(i) {
    setColumns((cs) => cs.filter((_, idx) => idx !== i));
  }

  const strat = MOCK.STRATEGIES.find((s) => s.id === strategy);

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="row" style={{ gap: "var(--gap-lg)" }}>
        <div className="card" style={{ flex: 2 }}>
          <div className="card-h">
            <div>
              <div className="card-title">回測參數</div>
              <div className="card-sub">strategy · symbol · window</div>
            </div>
            <div className="row" style={{ gap: 8 }}>
              <button className="btn ghost sm">Save preset</button>
              <button className="btn primary sm">▶ Run backtest</button>
            </div>
          </div>

          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <div className="field-label">Strategy</div>
              <select className="select" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                {MOCK.STRATEGIES.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              <div className="field-hint">{strat.desc}</div>
            </div>
            <div className="field">
              <div className="field-label">Symbol</div>
              <select className="select mono" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {MOCK.SYMBOLS.map((s) => <option key={s}>{s}</option>)}
              </select>
              <div className="field-hint">OKX instrument id</div>
            </div>
            <div className="field">
              <div className="field-label">Bar size</div>
              <select className="select mono" value={bar} onChange={(e) => setBar(e.target.value)}>
                {["1m", "5m", "15m", "1H", "4H", "1D"].map((b) => <option key={b}>{b}</option>)}
              </select>
            </div>
            <div className="field">
              <div className="field-label">Annualization periods</div>
              <input className="input mono" value={periods} onChange={(e) => setPeriods(+e.target.value)} />
              <div className="field-hint">365 (daily) · 8760 (hourly) · 525600 (minute)</div>
            </div>
            <div className="field">
              <div className="field-label">Start</div>
              <input className="input mono" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div className="field">
              <div className="field-label">End</div>
              <input className="input mono" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
            <div className="field">
              <div className="field-label">Initial equity (USD)</div>
              <input className="input mono" value={equity} onChange={(e) => setEquity(+e.target.value)} />
            </div>
            <div className="field">
              <div className="field-label">Validation</div>
              <select className="select">
                <option>Walk-Forward · IS=14d / OOS=7d</option>
                <option>CPCV · N=6 / k=2 / embargo=2%</option>
                <option>Both (full report)</option>
              </select>
            </div>
          </div>
        </div>

        <div className="card" style={{ flex: 1, minWidth: 280 }}>
          <div className="card-h">
            <div>
              <div className="card-title">策略參數</div>
              <div className="card-sub mono">{strategy}</div>
            </div>
          </div>
          <StrategyParams id={strategy} />
        </div>
      </div>

      {/* Data source + Schema editor */}
      <div className="card">
        <div className="card-h">
          <div>
            <div className="card-title">資料來源 · Schema editor</div>
            <div className="card-sub">map external columns to internal fields</div>
          </div>
          <div className="toggle">
            {[
              ["local", "Local file"],
              ["url", "URL"],
              ["api", "API"],
              ["paste", "Paste"],
            ].map(([v, l]) => (
              <button key={v} aria-pressed={source === v} onClick={() => setSource(v)}>{l}</button>
            ))}
          </div>
        </div>

        <div className="row" style={{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
          <div style={{ flex: 1, minWidth: 280 }}>
            {source === "local" && (
              <div className="dropzone">
                <div style={{ marginBottom: 6, color: "var(--text)" }}>Drop .parquet or .csv files here</div>
                <div className="mono" style={{ fontSize: 11 }}>data/ticks/&lt;INST&gt;/candles_1H.parquet</div>
                <div style={{ marginTop: 14 }}>
                  <button className="btn sm">Browse files</button>
                </div>
              </div>
            )}
            {source === "url" && (
              <div className="field">
                <div className="field-label">Remote URL</div>
                <input className="input mono" placeholder="https://example.com/btc_usdt_1h.parquet" />
                <div className="field-hint">Supports .parquet, .csv, .json. Auth via Headers.</div>
              </div>
            )}
            {source === "api" && (
              <div className="col" style={{ gap: 12 }}>
                <div className="field">
                  <div className="field-label">Endpoint</div>
                  <input className="input mono" defaultValue="https://www.okx.com/api/v5/market/candles" />
                </div>
                <div className="row" style={{ gap: 12 }}>
                  <div className="field" style={{ flex: 1 }}>
                    <div className="field-label">Method</div>
                    <select className="select"><option>GET</option><option>POST</option></select>
                  </div>
                  <div className="field" style={{ flex: 2 }}>
                    <div className="field-label">Auth header</div>
                    <input className="input mono" placeholder="Bearer …" />
                  </div>
                </div>
              </div>
            )}
            {source === "paste" && (
              <div className="field">
                <div className="field-label">Paste CSV / JSON</div>
                <textarea className="input mono" rows={6} placeholder="ts,open,high,low,close,vol&#10;2026-01-26T00:00:00Z,60123.4,…" />
              </div>
            )}

            <div style={{ marginTop: 16 }}>
              <div className="field-label" style={{ marginBottom: 8 }}>Column mapping</div>
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Source column</th>
                      <th>Maps to (internal)</th>
                      <th>Type</th>
                      <th>Required</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {columns.map((c, i) => (
                      <tr key={i}>
                        <td>
                          <input className="input mono" style={{ padding: "4px 8px", fontSize: 12 }} value={c.key} onChange={(e) => updateCol(i, { key: e.target.value })} />
                        </td>
                        <td>
                          <select className="select" style={{ padding: "4px 8px", fontSize: 12 }} value={c.maps} onChange={(e) => updateCol(i, { maps: e.target.value })}>
                            {["ts", "open", "high", "low", "close", "vol", "rate", "apr", "bid", "ask", "(ignore)"].map((m) => <option key={m}>{m}</option>)}
                          </select>
                        </td>
                        <td>
                          <select className="select" style={{ padding: "4px 8px", fontSize: 12 }} value={c.type} onChange={(e) => updateCol(i, { type: e.target.value })}>
                            {["datetime", "float", "int", "string"].map((m) => <option key={m}>{m}</option>)}
                          </select>
                        </td>
                        <td className="num">
                          <input type="checkbox" checked={c.required} onChange={(e) => updateCol(i, { required: e.target.checked })} />
                        </td>
                        <td className="num">
                          <button className="btn ghost sm" onClick={() => removeCol(i)}>×</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: 8 }}>
                <button className="btn sm" onClick={addCol}>+ Add column</button>
                <span className="kbd" style={{ marginLeft: 8 }}>auto-detect</span>
              </div>
            </div>
          </div>

          <div style={{ flex: 1, minWidth: 280 }}>
            <div className="field-label" style={{ marginBottom: 8 }}>Preview · first 6 rows</div>
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    {columns.map((c, i) => (
                      <th key={i} className={c.type === "float" || c.type === "int" ? "num" : ""}>
                        <div>{c.key}</div>
                        <div className="mono" style={{ fontWeight: 400, color: "var(--text-subtle)", fontSize: 10 }}>→ {c.maps}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {MOCK.sampleCandles.map((row, ri) => (
                    <tr key={ri}>
                      {columns.map((c, i) => {
                        const v = row[c.maps];
                        const isNum = c.type === "float" || c.type === "int";
                        return <td key={i} className={isNum ? "num" : ""}>{v ?? "—"}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="field-hint" style={{ marginTop: 8 }}>
              <span className="chip accent">2,160 rows</span>{" "}
              <span className="chip">no NaNs</span>{" "}
              <span className="chip">timezone UTC</span>{" "}
              <span className="chip">monotonic ✓</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StrategyParams({ id }) {
  const params = {
    funding_carry: [
      ["min_apr_threshold", "0.12", "minimum APR to enter"],
      ["rebalance_drift_threshold", "0.02", "spot/perp drift"],
      ["funding_check_interval_secs", "300", "REST poll cadence"],
    ],
    as_market_maker: [
      ["gamma", "0.10", "risk aversion"],
      ["kappa", "1.5", "arrival intensity"],
      ["sigma_lookback_min", "5", "vol estimator window"],
      ["beta_vpin", "2.0", "VPIN spread scaler"],
      ["max_pos_contracts", "50", "inventory cap"],
    ],
    obi_market_maker: [
      ["depth", "5", "book levels"],
      ["alpha_decay", "0.5", "OFI weight decay"],
      ["obi_threshold", "0.15", "signal threshold"],
      ["c_alpha", "100.0", "alpha coef"],
    ],
    pairs_trading: [
      ["kalman_delta", "0.0001", "process noise"],
      ["entry_z", "2.0", "z-score entry"],
      ["exit_z", "0.3", "z-score exit"],
      ["stop_z", "4.0", "stop-loss z"],
      ["lookback_hours", "168", "OU estimator"],
    ],
  }[id] || [];
  return (
    <div className="col" style={{ gap: 10 }}>
      {params.map(([k, v, hint]) => (
        <div key={k} className="row" style={{ alignItems: "center", gap: 10 }}>
          <div style={{ flex: 1, color: "var(--text-muted)", fontSize: 12 }} className="mono">{k}</div>
          <input className="input mono" defaultValue={v} style={{ width: 100, padding: "4px 8px", fontSize: 12, textAlign: "right" }} />
        </div>
      ))}
      <div className="sep"></div>
      <div className="field-hint">td_mode: cross · post_only: true · max_order_notional: $500</div>
    </div>
  );
}

window.RunConfigView = RunConfigView;
window.KPI = KPI;

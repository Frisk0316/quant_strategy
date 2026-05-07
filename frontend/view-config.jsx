/* global React, MOCK */
const { useState: useConfigState, useEffect: useConfigEffect } = React;

const BAR_PERIODS = {
  "1m": 525600, "3m": 175200, "5m": 105120, "15m": 35040,
  "30m": 17520, "1H": 8760, "2H": 4380, "4H": 2190, "1D": 365,
};

const todayUtc = new Date();
todayUtc.setUTCHours(0, 0, 0, 0);
const yesterday = new Date(todayUtc - 86400000).toISOString().slice(0, 10);

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

window.fmt = { pct: fmtPct, num: fmtNum, usd: fmtUSD, ts: fmtTs, date: fmtDate };

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
          <window.Charts.Sparkline values={spark} color={tone === "down" ? "var(--loss)" : tone === "up" ? "var(--profit)" : "var(--accent)"} mode={sparkMode} height={32} />
        </div>
      )}
    </div>
  );
}

function RunBacktestView() {
  const [instruments, setInstruments] = useConfigState([]);
  const [strategy, setStrategy] = useConfigState("funding_carry");
  const [symbol, setSymbol] = useConfigState("BTC-USDT-SWAP");
  const [spotSymbol, setSpotSymbol] = useConfigState("BTC-USDT");
  const [symbolX, setSymbolX] = useConfigState("BTC-USDT-SWAP");
  const [symbolY, setSymbolY] = useConfigState("ETH-USDT-SWAP");
  const [bar, setBar] = useConfigState("1H");
  const [periodsOverride, setPeriodsOverride] = useConfigState(null);
  const [start, setStart] = useConfigState("2024-01-01");
  const [end, setEnd] = useConfigState(yesterday);
  const [equity, setEquity] = useConfigState(5000);
  const [runJob, setRunJob] = useConfigState(null);
  const periods = periodsOverride ?? BAR_PERIODS[bar] ?? 8760;
  const strat = MOCK.STRATEGIES.find((s) => s.id === strategy) || {};
  const listingMap = Object.fromEntries(instruments.map((i) => [i.inst_id, i.list_date]));
  const selectedSwapSymbols = strategy === "pairs_trading"
    ? [symbolX, symbolY]
    : [symbol].filter((s) => s && s.includes("SWAP"));
  const startMin = selectedSwapSymbols
    .map((s) => listingMap[s])
    .filter(Boolean)
    .sort()
    .at(-1) || "";

  useConfigEffect(() => {
    window.API.fetchDataInstruments()
      .then((rows) => {
        setInstruments(rows || []);
        const swapSymbols = (rows || []).map((r) => r.inst_id).filter(Boolean);
        if (swapSymbols.length) {
          window.MOCK.SYMBOLS = [...new Set([...window.MOCK.SYMBOLS, ...swapSymbols])];
        }
      })
      .catch(() => setInstruments([]));
  }, []);

  useConfigEffect(() => {
    if (startMin && start < startMin) setStart(startMin);
  }, [startMin, start]);

  function onBarChange(newBar) {
    setBar(newBar);
    setPeriodsOverride(null);
  }

  function triggerBacktest() {
    const body = {
      strategy,
      bar,
      periods,
      start: startMin && start < startMin ? startMin : start,
      end,
      symbols: strategy === "pairs_trading" ? [symbolY, symbolX] : [symbol],
      symbol_x: strategy === "pairs_trading" ? symbolX : null,
      symbol_y: strategy === "pairs_trading" ? symbolY : null,
      perp_symbol: strategy === "funding_carry" ? symbol : null,
      spot_symbol: strategy === "funding_carry" ? spotSymbol : null,
    };
    setRunJob({ status: "running", progress: 0, message: "Submitting backtest..." });
    window.API.triggerBacktestRun(body).then((job) => {
      setRunJob(job);
      const iv = setInterval(() => {
        window.API.fetchBacktestRunStatus(job.job_id).then((s) => {
          setRunJob(s);
          if (s.status === "done" || s.status === "error") clearInterval(iv);
        }).catch((err) => {
          setRunJob({ status: "error", message: err.message });
          clearInterval(iv);
        });
      }, 2000);
    }).catch((err) => setRunJob({ status: "error", message: err.message }));
  }

  return (
    <div className="col" style={{ gap: "var(--gap-lg)" }}>
      <div className="row" style={{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
        <div className="card" style={{ flex: 2 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Backtest configuration</div>
              <div className="card-sub">strategy, symbol, bar, and date window</div>
            </div>
            <div className="row" style={{ gap: 8 }}>
              <button className="btn ghost sm">Save preset</button>
              <button className="btn primary sm" disabled={runJob?.status === "running" || (strategy === "pairs_trading" && symbolX === symbolY)} onClick={triggerBacktest}>Run backtest</button>
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
            {strategy === "pairs_trading" ? (
              <>
                <div className="field">
                  <div className="field-label">Reference symbol (X)</div>
                  <select className="select mono" value={symbolX} onChange={(e) => setSymbolX(e.target.value)}>
                    {MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => <option key={s}>{s}</option>)}
                  </select>
                  <div className="field-hint">Reference leg for hedge ratio and spread signal, e.g. BTC-USDT-SWAP.</div>
                </div>
                <div className="field">
                  <div className="field-label">Trade/spread symbol (Y)</div>
                  <select className="select mono" value={symbolY} onChange={(e) => setSymbolY(e.target.value)}>
                    {MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => <option key={s}>{s}</option>)}
                  </select>
                  <div className="field-hint">Dependent leg traded against X, e.g. ETH, LTC, SOL, or other available swaps.</div>
                </div>
                {symbolX === symbolY && (
                  <div className="field-hint" style={{ gridColumn: "1 / -1", color: "var(--loss)" }}>
                    Pair Trading requires two different symbols.
                  </div>
                )}
              </>
            ) : (
              <div className="field">
                <div className="field-label">{strategy === "funding_carry" ? "Perp symbol" : "Symbol"}</div>
                <select className="select mono" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                  {MOCK.SYMBOLS.filter((s) => strategy !== "funding_carry" || s.includes("SWAP")).map((s) => <option key={s}>{s}</option>)}
                </select>
                <div className="field-hint">OKX instrument id</div>
              </div>
            )}
            {strategy === "funding_carry" && (
              <div className="field">
                <div className="field-label">Spot hedge symbol</div>
                <input className="input mono" value={spotSymbol} onChange={(e) => setSpotSymbol(e.target.value)} />
                <div className="field-hint">Spot leg used for delta-neutral funding carry.</div>
              </div>
            )}
            <div className="field">
              <div className="field-label">Bar size</div>
              <select className="select mono" value={bar} onChange={(e) => onBarChange(e.target.value)}>
                {Object.keys(BAR_PERIODS).map((b) => <option key={b}>{b}</option>)}
              </select>
            </div>
            <div className="field">
              <div className="field-label">
                Annualization periods
                <span
                  className="chip"
                  style={{ marginLeft: 6, fontSize: 10 }}
                  title="Sharpe = mean_bar_return / std x sqrt(periods). Use 8,760 for 1H bars so metrics are annual. Changing bar size resets this automatically."
                >?</span>
              </div>
              <input
                className="input mono"
                value={periods}
                onChange={(e) => setPeriodsOverride(+e.target.value)}
              />
              <div className="field-hint">
                auto: {BAR_PERIODS[bar]?.toLocaleString()} - <span style={{ color: periodsOverride ? "var(--accent)" : "var(--text-muted)" }}>{periodsOverride ? "overridden" : "synced"}</span>
              </div>
            </div>
            <div className="field">
              <div className="field-label">Start</div>
              <input className="input mono" type="date" value={start} min={startMin || undefined} onChange={(e) => setStart(startMin && e.target.value < startMin ? startMin : e.target.value)} />
              {startMin && <div className="field-hint">min: {startMin} (latest listing date among selected symbols)</div>}
            </div>
            <div className="field">
              <div className="field-label">End</div>
              <input
                className="input mono"
                type="date"
                value={end}
                max={yesterday}
                onChange={(e) => setEnd(e.target.value > yesterday ? yesterday : e.target.value)}
              />
              <div className="field-hint">max: {yesterday} (data through yesterday)</div>
            </div>
            <div className="field">
              <div className="field-label">Initial equity (USD)</div>
              <input className="input mono" value={equity} onChange={(e) => setEquity(+e.target.value)} />
            </div>
            <div className="field">
              <div className="field-label">Validation</div>
              <select className="select">
                <option>Walk-Forward IS=14d / OOS=7d</option>
                <option>CPCV N=6 / k=2 / embargo=2%</option>
                <option>Both (full report)</option>
              </select>
            </div>
          </div>
          {runJob && (
            <div className="row" style={{ gap: 12, marginTop: 16, alignItems: "center" }}>
              <span className={`chip ${runJob.status === "done" ? "profit" : runJob.status === "error" ? "loss" : "warn"}`}>{runJob.status}</span>
              <span className="field-hint">{runJob.message || ""}</span>
              {runJob.run_id && <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>{runJob.run_id}</span>}
              {runJob.progress != null && (
                <div className="bar" style={{ flex: 1, height: 6 }}>
                  <i style={{ width: `${runJob.progress}%`, background: "var(--accent)" }} />
                </div>
              )}
            </div>
          )}
        </div>

        <div className="card" style={{ flex: 1, minWidth: 280 }}>
          <div className="card-h">
            <div>
              <div className="card-title">Strategy parameters</div>
              <div className="card-sub mono">{strategy}</div>
            </div>
          </div>
          <StrategyParams id={strategy} />
        </div>
      </div>

      <MarketDataCard />
    </div>
  );
}

function StrategyParams({ id }) {
  const params = {
    funding_carry: [
      ["min_apr_threshold", "0.12", "min APR to enter", "Minimum annualized funding rate (APR) required to open a carry position. Filters out low-yield periods. 0.12 = 12% APR."],
      ["rebalance_drift_threshold", "0.02", "spot/perp drift", "Max allowed deviation between spot and perp position sizes before rebalancing. Keeps delta-neutral exposure."],
      ["funding_check_interval_secs", "300", "poll cadence (s)", "How often (seconds) the strategy re-checks the funding rate via REST. Lower = more reactive, higher = fewer API calls."],
    ],
    as_market_maker: [
      ["gamma", "0.10", "risk aversion", "Avellaneda-Stoikov risk aversion parameter. Higher gamma widens spreads and shrinks inventory faster. Tune to your risk tolerance."],
      ["kappa", "1.5", "arrival intensity", "Expected order arrival rate. Affects bid/ask reservation prices. Higher kappa = tighter spreads."],
      ["sigma_lookback_min", "5", "vol estimator window (min)", "Rolling window in minutes for mid-price volatility estimation. Shorter = more reactive to recent vol spikes."],
      ["beta_vpin", "2.0", "VPIN spread scaler", "Multiplier applied to spread when VPIN (toxicity) is high. Wider spreads during informed order flow."],
      ["max_pos_contracts", "50", "inventory cap (contracts)", "Maximum net inventory the strategy will hold. Orders are suppressed on the side that would exceed this limit."],
    ],
    obi_market_maker: [
      ["depth", "5", "book levels", "Number of order book price levels to include in OBI calculation. More levels = smoother but slower signal."],
      ["alpha_decay", "0.5", "OFI weight decay", "Exponential decay applied to older order flow imbalance observations. Lower = memory of past flow fades faster."],
      ["obi_threshold", "0.15", "signal threshold", "Minimum absolute OBI score required to skew quotes. Below this, quotes are symmetric."],
      ["c_alpha", "100.0", "alpha coefficient", "Scales the adverse selection component of the spread. Higher = wider quotes when OBI signal is strong."],
    ],
    pairs_trading: [
      ["kalman_delta", "0.0001", "process noise", "Kalman filter process variance. Lower = hedge ratio changes slowly, more stable but lags regime shifts."],
      ["entry_z", "2.0", "entry z-score", "Open a position when the OU spread z-score crosses +/-entry_z. Higher = fewer but higher-conviction entries, lower fill rate."],
      ["exit_z", "0.3", "exit z-score", "Close the position when z-score reverts to +/-exit_z. Lower = exit close to mean, capturing full reversion."],
      ["stop_z", "4.0", "stop-loss z-score", "Force-close if z-score reaches +/-stop_z. Protects against spread divergence and non-stationary regimes."],
      ["lookback_hours", "168", "OU estimator window (h)", "Rolling window for estimating Ornstein-Uhlenbeck parameters. 168 h = 1 week. Shorter = adapts faster, noisier estimates."],
    ],
  }[id] || [];
  return (
    <div className="col" style={{ gap: 12 }}>
      {params.map(([k, v, short, full]) => (
        <div key={k} className="col" style={{ gap: 4 }}>
          <div className="row" style={{ alignItems: "center", gap: 10 }}>
            <div style={{ flex: 1, fontSize: 12 }} className="mono" title={short}>{k}</div>
            <input className="input mono" defaultValue={v}
              style={{ width: 100, padding: "4px 8px", fontSize: 12, textAlign: "right" }} />
          </div>
          <div className="field-hint" style={{ fontSize: 11 }}>{full}</div>
        </div>
      ))}
      <div className="sep"></div>
      <div className="field-hint">td_mode: cross - post_only: true - max_order_notional: $500</div>
    </div>
  );
}

function MarketDataCard() {
  const [coverage, setCoverage] = useConfigState(null);
  const [instruments, setInstruments] = useConfigState([]);
  const [fetchJob, setFetchJob] = useConfigState(null);
  const [showFetchPanel, setShowFetchPanel] = useConfigState(false);
  const [fetchForm, setFetchForm] = useConfigState({ symbols: ["BTC-USDT-SWAP"], bar: "1m", start: "2024-01-01", end: yesterday });
  const listingMap = Object.fromEntries(instruments.map((i) => [i.inst_id, i.list_date]));
  const latestSelectedListing = (fetchForm.symbols || [])
    .map((s) => listingMap[s])
    .filter(Boolean)
    .sort()
    .at(-1) || "";

  function refreshCoverage() {
    window.API.fetchDataCoverage().then(setCoverage).catch(() => setCoverage([]));
  }

  useConfigEffect(() => {
    refreshCoverage();
    window.API.fetchDataInstruments().then((rows) => setInstruments(rows || [])).catch(() => setInstruments([]));
  }, []);

  function triggerFetch() {
    const body = {
      ...fetchForm,
    };
    window.API.triggerDataFetch(body).then((job) => {
      setFetchJob(job);
      const iv = setInterval(() => {
        window.API.fetchDataFetchStatus(job.job_id).then((s) => {
          setFetchJob(s);
          if (s.status === "done" || s.status === "error") {
            clearInterval(iv);
            refreshCoverage();
          }
        }).catch(() => clearInterval(iv));
      }, 2000);
    });
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

  return (
    <div className="card">
      <div className="card-h">
        <div>
          <div className="card-title">Market Data Coverage</div>
          <div className="card-sub">OHLCV and funding rates stored in TimescaleDB</div>
        </div>
        <button className="btn sm" onClick={() => setShowFetchPanel((v) => !v)}>+ Fetch from Exchange</button>
      </div>

      {showFetchPanel && (
        <div className="card" style={{ background: "var(--surface-2)", marginBottom: 16 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Fetch 1m OHLCV from OKX</div>
          <div className="grid" style={{ gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 12 }}>
            <div className="field">
              <div className="field-label">USDT swap symbols</div>
              <div className="tbl-wrap" style={{ maxHeight: 160 }}>
                <table className="tbl" style={{ fontSize: 12 }}>
                  <tbody>
                    {(instruments.length ? instruments : MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => ({ inst_id: s }))).map((inst) => (
                      <tr key={inst.inst_id}>
                        <td style={{ width: 28 }}>
                          <input
                            type="checkbox"
                            checked={(fetchForm.symbols || []).includes(inst.inst_id)}
                            onChange={() => toggleFetchSymbol(inst.inst_id)}
                          />
                        </td>
                        <td className="mono">{inst.inst_id}</td>
                        <td className="num mono" style={{ color: "var(--text-subtle)" }}>{inst.list_date || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="field-hint">{(fetchForm.symbols || []).length} selected - listing dates from OKX instruments</div>
            </div>
            <div className="field">
              <div className="field-label">Bar</div>
              <select className="select mono" value={fetchForm.bar}
                onChange={(e) => setFetchForm((f) => ({ ...f, bar: e.target.value }))}>
                {["1m", "5m", "15m", "1H", "4H", "1D"].map((b) => <option key={b}>{b}</option>)}
              </select>
            </div>
            <div className="field">
              <div className="field-label">Start</div>
              <input className="input mono" type="date" value={fetchForm.start}
                onChange={(e) => setFetchForm((f) => ({ ...f, start: e.target.value }))} />
              {latestSelectedListing && <div className="field-hint">symbols listed after start auto-fetch from their listing date; latest selected listing: {latestSelectedListing}</div>}
            </div>
            <div className="field">
              <div className="field-label">End</div>
              <input className="input mono" type="date" value={fetchForm.end} max={yesterday}
                onChange={(e) => setFetchForm((f) => ({ ...f, end: e.target.value > yesterday ? yesterday : e.target.value }))} />
            </div>
          </div>
          {fetchJob && (
            <div className="row" style={{ gap: 12, marginTop: 12, alignItems: "center" }}>
              <span className={`chip ${fetchJob.status === "done" ? "profit" : fetchJob.status === "error" ? "loss" : "warn"}`}>
                {fetchJob.status}
              </span>
              <span className="field-hint">{fetchJob.message || ""}</span>
              {fetchJob.progress != null && (
                <div className="bar" style={{ flex: 1, height: 6 }}>
                  <i style={{ width: `${fetchJob.progress}%`, background: "var(--accent)" }} />
                </div>
              )}
            </div>
          )}
          <button className="btn primary sm" style={{ marginTop: 12 }}
            disabled={fetchJob?.status === "running" || !(fetchForm.symbols || []).length}
            onClick={triggerFetch}>
            Fetch selected data
          </button>
          {fetchJob?.results?.length > 0 && (
            <div className="field-hint" style={{ marginTop: 8 }}>
              {fetchJob.results.map((r) => `${r.symbol}: ${r.rows?.toLocaleString?.() ?? r.rows} rows from ${r.effective_start || r.list_date || "-"}`).join(" - ")}
            </div>
          )}
        </div>
      )}

      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Symbol</th><th>Bar</th><th className="num">First date</th>
              <th className="num">Last date</th><th className="num">Rows</th>
              <th className="num">Gaps</th>
            </tr>
          </thead>
          <tbody>
            {(coverage || []).map((row, i) => (
              <tr key={i}>
                <td className="mono">{row.inst_id}</td>
                <td className="mono">{row.bar}</td>
                <td className="num mono">{row.first_ts ? new Date(row.first_ts).toISOString().slice(0, 10) : "-"}</td>
                <td className="num mono">{row.last_ts ? new Date(row.last_ts).toISOString().slice(0, 10) : "-"}</td>
                <td className="num">{(row.row_count || 0).toLocaleString()}</td>
                <td className="num" style={{ color: row.gap_count > 0 ? "var(--warn)" : "var(--profit)" }}>
                  {row.gap_count ?? "-"}
                </td>
              </tr>
            ))}
            {(!coverage || !coverage.length) && (
              <tr><td colSpan={6} className="field-hint" style={{ textAlign: "center", padding: 24 }}>No data in DB. Use "Fetch from Exchange" to load historical data.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.RunConfigView = RunBacktestView;
window.KPI = KPI;

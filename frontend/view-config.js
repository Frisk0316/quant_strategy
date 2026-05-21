import { h, Fragment } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
const useConfigState = useState;
const useConfigEffect = useEffect;

const { Sparkline } = window.Charts;

const BAR_PERIODS = {
  "1m": 525600, "3m": 175200, "5m": 105120, "15m": 35040,
  "30m": 17520, "1H": 8760, "2H": 4380, "4H": 2190, "1D": 365,
};
const TECHNICAL_STRATEGIES = new Set(["ma_crossover", "ema_crossover", "macd_crossover"]);
const EXTERNAL_STRATEGIES = new Set(["fear_greed_sentiment", "cme_gap_fill"]);
const PARAMETERIZED_STRATEGIES = new Set([...TECHNICAL_STRATEGIES, ...EXTERNAL_STRATEGIES]);
const STRATEGY_PARAM_DEFAULTS = {
  ma_crossover: { fast_window: 20, slow_window: 50 },
  ema_crossover: { fast_span: 20, slow_span: 50 },
  macd_crossover: { fast_span: 12, slow_span: 26, signal_span: 9 },
  fear_greed_sentiment: { dataset_id: "fear_greed_btc", max_age_seconds: 172800, extreme_fear_label: "Extreme Fear", extreme_fear_threshold: 25, exit_value_threshold: 51 },
  cme_gap_fill: {
    dataset_id: "cme_btc_yfinance",
    max_age_seconds: 604800,
    min_gap_bps: 25,
    max_hold_days: 2,
    stop_loss_bps_mult: 1.5,
    max_gap_bps: 0,
    allow_direction: "long_only",
  },
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
  return html`
    <div class="kpi">
      <div class="kpi-label">
        ${label}
        ${hint && html`<span class="chip" style=${{ fontSize: 10, padding: "1px 6px" }}>${hint}</span>`}
      </div>
      <div class="kpi-value">${value}</div>
      ${sub && html`<div class=${`kpi-delta ${toneClass}`}>${sub}</div>`}
      ${spark && html`
        <div class="kpi-spark">
          <${Sparkline} values=${spark} color=${tone === "down" ? "var(--loss)" : tone === "up" ? "var(--profit)" : "var(--accent)"} mode=${sparkMode} height=${32} />
        </div>
      `}
    </div>
  `;
}

function RunBacktestView({ setView, setSelectedRunId }) {
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
  const [validation, setValidation] = useConfigState("both");
  const [runJob, setRunJob] = useConfigState(null);
  const [rotUniverse, setRotUniverse] = useConfigState(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]);
  const [technicalSymbols, setTechnicalSymbols] = useConfigState(["BTC-USDT-SWAP"]);
  const [rotBenchmark, setRotBenchmark] = useConfigState("BTC-USDT-SWAP");
  const [rotRebalanceMin, setRotRebalanceMin] = useConfigState(60);
  const [rotTopK, setRotTopK] = useConfigState(3);
  const [rotRankExitBuffer, setRotRankExitBuffer] = useConfigState(6);
  const [strategyParams, setStrategyParams] = useConfigState(STRATEGY_PARAM_DEFAULTS);
  const periods = periodsOverride ?? BAR_PERIODS[bar] ?? 8760;
  const strat = MOCK.STRATEGIES.find((s) => s.id === strategy) || {};
  const listingMap = Object.fromEntries(instruments.map((i) => [i.inst_id, i.list_date]));
  const isRotation = strategy === "ohlcv_rotation";
  const isDailyWinner = strategy === "daily_winner";
  const isTechnical = TECHNICAL_STRATEGIES.has(strategy);
  const hasStrategyParams = PARAMETERIZED_STRATEGIES.has(strategy);
  const isBasketStrategy = isRotation || isDailyWinner || isTechnical;
  const selectedSwapSymbols = strategy === "pairs_trading"
    ? [symbolX, symbolY]
    : isTechnical
    ? technicalSymbols
    : isBasketStrategy
    ? rotUniverse
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

  // Reconnect to any in-progress job after page refresh
  useConfigEffect(() => {
    const savedJobId = localStorage.getItem("activeBacktestJobId");
    if (!savedJobId) return;
    window.API.fetchBacktestRunStatus(savedJobId).then((s) => {
      if (s && s.status === "running") {
        setRunJob(s);
        const iv = setInterval(() => {
          window.API.fetchBacktestRunStatus(savedJobId).then((st) => {
            setRunJob(st);
            if (st.status === "done" || st.status === "error") {
              clearInterval(iv);
              localStorage.removeItem("activeBacktestJobId");
            }
          }).catch(() => { clearInterval(iv); localStorage.removeItem("activeBacktestJobId"); });
        }, 2000);
      } else {
        localStorage.removeItem("activeBacktestJobId");
      }
    }).catch(() => localStorage.removeItem("activeBacktestJobId"));
  }, []);

  useConfigEffect(() => {
    if (startMin && start < startMin) setStart(startMin);
  }, [startMin, start]);

  useConfigEffect(() => {
    if (isDailyWinner && bar !== "1D") {
      setBar("1D");
      setPeriodsOverride(null);
    }
  }, [isDailyWinner, bar]);

  function onBarChange(newBar) {
    setBar(newBar);
    setPeriodsOverride(null);
  }

  function triggerBacktest() {
    const body = {
      strategy,
      bar: isDailyWinner ? "1D" : bar,
      periods: isDailyWinner ? BAR_PERIODS["1D"] : periods,
      start: startMin && start < startMin ? startMin : start,
      end,
      symbols: strategy === "pairs_trading" ? [symbolY, symbolX] : isTechnical ? technicalSymbols : isBasketStrategy ? [] : [symbol],
      symbol_x: strategy === "pairs_trading" ? symbolX : null,
      symbol_y: strategy === "pairs_trading" ? symbolY : null,
      perp_symbol: strategy === "funding_carry" ? symbol : null,
      spot_symbol: strategy === "funding_carry" ? spotSymbol : null,
      validate: isRotation ? null : (validation === "none" ? null : validation),
      universe: (isRotation || isDailyWinner) ? rotUniverse : [],
      benchmark: isRotation ? rotBenchmark : undefined,
      rebalance_minutes: isRotation ? rotRebalanceMin : undefined,
      top_k: isRotation ? rotTopK : undefined,
      rank_exit_buffer: isRotation ? rotRankExitBuffer : undefined,
      initial_equity: +equity || 5000,
      strategy_params: hasStrategyParams ? (strategyParams[strategy] || {}) : {},
    };
    setRunJob({ status: "running", progress: 0, message: "Submitting backtest..." });
    window.API.triggerBacktestRun(body).then((job) => {
      setRunJob(job);
      localStorage.setItem("activeBacktestJobId", job.job_id);
      const iv = setInterval(() => {
        window.API.fetchBacktestRunStatus(job.job_id).then((s) => {
          setRunJob(s);
          if (s.status === "done" || s.status === "error") {
            clearInterval(iv);
            localStorage.removeItem("activeBacktestJobId");
          }
        }).catch((err) => {
          setRunJob({ status: "error", message: err.message });
          clearInterval(iv);
          localStorage.removeItem("activeBacktestJobId");
        });
      }, 2000);
    }).catch((err) => setRunJob({ status: "error", message: err.message }));
  }

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="row" style=${{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
        <div class="card" style=${{ flex: 2 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Backtest configuration</div>
              <div class="card-sub">strategy, symbol, bar, and date window</div>
            </div>
            <div class="row" style=${{ gap: 8 }}>
              <button class="btn ghost sm">Save preset</button>
              <button class="btn primary sm" disabled=${runJob?.status === "running" || (strategy === "pairs_trading" && symbolX === symbolY) || ((isRotation || isDailyWinner) && rotUniverse.length < 2) || (isTechnical && technicalSymbols.length < 1)} onClick=${triggerBacktest}>Run backtest</button>
            </div>
          </div>

          <div class="grid" style=${{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div class="field">
              <div class="field-label">Strategy</div>
              <select class="select" value=${strategy} onChange=${(e) => setStrategy(e.target.value)}>
                ${MOCK.STRATEGIES.map((s) => html`<option key=${s.id} value=${s.id}>${s.name}</option>`)}
              </select>
              <div class="field-hint">${strat.desc}</div>
            </div>
            ${isDailyWinner ? html`
              <${Fragment}>
                <div class="field" style=${{ gridColumn: "1 / -1" }}>
                  <div class="field-label">Universe (perpetual swaps)</div>
                  <div class="tbl-wrap" style=${{ maxHeight: 120 }}>
                    <table class="tbl" style=${{ fontSize: 12 }}>
                      <tbody>
                        ${MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => html`
                          <tr key=${s} style=${{ cursor: "pointer" }}
                              onClick=${() => setRotUniverse((u) => u.includes(s) ? u.filter((x) => x !== s) : [...u, s])}>
                            <td style=${{ width: 28 }}>
                              <input type="checkbox" checked=${rotUniverse.includes(s)} onChange=${() => {}} />
                            </td>
                            <td class="mono">${s}</td>
                          </tr>
                        `)}
                      </tbody>
                    </table>
                  </div>
                  <div class="field-hint">${rotUniverse.length} instruments selected - one round trip per complete day.</div>
                </div>
              <//>
            ` : strategy === "ohlcv_rotation" ? html`
              <${Fragment}>
                <div class="field" style=${{ gridColumn: "1 / -1" }}>
                  <div class="field-label">Universe (perpetual swaps)</div>
                  <div class="tbl-wrap" style=${{ maxHeight: 120 }}>
                    <table class="tbl" style=${{ fontSize: 12 }}>
                      <tbody>
                        ${MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => html`
                          <tr key=${s} style=${{ cursor: "pointer" }}
                              onClick=${() => setRotUniverse((u) => u.includes(s) ? u.filter((x) => x !== s) : [...u, s])}>
                            <td style=${{ width: 28 }}>
                              <input type="checkbox" checked=${rotUniverse.includes(s)} onChange=${() => {}} />
                            </td>
                            <td class="mono">${s}</td>
                          </tr>
                        `)}
                      </tbody>
                    </table>
                  </div>
                  <div class="field-hint">${rotUniverse.length} instruments selected — re-ranked every ${rotRebalanceMin} bars, top-${rotTopK} held</div>
                </div>
                <div class="field">
                  <div class="field-label">Benchmark</div>
                  <select class="select mono" value=${rotBenchmark} onChange=${(e) => setRotBenchmark(e.target.value)}>
                    ${MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => html`<option key=${s}>${s}</option>`)}
                  </select>
                  <div class="field-hint">Regime filter: go flat when benchmark is below its 240-min EMA.</div>
                </div>
                <div class="field">
                  <div class="field-label">Rebalance interval (min)</div>
                  <input class="input mono" value=${rotRebalanceMin} onChange=${(e) => setRotRebalanceMin(+e.target.value)} />
                  <div class="field-hint">Re-rank universe every N minutes. Default: 60.</div>
                </div>
                <div class="field">
                  <div class="field-label">Top-k positions</div>
                  <input class="input mono" value=${rotTopK} onChange=${(e) => setRotTopK(+e.target.value)} />
                  <div class="field-hint">Max simultaneous positions. Equal weight, capped at 35%.</div>
                </div>
                <div class="field">
                  <div class="field-label">Exit rank buffer</div>
                  <input class="input mono" value=${rotRankExitBuffer} onChange=${(e) => setRotRankExitBuffer(+e.target.value)} />
                  <div class="field-hint">Exit when rank falls below this threshold.</div>
                </div>
              <//>
            ` : isTechnical ? html`
              <${Fragment}>
                <div class="field" style=${{ gridColumn: "1 / -1" }}>
                  <div class="field-label">Symbols (perpetual swaps)</div>
                  <button class="btn sm" style=${{ marginBottom: 4 }}
                    onClick=${() => {
                      const all = MOCK.SYMBOLS.filter((s) => s.includes("SWAP"));
                      const allSelected = all.length > 0 && technicalSymbols.length === all.length;
                      setTechnicalSymbols(allSelected ? [] : [...all]);
                    }}>
                    ${MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).length > 0 && technicalSymbols.length === MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).length ? "Deselect All" : "Select All"}
                  </button>
                  <div class="tbl-wrap" style=${{ maxHeight: 120 }}>
                    <table class="tbl" style=${{ fontSize: 12 }}>
                      <tbody>
                        ${MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => html`
                          <tr key=${s} style=${{ cursor: "pointer" }}
                              onClick=${() => setTechnicalSymbols((u) => u.includes(s) ? u.filter((x) => x !== s) : [...u, s])}>
                            <td style=${{ width: 28 }}>
                              <input type="checkbox" checked=${technicalSymbols.includes(s)} onChange=${() => {}} />
                            </td>
                            <td class="mono">${s}</td>
                          </tr>
                        `)}
                      </tbody>
                    </table>
                  </div>
                  <div class="field-hint">${technicalSymbols.length} instruments selected - long/flat crossover backtest.</div>
                </div>
              <//>
            ` : strategy === "pairs_trading" ? html`
              <${Fragment}>
                <div class="field">
                  <div class="field-label">Reference symbol (X)</div>
                  <select class="select mono" value=${symbolX} onChange=${(e) => setSymbolX(e.target.value)}>
                    ${MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => html`<option key=${s}>${s}</option>`)}
                  </select>
                  <div class="field-hint">Reference leg for hedge ratio and spread signal, e.g. BTC-USDT-SWAP.</div>
                </div>
                <div class="field">
                  <div class="field-label">Trade/spread symbol (Y)</div>
                  <select class="select mono" value=${symbolY} onChange=${(e) => setSymbolY(e.target.value)}>
                    ${MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => html`<option key=${s}>${s}</option>`)}
                  </select>
                  <div class="field-hint">Dependent leg traded against X, e.g. ETH, LTC, SOL, or other available swaps.</div>
                </div>
                ${symbolX === symbolY && html`
                  <div class="field-hint" style=${{ gridColumn: "1 / -1", color: "var(--loss)" }}>
                    Pair Trading requires two different symbols.
                  </div>
                `}
              <//>
            ` : html`
              <div class="field">
                <div class="field-label">${strategy === "funding_carry" ? "Perp symbol" : "Symbol"}</div>
                <select class="select mono" value=${symbol} onChange=${(e) => setSymbol(e.target.value)}>
                  ${MOCK.SYMBOLS.filter((s) => strategy !== "funding_carry" || s.includes("SWAP")).map((s) => html`<option key=${s}>${s}</option>`)}
                </select>
                <div class="field-hint">OKX instrument id</div>
              </div>
            `}
            ${strategy === "funding_carry" && html`
              <div class="field">
                <div class="field-label">Spot hedge symbol</div>
                <input class="input mono" value=${spotSymbol} onChange=${(e) => setSpotSymbol(e.target.value)} />
                <div class="field-hint">Spot leg used for delta-neutral funding carry.</div>
              </div>
            `}
            <div class="field">
              <div class="field-label">Bar size</div>
              <select class="select mono" value=${isDailyWinner ? "1D" : bar} disabled=${isDailyWinner} onChange=${(e) => onBarChange(e.target.value)}>
                ${Object.keys(BAR_PERIODS).map((b) => html`<option key=${b}>${b}</option>`)}
              </select>
              ${isDailyWinner && html`<div class="field-hint">Daily Winner always uses 1D candles derived from DB 1m OHLCV when needed.</div>`}
            </div>
            <div class="field">
              <div class="field-label">
                Annualization periods
                <span
                  class="chip"
                  style=${{ marginLeft: 6, fontSize: 10 }}
                  title="Sharpe = mean_bar_return / std x sqrt(periods). Use 8,760 for 1H bars so metrics are annual. Changing bar size resets this automatically."
                >?</span>
              </div>
              <input
                class="input mono"
                value=${periods}
                onChange=${(e) => setPeriodsOverride(+e.target.value)}
              />
              <div class="field-hint">
                auto: ${BAR_PERIODS[isDailyWinner ? "1D" : bar]?.toLocaleString()} - <span style=${{ color: periodsOverride ? "var(--accent)" : "var(--text-muted)" }}>${periodsOverride ? "overridden" : "synced"}</span>
              </div>
            </div>
            <div class="field">
              <div class="field-label">Start</div>
              <input class="input mono" type="date" value=${start} min=${startMin || undefined} onChange=${(e) => setStart(startMin && e.target.value < startMin ? startMin : e.target.value)} />
              ${startMin && html`<div class="field-hint">min: ${startMin} (latest listing date among selected symbols)</div>`}
            </div>
            <div class="field">
              <div class="field-label">End</div>
              <input
                class="input mono"
                type="date"
                value=${end}
                max=${yesterday}
                onChange=${(e) => setEnd(e.target.value > yesterday ? yesterday : e.target.value)}
              />
              <div class="field-hint">max: ${yesterday} (data through yesterday)</div>
            </div>
            <div class="field">
              <div class="field-label">Initial equity (USD)</div>
              <input class="input mono" value=${equity} onChange=${(e) => setEquity(+e.target.value)} />
            </div>
            ${(() => {
              // Warm-up clock-time per strategy (minutes)
              const warmupMin = { funding_carry: 0, as_market_maker: 10, obi_market_maker: 10,
                                  pairs_trading: 168 * 60, ohlcv_rotation: 240, daily_winner: 24 * 60 };
              const wm = warmupMin[strategy] || 0;
              if (!wm || !start || !end) return null;
              const days = (new Date(end) - new Date(start)) / 86400000;
              const warmupDays = wm / 60 / 24;
              if (days < warmupDays * 3) {
                const warmupLabel = warmupDays >= 1 ? `${warmupDays.toFixed(1)} days` : `${(wm / 60).toFixed(1)} h`;
                return html`<div class="field-hint" style=${{ color: "var(--warn, #d97706)" }}>
                  ⚠ Warm-up: ~${warmupLabel}. Backtest window (${days.toFixed(0)} d) may have limited active trading.
                </div>`;
              }
              return null;
            })()}
            ${!isRotation && html`
              <div class="field">
                <div class="field-label">Validation</div>
                <select class="select" value=${validation} onChange=${(e) => setValidation(e.target.value)}>
                  <option value="both">Both (WF + CPCV)</option>
                  <option value="wf">Walk-Forward</option>
                  <option value="cpcv">CPCV</option>
                  <option value="none">None</option>
                </select>
              </div>
            `}
          </div>
          ${runJob && html`
            <div class="row" style=${{ gap: 12, marginTop: 16, alignItems: "center" }}>
              <span class=${`chip ${runJob.status === "done" ? "profit" : runJob.status === "error" ? "loss" : "warn"}`}>${runJob.status}</span>
              <span class="field-hint">${runJob.message || ""}</span>
              ${runJob.run_id && html`<span class="mono" style=${{ fontSize: 11, color: "var(--text-muted)" }}>${runJob.run_id}</span>`}
              ${runJob.progress != null && html`
                <div class="bar" style=${{ flex: 1, height: 6 }}>
                  <i style=${{ width: `${runJob.progress}%`, background: "var(--accent)" }}></i>
                </div>
              `}
              ${runJob.status === "done" && runJob.run_id && setView && html`
                <button class="btn primary sm" onClick=${() => {
                  setSelectedRunId?.(runJob.run_id);
                  setView("backtest");
                }}>View Results →</button>
              `}
            </div>
            ${runJob.status === "error" && runJob.output && html`
              <pre style=${{ marginTop: 8, padding: "8px 12px", background: "var(--surface-2)", borderRadius: 6, fontSize: 11, color: "var(--loss)", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 200, overflowY: "auto" }}>${runJob.output}</pre>
            `}
          `}
        </div>

        <div class="card" style=${{ flex: 1, minWidth: 280 }}>
          <div class="card-h">
            <div>
              <div class="card-title">Strategy parameters</div>
              <div class="card-sub mono">${strategy}</div>
            </div>
          </div>
          <${StrategyParams} id=${strategy} params=${strategyParams[strategy] || {}} setParams=${(next) => setStrategyParams((all) => ({ ...all, [strategy]: next }))} />
        </div>
      </div>

      <${MarketDataCard} />
    </div>
  `;
}

function StrategyParams({ id, params: activeParams = {}, setParams = () => {} }) {
  const specs = {
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
    ma_crossover: [
      ["fast_window", "20", "fast MA window", "Number of selected-bar closes used for the fast simple moving average. Must be smaller than slow_window."],
      ["slow_window", "50", "slow MA window", "Number of selected-bar closes used for the slow simple moving average. Default: 50."],
    ],
    ema_crossover: [
      ["fast_span", "20", "fast EMA span", "Exponential moving average span for the fast trend line. Must be smaller than slow_span."],
      ["slow_span", "50", "slow EMA span", "Exponential moving average span for the slow trend line. Default: 50."],
    ],
    macd_crossover: [
      ["fast_span", "12", "MACD fast EMA", "Fast EMA span used in MACD. Must be smaller than slow_span."],
      ["slow_span", "26", "MACD slow EMA", "Slow EMA span used in MACD. Default: 26."],
      ["signal_span", "9", "signal EMA", "EMA span applied to the MACD line. Default: 9."],
    ],
    fear_greed_sentiment: [
      ["dataset_id", "fear_greed_btc", "external dataset", "External feature dataset id. Missing or stale observations suppress trading signals."],
      ["max_age_seconds", "172800", "feature TTL", "Maximum age for the as-of Fear & Greed value. Older values are treated as stale and generate no signal."],
      ["extreme_fear_label", "Extreme Fear", "entry label", "Classification label that opens a long position when the feature is fresh."],
      ["extreme_fear_threshold", "25", "numeric entry", "Numeric Fear & Greed value at or below this threshold also opens a long position."],
      ["exit_value_threshold", "51", "numeric exit", "Numeric Fear & Greed value at or above this threshold exits an existing position."],
    ],
    cme_gap_fill: [
      ["dataset_id", "cme_btc_yfinance", "external dataset", "External BTC futures dataset id. cme_btc_yfinance is research-only proxy; cme_btc1_continuous requires official data ingest."],
      ["max_age_seconds", "604800", "feature TTL", "Maximum age for the as-of CME observation before it is treated as stale."],
      ["min_gap_bps", "25", "gap threshold", "Minimum weekend CME gap size in basis points before the strategy considers an entry."],
      ["max_hold_days", "2", "max hold", "Maximum holding time in days before a gap-fill position exits by timeout."],
      ["stop_loss_bps_mult", "1.5", "stop multiple", "Stop-loss distance as a multiple of gap_bps from the OKX entry anchor. 0 disables stop-loss."],
      ["max_gap_bps", "0", "upper gap filter", "Optional upper bound for oversized gaps. 0 disables the upper-bound filter."],
      ["allow_direction", "long_only", "direction filter", "long_only trades only down-gaps. This default is regime-fitted to BTC 2024-26 and needs bear-regime walk-forward."],
    ],
    ohlcv_rotation: [
      ["top_k", "3", "max simultaneous positions", "Max instruments held at once. Each gets equal weight (1/n), capped at max_position_weight=0.35."],
      ["rebalance_minutes", "60", "rebalance cadence (min)", "Re-rank universe every N minutes. Lower = more reactive, higher turnover cost."],
      ["atr_stop_multiple", "2.0", "ATR stop loss", "Close position if price drops more than N × ATR below entry price."],
      ["max_holding_minutes", "480", "max holding time (min)", "Force-exit if held longer than this and composite score ≤ 0."],
      ["min_volume_z", "1.0", "volume z-score (diagnostic)", "Diagnostic threshold shown in backtest report. Not a hard entry filter; volume enters selection via composite score weight. Controls the vol_filter_pass_pct diagnostic metric."],
    ],
    daily_winner: [
      ["selection", "yesterday_return", "ranking signal", "Ranks the selected universe by yesterday's daily close/open return, then trades the strongest symbol today."],
      ["holding_period", "1 day", "forced round trip", "Buys today's open and exits at today's daily close, producing one expected trade per complete day."],
      ["purpose", "validation", "backtest smoke test", "Designed to verify DB daily aggregation, trade generation, metrics, and frontend artifacts. Not a live trading candidate."],
    ],
  }[id] || [];
  const editable = PARAMETERIZED_STRATEGIES.has(id);
  function parseParam(value) {
    const num = Number(value);
    return value !== "" && Number.isFinite(num) ? num : value;
  }
  return html`
    <div class="col" style=${{ gap: 12 }}>
      ${specs.map(([k, v, short, full]) => html`
        <div key=${k} class="col" style=${{ gap: 4 }}>
          <div class="row" style=${{ alignItems: "center", gap: 10 }}>
            <div style=${{ flex: 1, fontSize: 12 }} class="mono" title=${short}>${k}</div>
            <input class="input mono" value=${editable ? (activeParams[k] ?? v) : v} disabled=${!editable}
              onChange=${(e) => setParams({ ...activeParams, [k]: parseParam(e.target.value) })}
              style=${{ width: 156, padding: "4px 8px", fontSize: 12, textAlign: "right" }} />
          </div>
          <div class="field-hint" style=${{ fontSize: 11 }}>${full}</div>
        </div>
      `)}
      <div class="sep"></div>
      <div class="field-hint">td_mode: cross - post_only: true - max_order_notional: $500${editable ? " - parameters are sent with this run" : ""}</div>
    </div>
  `;
}

function MarketDataCard() {
  const [coverage, setCoverage] = useConfigState(null);
  const [instruments, setInstruments] = useConfigState([]);
  const [fetchJob, setFetchJob] = useConfigState(null);
  const [showFetchPanel, setShowFetchPanel] = useConfigState(false);
  const [showExportPanel, setShowExportPanel] = useConfigState(false);
  const [fetchForm, setFetchForm] = useConfigState({ symbols: [], bar: "1m", start: "2024-01-01", end: yesterday });
  const [exportForm, setExportForm] = useConfigState({ symbols: [], bar: "1H", start: "2024-01-01", end: yesterday, format: "xlsx" });
  const listingMap = Object.fromEntries(instruments.map((i) => [i.inst_id, i.list_date]));
  const latestSelectedListing = (fetchForm.symbols || [])
    .map((s) => listingMap[s])
    .filter(Boolean)
    .sort()
    .at(-1) || "";
  const exportCoverageBar = exportForm.bar === "1H" ? "1m" : exportForm.bar;
  const ROWS_PER_DAY = { "1H": 24, "1m": 1440, "5m": 288, "15m": 96 };
  const estDays = Math.max(0, (new Date(exportForm.end) - new Date(exportForm.start)) / 86_400_000);
  const estRows = (exportForm.symbols || []).length * estDays * (ROWS_PER_DAY[exportForm.bar] || 24);
  const estBytes = estRows * (exportForm.format === "xlsx" ? 60 : 80);
  function fmtBytes(b) {
    if (b < 1024) return b + " B";
    if (b < 1_048_576) return (b / 1024).toFixed(1) + " KB";
    if (b < 1_073_741_824) return (b / 1_048_576).toFixed(1) + " MB";
    return (b / 1_073_741_824).toFixed(1) + " GB";
  }
  const coverageSymbols = [...new Set((coverage || [])
    .filter((r) => r.bar === exportCoverageBar)
    .map((r) => r.inst_id)
    .filter(Boolean))]
    .sort();
  const exportSymbols = coverageSymbols.length
    ? coverageSymbols
    : (instruments.length ? instruments.map((i) => i.inst_id) : MOCK.SYMBOLS.filter((s) => s.includes("SWAP"))).sort();

  function refreshCoverage() {
    window.API.fetchDataCoverage().then(setCoverage).catch(() => setCoverage([]));
  }

  useConfigEffect(() => {
    refreshCoverage();
    window.API.fetchDataInstruments().then((rows) => setInstruments(rows || [])).catch(() => setInstruments([]));
  }, []);

  function triggerFetch() {
    const body = { ...fetchForm };
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

  function toggleExportSymbol(symbol) {
    setExportForm((f) => {
      const symbols = f.symbols || [];
      const next = symbols.includes(symbol)
        ? symbols.filter((s) => s !== symbol)
        : [...symbols, symbol];
      return { ...f, symbols: next };
    });
  }

  function triggerExport() {
    const symbols = (exportForm.symbols || []).join(",");
    if (!symbols) return;
    window.location.assign(window.API.dataExportUrl({
      symbols,
      bar: exportForm.bar,
      start: exportForm.start,
      end: exportForm.end,
      format: exportForm.format,
    }));
  }

  return html`
    <div class="card">
      <div class="card-h">
        <div>
          <div class="card-title">Market Data Coverage</div>
          <div class="card-sub">OHLCV, funding rates, and external feature observations stored in TimescaleDB</div>
        </div>
        <div class="row" style=${{ gap: 8 }}>
          <button class="btn sm" onClick=${() => setShowExportPanel((v) => !v)}>Export CSV</button>
          <button class="btn sm" onClick=${() => setShowFetchPanel((v) => !v)}>+ Fetch from Exchange</button>
        </div>
      </div>

      ${showExportPanel && html`
        <div class="card" style=${{ background: "var(--surface-2)", marginBottom: 16 }}>
          <div class="card-title" style=${{ marginBottom: 12 }}>Export OHLCV Data</div>
          <div class="grid" style=${{ gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr", gap: 12 }}>
            <div class="field">
              <div class="field-label">Perpetual symbols</div>
              <button class="btn sm" style=${{ marginBottom: 4 }}
                onClick=${() => {
                  const allSelected = exportSymbols.length > 0 && (exportForm.symbols || []).length === exportSymbols.length;
                  setExportForm((f) => ({ ...f, symbols: allSelected ? [] : [...exportSymbols] }));
                }}>
                ${exportSymbols.length > 0 && (exportForm.symbols || []).length === exportSymbols.length ? "Deselect All" : "Select All"}
              </button>
              <div class="tbl-wrap" style=${{ maxHeight: 160 }}>
                <table class="tbl" style=${{ fontSize: 12 }}>
                  <tbody>
                    ${exportSymbols.map((symbol) => html`
                      <tr key=${symbol} style=${{ cursor: "pointer" }} onClick=${() => toggleExportSymbol(symbol)}>
                        <td style=${{ width: 28 }}>
                          <input
                            type="checkbox"
                            checked=${(exportForm.symbols || []).includes(symbol)}
                            onChange=${() => {}}
                          />
                        </td>
                        <td class="mono">${symbol}</td>
                      </tr>
                    `)}
                  </tbody>
                </table>
              </div>
              <div class="field-hint">
                ${(exportForm.symbols || []).length} selected${exportForm.bar === "1H" ? " - 1H exports are aggregated from 1m candles" : ""}
              </div>
              ${estRows > 0 && html`<div class="field-hint">Est. size: ~${fmtBytes(estBytes)}</div>`}
            </div>
            <div class="field">
              <div class="field-label">Bar</div>
              <select class="select mono" value=${exportForm.bar}
                onChange=${(e) => setExportForm((f) => ({ ...f, bar: e.target.value, symbols: [] }))}>
                ${["1H", "1m", "5m", "15m"].map((b) => html`<option key=${b}>${b}</option>`)}
              </select>
            </div>
            <div class="field">
              <div class="field-label">Start</div>
              <input class="input mono" type="date" value=${exportForm.start}
                onChange=${(e) => setExportForm((f) => ({ ...f, start: e.target.value }))} />
            </div>
            <div class="field">
              <div class="field-label">End</div>
              <input class="input mono" type="date" value=${exportForm.end}
                onChange=${(e) => setExportForm((f) => ({ ...f, end: e.target.value }))} />
            </div>
            <div class="field">
              <div class="field-label">Format</div>
              <select class="select mono" value=${exportForm.format}
                onChange=${(e) => setExportForm((f) => ({ ...f, format: e.target.value }))}>
                <option value="xlsx">xlsx (multi-sheet)</option>
                <option value="csv">csv (single file)</option>
              </select>
            </div>
          </div>
          <button class="btn primary sm" style=${{ marginTop: 12 }}
            disabled=${!(exportForm.symbols || []).length || exportForm.start >= exportForm.end}
            onClick=${triggerExport}>
            Download Data
          </button>
        </div>
      `}

      ${showFetchPanel && html`
        <div class="card" style=${{ background: "var(--surface-2)", marginBottom: 16 }}>
          <div class="card-title" style=${{ marginBottom: 12 }}>Fetch 1m OHLCV from OKX</div>
          <div class="grid" style=${{ gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 12 }}>
            <div class="field">
              <div class="field-label">USDT swap symbols</div>
              <div class="tbl-wrap" style=${{ maxHeight: 160 }}>
                <table class="tbl" style=${{ fontSize: 12 }}>
                  <tbody>
                    ${(instruments.length ? instruments : MOCK.SYMBOLS.filter((s) => s.includes("SWAP")).map((s) => ({ inst_id: s }))).map((inst) => html`
                      <tr key=${inst.inst_id}>
                        <td style=${{ width: 28 }}>
                          <input
                            type="checkbox"
                            checked=${(fetchForm.symbols || []).includes(inst.inst_id)}
                            onChange=${() => toggleFetchSymbol(inst.inst_id)}
                          />
                        </td>
                        <td class="mono">${inst.inst_id}</td>
                        <td class="num mono" style=${{ color: "var(--text-subtle)" }}>${inst.list_date || "-"}</td>
                      </tr>
                    `)}
                  </tbody>
                </table>
              </div>
              <div class="field-hint">${(fetchForm.symbols || []).length} selected - listing dates from OKX instruments</div>
            </div>
            <div class="field">
              <div class="field-label">Bar</div>
              <select class="select mono" value=${fetchForm.bar}
                onChange=${(e) => setFetchForm((f) => ({ ...f, bar: e.target.value }))}>
                ${["1m", "5m", "15m", "1H", "4H", "1D"].map((b) => html`<option key=${b}>${b}</option>`)}
              </select>
            </div>
            <div class="field">
              <div class="field-label">Start</div>
              <input class="input mono" type="date" value=${fetchForm.start}
                onChange=${(e) => setFetchForm((f) => ({ ...f, start: e.target.value }))} />
              ${latestSelectedListing && html`<div class="field-hint">symbols listed after start auto-fetch from their listing date; latest selected listing: ${latestSelectedListing}</div>`}
            </div>
            <div class="field">
              <div class="field-label">End</div>
              <input class="input mono" type="date" value=${fetchForm.end} max=${yesterday}
                onChange=${(e) => setFetchForm((f) => ({ ...f, end: e.target.value > yesterday ? yesterday : e.target.value }))} />
            </div>
          </div>
          ${fetchJob && html`
            <div class="row" style=${{ gap: 12, marginTop: 12, alignItems: "center" }}>
              <span class=${`chip ${fetchJob.status === "done" ? "profit" : fetchJob.status === "error" ? "loss" : "warn"}`}>
                ${fetchJob.status}
              </span>
              <span class="field-hint">${fetchJob.message || ""}</span>
              ${fetchJob.progress != null && html`
                <div class="bar" style=${{ flex: 1, height: 6 }}>
                  <i style=${{ width: `${fetchJob.progress}%`, background: "var(--accent)" }}></i>
                </div>
              `}
            </div>
          `}
          <button class="btn primary sm" style=${{ marginTop: 12 }}
            disabled=${fetchJob?.status === "running" || !(fetchForm.symbols || []).length}
            onClick=${triggerFetch}>
            Fetch selected data
          </button>
          ${fetchJob?.results?.length > 0 && html`
            <div class="field-hint" style=${{ marginTop: 8 }}>
              ${fetchJob.results.map((r) => `${r.symbol}: ${r.rows?.toLocaleString?.() ?? r.rows} rows from ${r.effective_start || r.list_date || "-"}`).join(" - ")}
            </div>
          `}
        </div>
      `}

      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Dataset / Symbol</th><th>Type</th><th>Bar / Frequency</th><th>Provider</th><th class="num">First date</th>
              <th class="num">Last date</th><th class="num">Rows</th>
              <th class="num">Gaps</th>
            </tr>
          </thead>
          <tbody>
            ${(coverage || []).map((row, i) => html`
              <tr key=${i}>
                <td class="mono">${row.inst_id}</td>
                <td>${row.data_kind || (row.bar === "funding" ? "funding" : "ohlcv")}</td>
                <td class="mono">${row.bar}</td>
                <td class="mono">${row.provider || "-"}</td>
                <td class="num mono">${row.first_ts ? new Date(row.first_ts).toISOString().slice(0, 10) : "-"}</td>
                <td class="num mono">${row.last_ts ? new Date(row.last_ts).toISOString().slice(0, 10) : "-"}</td>
                <td class="num">${(row.row_count || 0).toLocaleString()}</td>
                <td class="num" style=${{ color: row.gap_count > 0 ? "var(--warn)" : "var(--profit)" }}>
                  ${row.gap_count ?? "-"}
                </td>
              </tr>
            `)}
            ${(!coverage || !coverage.length) && html`
              <tr><td colSpan=${8} class="field-hint" style=${{ textAlign: "center", padding: 24 }}>No data in DB. Use "Fetch from Exchange" or external ingest scripts to load historical data.</td></tr>
            `}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

window.RunConfigView = RunBacktestView;
window.KPI = KPI;

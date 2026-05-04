// Mock data + helpers for the OKX backtester UI
// Deterministic so the UI is reproducible.

(function () {
  function seeded(seed) {
    let s = seed | 0;
    return function () {
      s = (s * 1664525 + 1013904223) | 0;
      return ((s >>> 0) % 100000) / 100000;
    };
  }

  function buildEquity(seed, n, mu, sigma) {
    const rand = seeded(seed);
    const eq = [1];
    const ret = [];
    for (let i = 1; i < n; i++) {
      // Box–Muller
      const u1 = rand() || 1e-9, u2 = rand();
      const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      const r = mu + sigma * z;
      ret.push(r);
      eq.push(eq[i - 1] * (1 + r));
    }
    return { eq, ret };
  }

  function summarize(ret, periods) {
    const n = ret.length;
    const mean = ret.reduce((a, b) => a + b, 0) / n;
    const variance = ret.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1);
    const std = Math.sqrt(variance);
    const sharpe = (mean / std) * Math.sqrt(periods);
    const dn = ret.filter((r) => r < 0);
    const dnStd = Math.sqrt(dn.reduce((a, b) => a + b * b, 0) / Math.max(dn.length, 1));
    const sortino = dn.length ? (mean / dnStd) * Math.sqrt(periods) : 0;
    let eq = 1, peak = 1, mdd = 0;
    for (const r of ret) {
      eq *= 1 + r;
      if (eq > peak) peak = eq;
      const dd = (eq - peak) / peak;
      if (dd < mdd) mdd = dd;
    }
    const total = eq - 1;
    const years = n / periods;
    const cagr = Math.pow(eq, 1 / years) - 1;
    const calmar = mdd === 0 ? Infinity : cagr / Math.abs(mdd);
    const wins = ret.filter((r) => r > 0);
    const losses = ret.filter((r) => r < 0);
    const win = wins.length / Math.max(wins.length + losses.length, 1);
    const pf = wins.reduce((a, b) => a + b, 0) / Math.max(Math.abs(losses.reduce((a, b) => a + b, 0)), 1e-9);
    return {
      total_return: total,
      cagr,
      sharpe,
      sortino,
      max_drawdown: mdd,
      calmar,
      win_rate: win,
      profit_factor: pf,
      n_periods: n,
    };
  }

  // Strategies catalog
  const STRATEGIES = [
    { id: "as_market_maker", name: "Avellaneda–Stoikov MM", tag: "Market Making", desc: "AS quotes with VPIN spread multiplier and OBI/OFI alpha skew" },
    { id: "obi_market_maker", name: "OBI Market Maker", tag: "Market Making", desc: "Order book imbalance-driven market making" },
    { id: "funding_carry", name: "Funding Carry", tag: "Carry", desc: "Delta-neutral long spot / short perp, earns 8h funding" },
    { id: "pairs_trading", name: "Pairs Trading", tag: "Stat Arb", desc: "Kalman filter hedge ratio + OU spread z-score" },
  ];

  const SYMBOLS = [
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT-SWAP",
  ];

  // Default current run — Funding Carry on BTC-USDT-SWAP, hourly, 90 days
  const PERIODS = 365 * 24;
  const N = 24 * 90; // 2160 hourly bars
  const main = buildEquity(7, N, 0.0008, 0.0042);
  const mainStats = summarize(main.ret, PERIODS);

  // Generate timestamps
  const startTs = new Date("2026-01-26T00:00:00Z").getTime();
  const ts = Array.from({ length: N }, (_, i) => startTs + i * 3600 * 1000);

  // Drawdown series
  function drawdownSeries(eq) {
    let peak = eq[0];
    return eq.map((v) => {
      if (v > peak) peak = v;
      return (v - peak) / peak;
    });
  }
  const dd = drawdownSeries(main.eq);

  // Walk-forward windows: IS=14d, OOS=7d, hourly => IS=336, OOS=168
  function buildWalkForward() {
    const isLen = 14 * 24, oosLen = 7 * 24;
    const windows = [];
    let cursor = isLen;
    let i = 0;
    while (cursor + oosLen <= N) {
      const isStart = cursor - isLen, isEnd = cursor;
      const oosStart = cursor, oosEnd = cursor + oosLen;
      const isRet = main.ret.slice(isStart, isEnd);
      const oosRet = main.ret.slice(oosStart, oosEnd);
      const isStats = summarize(isRet, PERIODS);
      const oosStats = summarize(oosRet, PERIODS);
      windows.push({
        i: i++,
        is_start: ts[isStart],
        is_end: ts[isEnd - 1],
        oos_start: ts[oosStart],
        oos_end: ts[oosEnd - 1],
        is_sharpe: isStats.sharpe,
        oos_sharpe: oosStats.sharpe,
        oos_return: oosStats.total_return,
        oos_mdd: oosStats.max_drawdown,
      });
      cursor += oosLen;
    }
    return windows;
  }
  const walkForward = buildWalkForward();

  // CPCV: N=6, k=2 => 15 combinations, 5 paths
  function buildCPCV() {
    const groups = 6, k = 2;
    const combos = [];
    for (let a = 0; a < groups; a++)
      for (let b = a + 1; b < groups; b++) combos.push([a, b]);
    const groupSize = Math.floor(N / groups);
    const groupRet = [];
    for (let g = 0; g < groups; g++) {
      const slice = main.ret.slice(g * groupSize, (g + 1) * groupSize);
      groupRet.push(slice);
    }
    const comboResults = combos.map(([a, b], i) => {
      // Build per-combo OOS series — slight per-combo perturbation to mimic train-on-rest
      const rand = seeded(31 + i);
      const oos = [...groupRet[a], ...groupRet[b]].map((r) => r * (0.9 + 0.2 * rand()));
      const stats = summarize(oos, PERIODS);
      return { test_groups: [a, b], sharpe: stats.sharpe, ret: stats.total_return, mdd: stats.max_drawdown, n: oos.length };
    });
    // 5 paths each covering all 6 groups (every group appears once per path)
    // Heuristic assignment for visualization
    const paths = [
      [[0, 1], [2, 3], [4, 5]],
      [[0, 2], [1, 4], [3, 5]],
      [[0, 3], [2, 5], [1, 4]],
      [[0, 4], [3, 5], [1, 2]],
      [[0, 5], [2, 4], [1, 3]],
    ];
    const pathSeries = paths.map((path, pi) => {
      const merged = [];
      path.forEach(([a, b]) => {
        const idx = combos.findIndex((c) => c[0] === a && c[1] === b);
        const rand = seeded(101 + pi * 7 + idx);
        merged.push(...groupRet[a].map((r) => r * (0.9 + 0.2 * rand())));
        merged.push(...groupRet[b].map((r) => r * (0.9 + 0.2 * rand())));
      });
      const stats = summarize(merged, PERIODS);
      const eq = [1];
      for (const r of merged) eq.push(eq[eq.length - 1] * (1 + r));
      return { i: pi, sharpe: stats.sharpe, ret: stats.total_return, mdd: stats.max_drawdown, eq };
    });
    const sharpes = comboResults.map((c) => c.sharpe);
    const meanS = sharpes.reduce((a, b) => a + b, 0) / sharpes.length;
    const varS = sharpes.reduce((a, b) => a + (b - meanS) ** 2, 0) / (sharpes.length - 1);
    const dsr = 0.97; // simulated deflated sharpe (post-haircut)
    const psr = 0.94;
    return { combos: comboResults, paths: pathSeries, dsr, psr, mean_oos_sharpe: meanS, std_oos_sharpe: Math.sqrt(varS) };
  }
  const cpcv = buildCPCV();

  // Trades — 200 mock trades
  function buildTrades() {
    const rand = seeded(41);
    const list = [];
    for (let i = 0; i < 200; i++) {
      const symIdx = Math.floor(rand() * 2);
      const sym = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"][symIdx];
      const side = rand() > 0.5 ? "BUY" : "SELL";
      const px = sym.startsWith("BTC") ? 60000 + (rand() - 0.5) * 4000 : 3200 + (rand() - 0.5) * 200;
      const qty = +(0.005 + rand() * 0.04).toFixed(4);
      const fee = +(px * qty * 0.0002).toFixed(3);
      const pnl = +((rand() - 0.45) * 60).toFixed(2);
      const tStamp = ts[Math.min(N - 1, Math.floor(rand() * N))];
      const status = rand() > 0.05 ? "FILLED" : (rand() > 0.5 ? "CANCELLED" : "REJECTED");
      list.push({
        id: 100000 + i,
        ts: tStamp,
        symbol: sym,
        side,
        type: "post_only",
        price: px,
        qty,
        notional: px * qty,
        fee,
        pnl,
        status,
        strategy: ["funding_carry", "as_market_maker", "obi_market_maker"][Math.floor(rand() * 3)],
      });
    }
    return list.sort((a, b) => b.ts - a.ts);
  }
  const trades = buildTrades();

  // Compare runs (3): conservative / baseline / aggressive
  const compareRuns = [
    { id: "run-A", name: "Conservative · gamma=0.05", strategy: "as_market_maker", color: "var(--text-muted)", seed: 11, mu: 0.0004, sigma: 0.0028 },
    { id: "run-B", name: "Baseline · gamma=0.10", strategy: "as_market_maker", color: "var(--accent)", seed: 7, mu: 0.0008, sigma: 0.0042 },
    { id: "run-C", name: "Aggressive · gamma=0.20", strategy: "as_market_maker", color: "var(--loss)", seed: 23, mu: 0.0014, sigma: 0.0078 },
  ].map((r) => {
    const eqd = buildEquity(r.seed, N, r.mu, r.sigma);
    const stats = summarize(eqd.ret, PERIODS);
    return { ...r, eq: eqd.eq, ret: eqd.ret, stats, dd: drawdownSeries(eqd.eq) };
  });

  // Risk monitor live values
  const risk = {
    equity_usd: 5000 * (1 + mainStats.total_return),
    daily_pnl_pct: -0.018,
    daily_pnl_usd: -90.32,
    soft_dd_used: Math.abs(mainStats.max_drawdown),
    leverage: 1.42,
    max_leverage: 3.0,
    max_pos_pct_equity: 0.30,
    pos_pct_equity: 0.21,
    max_order_notional: 500,
    last_order_notional: 312.40,
    ws_reconnects: 0,
    rest_error_rate: 0.012,
  };

  // Schema preview rows (default: candles)
  const sampleCandles = [
    { ts: "2026-01-26T00:00:00Z", open: 60123.4, high: 60342.1, low: 60001.0, close: 60201.7, vol: 1284.21 },
    { ts: "2026-01-26T01:00:00Z", open: 60201.7, high: 60410.3, low: 60150.0, close: 60388.4, vol: 1102.55 },
    { ts: "2026-01-26T02:00:00Z", open: 60388.4, high: 60450.2, low: 60280.0, close: 60315.0, vol: 940.12 },
    { ts: "2026-01-26T03:00:00Z", open: 60315.0, high: 60330.0, low: 60100.5, close: 60144.8, vol: 1521.07 },
    { ts: "2026-01-26T04:00:00Z", open: 60144.8, high: 60200.1, low: 59980.0, close: 60020.3, vol: 1310.66 },
    { ts: "2026-01-26T05:00:00Z", open: 60020.3, high: 60150.0, low: 59950.0, close: 60088.9, vol: 988.77 },
  ];

  window.MOCK = {
    STRATEGIES,
    SYMBOLS,
    N,
    ts,
    main: { eq: main.eq, ret: main.ret, dd },
    mainStats,
    walkForward,
    cpcv,
    trades,
    compareRuns,
    risk,
    sampleCandles,
    PERIODS,
  };
})();

// ---------------------------------------------------------------------------
// window.API — fetch real data from the FastAPI backend.
// Falls back gracefully when the server is not running (window.MOCK is always
// available as the fallback data source).
// ---------------------------------------------------------------------------
window.API = (function () {
  async function _get(path) {
    const r = await fetch(path, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  return {
    /** Check if the engine is running. Resolves with status dict or rejects. */
    fetchStatus:        ()        => _get("/api/live/status"),
    /** Current risk metrics matching window.MOCK.risk schema. */
    fetchLiveRisk:      ()        => _get("/api/live/risk"),
    /** List of open positions. */
    fetchLivePositions: ()        => _get("/api/live/positions"),
    /** Recent fills matching window.MOCK.trades schema. */
    fetchLiveTrades:    (n = 200) => _get("/api/live/trades?limit=" + n),
    /** List of saved backtest runs (summary only). */
    fetchBacktestRuns:  ()        => _get("/api/backtest/runs"),
    /** Full result.json for a run — same shape as window.MOCK. */
    fetchBacktest:      (id)      => _get("/api/backtest/" + id),
  };
})();
